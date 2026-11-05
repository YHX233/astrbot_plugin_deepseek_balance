# DeepSeek 余额查询

[![AstrBot](https://img.shields.io/badge/AstrBot-%3E%3D4.20-blue)](https://github.com/AstrBotDevs/AstrBot)
[![Version](https://img.shields.io/badge/version-1.0.1-green)](https://github.com/YHX233/astrbot_plugin_deepseek_balance)
[![License](https://img.shields.io/badge/license-MIT-orange)](LICENSE)

一条命令查清你的 DeepSeek 余额。

支持配置多个 API Key，一次性全查，也可以只查指定的某一个。总余额、赠送余额、充值余额会分开列出来，不用再开网页翻控制台。

## 效果

<!-- 建议在这里放一张实际使用截图 -->
<!-- ![效果图](docs/screenshot.png) -->

```
DeepSeek 余额

【主号】 sk-36****03c2
账户状态: 可用
总余额: ¥12.94 CNY
  赠送余额: ¥0.00    充值余额: ¥12.94
```

配置了多个 Key 的时候，每个 Key 一段，中间空行隔开。

## 安装

### 方式一：插件商城（推荐）

在 AstrBot 的插件商城搜索「DeepSeek余额查询」直接安装。

### 方式二：WebUI 上传

1. 下载 [astrbot_plugin_deepseek_balance_v1.1.0.zip](dist/astrbot_plugin_deepseek_balance_v1.2.0.zip)（也可在 [Releases](https://github.com/YHX233/astrbot_plugin_deepseek_balance/releases) 页面获取）
2. 打开 AstrBot WebUI，进入插件管理
3. 点「安装插件」，上传这个 zip
4. 装完自动加载，插件列表里会出现「DeepSeek余额查询」

### 方式三：手动放置

把 `astrbot_plugin_deepseek_balance` 文件夹放到 `data/plugins/` 下，然后在 WebUI 里重载插件或重启 AstrBot。

依赖只有 `aiohttp`，AstrBot 自带，一般不需要额外安装。

## 配置

装好后进插件配置页面。

### api_keys

核心配置，填你的 Key。每条格式为 `备注名=sk-xxxxxxxx`，备注名会显示在结果里方便区分。

只填 `sk-xxxxxxxx` 不带备注名也可以，插件会自动编号成 Key1、Key2。

```yaml
api_keys:
  - 主号=sk-你的Key1
  - 测试号=sk-你的Key2
```

### 其他配置项

| 配置项 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `api_keys` | list | 空 | Key 列表，格式 `备注名=sk-xxx` |
| `admin_only` | bool | `true` | 仅管理员/群主可查询 |
| `allowed_users` | list | 空 | 额外允许的 QQ 号白名单 |
| `timeout` | int | `15` | 请求超时秒数 |
| `show_masked_key` | bool | `true` | 结果里显示脱敏 Key |
| `enable_auto_check` | bool | `false` | 开启定期余额检查 |
| `check_interval_minutes` | int | `60` | 检查间隔（分钟） |
| `low_balance_threshold` | float | `5.0` | 低余额阈值（元） |
| `notify_mode` | string | `agent` | 通知方式：`agent` 或 `message` |
| `notify_session` | string | 空 | 通知目标会话，留空则用 `/余额订阅` 记录的 |
| `notify_cooldown_hours` | int | `6` | 同一个 Key 的提醒冷却时间 |
| `enable_ledger` | bool | `true` | 记录余额账本 |
| `ledger_max_records` | int | `500` | 账本最多保留条数 |
| `ledger_show_count` | int | `5` | 账本里每个 Key 显示几条明细 |
| `enable_query_report` | bool | `false` | 查询后额外回报给 AI |
| `enable_auto_switch_provider` | bool | `false` | 低余额时自动切换供应商 |
| `fallback_provider_id` | string | 空 | 切换目标供应商 ID |

`admin_only` 默认开启，避免插件被人当免费额度查询器用。想对所有人开放就把这个关掉。

## 用法

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

命令别名：`/查余额`、`/ds余额`、`/deepseek余额`，效果一样。

查询需要联网，会先回一句「查询中，稍等…」，然后出结果。

## 余额账本

默认开启。每次查余额都会记一条——手动 `/余额` 和定期检查都算——用 `/余额账本` 看变化。

```
DeepSeek 余额账本

【主号】
当前 3.20 元 ｜ 记录 5 次 ｜ 最高 12.00 ｜ 最低 3.20
11-05 18:45   7.20 元  ↓2.30
11-05 19:45   4.80 元  ↓2.40
11-05 20:45   3.20 元  ↓1.60
```

箭头是和上一条记录相比的变化。每个 Key 只显示最近 `ledger_show_count` 条明细，总量上限 `ledger_max_records`，超了丢最早的。

数据存在插件自己的 KV 存储里，不落地成文件。不想记就把 `enable_ledger` 关掉，已有的记录用 `/余额账本 清空` 抹掉。

## 余额监控

插件可以自己盯着余额，低到阈值时主动喊你，不用天天手动查。

### 开启步骤

1. 在 AstrBot 里给这个插件填好 `api_keys`
2. 在要收提醒的群或私聊里发一次 `/余额订阅`，把当前会话记下来
3. 插件配置里把 `enable_auto_check` 打开，按需调整 `check_interval_minutes` 和 `low_balance_threshold`

之后每过一个间隔就会查一轮，任一 Key 的总余额小于等于阈值时触发提醒，内容形如：

```
⚠️ DeepSeek 余额不足
当前api余额剩余 3.20 元（主号）
提醒阈值：5.00 元
```

### 通知方式

`notify_mode` 有两个取值：

- `agent`（默认）：构造一个事件唤醒主 AI，由 AI 组织语言回复。好处是它知道上下文，能顺便帮你看看该不该充值。
- `message`：直接发一段纯文本，不经过 AI，最省 token。

`agent` 方式依赖 AstrBot 内部接口，万一某个版本变动导致失败，会自动降级成 `message`，不会静默丢消息。

### 避免刷屏

`notify_cooldown_hours` 控制同一个 Key 的提醒频率，默认 6 小时。余额回到阈值以上后冷却会重置，下次再低会重新提醒。

### 低余额自动切换供应商

`enable_auto_switch_provider` 打开后，余额过低时会自动把聊天供应商切到 `fallback_provider_id` 指定的那个，让 bot 继续跑在别的 Key 上。

> ⚠️ **此功能会破坏缓存导致消费增加。** 切换供应商会让 prompt 缓存失效，同样的对话要多花一遍钱。除非余额真的见底，否则不建议开。

`fallback_provider_id` 填 AstrBot「服务提供商」页面里那个 ID，留空则不切换。切换会同时作用于当前会话和全局，避免只对单个会话生效。

## 查询回报

`enable_query_report` 打开后，每次 `/余额` 查询完会额外唤醒一次 AI，让它知道「xx点xx分查询了ds余额，剩余xxx」这件事，后续对话里就能提起来。

默认关闭，原因很实在：每次查询都要多跑一轮模型，费 token，而且账本已经把同样的信息记下来了，`/余额账本` 随时能查。想要 AI 对余额有记忆再开。

回报走后台任务，不会拖慢查询结果的返回速度。唤醒失败只记日志，不会重复发消息骚扰你。

## 常见问题

**401 报错**

Key 无效或已被吊销，检查有没有填错、有没有多余的空白字符。

**403 报错**

这个 Key 没有权限访问余额接口，通常是 Key 的权限范围被限制了。

**请求超时**

网络问题。可以把 `timeout` 调大，或者检查服务器能不能访问 `api.deepseek.com`。

**提示「还没配置 API Key」**

去插件配置里的 `api_keys` 填上 Key，保存后重载插件。

**查询结果里没有赠送余额**

DeepSeek 只有在你领过赠送额度时才会返回 `granted_balance`，没有就是 0.00，属于正常情况。

## 数据来源

调用 DeepSeek 官方接口 `GET https://api.deepseek.com/user/balance`，Bearer token 认证。

返回的 `is_available` 会映射成「账户状态」，`balance_infos` 按币种分开列，目前 DeepSeek 只返回 CNY。

插件只读取余额信息，不会把 Key 发送到除 DeepSeek 官方以外的任何地方。结果里显示的 Key 经过脱敏处理，只保留头尾几位。

## 许可

[MIT License](LICENSE)
