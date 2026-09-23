[English](feishu-quiet-group-delivery.md) | 简体中文

# 飞书群里的安静投递

Hermes 机器人在热闹的飞书群里，一个任务可能刷出很多系统消息：`Working — N min` 心跳、`Self-improvement review` 通知、短确认、工具进度、单独发的图片。本文是这里的配置：每个任务在主时间线最多一条消息，工作都在话题里进行。

下文部分行为来自 [fork overlay](hermes-fork.zh-CN.md)，不是上游 Hermes 自带，已标 **（fork）**。细节和当前 commit 见 [飞书定制](feishu-customizations.zh-CN.md) 和 fork 的 [`PATCHES.md`](https://github.com/Adonis0123/hermes-agent/blob/main/PATCHES.md)。

## 目标

- 主时间线：每个任务最多 **1** 条，常常是 0 条。
- 任务在触发消息下建消息话题，过程和结论都进话题。
- 话题内：普通消息，不用流式卡片。
- 关掉系统噪音：心跳、自改进聊天通知、工具进度。
- 每轮只有一条终态回答，不出现内容相同的第二个气泡。

## 决策

| # | 问题 | 选择 | 理由 | 放弃的方案 |
| --- | --- | --- | --- | --- |
| 1 | 终态回答形态 | 消息条数优先。飞书关掉 token 流式，终态整条发一次 | token 流式会在工具边界把中间句子留成永久气泡，实测一个任务在话题里留下 7 条 | 默认打字机流式 |
| 2 | 话题 | 每个 @ 任务都建话题；话题内普通消息；主时间线最多一张卡 | 群保持可读，上下文留在话题 | 只在讨论时建；默认用话题群；永不自动建 |
| 3 | 短确认 | 主时间线永远不单独发第二条 | “一条”就是一条 | 独立的中间气泡 |
| 4 | 改动落点 | 先配置和 skill；缺开关才改 adapter | 改动面小 | 一上来大改网关 |
| 5 | 主时间线那一条 | 如果发，就是最终结论；开场和过程只在话题里 | 主时间线最干净 | 开场摘要卡 + 话题细节 |
| 6 | 卡片粒度 | 卡片：全局开关、按群覆盖、话题单独一个开关 **（fork）** | 有的群想要打字卡片，话题可以单独配置 | 按单张卡开关 |

## 降噪配置（上游配置项）

这些键上游 Hermes 就有。改完在飞书里发 `/restart` 重启网关。

```yaml
display:
  memory_notifications: off
  long_running_notifications: false
  platforms:
    feishu:
      streaming: false                  # 不做 token 流式，终态整条发一次
      tool_progress: off
      long_running_notifications: false
      busy_ack_detail: false
      memory_notifications: off
      interim_assistant_messages: false
```

- `memory_notifications: off` 只静音聊天通知，后台 review 仍可能改 skill。
- 飞书没有可靠的事后删除进度气泡的办法，所以从源头关掉，不要指望清理。
- 只关 `interim_assistant_messages` 不够。设了 `streaming: false` 之后多余气泡才消失。

## 话题和卡片（fork）

```yaml
platforms:
  feishu:
    extra:
      require_mention: true           # 上游
      auto_thread: true               # （fork）群里第一次 @ 就建话题
      stream_card: true               # （fork）每个回答一张 CardKit 卡，用于主时间线 / 私聊
      stream_card_in_thread: false    # （fork）话题里用普通消息
      group_rules:
        oc_xxx:
          stream_card: false          # （fork）按群覆盖
          stream_card_in_thread: true # （fork）按群覆盖
```

- **auto_thread（fork）。** 群消息没有 root 或 thread id 时，用触发消息的 `message_id` 当话题根。回复以 `reply_in_thread=true` 发出，这是普通消息话题，不是话题群。会话键优先用根 `om_` id，后续的 `omt_` id 不会把会话拆开。
- **跨工具轮次同一张卡（fork）。** `stream_card: true` 时，回答流进一张 CardKit 卡，跨工具调用保持打开。卡片开着时 token 只进卡片，工具边界不会拆出新气泡。
- **话题内不用卡（fork）。** 话题里默认关卡片，除非设 `stream_card_in_thread: true`。
- CardKit 需要应用权限 `cardkit:card:write`，飞书客户端 7.20 及以上。卡片创建失败时回退为普通消息。

## 目标行为

| 场景 | 主时间线 | 话题内 | 卡片 |
| --- | --- | --- | --- |
| 群里第一次 @ | 在触发消息下建话题（fork） | 过程和结论 | 话题内关 |
| @ 并下任务（收单、写代码、长评审） | 最多一张终态卡，或只加一个表情 | 过程和结论 | 话题内关 |
| 话题内跟进 | 不发 | 普通消息 | 否 |
| 图片 | 能嵌就嵌进终态卡 | 带图的 post | 卡片优先 |
| 心跳、自改进通知 | 永不 | 永不 | — |
| 私聊 | 平铺对话 | 不建话题 | 可以用 |

## 飞书平台事实

- CardKit 流式：先创建 `streaming_mode: true` 的卡片实体，再发带 `card_id` 的 `msg_type=interactive`，然后全量更新 markdown 元素内容，最后设 `streaming_mode: false` 收尾。更新同一个 `card_id` 仍算一条消息。流式约 10 分钟后自动关闭，所以要主动收尾。
- 卡片里放图用 markdown `![hover_text](image_key)`，`image_key` 来自图片上传接口。单独发图就是第二条消息。

## 推进顺序

| 里程碑 | 步骤 | 用户看到的变化 |
| --- | --- | --- |
| M0 | 应用降噪配置，重启 | 不再有心跳和自改进通知 |
| M1 | 打开话题和卡片；任务类 skill 改为在话题里回复 | 任务进话题 |
| M2 | 话题内强制普通消息（fork） | 话题里没有卡片 |
| M3 | 图片嵌进终态卡 | 一张带图的卡。这里还没做：图片仍单独发一条 |

卡片回滚：`stream_card: false`。

## 风险

| 风险 | 对策 |
| --- | --- |
| 应用没有 CardKit 权限 | 创建卡片失败，回退为普通消息；补上权限 |
| 话题太多 | 只有任务建话题；如果愿意，短答可以留在主时间线 |
| 流式 10 分钟后自动关闭 | 主动收尾 |
| 仍然出现中间气泡 | 关掉飞书的 `streaming`，不只关 `interim_assistant_messages` |

## 验收

1. 跑 3 分钟的任务，群里没有 `Working —`，也没有 `Self-improvement review`。
2. 群任务会建话题，过程留在话题里。
3. 每轮只有一条可见的终态回答。
4. 话题内回复是普通消息，不是卡片。
5. 能嵌图时图在卡片里；否则只在话题里多一条消息。

用 [黑盒验收清单](feishu-gateway-blackbox-checklist.zh-CN.md) 验证。

## 参考

- Hermes [Feishu 指南](https://github.com/NousResearch/hermes-agent/blob/main/website/docs/user-guide/messaging/feishu.md)（Streaming Card Replies、Per-Group Access Control）
- Hermes [Messaging 概览](https://github.com/NousResearch/hermes-agent/blob/main/website/docs/user-guide/messaging/index.md)（`long_running_notifications`、`tool_progress`）
- [飞书定制](feishu-customizations.zh-CN.md)
