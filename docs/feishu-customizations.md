English | [简体中文](feishu-customizations.zh-CN.md)

# Feishu customizations in the fork

What the [Hermes fork](hermes-fork.md) changes for people who run Hermes as a Feishu bot. This page describes behavior and settings. For files touched and upstream status, see [`PATCHES.md`](https://github.com/Adonis0123/hermes-agent/blob/main/PATCHES.md) in the fork.

Commit links point to the overlay on upstream `v2026.9.21`: three patch commits plus one docs commit (`PATCHES.md`) (tag `v2026.9.21-adonis.1`). The overlay is rebased on every upstream release, so these SHAs change with each sync. `PATCHES.md` always names the current ones.

## Summary

| Behavior | Default on the fork | Setting |
| --- | --- | --- |
| `@all` in a group is not a mention of the bot | on | none |
| First `@bot` in a group opens a topic thread for the reply | on | `auto_thread` |
| Follow-ups in the bot's own topic need no new `@` | on | `thread_followup_without_mention` |
| Emoji reactions on bot messages reach the agent | off | `route_inbound_reactions` |
| Answers stream into one CardKit card | off | `stream_card`, `stream_card_in_thread`, `stream_card_title` |
| `hermes feishu send` posts a classic, threadable message | always available | none |
| `/new` and `/reset` show your own tip lines | off (built-in tips) | `display.tips` |

Feishu settings go under `platforms.feishu.extra` in `config.yaml`, or in the environment variable named in each section. A `config.yaml` value wins over the environment variable.

```yaml
platforms:
  feishu:
    extra:
      auto_thread: true
      thread_followup_without_mention: true
      route_inbound_reactions: false
      stream_card: true
      stream_card_in_thread: false
      stream_card_title: "Hermes"   # card header, default "Hermes"
      group_rules:
        oc_example_chat_id:
          stream_card: false        # per-chat override
          stream_card_title: "Ops Bot"
```

## Quiet group behavior

Commit: [`feff7a85`](https://github.com/Adonis0123/hermes-agent/commit/feff7a85f5a0b929bc1a4795be85437cda4b2ccf).

- **`@all` is not a mention.** With `require_mention` on, a message that only says `@all` does not wake the bot. The Feishu SDK sometimes leaves `@_all` out of the mention list, so the fork adds it back before deciding.
- **Replies go into a topic.** In a group, the first `@bot` message becomes the root of a topic thread, and the reply lands there. DMs stay flat. Turn off with `auto_thread: false` (`FEISHU_AUTO_THREAD`).
- **Follow-ups without `@`.** Inside a topic the bot already answers, the same sender can keep talking without mentioning the bot again. Other people in that topic still need to `@` it. Turn off with `thread_followup_without_mention: false` (`FEISHU_THREAD_FOLLOWUP_WITHOUT_MENTION`).
- **Reactions are ignored by default.** A thumbs-up on a bot reply does not start a new turn. Set `route_inbound_reactions: true` (`FEISHU_ROUTE_INBOUND_REACTIONS`) to send reactions to the agent as `reaction:added:<EMOJI>` events. Even then, plain acknowledgements (thumbs-up, OK, done, heart, clap, and similar) stay silent.

## One CardKit card per answer

Commits: [`feff7a85`](https://github.com/Adonis0123/hermes-agent/commit/feff7a85f5a0b929bc1a4795be85437cda4b2ccf) (Feishu card), [`e9b8eb26`](https://github.com/Adonis0123/hermes-agent/commit/e9b8eb2635ede18f0996fabd34114d687f9e8157) (one stream across tool rounds, gateway core).

- With `stream_card: true` (`FEISHU_STREAM_CARD`), an answer streams into a single Feishu CardKit card that is edited in place.
- The same card stays open across tool calls. Without this, each tool round could start a new message bubble.
- If a card's streaming mode has already closed (CardKit error `300309`), the fork reopens it and keeps editing.
- If a card cannot be created at all, the first part of the answer is sent as a normal message, so the start of the answer is never lost.
- Inside topic threads, cards are off unless `stream_card_in_thread: true` (`FEISHU_STREAM_CARD_IN_THREAD`).
- The card header reads `stream_card_title` (`FEISHU_STREAM_CARD_TITLE`), default `Hermes`. Set it to your bot's name.
- `stream_card`, `stream_card_in_thread` and `stream_card_title` can be overridden per chat under `group_rules.<chat_id>`.
- Whether Feishu streams at all follows the global streaming switch (`display.platforms.feishu` inherits it).

## `hermes feishu send`

Commit: [`feff7a85`](https://github.com/Adonis0123/hermes-agent/commit/feff7a85f5a0b929bc1a4795be85437cda4b2ccf).

A plugin CLI command from the bundled Feishu platform plugin. It always posts a classic (non-card) message, so the returned id is an `om_` message id that other tools can reply to in a thread. It also mirrors the text into the target chat's session, as `hermes send` does.

```bash
hermes feishu send "Build finished"                      # home channel (FEISHU_HOME_CHANNEL)
hermes feishu send -t feishu:<chat_id> -f notes.md       # body from a file
echo "done" | hermes feishu send -t feishu:<chat_id> --json
```

The command lives in the Feishu plugin, so core `hermes send` and `send_message` files match upstream.

## Tips on `/new`

Commit: [`ffbf2d05`](https://github.com/Adonis0123/hermes-agent/commit/ffbf2d05127c3c8bc2bcd60e296f85dc99a9c3a1).

- `display.tips` is a list of strings. When it is not empty, gateway `/new` and `/reset` append one line picked at random from it. The same chat does not get the same line twice in a row while the gateway process stays up.
- An empty list (the default) keeps the built-in English tips. CLI startup and `/clear` always use the built-in tips.
- The reset notice now shows only the `Model` line. Provider and context length moved to `/status`.

```yaml
display:
  tips:
    - Run /status to see the model and context size.
    - Say "new topic" before switching subjects.
```

## Earlier fork commits

Before `v2026.9.21-adonis.1` the fork carried more commits, including reverts and workflow tweaks. They were squashed into the three patch commits above; the ones whose net change was zero (core send files, `/restart` receipts, the `install-e2e` workflow file) are gone, and those files match upstream. The upstream `Install & Update E2E` workflow is disabled in the fork's GitHub settings instead.
