English | [简体中文](feishu-quiet-group-delivery.zh-CN.md)

# Quiet delivery in Feishu groups

A Hermes bot in a busy Feishu group can post many system lines per task: `Working — N min` heartbeats, `Self-improvement review` notices, short acks, tool progress, and separate image messages. This page is the setup used here to keep the main timeline to at most one message per task, with work happening inside a topic.

Some behavior below comes from the [fork overlay](hermes-fork.md), not from upstream Hermes. Those parts are marked **(fork)**. Details and current commits: [Feishu customizations](feishu-customizations.md) and the fork's [`PATCHES.md`](https://github.com/Adonis0123/hermes-agent/blob/main/PATCHES.md).

## Goals

- Main timeline: at most **one** message per task, often zero.
- A task gets a message topic under the triggering message; progress and the conclusion go there.
- Inside a topic: plain messages, no streaming cards.
- System noise off: heartbeats, self-improvement chat notices, tool progress.
- One final answer per turn. No second bubble with the same content.

## Decisions

| # | Question | Choice | Why | Rejected |
| --- | --- | --- | --- | --- |
| 1 | Final answer shape | Fewest messages first. Turn off token streaming for Feishu; send the final answer once | Token streaming can turn in-between sentences at tool boundaries into permanent bubbles. One observed task left 7 of them in a topic | Typewriter streaming by default |
| 2 | Topics | Every `@` task becomes a topic; plain messages inside; main timeline gets at most one card | Keeps the group readable; context stays in the topic | Topic only for discussions; a dedicated topic-mode group by default; never auto-topic |
| 3 | Short acks | Never a separate second message on the main timeline | "One message" means one | A standalone interim bubble |
| 4 | Where to change things | Config and skills first; patch the adapter only when a switch is missing | Smaller change surface | A big gateway rewrite up front |
| 5 | The one main-timeline message | The final conclusion, if anything; opening and progress stay in the topic | Cleanest main timeline | An opening summary card plus topic details |
| 6 | Card vs. chat granularity | Cards: a global flag, per-chat overrides, and a separate flag for topics **(fork)** | Some chats want a typing card; topics stay configurable | Per-card switches |

## Noise controls (upstream settings)

These keys exist in upstream Hermes. Restart the gateway (`/restart` in Feishu) after changing them.

```yaml
display:
  memory_notifications: off
  long_running_notifications: false
  platforms:
    feishu:
      streaming: false                  # no token streaming; final answer sent once
      tool_progress: off
      long_running_notifications: false
      busy_ack_detail: false
      memory_notifications: off
      interim_assistant_messages: false
```

- `memory_notifications: off` only silences the chat notice. Background review can still patch skills.
- Feishu has no reliable way to delete progress bubbles afterwards, so turn them off at the source instead of relying on cleanup.
- `interim_assistant_messages: false` alone was not enough. The extra bubbles stopped only after `streaming: false`.

## Topics and cards (fork)

```yaml
platforms:
  feishu:
    extra:
      require_mention: true           # upstream
      auto_thread: true               # (fork) first @ in a group opens a topic
      stream_card: true               # (fork) one CardKit card per answer, main timeline / DM
      stream_card_in_thread: false    # (fork) topics use plain messages
      group_rules:
        oc_xxx:
          stream_card: false          # (fork) per-chat override
          stream_card_in_thread: true # (fork) per-chat override
```

- **auto_thread (fork).** In a group, a message with no root or thread id uses the triggering `message_id` as the topic root. Replies go out as a reply with `reply_in_thread=true`, which is a normal message topic, not a topic-mode group. The session key prefers the root `om_` id so later `omt_` ids do not split the session.
- **One card across tool rounds (fork).** With `stream_card: true`, the answer streams into one CardKit card that stays open across tool calls. When the card is on, tokens go only to the card, and tool boundaries do not split it into new bubbles.
- **No cards in topics (fork).** Inside a topic, cards are off unless `stream_card_in_thread: true`.
- CardKit needs the app permission `cardkit:card:write` and a Feishu client of 7.20 or later. If card creation fails, the answer falls back to a normal message.

## Target behavior

| Situation | Main timeline | Inside the topic | Card |
| --- | --- | --- | --- |
| First `@` in a group | a topic opens under the trigger (fork) | process and conclusion | off in topics |
| `@` with a task (intake, code, long review) | at most one final card, or only a reaction | process and conclusion | off in topics |
| Follow-up in the topic | nothing | plain messages | no |
| Image | embedded in the final card when possible | a post with the image | card first |
| Heartbeat, self-improvement notice | never | never | — |
| DM | flat conversation | no topics | allowed |

## Feishu platform facts

- CardKit streaming: create a card entity with `streaming_mode: true`, send `msg_type=interactive` with the `card_id`, update the markdown element's full content, then set `streaming_mode: false` to finish. Updates to the same `card_id` stay one message. Streaming closes itself after about 10 minutes, so finish it explicitly.
- An image in a card is markdown `![hover_text](image_key)`, where `image_key` comes from the image upload API. A separate image message is a second message.

## Rollout order

| Milestone | Steps | What users see |
| --- | --- | --- |
| M0 | Apply the noise controls, restart | No more heartbeats or self-improvement lines |
| M1 | Turn on topics and cards; make task skills reply in the topic | Tasks go into topics |
| M2 | Force plain messages inside topics (fork) | No cards in topics |
| M3 | Embed images in the final card | One card with images. Not done here: images still go as a separate message |

Rollback for cards: `stream_card: false`.

## Risks

| Risk | Mitigation |
| --- | --- |
| App lacks the CardKit permission | Card creation fails and falls back to a normal message; add the permission |
| Too many topics | Only turn tasks into topics; short answers may stay on the main timeline if you prefer |
| Streaming closes after 10 minutes | Finish the card explicitly |
| Interim bubbles still appear | Turn off `streaming` for Feishu, not only `interim_assistant_messages` |

## Acceptance

1. A 3-minute task posts no `Working —` and no `Self-improvement review` line.
2. A group task opens a topic, and progress stays in it.
3. Each turn has one visible final answer.
4. Replies inside a topic are plain messages, not cards.
5. Images appear in the card when embedding works; otherwise as one extra message in the topic.

Verify with the [black-box checklist](feishu-gateway-blackbox-checklist.md).

## References

- Hermes [Feishu guide](https://github.com/NousResearch/hermes-agent/blob/main/website/docs/user-guide/messaging/feishu.md) (Streaming Card Replies, Per-Group Access Control)
- Hermes [Messaging overview](https://github.com/NousResearch/hermes-agent/blob/main/website/docs/user-guide/messaging/index.md) (`long_running_notifications`, `tool_progress`)
- [Feishu customizations](feishu-customizations.md)
