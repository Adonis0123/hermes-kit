English | [简体中文](memory-provider-adoption-gate.zh-CN.md)

# When to adopt an external memory provider

Hermes can attach an external memory provider (a plugin that recalls scenes or a user profile on each turn). When the built-in memory feels full, adding one is tempting. This page is the gate used here: stay on built-in memory until every trigger condition holds, then run a small pilot.

It pairs with the [memory write gate](memory-method.md), which decides what goes into `MEMORY.md` in the first place.

## Hot, warm, cold

| Tier | What | Loaded | Cost |
| --- | --- | --- | --- |
| Hot | `SOUL.md`, `USER.md`, `MEMORY.md` | every turn | tokens on every turn, hard char limit |
| Warm | an external provider's recalled scenes or profile | every turn, only what matches | a sidecar process, an LLM key, recall errors |
| Cold | session history via `session_search` (SQLite FTS5), skills, specs | on demand | nothing until used; history is unbounded |

Hot memory holds stable rules and long-term facts only. Past events and process live in cold storage. Steps live in skills. A warm tier is an optional add-on for recall that the cold tier cannot give. It is not an emergency fix for a full hot layer.

## Why not just raise the char limit

A full `MEMORY.md` usually means weak write discipline: duplicate entries, cron status, one-off findings. Raising `memory.memory_char_limit` makes the bin bigger and fills it with the same things, and every extra character is paid on every turn. Compress first with the [write gate](memory-method.md). If it is still tight after that, raising the limit can be discussed again.

It also helps to check what "not enough memory" means. The model's context window, the hot-layer char limit, and session history are three different sizes. Session history is already unbounded.

## Trigger conditions

Start a pilot only when **all** of these hold. If any one is missing, stay deferred.

1. `MEMORY.md` has stayed under **60%** of its limit for at least **two weeks**, without adding entries just to survive.
2. There is a **reproducible** pain point: the owner has to re-explain the same scene or decision across sessions, and `session_search` plus skills do not solve it.
3. The owner explicitly accepts the operating cost: a sidecar process, provider API keys, recall mistakes, and debugging.
4. A success measure is chosen before the pilot, for example "five DM conversations of type X in a row without re-explaining the background".

## Pilot rules

| Item | Rule |
| --- | --- |
| Install path | Attach the provider to the existing Hermes install, following the provider's current Hermes docs. Do not reinstall Hermes for it. |
| Relationship to built-in memory | Additive. Hermes providers do not replace `MEMORY.md`. |
| No double writes | Hot memory keeps the hard rules. The provider keeps scenes. The same fact is never written to both. |
| Scope | Start with the owner's DM only. Do not turn on automatic recall in group chats until identity isolation is proven. |
| Secrets | Provider keys go in `~/.hermes/.env` or the provider's own directory, never echoed into chat. |
| Rollback | Turn the provider off (`hermes memory off` or clear `memory.provider`) and stop its sidecar. The hot layer is untouched. |
| Verification | `hermes memory status`, one real cross-session recall test, and logs checked for leaked keys. |

## Target shape (if the pilot passes)

```text
Every turn:
  MEMORY.md / USER.md / SOUL.md       hot: hard rules, short
  + provider prefetch for this turn   warm: matching scenes / profile
  + session_search, provider search   cold: dig on demand

Writes:
  stable preference, safety rule  -> USER.md / MEMORY.md / SOUL.md
  conversation scenes             -> the provider (it maintains them)
  steps and commands              -> a skill
  cron or one-off state           -> a state file outside memory
```

## Alternatives rejected

| Option | Why not |
| --- | --- |
| Adopt a provider now | Adds operations without proof of a recall gap |
| Only raise the char limit | Makes the bin bigger; keep it as a later option after compressing |
| Replace built-in memory with the provider | Hermes providers are additive by design; hard rules still need stable hot injection |
| Reuse tool names from another host's integration | Tool names differ per host; use the provider's Hermes docs |

## References

- Hermes [Persistent Memory](https://github.com/NousResearch/hermes-agent/blob/main/website/docs/user-guide/features/memory.md)
- Hermes [Memory Providers](https://github.com/NousResearch/hermes-agent/blob/main/website/docs/user-guide/features/memory-providers.md)
- [Memory write gate](memory-method.md)
