English | [简体中文](hermes-fork.zh-CN.md)

# The patched Hermes fork

[Adonis0123/hermes-agent](https://github.com/Adonis0123/hermes-agent) is a fork of [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent). It is upstream plus a small overlay of patches, mostly for Feishu. The patches are described for users in [feishu-customizations.md](feishu-customizations.md).

## Branches and tags

| Ref | Meaning |
| --- | --- |
| `main` | Upstream release plus the overlay. This is what you install. |
| `upstream-main` | The upstream commit the current overlay is based on, no overlay. It moves forward at each sync. |
| `vYYYY.M.D-adonis.N` | One tag per sync, for example `v2026.9.21-adonis.1` = overlay number 1 on upstream `v2026.9.21`. |

On each upstream release the overlay is re-applied on top by rebase, and `main` is force-pushed. See [ADR 0002](adr/0002-fork-overlay-via-rebase.md) for why. The maintainer runs the "Sync procedure" in `PATCHES.md`, with `origin` = this fork and `upstream` = NousResearch.

Each patch (purpose, files, whether it could go upstream) is listed in [`PATCHES.md`](https://github.com/Adonis0123/hermes-agent/blob/main/PATCHES.md) at the fork root.

## Who should use it

Use the fork if you run Hermes as a Feishu bot in group chats and want:

- fewer replies: `@all` does not count as a mention, and emoji reactions are not routed to the agent by default;
- replies in a topic thread, with follow-ups in that thread answered without a new mention;
- one CardKit streaming card per answer instead of several bubbles.

Stay on upstream if you do not use Feishu. The overlay adds nothing for other platforms except the `/new` tip option.

## Install fresh

> UNVERIFIED: this path follows the installer's source code but has not been run end to end on a clean machine.

The official installer clones upstream. It also keeps an existing checkout at `$HERMES_HOME/hermes-agent` (default `~/.hermes/hermes-agent`) and updates it in place from its own `origin`. So clone the fork there first, then run the installer from the checkout:

```bash
git clone -b main https://github.com/Adonis0123/hermes-agent ~/.hermes/hermes-agent
bash ~/.hermes/hermes-agent/scripts/install.sh
```

Installer options such as `--skip-setup`, `--skip-browser`, and `--hermes-home <path>` work as upstream. Do not pass `--dir` to a different path, or the installer will clone upstream there instead.

## Switch an existing install to the fork

> UNVERIFIED: based on how `hermes update` handles a rewritten `origin/main`.

```bash
git -C ~/.hermes/hermes-agent remote set-url origin https://github.com/Adonis0123/hermes-agent.git
hermes update
```

The fork's `main` does not fast-forward from upstream `main`. `hermes update` stashes local changes and resets the checkout to `origin/main`, then reinstalls dependencies and restarts gateways.

## How `hermes update` follows the fork

- It fetches `origin/main` and fast-forwards when it can.
- After a rebase and force-push on the fork, fast-forward fails. On the same branch `hermes update` then resets to `origin/main`, after stashing your local changes.
- Because `origin` is not the official repo, `hermes update` may offer to add an `upstream` remote. It then sees that the fork has commits upstream lacks and skips the upstream sync. That is expected.
- Do not run the `git pull upstream main` it suggests. That merges upstream into your checkout and leaves you on a history the fork will never have.

## Switch back to upstream

```bash
git -C ~/.hermes/hermes-agent remote set-url origin https://github.com/NousResearch/hermes-agent.git
hermes update
```

The same reset path applies. Fork-only config keys (see [feishu-customizations.md](feishu-customizations.md)) stay in your `config.yaml` and `.env`. Upstream code does not read them, so remove them if you want a clean config.

## Report a problem

If a bug only happens on the fork, open an issue on [Adonis0123/hermes-agent](https://github.com/Adonis0123/hermes-agent/issues) and include the tag from `git -C ~/.hermes/hermes-agent describe --tags`. If it also happens on upstream, report it to [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent/issues).
