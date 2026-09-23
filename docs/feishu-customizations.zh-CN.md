[English](feishu-customizations.md) | 简体中文

# fork 里的飞书定制

本页说明 [Hermes fork](hermes-fork.zh-CN.md) 对“把 Hermes 当飞书机器人用”的人有哪些变化，只讲行为和配置。涉及哪些文件、能否回馈上游，见 fork 里的 [`PATCHES.zh-CN.md`](https://github.com/Adonis0123/hermes-agent/blob/main/PATCHES.zh-CN.md)。

提交链接指向叠在上游 `v2026.9.21` 上的 overlay：3 个补丁提交加 1 个文档提交（`PATCHES.md`）（tag `v2026.9.21-adonis.1`）。overlay 每次上游发版都会 rebase，所以这些 SHA 每次同步都会变。`PATCHES.md` 始终写着当前的 SHA。

## 一览

| 行为 | fork 默认 | 配置项 |
| --- | --- | --- |
| 群里的 `@所有人` 不算提及机器人 | 开 | 无 |
| 群里第一次 `@机器人` 会开一个话题来回复 | 开 | `auto_thread` |
| 机器人自己的话题里追问不用再 `@` | 开 | `thread_followup_without_mention` |
| 机器人消息上的表情回应转给 agent | 关 | `route_inbound_reactions` |
| 回答流式写进一张 CardKit 卡片 | 关 | `stream_card`、`stream_card_in_thread`、`stream_card_title` |
| `hermes feishu send` 发送可进话题的普通消息 | 始终可用 | 无 |
| `/new` 和 `/reset` 显示你自己的提示语 | 关（用内置提示） | `display.tips` |

飞书配置写在 `config.yaml` 的 `platforms.feishu.extra` 下，也可以用各节注明的环境变量。两者都设时，`config.yaml` 优先。

```yaml
platforms:
  feishu:
    extra:
      auto_thread: true
      thread_followup_without_mention: true
      route_inbound_reactions: false
      stream_card: true
      stream_card_in_thread: false
      stream_card_title: "Hermes"   # 卡片标题，默认 "Hermes"
      group_rules:
        oc_example_chat_id:
          stream_card: false        # 按群覆盖
          stream_card_title: "Ops Bot"
```

## 群里少打扰

提交：[`feff7a85`](https://github.com/Adonis0123/hermes-agent/commit/feff7a85f5a0b929bc1a4795be85437cda4b2ccf)。

- **`@所有人` 不算提及。** 开启 `require_mention` 时，只有 `@所有人` 的消息不会唤醒机器人。飞书 SDK 有时会漏掉 `@_all`，fork 会先补回来再判断。
- **回复进话题。** 在群里，第一条 `@机器人` 的消息会成为话题的根，回复落在话题里。私聊保持平铺。用 `auto_thread: false`（`FEISHU_AUTO_THREAD`）关闭。
- **追问不用 `@`。** 在机器人已经回答过的话题里，同一个发送者可以继续说，不用再 @。话题里的其他人仍要 @。用 `thread_followup_without_mention: false`（`FEISHU_THREAD_FOLLOWUP_WITHOUT_MENTION`）关闭。
- **默认忽略表情回应。** 给机器人回复点个赞，不会触发新一轮对话。设 `route_inbound_reactions: true`（`FEISHU_ROUTE_INBOUND_REACTIONS`）后，表情会以 `reaction:added:<EMOJI>` 事件发给 agent。即使开启，点赞、OK、完成、爱心、鼓掌这类表示“收到”的表情仍然静默。

## 每个回答一张 CardKit 卡片

提交：[`feff7a85`](https://github.com/Adonis0123/hermes-agent/commit/feff7a85f5a0b929bc1a4795be85437cda4b2ccf)（飞书卡片）、[`e9b8eb26`](https://github.com/Adonis0123/hermes-agent/commit/e9b8eb2635ede18f0996fabd34114d687f9e8157)（跨工具轮保持一条流，网关核心）。

- 设 `stream_card: true`（`FEISHU_STREAM_CARD`）后，回答流式写进一张飞书 CardKit 卡片，原地更新。
- 调用工具期间这张卡片保持打开。没有这个补丁，每轮工具调用都可能新起一个气泡。
- 卡片的流式模式已关闭时（CardKit 错误 `300309`），fork 会重新打开它继续写。
- 卡片完全建不出来时，回答的开头改用普通消息发出，开头不会丢。
- 话题里默认不用卡片，除非设 `stream_card_in_thread: true`（`FEISHU_STREAM_CARD_IN_THREAD`）。
- 卡片标题读 `stream_card_title`（`FEISHU_STREAM_CARD_TITLE`），默认 `Hermes`，可以改成你机器人的名字。
- `stream_card`、`stream_card_in_thread` 和 `stream_card_title` 都可以在 `group_rules.<chat_id>` 下按群覆盖。
- 飞书是否流式输出，跟随全局流式开关（`display.platforms.feishu` 继承全局设置）。

## `hermes feishu send`

提交：[`feff7a85`](https://github.com/Adonis0123/hermes-agent/commit/feff7a85f5a0b929bc1a4795be85437cda4b2ccf)。

这是内置飞书平台插件提供的 CLI 命令。它总是发送普通（非卡片）消息，所以返回的是 `om_` 消息 ID，其他工具可以在话题里回复它。它还会像 `hermes send` 一样，把文本同步进目标会话。

```bash
hermes feishu send "构建完成"                             # 发到主频道（FEISHU_HOME_CHANNEL）
hermes feishu send -t feishu:<chat_id> -f notes.md       # 正文取自文件
echo "done" | hermes feishu send -t feishu:<chat_id> --json
```

这个命令放在飞书插件里，核心的 `hermes send` 和 `send_message` 文件与上游一致。

## `/new` 的提示语

提交：[`ffbf2d05`](https://github.com/Adonis0123/hermes-agent/commit/ffbf2d05127c3c8bc2bcd60e296f85dc99a9c3a1)。

- `display.tips` 是字符串列表。列表非空时，网关的 `/new` 和 `/reset` 会从中随机取一行附在后面。网关进程不重启期间，同一个聊天不会连续两次拿到同一行。
- 空列表（默认）使用内置英文提示。CLI 启动和 `/clear` 始终用内置提示。
- 重置提示现在只显示 `Model` 一行，provider 和上下文长度改到 `/status` 查看。

```yaml
display:
  tips:
    - 用 /status 查看模型和上下文大小。
    - 换话题前先说一声“新话题”。
```

## 早先的 fork 提交

`v2026.9.21-adonis.1` 之前，fork 上有更多提交，包括撤回和 workflow 调整。它们已压成上面 3 个补丁提交；净改动为零的部分（核心发送文件、`/restart` 回执、`install-e2e` workflow 文件）已去掉，这些文件与上游一致。上游的 `Install & Update E2E` workflow 改为在 fork 的 GitHub 设置里停用。
