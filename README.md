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

1. 到 [Releases](https://github.com/YHX233/astrbot_plugin_deepseek_balance/releases) 下载 zip
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
  - 主号=sk-你的Key写在这里
  - 测试号=sk-你的Key写在这里
```

### 其他配置项

| 配置项 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `api_keys` | list | 空 | Key 列表，格式 `备注名=sk-xxx` |
| `admin_only` | bool | `true` | 仅管理员/群主可查询 |
| `allowed_users` | list | 空 | 额外允许的 QQ 号白名单 |
| `timeout` | int | `15` | 请求超时秒数 |
| `show_masked_key` | bool | `true` | 结果里显示脱敏 Key |

`admin_only` 默认开启，避免插件被人当免费额度查询器用。想对所有人开放就把这个关掉。

## 用法

| 命令 | 说明 |
| --- | --- |
| `/余额` | 查询所有已配置 Key 的余额 |
| `/余额 备注名` | 只查指定的那一个 |
| `/余额帮助` | 查看用法 |

命令别名：`/查余额`、`/ds余额`、`/deepseek余额`，效果一样。

查询需要联网，会先回一句「查询中，稍等…」，然后出结果。

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
