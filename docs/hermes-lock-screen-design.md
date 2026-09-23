English | [简体中文](hermes-lock-screen-design.zh-CN.md)

# Design: remote Mac lock from a Feishu DM

Design notes for the [`hermes-lock-screen`](../plugins/hermes-lock-screen/) plugin. The owner is away from the Mac and wants it locked now, from a Feishu DM, with proof that it is really locked.

Success means the Mac asks for authentication before showing the desktop again. Display off, screensaver, sleep without a proven lock, or "the command was accepted" do not count.

## Two entry points, one execution path

| Entry | How it is triggered | LLM involved |
| --- | --- | --- |
| `/lock` (preferred) | The owner sends exactly `/lock` in the approved DM | No. It skips the model and Feishu text batching |
| Natural language | The model decides the owner is asking to lock the Mac now and calls the no-argument `lock_screen` tool | Only for intent; never for authorization |

Both build the same `LockRequest` and go through the same authorization, replay protection, audit, fixed Shortcut, and lock verification. There is one execution function; subprocess, audit, and replay logic are never copied.

Why `/lock` is preferred: Feishu text messages are debounced for about 0.6 seconds and merged with newlines, while messages starting with `/` are commands and skip batching. A deterministic command also does not depend on the model choosing the tool.

## The minimal trusted chain

1. Prove the request comes from the approved owner DM.
2. For the natural-language entry, the model's tool choice expresses intent; the plugin proves the request is not a replay.
3. Run a fixed Shortcut with a fixed argv and no user arguments.
4. Read the system lock state. A Shortcut exit code of 0 only proves "invoked", not "locked".

## Authorization (fail closed)

Every call is rejected unless all of these hold:

1. The request resolves to a known session (from `state.db`, or the gateway's inbound event for `/lock`).
2. The platform is `feishu`.
3. The chat is a DM.
4. The chat id is in `owner_dm_chat_ids`.
5. The sender (`user_id` or `user_id_alt`) is in `owner_user_ids`.
6. The tool got no arguments; `/lock` got no trailing text.
7. The triggering message has not already caused a lock attempt.

Owner ids are settings, not secrets. They live in `config.yaml`, never in source:

```yaml
plugins:
  entries:
    hermes-lock-screen:
      owner_user_ids: ["ou_xxx"]
      owner_dm_chat_ids: ["oc_xxx"]
```

The Feishu message itself is the per-call authorization. There is no second prompt on the desktop, because the use case is locking a Mac nobody is sitting at.

Enable the `lock_screen` toolset for Feishu sessions only. The CLI, other platforms, groups, other DMs, and missing context are all rejected.

## How `/lock` gets a trusted context

The owner check needs the sender and chat, but upstream plugin slash commands receive only the raw argument string. Two designs were considered:

| Option | Status |
| --- | --- |
| Extend the host: pass an immutable `PluginCommandContext` (platform, chat id, chat type, user ids, message id, session key) to command handlers that opt in with `accepts_context=True`, and add `busy_policy="dispatch"` so the command runs while the agent is busy | Designed first. It needs a patch to Hermes core, so it would live in the fork; any such patch is listed in the fork's [`PATCHES.md`](https://github.com/Adonis0123/hermes-agent/blob/main/PATCHES.md) |
| Use the upstream `pre_gateway_dispatch` plugin hook, which sees the whole inbound event before dispatch | **Current.** The plugin reads the sender and chat from the event, answers the owner's `/lock` there, and returns `skip`. It works on stock Hermes |

With the hook, anyone who is not the owner falls through to normal dispatch: the gateway's own auth, then the registered `/lock` command, which fails closed with `command_context_missing` because it has no trusted context. The hook runs before the busy check, so `/lock` works while the agent is in the middle of a turn, without interrupting or queuing it.

## Natural-language intent

- Call the tool for any request to lock now, including free-form and polite questions ("can you lock my screen?", "I'm heading out, lock it").
- Do not call it for capability questions, discussion, negation, or hypothetical future requests.
- The plugin does not re-parse the sentence. An earlier version compared the message with a fixed phrase list using the tool's `user_task` field. That failed in practice: Hermes does not pass `user_task` to ordinary tool handlers, and the field means the original task, not the current message. The tool choice now maps to an internal `model_intent` marker instead.

## Execution

1. Validate arguments, context, and policy.
2. Write an `accepted` audit record. If the audit cannot be written, fail.
3. Atomically reserve `(session_id, message_id)`. A duplicate never runs again.
4. Confirm the Shortcut exists by exact name.
5. Run `/usr/bin/shortcuts run "Hermes Lock Screen"` with `shell=False` and a bounded timeout. The name is a source constant, never an argument.
6. Poll the lock state up to five times: `CGSSessionScreenIsLocked` from the `IOConsoleUsers` I/O Registry entry.
7. Return one outcome.

| Outcome | Meaning | Reply to the owner |
| --- | --- | --- |
| `locked`, `verified=true` | System state proves the lock | `🔒 已锁屏。` ("locked") |
| `invoked_unverified` | The Shortcut ran, but the lock could not be proven | `🔒 已执行锁屏。` ("lock requested") |
| `failed` + bounded reason | Authorization, availability, timeout, Shortcut, or audit failed | a safe failure line |

`invoked_unverified` must never be reported as "locked". After `locked` or `invoked_unverified`, no entry may report failure.

Locking does not end the login session, so the gateway keeps running and can deliver the reply while the screen is locked.

## Audit

One JSONL line per attempt in `$HERMES_HOME/logs/lock-screen-audit.jsonl`, file mode `0600`: timestamp, session id, hashed chat and user ids, message id, authorization decision, dispatch result, verification result, bounded error category. Never message text, tokens, credentials, environment values, or unbounded subprocess output.

## Failure behavior

| Failure | Result |
| --- | --- |
| Mac or gateway offline | Nothing runs; no false success |
| Wrong platform, group, chat, or sender | Rejected before dispatch |
| Arguments given | Rejected before dispatch |
| Shortcut missing or renamed | `failed` |
| Shortcut exits non-zero or times out | `failed` |
| Lock state not provable | `invoked_unverified` |
| Same message twice | Rejected as duplicate |

## Tests

Automated tests never lock the real Mac. They use a temporary `HERMES_HOME`, a temporary session database, and mocked subprocess and state probes. They cover: each entry point for the owner DM; rejection of wrong sender, chat, platform, group, arguments, missing message id, and CLI; fixed argv with `shell=False`; duplicate rejection; missing Shortcut, non-zero exit, timeout, verified and unverified lock; audit redaction and file mode. The registered `/lock` handler is tested through the real adapter, classification, and reply formatting, with only the macOS subprocess mocked, so "it ran but the reply said failed" cannot slip through.

Final acceptance is a real test by the owner: send `/lock` from the DM, see the real Lock Screen, unlock locally, and check that the Feishu reply and the audit record match what happened.

## Out of scope

- No change to the `computer_use` key-combo denylist, no AppleScript, no keystroke injection, no arbitrary Shortcut names or shell text.
- No unlock, password entry, sleep, log out, or shutdown.
- Gateway reloads go through `/restart` in Feishu, not from a local session.

Rollback: disable the plugin and the toolset, then `/restart`. The Shortcut can stay installed; it does nothing unless run.

## Appendix: the Shortcut

The plugin depends on one Apple Shortcut in the current macOS user session.

1. In Shortcuts, create a shortcut named exactly `Hermes Lock Screen` with the built-in **Lock Screen** action and nothing else.
2. Run it once by hand. The Mac should show the lock screen within two seconds. Unlock it yourself.
3. Check `shortcuts list` shows `Hermes Lock Screen`, and that it runs again after unlocking.

No new Accessibility permission is needed.

Why a Shortcut:

| Option | Verdict |
| --- | --- |
| Shortcuts' built-in Lock Screen action | Chosen: Apple's own action, lowest permission and maintenance cost |
| A small Swift app | Needs private APIs, signing, notarization, compatibility work |
| AppleScript sending Control-Command-Q | Still a way around the key-combo block |
| `pmset`, screensaver | Cannot prove the system is really locked |
