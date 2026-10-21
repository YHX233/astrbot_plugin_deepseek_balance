"""DeepSeek 余额查询插件

用法:
    /余额          查询所有已配置 Key 的余额
    /余额 备注名   只查询指定备注名的 Key

数据来源: GET https://api.deepseek.com/user/balance
"""

from __future__ import annotations

import aiohttp

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register

BALANCE_URL = "https://api.deepseek.com/user/balance"
CURRENCY_SYMBOL = {"CNY": "¥", "USD": "$"}
COMMANDS = ("余额", "查余额", "ds余额", "deepseek余额")


@register(
    "deepseek_balance",
    "DeepSeek余额查询",
    "查询 DeepSeek API Key 的账户余额",
    "1.0.1",
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

        if not self.api_keys:
            logger.warning("[DS余额] 还没有配置任何 API Key，/余额 暂不可用")
        else:
            logger.info(f"[DS余额] 插件已加载，共配置 {len(self.api_keys)} 个 Key")

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
        for name, key in keys_to_query:
            try:
                data = await self._query_balance(key)
                blocks.append(self._format_one(name, key, data))
            except ValueError as e:
                blocks.append(f"【{name}】查询失败: {e}")
            except aiohttp.ClientError as e:
                blocks.append(f"【{name}】网络错误: {e}")
            except TimeoutError:
                blocks.append(f"【{name}】请求超时（{self.timeout}s）")
            except Exception as e:  # noqa: BLE001
                logger.exception("[DS余额] 查询异常")
                blocks.append(f"【{name}】查询异常: {e}")

        yield event.plain_result("DeepSeek 余额\n\n" + "\n\n".join(blocks))

    @filter.command("余额帮助", alias={"ds帮助"})
    async def balance_help(self, event: AstrMessageEvent):
        """查看余额插件用法"""
        yield event.plain_result(
            "DeepSeek 余额查询\n"
            "/余额        查询所有 Key 的余额\n"
            "/余额 备注名  只查某一个\n"
            "配置项在插件设置里，格式：备注名=sk-xxxxxxxx"
        )
