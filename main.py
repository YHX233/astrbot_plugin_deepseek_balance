"""DeepSeek 余额查询插件

用法:
    /余额          查询所有已配置 Key 的余额
    /余额 备注名   只查询指定备注名的 Key
    /余额订阅      把当前会话设为低余额通知目标（发「/余额订阅 关闭」可取消）
    /余额检查      立即跑一次自动检查（忽略冷却）

数据来源: GET https://api.deepseek.com/user/balance
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import time

import aiohttp

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.message_components import Plain
from astrbot.api.star import Context, Star, register
from astrbot.core.message.message_event_result import MessageChain

BALANCE_URL = "https://api.deepseek.com/user/balance"
CURRENCY_SYMBOL = {"CNY": "¥", "USD": "$"}
COMMANDS = ("余额", "查余额", "ds余额", "deepseek余额")

# 订阅关系、提醒状态、账本都放 KV，重载/重启后不丢
KV_NOTIFY_SESSION = "notify_session"
KV_ALERT_STATE = "alert_state"
KV_LEDGER = "ledger"


@register(
    "deepseek_balance",
    "DeepSeek余额查询",
    "查询 DeepSeek API Key 的账户余额，支持定期检查与低余额提醒",
    "1.2.0",
)
class DeepSeekBalance(Star):
    def __init__(self, context: Context, config: dict | None = None):
        super().__init__(context)
        self.config = config or {}
        self.api_keys = self._parse_keys(self.config.get("api_keys", []))
        self.admin_only = bool(self.config.get("admin_only", True))
        self.allowed_users = {
            str(u) for u in (self.config.get("allowed_users") or [])
        }
        self.timeout = max(3, int(self.config.get("timeout", 15) or 15))
        self.show_masked_key = bool(self.config.get("show_masked_key", True))

        # ---- 定期检查 ----
        self.enable_auto_check = bool(self.config.get("enable_auto_check", False))
        self.check_interval = (
            max(1, self._as_int(self.config.get("check_interval_minutes"), 60)) * 60
        )
        self.low_balance_threshold = self._as_float(
            self.config.get("low_balance_threshold"), 5.0
        )
        self.notify_mode = (
            str(self.config.get("notify_mode", "agent") or "agent").strip().lower()
        )
        self.notify_session = str(self.config.get("notify_session", "") or "").strip()
        self.notify_cooldown = (
            max(0, self._as_int(self.config.get("notify_cooldown_hours"), 6)) * 3600
        )

        # ---- 低余额自动切换供应商 ----
        self.enable_auto_switch = bool(
            self.config.get("enable_auto_switch_provider", False)
        )
        self.fallback_provider_id = str(
            self.config.get("fallback_provider_id", "") or ""
        ).strip()

        # ---- 查询账本（默认开） ----
        self.enable_ledger = bool(self.config.get("enable_ledger", True))
        self.ledger_max_records = max(
            10, self._as_int(self.config.get("ledger_max_records"), 500)
        )
        self.ledger_show_count = max(
            1, self._as_int(self.config.get("ledger_show_count"), 5)
        )

        # ---- 查询后回报 agent（默认关） ----
        self.enable_query_report = bool(self.config.get("enable_query_report", False))

        self._watch_task: asyncio.Task | None = None
        self._alert_state: dict[str, float] = {}

        if not self.api_keys:
            logger.warning("[DS余额] 还没有配置任何 API Key，/余额 暂不可用")
        else:
            logger.info(f"[DS余额] 插件已加载，共配置 {len(self.api_keys)} 个 Key")
        if self.enable_auto_switch and not self.fallback_provider_id:
            logger.warning(
                "[DS余额] 已开启自动切换供应商，但没有填 fallback_provider_id，该功能不会生效"
            )

    # ---------------- 生命周期 ----------------

    async def initialize(self) -> None:
        """插件加载后启动后台检查任务。"""
        with contextlib.suppress(Exception):
            state = await self.get_kv_data(KV_ALERT_STATE, {})
            if isinstance(state, dict):
                self._alert_state = {
                    str(k): float(v) for k, v in state.items() if v
                }

        if not self.enable_auto_check:
            logger.info("[DS余额] 定期检查未开启")
            return
        if not self.api_keys:
            logger.warning("[DS余额] 未配置 Key，定期检查不启动")
            return
        if self._watch_task and not self._watch_task.done():
            return
        self._watch_task = asyncio.create_task(self._watch_loop())
        logger.info(
            "[DS余额] 定期检查已启动：每 %d 分钟一次，阈值 %.2f 元"
            % (self.check_interval // 60, self.low_balance_threshold)
        )

    async def terminate(self) -> None:
        """插件卸载/重载时停止后台任务。"""
        task = self._watch_task
        self._watch_task = None
        if task and not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task
        logger.info("[DS余额] 定期检查已停止")

    async def _watch_loop(self) -> None:
        # 启动后先缓 30 秒，避开加载高峰
        await asyncio.sleep(30)
        while True:
            try:
                alerts = await self._auto_check()
                if alerts:
                    await self._send_alert(alerts)
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001
                logger.exception("[DS余额] 定期检查异常")
            await asyncio.sleep(self.check_interval)

    # ---------------- 配置解析 ----------------

    @staticmethod
    def _as_int(raw, default: int) -> int:
        try:
            return int(float(raw))
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _as_float(raw, default: float) -> float:
        try:
            return float(raw)
        except (TypeError, ValueError):
            return default

    # ---------------- 内部工具 ----------------

    @staticmethod
    def _parse_keys(raw) -> list[tuple[str, str]]:
        """把配置项解析成 [(备注名, key), ...]"""
        if not raw:
            return []
        if isinstance(raw, str):
            raw = [raw]
        result: list[tuple[str, str]] = []
        for idx, item in enumerate(raw, start=1):
            if not isinstance(item, str):
                continue
            text = item.strip()
            if not text:
                continue
            if "=" in text:
                name, _, key = text.partition("=")
                name = name.strip() or f"Key{idx}"
                key = key.strip()
            else:
                name, key = f"Key{idx}", text
            if key:
                result.append((name, key))
        return result

    @staticmethod
    def _mask(key: str) -> str:
        if len(key) <= 10:
            return key[:2] + "****"
        return f"{key[:5]}****{key[-4:]}"

    def _is_allowed(self, event: AstrMessageEvent) -> bool:
        if not self.admin_only:
            return True
        if event.is_admin():
            return True
        return str(event.get_sender_id()) in self.allowed_users

    async def _query_balance(self, key: str) -> dict:
        """调用 DeepSeek 余额接口，返回原始 JSON"""
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {key}",
        }
        timeout = aiohttp.ClientTimeout(total=self.timeout)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(BALANCE_URL, headers=headers) as resp:
                text = await resp.text()
                if resp.status == 401:
                    raise ValueError("API Key 无效或已被吊销 (401)")
                if resp.status == 403:
                    raise ValueError("没有权限访问余额接口 (403)")
                if resp.status != 200:
                    raise ValueError(f"接口返回异常 HTTP {resp.status}: {text[:120]}")
                try:
                    return await resp.json(content_type=None)
                except Exception:
                    raise ValueError(f"返回内容不是合法 JSON: {text[:120]}")

    @staticmethod
    def _extract_total(data: dict) -> float | None:
        """从接口返回里取总余额，多币种优先 CNY"""
        infos = data.get("balance_infos") or []
        if not infos:
            return None
        picked = next(
            (i for i in infos if i.get("currency") == "CNY"), infos[0]
        )
        try:
            return float(picked.get("total_balance") or 0)
        except (TypeError, ValueError):
            return None

    def _format_one(self, name: str, key: str, data: dict) -> str:
        lines = []
        title = f"【{name}】"
        if self.show_masked_key:
            title += f" {self._mask(key)}"
        lines.append(title)

        available = data.get("is_available")
        if available is None:
            lines.append("账户状态: 未知")
        else:
            status = "可用" if available else "不可用（余额不足或被禁用）"
            lines.append(f"账户状态: {status}")

        infos = data.get("balance_infos") or []
        if not infos:
            lines.append("余额信息: 接口未返回明细")
            return "\n".join(lines)

        for info in infos:
            currency = info.get("currency", "")
            symbol = CURRENCY_SYMBOL.get(currency, "")
            total = info.get("total_balance", "-")
            granted = info.get("granted_balance", "-")
            topped = info.get("topped_up_balance", "-")
            lines.append(f"总余额: {symbol}{total} {currency}")
            lines.append(f"  赠送余额: {symbol}{granted}    充值余额: {symbol}{topped}")
        return "\n".join(lines)

    # ---------------- 定期检查 ----------------

    async def _auto_check(self, force: bool = False) -> list[str]:
        """跑一轮检查，返回需要提醒的文案列表（空列表表示一切正常）。"""
        if not self.api_keys:
            return []
        now = time.time()
        alerts: list[str] = []
        state_changed = False
        records: list[tuple[str, float]] = []

        for name, key in self.api_keys:
            try:
                data = await self._query_balance(key)
            except Exception as e:  # noqa: BLE001
                logger.warning(f"[DS余额] 检查「{name}」失败: {e}")
                continue

            total = self._extract_total(data)
            if total is None:
                continue
            records.append((name, total))

            if total <= self.low_balance_threshold:
                last = self._alert_state.get(name, 0.0)
                in_cooldown = (
                    not force
                    and self.notify_cooldown > 0
                    and now - last < self.notify_cooldown
                )
                if in_cooldown:
                    continue
                alerts.append(f"当前api余额剩余 {total:.2f} 元（{name}）")
                self._alert_state[name] = now
                state_changed = True
            elif name in self._alert_state:
                # 余额恢复，清掉提醒标记，下次再低会重新提醒
                self._alert_state.pop(name, None)
                state_changed = True

        if state_changed:
            with contextlib.suppress(Exception):
                await self.put_kv_data(KV_ALERT_STATE, self._alert_state)

        await self._record_ledger(records)
        return alerts

    async def _send_alert(self, alerts: list[str]) -> bool:
        """把提醒发出去，顺便处理自动切换供应商。"""
        lines = ["⚠️ DeepSeek 余额不足"]
        lines.extend(alerts)
        lines.append(f"提醒阈值：{self.low_balance_threshold:.2f} 元")

        switch_note = await self._maybe_switch_provider()
        if switch_note:
            lines.append(switch_note)

        return await self._notify("\n".join(lines))

    async def _maybe_switch_provider(self) -> str:
        """余额过低时按配置切换聊天供应商。返回一句结果说明。"""
        if not (self.enable_auto_switch and self.fallback_provider_id):
            return ""
        try:
            from astrbot.api.provider import ProviderType
        except Exception:  # noqa: BLE001
            logger.exception("[DS余额] 当前 AstrBot 版本不支持切换供应商")
            return "自动切换供应商失败：当前版本不支持"

        provider_id = self.fallback_provider_id
        try:
            provider = await self.context.provider_manager.get_provider_by_id(
                provider_id
            )
            if not provider:
                return f"自动切换供应商失败：找不到 {provider_id}"

            umo = await self._resolve_notify_session()
            # 切到当前会话 + 全局，避免只对单个会话生效
            await self.context.provider_manager.set_provider(
                provider_id, ProviderType.CHAT_COMPLETION, umo=umo or None
            )
            if umo:
                await self.context.provider_manager.set_provider(
                    provider_id, ProviderType.CHAT_COMPLETION
                )
            logger.info(f"[DS余额] 已自动切换供应商 → {provider_id}")
            return f"已自动切换供应商 → {provider_id}"
        except Exception as e:  # noqa: BLE001
            logger.exception("[DS余额] 自动切换供应商失败")
            return f"自动切换供应商失败：{e}"

    # ---------------- 账本 ----------------

    async def _record_ledger(self, pairs: list[tuple[str, float]]) -> None:
        """把一次查询的结果追加进账本。pairs 是 [(备注名, 总余额), ...]"""
        if not self.enable_ledger or not pairs:
            return
        try:
            ledger = await self.get_kv_data(KV_LEDGER, [])
            if not isinstance(ledger, list):
                ledger = []
            now = int(time.time())
            for name, total in pairs:
                ledger.append({"t": now, "name": str(name), "total": round(float(total), 2)})
            if len(ledger) > self.ledger_max_records:
                ledger = ledger[-self.ledger_max_records:]
            await self.put_kv_data(KV_LEDGER, ledger)
        except Exception:  # noqa: BLE001
            logger.exception("[DS余额] 写入账本失败")

    async def _load_ledger(self) -> list[dict]:
        try:
            ledger = await self.get_kv_data(KV_LEDGER, [])
            return ledger if isinstance(ledger, list) else []
        except Exception:  # noqa: BLE001
            logger.exception("[DS余额] 读取账本失败")
            return []

    def _format_ledger(self, ledger: list[dict]) -> str:
        """把账本渲染成给用户看的文本。"""
        if not ledger:
            return "账本还是空的。查询一次余额就会开始记录。"

        # 按 Key 分组，保留时间顺序
        grouped: dict[str, list[dict]] = {}
        for item in ledger:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "未知"))
            grouped.setdefault(name, []).append(item)

        blocks: list[str] = ["DeepSeek 余额账本"]
        for name, items in grouped.items():
            items = [i for i in items if "total" in i and "t" in i]
            if not items:
                continue
            items.sort(key=lambda x: x["t"])
            totals = [float(i["total"]) for i in items]
            latest = totals[-1]
            blocks.append(f"\n【{name}】")
            blocks.append(
                f"当前 {latest:.2f} 元 ｜ 记录 {len(items)} 次 ｜ "
                f"最高 {max(totals):.2f} ｜ 最低 {min(totals):.2f}"
            )
            for idx, item in enumerate(items[-self.ledger_show_count:]):
                ts = time.strftime("%m-%d %H:%M", time.localtime(item["t"]))
                total = float(item["total"])
                line = f"{ts}   {total:.2f} 元"
                pos = len(items) - self.ledger_show_count + idx
                if pos > 0:
                    prev = float(items[pos - 1]["total"])
                    diff = total - prev
                    if abs(diff) >= 0.005:
                        arrow = "↓" if diff < 0 else "↑"
                        line += f"  {arrow}{abs(diff):.2f}"
                blocks.append(line)
        return "\n".join(blocks)

    # ---------------- 通知 ----------------

    async def _resolve_notify_session(self) -> str:
        """优先用配置里的会话，其次用 /余额订阅 记录的会话。"""
        if self.notify_session:
            return self.notify_session
        with contextlib.suppress(Exception):
            saved = await self.get_kv_data(KV_NOTIFY_SESSION, "")
            if saved:
                return str(saved)
        return ""

    async def _notify(self, text: str) -> bool:
        session_str = await self._resolve_notify_session()
        if not session_str:
            logger.warning(
                "[DS余额] 没有通知会话，先在群里发一次 /余额订阅 建立订阅"
            )
            return False

        if self.notify_mode == "agent":
            if await self._notify_via_agent(text, session_str):
                return True
            logger.warning("[DS余额] 唤醒 agent 失败，降级为直接发送文本")
        return await self._send_plain(session_str, text)

    async def _send_plain(self, session_str: str, text: str) -> bool:
        try:
            ok = await self.context.send_message(
                session_str, MessageChain([Plain(text)])
            )
            return bool(ok)
        except Exception:  # noqa: BLE001
            logger.exception("[DS余额] 主动发送消息失败")
            return False

    async def _notify_via_agent(self, text: str, session_str: str) -> bool:
        """构造一个事件丢给主 agent，让它自己组织语言回复。

        用的是 AstrBot 官方 cron 任务同一套入口（CronMessageEvent +
        build_main_agent）。这些是内部 API，升级后可能变动，所以整段
        兜底 try/except，失败由调用方降级为直接发文本。
        """
        try:
            from astrbot.api.provider import ProviderRequest
            from astrbot.core.agent.tool import ToolSet
            from astrbot.core.astr_main_agent import (
                MainAgentBuildConfig,
                _get_session_conv,
                build_main_agent,
            )
            from astrbot.core.cron.events import CronMessageEvent
            from astrbot.core.platform.message_session import MessageSession
            from astrbot.core.tools.message_tools import SendMessageToUserTool

            session = MessageSession.from_str(session_str)
            event = CronMessageEvent(
                context=self.context,
                session=session,
                message=text,
                extras={"source": "deepseek_balance_low_alert"},
                message_type=session.message_type,
            )

            cfg = self.context.get_config(umo=event.unified_msg_origin) or {}
            provider_settings = cfg.get("provider_settings", {}) or {}
            config = MainAgentBuildConfig(
                tool_call_timeout=120,
                streaming_response=False,
                provider_settings=provider_settings,
            )

            conv = await _get_session_conv(event=event, plugin_context=self.context)
            req = ProviderRequest()
            req.conversation = conv
            with contextlib.suppress(Exception):
                req.contexts = json.loads(conv.history or "[]")
            req.prompt = text

            if not req.func_tool:
                req.func_tool = ToolSet()
            tool = self.context.get_llm_tool_manager().get_builtin_tool(
                SendMessageToUserTool
            )
            if tool:
                req.func_tool.add_tool(tool)

            result = await build_main_agent(
                event=event, plugin_context=self.context, config=config, req=req
            )
            if not result:
                return False

            runner = result.agent_runner
            async for _ in runner.step_until_done(16):
                pass
            return True
        except Exception:  # noqa: BLE001
            logger.exception("[DS余额] agent 通知失败")
            return False

    # ---------------- 命令 ----------------

    @filter.command("余额", alias={"查余额", "ds余额", "deepseek余额"})
    async def query_balance(self, event: AstrMessageEvent):
        """查询 DeepSeek API Key 余额"""
        if not self._is_allowed(event):
            yield event.plain_result("这个命令只有管理员能用哦")
            return

        if not self.api_keys:
            yield event.plain_result(
                "还没配置 API Key。请到插件配置里的 api_keys 添加，格式为 备注名=sk-xxxx"
            )
            return

        raw = (event.message_str or "").strip()
        target = ""
        for cmd in COMMANDS:
            if raw.startswith(cmd):
                target = raw[len(cmd):].strip()
                break

        if target:
            matched = [item for item in self.api_keys if item[0] == target]
            if not matched:
                names = "、".join(n for n, _ in self.api_keys)
                yield event.plain_result(
                    f"没有找到备注名为「{target}」的 Key\n现有: {names}"
                )
                return
            keys_to_query = matched
        else:
            keys_to_query = self.api_keys

        yield event.plain_result("查询中，稍等…")

        blocks: list[str] = []
        pairs: list[tuple[str, float]] = []
        for name, key in keys_to_query:
            try:
                data = await self._query_balance(key)
                blocks.append(self._format_one(name, key, data))
                total = self._extract_total(data)
                if total is not None:
                    pairs.append((name, total))
            except ValueError as e:
                blocks.append(f"【{name}】查询失败: {e}")
            except aiohttp.ClientError as e:
                blocks.append(f"【{name}】网络错误: {e}")
            except TimeoutError:
                blocks.append(f"【{name}】请求超时（{self.timeout}s）")
            except Exception as e:  # noqa: BLE001
                logger.exception("[DS余额] 查询异常")
                blocks.append(f"【{name}】查询异常: {e}")

        await self._record_ledger(pairs)

        if self.enable_query_report and pairs:
            # 回报走后台，不挡查询结果的返回
            asyncio.create_task(
                self._report_query_safe(pairs, event.unified_msg_origin)
            )

        yield event.plain_result("DeepSeek 余额\n\n" + "\n\n".join(blocks))

    async def _report_query_safe(
        self, pairs: list[tuple[str, float]], session_str: str
    ) -> None:
        try:
            await self._report_query(pairs, session_str)
        except Exception:  # noqa: BLE001
            logger.exception("[DS余额] 查询回报失败")

    async def _report_query(
        self, pairs: list[tuple[str, float]], session_str: str
    ) -> None:
        """把「几点查了余额、剩多少」作为一条事件推给 agent。"""
        if not pairs:
            return
        now = time.strftime("%H点%M分", time.localtime())
        if len(pairs) == 1:
            detail = f"{pairs[0][1]:.2f} 元"
        else:
            detail = "、".join(f"{total:.2f} 元（{name}）" for name, total in pairs)
        text = f"{now}查询了 DeepSeek 余额，剩余 {detail}"
        if not await self._notify_via_agent(text, session_str):
            logger.warning("[DS余额] 查询回报未能送达 agent")

    @filter.command("余额订阅")
    async def subscribe(self, event: AstrMessageEvent):
        """把当前会话设为低余额通知目标"""
        if not self._is_allowed(event):
            yield event.plain_result("这个命令只有管理员能用哦")
            return

        raw = (event.message_str or "").strip()
        arg = raw[len("余额订阅"):].strip() if raw.startswith("余额订阅") else ""

        if arg in ("关闭", "取消", "off", "cancel"):
            await self.put_kv_data(KV_NOTIFY_SESSION, "")
            yield event.plain_result("已取消低余额通知订阅")
            return

        umo = event.unified_msg_origin
        await self.put_kv_data(KV_NOTIFY_SESSION, umo)
        yield event.plain_result(
            "已把当前会话设为低余额通知目标\n"
            f"{umo}\n"
            "取消请发 /余额订阅 关闭"
        )

    @filter.command("余额检查")
    async def check_now(self, event: AstrMessageEvent):
        """立即执行一次检查，忽略冷却时间"""
        if not self._is_allowed(event):
            yield event.plain_result("这个命令只有管理员能用哦")
            return

        if not self.api_keys:
            yield event.plain_result("还没配置 API Key")
            return

        yield event.plain_result("正在检查…")

        alerts = await self._auto_check(force=True)
        if not alerts:
            yield event.plain_result(
                f"检查完成，所有 Key 余额都高于阈值 {self.low_balance_threshold:.2f} 元"
            )
            return

        lines = ["⚠️ 余额低于阈值"] + alerts
        lines.append(f"提醒阈值：{self.low_balance_threshold:.2f} 元")
        if self.enable_auto_switch:
            if self.fallback_provider_id:
                lines.append("已开启自动切换供应商，下轮定期检查时会执行")
            else:
                lines.append("已开启自动切换供应商，但没填 fallback_provider_id")
        yield event.plain_result("\n".join(lines))

    @filter.command("余额账本", alias={"ds账本"})
    async def ledger_cmd(self, event: AstrMessageEvent):
        """查看余额变化账本"""
        if not self._is_allowed(event):
            yield event.plain_result("这个命令只有管理员能用哦")
            return

        if not self.enable_ledger:
            yield event.plain_result(
                "账本功能没开。到插件配置里把 enable_ledger 打开就会开始记录。"
            )
            return

        raw = (event.message_str or "").strip()
        arg = raw[len("余额账本"):].strip() if raw.startswith("余额账本") else ""

        if arg in ("清空", "清除", "clear"):
            await self.put_kv_data(KV_LEDGER, [])
            yield event.plain_result("账本已清空")
            return

        ledger = await self._load_ledger()
        yield event.plain_result(self._format_ledger(ledger))

    @filter.command("余额帮助", alias={"ds帮助"})
    async def balance_help(self, event: AstrMessageEvent):
        """查看余额插件用法"""
        yield event.plain_result(
            "DeepSeek 余额查询\n"
            "/余额        查询所有 Key 的余额\n"
            "/余额 备注名  只查某一个\n"
            "/余额账本     查看余额变化记录\n"
            "/余额账本 清空  清空账本\n"
            "/余额订阅     把当前会话设为低余额通知目标\n"
            "/余额订阅 关闭  取消订阅\n"
            "/余额检查     立即检查一次\n"
            "配置项在插件设置里，格式：备注名=sk-xxxxxxxx"
        )
