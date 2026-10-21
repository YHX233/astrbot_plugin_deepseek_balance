# DeepSeek 余额查询

一个给你自己的 AstrBot 加的小插件，用来查 DeepSeek API Key 的账户余额。

支持配置多个 Key，一次性全查，也可以只查指定的某个。余额、赠送额度、充值额度都会分开列出来。

## 安装

方式一：WebUI 上传

1. 下载 `astrbot_plugin_deepseek_balance.zip`
2. 打开 AstrBot WebUI，进插件管理页面
3. 点安装插件，上传这个 zip
4. 装完会自动加载，插件列表里会出现「DeepSeek余额查询」

方式二：手动放目录

把解压出来的 `astrbot_plugin_deepseek_balance` 文件夹丢到 `data/plugins/` 下面，然后在 WebUI 里重载插件或重启 AstrBot。

依赖只有 `aiohttp`，AstrBot 自带，一般不用额外装。

## 配置

装好后去插件配置页面填这几项。

`api_keys` 是核心配置，用来填 Key。每条格式是 `备注名=sk-xxxxxxxx`，备注名会显示在查询结果里方便区分。只填 `sk-xxxxxxxx` 不带备注名也可以，插件会自动编号成 Key1、Key2。

举个例子：

```
主号=sk-你的Key写在这里
测试号=sk-你的Key写在这里
```

几个可选项：

`admin_only` 默认开启，只有群管理员或群主才能查余额，避免被人当免费额度查询器用。想放开就把这个关掉。

`allowed_users` 白名单，填 QQ 号。即使对方不是群管理员，只要在这个列表里也能查询。

`timeout` 请求超时秒数，默认 15 秒。

`show_masked_key` 默认开启，会在结果里显示脱敏后的 Key，像 `sk-36****03c2` 这样，方便你分辨是哪一条。

## 用法

```
/余额
```

查询所有已配置 Key 的余额。因为查询要联网，会先回一句「查询中」，然后出结果。

```
/余额 主号
```

只查备注名是「主号」的那一个。

```
/余额帮助
```

看用法说明。

## 输出示例

```
DeepSeek 余额

【主号】 sk-36****03c2
账户状态: 可用
总余额: ¥12.94 CNY
  赠送余额: ¥0.00    充值余额: ¥12.94
```

配了多个 Key 的时候，每个 Key 一段，中间空行隔开。

## 说明

查询用的是 DeepSeek 官方接口 `GET https://api.deepseek.com/user/balance`，需要 Bearer token 认证。

返回里的 `is_available` 会显示成「账户状态」，余额明细按币种分开列，目前 DeepSeek 只返回 CNY。

如果遇到报错，常见的是这几种：

401 说明 Key 无效或者被吊销了，检查有没有填错。

403 说明这个 Key 没权限访问余额接口。

超时的话一般是网络问题，可以把 `timeout` 调大一点，或者检查一下服务器能不能连到 `api.deepseek.com`。

## 作者

汐研
