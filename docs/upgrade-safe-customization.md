English | [简体中文](upgrade-safe-customization.zh-CN.md)

# Customizing Hermes so upgrades don't undo it

`hermes update` and upstream rebases replace the Hermes checkout. Anything you put inside it can disappear silently. This page lists what survives, where each kind of customization belongs, and how to prove after an upgrade that nothing was lost.

The fork side of this is covered by [ADR 0002](adr/0002-fork-overlay-via-rebase.md) and [the Hermes fork](hermes-fork.md).

## What survives an upgrade

| Replaced on upgrade | Kept |
| --- | --- |
| The checkout `~/.hermes/hermes-agent/**`, including its bundled `skills/` and `plugins/` | `~/.hermes/skills/` (your skills) |
| Local edits in the checkout (`hermes update` stashes them and resets to `origin/main` when fast-forward fails) | `~/.hermes/plugins/` (your plugins) |
| A skill installed by a skills CLI with a global flag, when another install has the same name | `~/.hermes/memories/`, `SOUL.md`, `AGENTS.md`, `config.yaml`, `.env` |
| | Your own notes and specs under `~/.hermes/` |
| | Anything you back up in your own git repo |

Bundled skills are synced from the checkout into `~/.hermes/skills/`. A bundled skill you edited is left alone, but one you did not edit is updated to the new version. Give your own skills names that do not collide with bundled ones.

## Where each customization belongs

| Customization | Home | Not here |
| --- | --- | --- |
| A procedure: steps, commands, pitfalls | a skill in `~/.hermes/skills/<name>/` | the Hermes checkout; memory |
| A routing preference ("for long prose, use skill X") | one line in `USER.md` or a pointer in `MEMORY.md` | copied steps in memory |
| A behavior change in Hermes code | a plugin in `~/.hermes/plugins/`, or an overlay commit on your fork | uncommitted edits in the checkout |
| Settings | `config.yaml`, `.env` | hard-coded in source |
| Decisions and why | a spec or ADR in your notes | memory |

The hot-memory line is only a pointer. The skill holds the procedure. See the [memory write gate](memory-method.md).

## Example: a writing route

The [`writing-with-cursor`](../skills/writing-with-cursor/) and [`cursor-cli`](../skills/cursor-cli/) skills route long prose through another tool.

- Policy and adapter live in `~/.hermes/skills/`, never in `~/.hermes/hermes-agent/skills/`.
- `USER.md` has one preference line. `MEMORY.md` has the skill name only, no steps. `AGENTS.md` does not repeat the route.
- A version floor, if any, lives in one place: the script that picks the model. Text says "the latest model of family X", not a version number.

## Overlay tests as the gate

After every `hermes update` or fork rebase, run a small set of local tests that assert your customizations are still wired up. For example:

- the skill directory exists under `~/.hermes/skills/` and its `SKILL.md` names the expected skill;
- the pointer line is still present in `USER.md` or `MEMORY.md`;
- plugins you rely on are still enabled;
- fork-only behavior still works (for Feishu, the [black-box checklist](feishu-gateway-blackbox-checklist.md)).

Keep these tests in your own repo, outside the checkout. A red test means the customization is gone: do not report the upgrade as complete until it is green again.

```bash
python3 ~/.hermes/tests/test_<customization>_overlay.py   # your own test, kept outside the checkout
```

## Checklist before customizing

1. Can it be a skill, a plugin, or a config value? Then do that.
2. Does it really need a core code change? Then make it an overlay commit on a fork, document it in `PATCHES.md`, and prefer seams upstream already offers. See [ADR 0002](adr/0002-fork-overlay-via-rebase.md).
3. Is there a test that fails if the upgrade removes it? If not, write one.
