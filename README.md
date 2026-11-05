# DeepSeek 余额查询

[![AstrBot](https://img.shields.io/badge/AstrBot-%3E%3D4.20-blue)](https://github.com/AstrBotDevs/AstrBot)
[![Version](https://img.shields.io/badge/version-1.2.1-green)](https://github.com/YHX233/astrbot_plugin_deepseek_balance)
[![License](https://img.shields.io/badge/license-MIT-orange)](LICENSE)

给 AstrBot 用的 DeepSeek 余额插件。一条命令查清余额，也能自己盯着，低了主动喊你。

## 功能

- **多 Key 查询** — 配置多个 API Key，一次全查，也可以只查指定的某个
- **余额明细** — 总余额、赠送余额、充值余额分开列
- **余额账本** — 每次查询自动记一笔，`/余额账本` 看涨跌趋势（默认开启）
- **定期检查** — 按间隔自动查，低于阈值主动提醒（默认关闭）
- **查询回报** — 查询后把结果告诉 AI，后续对话能提起来（默认关闭）
- **自动切换供应商** — 余额见底时切到备用供应商（默认关闭，会破坏缓存）

## 效果

```
DeepSeek 余额

【主号】 sk-36****03c2
账户状态: 可用
总余额: ¥12.94 CNY
  赠送余额: ¥0.00    充值余额: ¥12.94
```

配了多个 Key 时，每个 Key 一段，中间空行隔开。

账本长这样：

```
DeepSeek 余额账本

【主号】
当前 3.20 元 ｜ 记录 5 次 ｜ 最高 12.00 ｜ 最低 3.20
11-05 18:45   7.20 元  ↓2.30
11-05 19:45   4.80 元  ↓2.40
11-05 20:45   3.20 元  ↓1.60
```

## 安装

### 方式一：WebUI 上传（推荐）

1. 下载 [astrbot_plugin_deepseek_balance_v1.2.1.zip](dist/astrbot_plugin_deepseek_balance_v1.2.1.zip)
2. 打开 AstrBot WebUI，进入插件管理
3. 点「安装插件」，上传这个 zip
4. 装完自动加载，插件列表里出现「DeepSeek余额查询」

### 方式二：手动放置

把 `astrbot_plugin_deepseek_balance` 文件夹放到 `data/plugins/` 下，然后在 WebUI 里重载插件或重启 AstrBot。

依赖只有 `aiohttp`，AstrBot 自带，不用额外装。

## 快速开始

1. 插件配置里填 `api_keys`，格式 `备注名=sk-xxxxxxxx`
2. 在群里发 `/余额`，确认能查到
3. 想让插件自己盯余额，就去要收提醒的会话发 `/余额订阅`，再把 `enable_auto_check` 打开

前两步做完就能用了，第三步是可选的。

## 配置

### api_keys（必填）

核心配置，一行一个 Key，格式 `备注名=sk-xxxxxxxx`。备注名会显示在查询结果里，方便区分。

```yaml
api_keys:
  - 主号=sk-你的Key1
  - 测试号=sk-你的Key2
```

不带备注名也行，插件会自动编号成 Key1、Key2。

### 基础

| 配置项 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `api_keys` | list | 空 | Key 列表，格式 `备注名=sk-xxx` |
| `admin_only` | bool | `true` | 仅管理员/群主可查询 |
| `allowed_users` | list | 空 | 额外允许的 QQ 号白名单 |
| `timeout` | int | `15` | 请求超时秒数 |
| `show_masked_key` | bool | `true` | 结果里显示脱敏 Key |

`admin_only` 默认开启，避免插件被人当免费额度查询器用。想对所有人开放就关掉它。

### 定期检查

| 配置项 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `enable_auto_check` | bool | `false` | 开启定期余额检查 |
| `check_interval_minutes` | int | `60` | 检查间隔（分钟） |
| `low_balance_threshold` | float | `5.0` | 低余额阈值（元），低于等于它触发提醒 |
| `notify_mode` | string | `agent` | 通知方式：`agent` 或 `message` |
| `notify_session` | string | 空 | 通知目标会话，留空则用 `/余额订阅` 记录的 |
| `notify_cooldown_hours` | int | `6` | 同一个 Key 的提醒冷却时间 |

### 账本

| 配置项 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `enable_ledger` | bool | `true` | 记录余额账本 |
| `ledger_max_records` | int | `500` | 账本最多保留条数 |
| `ledger_show_count` | int | `5` | 账本里每个 Key 显示几条明细 |

### 回报与供应商切换

| 配置项 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `enable_query_report` | bool | `false` | 查询后额外回报给 AI |
| `enable_auto_switch_provider` | bool | `false` | 低余额时自动切换供应商 |
| `fallback_provider_id` | string | 空 | 切换目标供应商 ID |

## 命令

| 命令 | 说明 |
| --- | --- |
| `/余额` | 查询所有已配置 Key 的余额 |
| `/余额 备注名` | 只查指定的那一个 |
| `/余额账本` | 查看余额变化记录 |
| `/余额账本 清空` | 清空账本 |
| `/余额订阅` | 把当前会话设为低余额通知目标 |
| `/余额订阅 关闭` | 取消订阅 |
| `/余额检查` | 立即检查一次（忽略冷却） |
| `/余额帮助` | 查看用法 |

命令别名：`/查余额`、`/ds余额`、`/deepseek余额`。

查询要联网，会先回一句「查询中，稍等…」，然后出结果。

## 余额账本

默认开启。每次查余额都会记一条——手动 `/余额` 和定期检查都算。

箭头是和上一条记录相比的变化。每个 Key 只显示最近 `ledger_show_count` 条明细，总量上限 `ledger_max_records`，超了丢最早的。

数据存在插件自己的 KV 存储里，不落地成文件。不想记就把 `enable_ledger` 关掉，已有记录用 `/余额账本 清空` 抹掉。

## 低余额监控

插件可以自己盯着余额，低到阈值时主动喊你。

开启三步：

1. 填好 `api_keys`
2. 在要收提醒的群或私聊发一次 `/余额订阅`
3. 把 `enable_auto_check` 打开，按需调间隔和阈值

之后每过一个间隔查一轮，任一 Key 的总余额小于等于阈值时触发：

```
⚠️ DeepSeek 余额不足
当前api余额剩余 3.20 元（主号）
提醒阈值：5.00 元
```

### 通知方式

`notify_mode` 两个取值：

- `agent`（默认）— 构造事件唤醒主 AI，由它组织语言回复。它知道上下文，能顺便帮你看看该不该充值。
- `message` — 直接发纯文本，不经过 AI，最省 token。

`agent` 依赖 AstrBot 内部接口，版本变动导致失败时会自动降级成 `message`，不会静默丢消息。

### 防刷屏

`notify_cooldown_hours` 控制同一个 Key 的提醒频率，默认 6 小时。余额回到阈值以上后冷却重置，下次再低会重新提醒。

## 查询回报

`enable_query_report` 打开后，每次 `/余额` 查询完会额外唤醒一次 AI，让它知道「xx点xx分查询了ds余额，剩余xxx」，后续对话里能提起来。

默认关闭，原因很实在：每次查询多跑一轮模型，费 token，而且账本已经记了同样的信息。想要 AI 对余额有记忆再开。

回报走后台任务，不拖慢查询结果的返回。唤醒失败只记日志，不会重复发消息骚扰。

## 自动切换供应商

`enable_auto_switch_provider` 打开后，余额过低时自动把聊天供应商切到 `fallback_provider_id` 指定的那个，让 bot 继续跑在别的 Key 上。

> ⚠️ **此功能会破坏缓存导致消费增加。** 切换供应商会让 prompt 缓存失效，同样的对话要多花一遍钱。除非余额真的见底，否则不建议开。

`fallback_provider_id` 填 AstrBot「服务提供商」页面里的 ID，留空则不切换。切换同时作用于当前会话和全局，避免只对单个会话生效。

## 常见问题

**401 报错**

Key 无效或已被吊销，检查有没有填错、有没有多余的空白字符。

**403 报错**

这个 Key 没有权限访问余额接口，通常是 Key 的权限范围被限制了。

**请求超时**

网络问题。把 `timeout` 调大，或检查服务器能不能访问 `api.deepseek.com`。

**提示「还没配置 API Key」**

去配置里的 `api_keys` 填上 Key，保存后重载插件。

**查询结果里没有赠送余额**

DeepSeek 只在你领过赠送额度时才返回 `granted_balance`，没有就是 0.00，正常。

**开了定期检查但收不到提醒**

按顺序排查：`api_keys` 填了没 → 有没有发过 `/余额订阅`（或填了 `notify_session`）→ 余额是不是真的低于阈值 → 是不是在冷却期内。手动发 `/余额检查` 可以直接跳过冷却验证。

**余额恢复后还会一直提醒吗**

不会。余额回到阈值以上后再降下来，才会重新提醒一次。

## 数据来源与隐私

调用 DeepSeek 官方接口 `GET https://api.deepseek.com/user/balance`，Bearer token 认证。

返回的 `is_available` 映射成「账户状态」，`balance_infos` 按币种分开列，目前 DeepSeek 只返回 CNY。

插件只读取余额信息，不会把 Key 发到除 DeepSeek 官方以外的任何地方。结果里的 Key 经过脱敏，只保留头尾几位。账本只存「时间 + 备注名 + 金额」，不存 Key。

## 更新日志

### 1.2.1
- 新增余额账本：每次查询记录时间与余额，`/余额账本` 查看趋势，支持清空
- 新增查询回报：查询后把结果作为事件推给 AI（默认关闭）

### 1.1.0
- 新增定期余额检查与低余额提醒
- 新增低余额自动切换供应商（默认关闭）
- 新增 `/余额订阅`、`/余额检查` 命令

### 1.0.1
- 补充 MIT 许可证
- 完善插件元数据（标签、关键词、版本要求）
- 重写文档

### 1.0.0
- 首次发布：多 Key 余额查询

## 许可

[MIT License](LICENSE)
