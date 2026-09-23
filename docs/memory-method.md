English | [简体中文](memory-method.zh-CN.md)

# A write gate for agent memory

Hermes injects `MEMORY.md` and `USER.md` into every turn. They are small on purpose: by default 2,200 and 1,375 characters (`memory.memory_char_limit`, `memory.user_char_limit`). Without a rule for what goes in, they fill up, get compressed in one big rewrite, and fill up again.

This page is the rule used here. It is a discipline for the agent and the person, not a code change. Hermes background: [Persistent Memory](https://github.com/NousResearch/hermes-agent/blob/main/website/docs/user-guide/features/memory.md) and [Personality & SOUL.md](https://github.com/NousResearch/hermes-agent/blob/main/website/docs/user-guide/features/personality.md).

## Where things live

| Layer | Loaded | Holds |
| --- | --- | --- |
| `SOUL.md` | every turn, first | Who the agent is, tone, hard rules |
| `USER.md` | every turn | Who the user is, long-term preferences, things never to do |
| `MEMORY.md` | every turn | Stable rules across sessions, short pointers to skills |
| Skills | when triggered | Steps, commands, pitfalls |
| Specs / decision docs | when read | Decisions, triggers, acceptance criteria |
| Cache or state files | by scripts | Runtime state: last run, one-off confirmations |
| Session history (`session_search`) | on demand | Everything that happened once |

The hot layers (`SOUL.md`, `USER.md`, `MEMORY.md`) cost tokens on every turn. Everything else costs nothing until used.

## The three questions

Before adding anything to `MEMORY.md`, answer all three. Any "no" means it does not go in.

1. **Will it still be true in three months?** A temporary finding, one PR, or today's status: no.
2. **Is there no better home?** Runnable steps belong in a skill. A decision belongs in a spec. "Who I am" belongs in `USER.md`.
3. **Must it be in front of the agent every turn?** If it is only looked up now and then, use a skill or `session_search`.

A one-line pointer is allowed: `MEMORY.md` can say "for X, use skill Y", and the details live in the skill.

## Where it goes instead

| This kind of content | Goes to |
| --- | --- |
| Identity, long-term preference, communication no-go | `USER.md` |
| Steps, commands, pitfalls | The matching skill (patch an existing one first) |
| Architecture decision, trigger condition, acceptance | A spec or ADR |
| Cron state, one-off confirmation | A cache or state file outside memory |
| One task, a PR number, what happened in a session | Nowhere (it is in session history) |

## Keeping it small

- Before adding, look for an entry to merge with and use `replace` instead of `add`.
- Above **60%** of the limit, compress first, then add.
- Aim to sit under **50%** day to day.
- Never paste a skill's body into memory.
- Entries are short headlines plus the name of the skill or spec that holds the detail. No walls of commands.

## Put the gate in memory itself

The gate only works if the agent sees it when deciding. Make it the first `MEMORY.md` entry, in one line:

```text
Write gate: before adding to MEMORY ask (1) true in 3 months? (2) better as skill/spec/USER? (3) needed every turn? Any no -> demote. Preference->USER, steps->skill, decision->spec, runtime state->cache, process->don't write. Over 60% full -> compress first.
```

See also: [When to adopt an external memory provider](memory-provider-adoption-gate.md) (hot, warm, and cold tiers, and why raising the char limit is not the fix).

## Templates

Structure and fictional examples only. Copy into `~/.hermes/` and rewrite.

- [`MEMORY.example.md`](templates/MEMORY.example.md)
- [`USER.example.md`](templates/USER.example.md)
- [`SOUL.example.md`](templates/SOUL.example.md)

Hermes separates memory entries with a line containing only `§`. The templates follow that format.
