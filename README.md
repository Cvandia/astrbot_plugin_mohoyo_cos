<div align="center">

# astrbot_plugin_mohoyo_cos

<a href="https://cloud.astrbot.app/plugin/Cvandia/astrbot_plugin_mohoyo_cos">
<img src="https://count.getloli.com/get/@astrbot_plugin_mohoyo_cos?theme=booru-lewd"></a>

_⭐基于AstrBot获取米游社社区cos照片的插件项目⭐_

<a href="https://www.python.org/downloads/">
    <img src="https://img.shields.io/badge/python-3.12+-blue"></a>
<a href="https://qm.qq.com/q/SL6m4KdFe4">
    <img src="https://img.shields.io/badge/QQ-1141538825-yellow"></a>
<a href="https://github.com/Cvandia/astrbot_plugin_mohoyo_cos/blob/master/LICENSE">
    <img src="https://img.shields.io/badge/license-MIT-blue"></a>
<a href="https://github.com/AstrBotDevs/AstrBot">
    <img src="https://img.shields.io/badge/AstrBot-4.29.1+-red"></a>

**中文简体**

</div>

---

基于 AstrBot 的米游社图片插件，支持原神、崩坏3、崩坏2、星穹铁道、大别野和绝区零。
参考 [nonebot-plugin-genshin-cos](https://github.com/Cvandia/nonebot-plugin-genshin-cos)
的异步客户端、榜单参数、流式下载和冷却实现，使用 AstrBot 原生消息、LLM 工具、配置和插件生命周期。

## 使用

1. 在 AstrBot 插件管理中通过本仓库链接安装；也可以将仓库放入 `astrbot/data/plugins/astrbot_plugin_mohoyo_cos`，安装 `requirements.txt` 后重载插件。
2. 需要 **Python 3.12+、AstrBot 4.29.1+**，配置在 AstrBot 管理面板中编辑。
3. 输入 `/coshelp` 查看帮助；完整更新记录见 [更新日志](changelog.md)。

### 指令

| 指令 | 示例 | 权限 |
| --- | --- | --- |
| 热门 / 最新 | `/热门cos 原神 x3`、`/最新cos 崩铁 2` | 所有人 |
| 日榜 / 周榜 / 月榜 | `/周榜cos 大别野 x3` | 所有人 |
| 精品 | `/精品cos 绝区零 x2` | 所有人 |
| 搜索 | `/搜索cos 原神 "甘雨 cosplay" x2` | 所有人 |
| 兼容旧搜索 | `/hoyocos 钟离 2`、`/hoyocos 崩铁流萤 1` | 所有人 |
| 下载 | `/下载cos 原神`；别名 `保存cos`、`cos保存` | 管理员 |
| 开启每日推送 | `/开启每日推送 原神 08:30` | 群内管理员 |
| 关闭每日推送 | `/关闭每日推送 原神` | 群内管理员 |
| 查看推送 | `/查看本群推送`；别名 `查看推送`、`查看订阅` | 所有人 |
| 帮助 | `/coshelp` | 所有人 |

榜单和搜索支持 `coser`、`cos图` 后缀，例如 `/热门cos图 原神 x3`。
数量可写 `3`、`x3`、`X3`、`*3`，超过上限时截断，零、负数和非整数会提示错误。
找到的图片不足时发送实际可用数量，URL 去重后随机选取。
游戏别名包括 `OP`、`崩三`、`崩二`、`崩铁`、`星铁`、`DBY`、`绝零`、`ZZZ` 等。
无独立 Cos 分区的崩坏3、崩坏2和绝区零搜索时，不限定分区并在关键词后附加 `cos`，保留远端已有搜索策略。
榜单、搜索、下载、订阅管理通过正则匹配，也支持省略 `/`；帮助、旧指令和订阅列表遵循 AstrBot 唤醒配置。
与参考插件不同，游戏参数需要空格分隔，不支持 `搜索原神cos甘雨` 等紧凑格式；下载未填写游戏时直接返回用法。

管理员指 AstrBot 配置的管理员；OneBot 风格事件还识别群主、群管理员角色。
其他适配器请配置 AstrBot 管理员。每日推送仅支持原神和大别野，默认北京时间。
订阅绑定 AstrBot 的统一会话标识（平台实例、消息类型及会话），重载后恢复，不会跨平台实例共享。
推送使用普通图片消息，以支持不同适配器；平台离线或发送失败会记录日志，不补发。

启用 LLM 并允许 `get_cos_pic` 工具后，可用自然语言请求图片。工具与指令使用相同的冷却、数量限制及错误处理。

### 配置

| 配置项 | 默认值 | 说明 |
| --- | --- | --- |
| `cos_max` | `10` | 每次最多发送的图片数，限制为 1–100 |
| `cos_cd` | `10` | 每个平台实例下每位用户的冷却秒数；0 关闭 |
| `cos_forward_msg` | `false` | 查询图片使用合并转发，需要适配器支持 AstrBot `Nodes` |
| `cos_delay` | `0.5` | 查询逐张发送的间隔秒数 |
| `cos_timeout` | `20` | HTTP 请求超时秒数 |
| `cos_path` | 空 | 下载目录；空值使用插件数据目录下的 `images` |
| `cos_timezone` | `Asia/Shanghai` | 每日推送的 IANA 时区，修改后重载插件 |

默认数据目录为 `data/plugin_data/astrbot_plugin_mohoyo_cos`，订阅保存为 `subscriptions.json`。
订阅以临时文件原子替换方式保存，损坏的数据会阻止初始化，不会静默覆盖。
下载按 URL 的 SHA-256 命名，使用 64 KiB 分块写入，跳过已有文件，失败或取消时清理 `.part` 文件。
最多同时处理 4 个请求流程，下载任务串行执行。HTTP 连接池按需创建，插件卸载时关闭。
普通查询将图片 URL 交给 AstrBot 适配器发送，不创建随后立即删除的临时图片。

### 从 1.x 升级

保留 `/hoyocos`、`/coshelp` 和 `get_cos_pic` 工具名。旧 `timeout` 在未设置 `cos_timeout` 时作为回退；
建议在管理面板重新保存新版配置。旧 `Search`、`Rank` 等内部 Python 接口已被 `HoyoClient` 替代。
本插件不读取 NoneBot 的配置或订阅文件，两个框架的数据目录和会话标识不同。

### 开发验证

在仓库根目录使用已安装 AstrBot 的 Python 环境：

```bash
python -m pip install 'astrbot==4.29.1' -r requirements.txt pytest pytest-asyncio ruff
python -m pytest -q
ruff check .
ruff format --check .
```

兼容性验证覆盖 AstrBot 4.29.1 和 4.29.4。测试使用真实 AstrBot SDK，模拟米游社 HTTP 响应及平台发送边界，覆盖接口参数、错误响应、
下载中断清理、指令、LLM、冷却、权限、订阅保存和恢复。模拟测试不代表真实平台发送或米游社在线接口可用。

精品接口 `forumGoodPostFullList` 曾在参考项目中返回 404；原神和星穹铁道不支持精品。
网络需要允许 `bbs-api.mihoyo.com` 及实际图片 CDN；图片展示和合并转发能力取决于所用平台。
图片版权归原作者所有。

## 💝 特别鸣谢

- [x] [AstrBot](https://github.com/AstrBotDevs/AstrBot): 本项目的基础，非常好用的基于LLM聊天的机器人框架。
- [x] [@qxdn](https://github.com/qxdn):感谢qxdn的[博客文章](https://qianxu.run/2021/11/12/mihoyo-bbs-crawler/)

- [x] [nonebot-plugin-genshin-cos](https://github.com/Cvandia/nonebot-plugin-genshin-cos)：本次重构参考的取图、下载与冷却实现。

### 感谢以下开发者

<a href="https://github.com/Cvandia/astrbot_plugin_mohoyo_cos/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=Cvandia/astrbot_plugin_mohoyo_cos&max=100" alt="contributors" />
</a>

# 支持

[帮助文档](https://docs.astrbot.app/) · [问题反馈](https://github.com/Cvandia/astrbot_plugin_mohoyo_cos/issues) · [更新日志](changelog.md)

MIT，见 [LICENSE](LICENSE)。参考实现版本 `4455879705e63f716b9b2049442a5a24eb989e83`，复用部分的原始许可保留在 [LICENSE.reference](LICENSE.reference)。
