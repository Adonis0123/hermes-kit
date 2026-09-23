English | [简体中文](feishu-gateway-blackbox-checklist.zh-CN.md)

# Feishu gateway black-box checklist

Config that looks right is not the same as a bot that behaves right. After changing Feishu settings, upgrading Hermes, or rebasing the fork, run these six checks by hand in a real chat. Each one leaves message ids as evidence, not "should be fine".

The whole run takes 15 to 30 minutes. Use a test group or a quiet hour, not a busy production group.

Related: [Quiet group delivery](feishu-quiet-group-delivery.md) describes the behavior these checks verify.

## Mention gate: fail closed

Set the gate explicitly in both places, so a missing environment variable cannot silently open it.

| Source | Expected |
| --- | --- |
| `~/.hermes/.env`: `FEISHU_REQUIRE_MENTION` | `true` |
| `config.yaml`: `platforms.feishu.extra.require_mention` | `true` (explicit, so it does not depend on the env var alone) |
| `config.yaml`: `platforms.feishu.extra.auto_thread` | `true` (fork overlay, see below) |
| A group that may talk without `@` | only `group_rules.<chat_id>.require_mention: false` for that one chat |

`require_mention` and `group_rules` are upstream Hermes settings. `auto_thread` and follow-ups without `@` come from the fork overlay; see [Feishu customizations](feishu-customizations.md) and the fork's [`PATCHES.md`](https://github.com/Adonis0123/hermes-agent/blob/main/PATCHES.md). On stock Hermes, skip or adapt checks 2 and 3.

After changing config, send `/restart` to the bot in Feishu so the gateway reloads.

## The six checks

| # | Check | Do | Expect | Evidence |
| --- | --- | --- | --- | --- |
| 1 | No `@`, no reply | Post plain text in the group without mentioning the bot | No reply and no agent turn | trigger `om_` id; no bot message after it |
| 2 | `@` opens a topic | `@` the bot with a short question | The reply is inside a message topic under your message; the main timeline stays clean | trigger `om_` id; reply's root / thread id |
| 3 | Topic follow-up | Post again in the same topic (with and without `@`) | The conversation continues, or you write down that `@` is required again | both `om_` ids |
| 4 | Long task stays quiet | Ask for a multi-step task | At most one short line on the main timeline; progress stays in the topic | message count on the main timeline |
| 5 | Real `@` of the owner | Have the bot ask the owner a question inside the topic | The message's `mentions[]` contains the owner's `ou_` id (read the message back through the API) | outbound `om_` id + the API response |
| 6 | One final message | Take a path that reaches a conclusion | Exactly one user-visible final answer; no second bubble with the same content | bot message count in the thread |

Check 6 usually fails when two paths both deliver the final answer, for example a CLI send plus the gateway's own reply. Pick one delivery path for the final answer.

## Record template

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

Keep each run in your private notes next to the spec it verifies, with the date. Do not publish real message ids.

## Not covered

- It does not replace automated end-to-end tests.
- It does not test DMs, which stay flat and need no mention.
