[English](feishu-gateway-blackbox-checklist.md) | 简体中文

# 飞书网关黑盒验收清单

配置看起来对，不等于机器人实际表现对。改完飞书配置、升级 Hermes 或 rebase fork 之后，在真实聊天里手动跑这 6 项。每项都留下消息 id 作证据，不写“应该没问题”。

整套大约 15 到 30 分钟。用测试群或低峰时段，别在忙碌的生产大群里跑。

相关：[飞书群安静投递](feishu-quiet-group-delivery.zh-CN.md) 描述了这些检查要验证的行为。

## @ 门禁：默认拒绝

两处都显式设置，避免少一个环境变量就悄悄放开。

| 来源 | 期望 |
| --- | --- |
| `~/.hermes/.env`：`FEISHU_REQUIRE_MENTION` | `true` |
| `config.yaml`：`platforms.feishu.extra.require_mention` | `true`（显式写，不只靠环境变量） |
| `config.yaml`：`platforms.feishu.extra.auto_thread` | `true`（fork overlay，见下文） |
| 允许免 @ 的群 | 只给那一个群设 `group_rules.<chat_id>.require_mention: false` |

`require_mention` 和 `group_rules` 是上游 Hermes 的配置。`auto_thread` 和话题内免 @ 跟进来自 fork overlay，见 [飞书定制](feishu-customizations.zh-CN.md) 和 fork 的 [`PATCHES.md`](https://github.com/Adonis0123/hermes-agent/blob/main/PATCHES.md)。用原版 Hermes 时，跳过或改写第 2、3 项。

改完配置，在飞书里给机器人发 `/restart`，让网关重新加载。

## 6 项检查

| # | 检查 | 操作 | 期望 | 证据 |
| --- | --- | --- | --- | --- |
| 1 | 不 @ 不回 | 在群里发纯文本，不 @ 机器人 | 没有回复，也没有 agent turn | 触发消息 `om_` id；其后没有机器人消息 |
| 2 | @ 后进话题 | @ 机器人问一句短问题 | 回复在你那条消息下的消息话题里；主时间线保持干净 | 触发 `om_` id；回复的 root / thread id |
| 3 | 话题内跟进 | 在同一话题再发一条（带 @ 和不带 @ 各试一次） | 会话能继续；或者记下“需要再次 @” | 前后两条 `om_` id |
| 4 | 长任务不刷屏 | 让它做一个多步任务 | 主时间线最多一句短话，过程都在话题里 | 主时间线消息数 |
| 5 | 真的 @ 到主人 | 让机器人在话题里向主人提问 | 通过 API 读回这条消息，`mentions[]` 里有主人的 `ou_` id | 出站 `om_` id + API 返回 |
| 6 | 终态只有一条 | 走一条会得出结论的路径 | 用户只看到一条终态回答，没有内容相同的第二个气泡 | 话题里机器人消息数 |

第 6 项失败，通常是两条路径都在发终态回答，比如 CLI 发送一次、网关自己又回复一次。终态回答只选一条投递路径。

## 记录模板

```markdown
## Run YYYY-MM-DD
| # | pass? | trigger_om | result_om | notes |
|---|-------|------------|-----------|-------|
| 1 |       |            |           |       |
| 2 |       |            |           |       |
| 3 |       |            |           |       |
| 4 |       |            |           |       |
| 5 |       |            |           |       |
| 6 |       |            |           |       |
config: require_mention= / auto_thread=
```

每次结果连同日期记在私有笔记里，放在它验证的 spec 旁边。不要公开真实消息 id。

## 不覆盖的内容

- 不替代自动化端到端测试。
- 不测私聊：私聊不建话题，也不需要 @。
