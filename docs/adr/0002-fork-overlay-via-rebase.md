English | [简体中文](0002-fork-overlay-via-rebase.zh-CN.md)

# ADR 0002: Keep the Hermes fork as an overlay, re-applied by rebase

- Status: Accepted
- Date: 2026-09-23

## Context

The live Hermes install runs a handful of patches on top of [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent), mostly Feishu behavior (see [feishu-customizations.md](../feishu-customizations.md)). Upstream releases often, and some releases rewrite the same files. The patches need to be public at [Adonis0123/hermes-agent](https://github.com/Adonis0123/hermes-agent) so others can use them, and so each one can be proposed upstream on its own.

## Decision

- `upstream-main` points at the upstream commit the current overlay is based on, with no changes. It moves forward at each sync.
- `main` is the upstream release plus a short, readable stack of overlay commits.
- On each upstream release the overlay is rebased onto the new release, conflicts are resolved commit by commit, tests run, and `main` is force-pushed.
- Each sync gets a tag such as `v2026.9.21-adonis.1`, so any past state stays reachable after a force-push.
- `PATCHES.md` and `PATCHES.zh-CN.md` at the fork root describe each patch: purpose, files, and whether it could go upstream.
- Patches prefer seams upstream already offers (plugins, CLI registration, config) over edits to core files. When a patch can move into a plugin, it does.

## Alternatives considered

- **Merge upstream into `main`.** No force-push, and `git pull` always works. But the overlay dissolves into merge commits; after a few releases nobody can say what the fork changes, and extracting one patch for upstream means untangling history.
- **Patch files applied at install time (quilt style).** Keeps upstream pristine, but Hermes installs and updates from a git checkout, so users would need a custom update path.
- **A plugin only, no fork.** Preferred where possible, and some patches already moved there. Other changes touch the gateway stream loop, which has no plugin hook yet.

## Consequences

- `main` history is rewritten on every sync. `hermes update` handles this: when fast-forward fails on the same branch it resets to `origin/main` after stashing local changes. Anyone who builds on the fork with their own commits must rebase too.
- Commit SHAs of overlay patches change on every sync. Docs link to `PATCHES.md` for current SHAs.
- The overlay stays small and reviewable, and each patch can be offered upstream as one commit.
- Sync work is per release and happens by hand, with tests, before the tag is pushed.
