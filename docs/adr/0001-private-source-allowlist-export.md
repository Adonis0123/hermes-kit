English | [简体中文](0001-private-source-allowlist-export.zh-CN.md)

# ADR 0001: Private source repos, published by allowlist export

- Status: Accepted
- Date: 2026-09-23

## Context

Skills, plugins, and memory notes are written and used every day in two private repos: a private config repo (Hermes-only skills, plugins, memory) and a private shared-skills repo (skills every agent uses). Those repos mix generic content with personal and company specifics: chat IDs, local paths, internal project names, colleagues' names.

Some of that work is useful to other people. Publishing it must not leak private data, now or through history, and must not create a second copy that drifts from the one actually in use.

## Decision

- The private repos stay the single source of truth. Public repos (`hermes-kit`, `adonis-skills`) are outputs.
- Content is sanitized in place, in one copy. Generic text stays in `SKILL.md`. Personal or company specifics move to `references/local-*.md` (or local config), and `SKILL.md` says "if `references/local-*.md` exists, read it". The private install keeps its behavior.
- An export script copies only allowlisted paths and always excludes `**/local-*`.
- Before writing, the export runs a privacy scan: gitleaks with generic rules, plus a personal denylist that exists only in the private repo.
- Each export is one new commit in the public repo. No private history is carried over.
- Public repos run the generic scan again in CI.
- Third-party skills are never copied. They are linked with install commands.

## Alternatives considered

- **`git filter-repo` on the private repo.** Rewrites history to drop paths, but every missed secret in any old commit becomes public. The allowlist also becomes a denylist in practice.
- **`git subtree split`.** Keeps history for a subdirectory, which carries the same leak risk and needs a clean directory boundary the private repos do not have.
- **Copybara.** Built for this job, with transforms and history mapping, but adds a Java toolchain and config for two small repos.
- **Public repo as the source, private overlay on top.** The cleanest for contributors, but daily edits happen in the private install. Every change would need a round trip, and private specifics would still need a place to live.

## Consequences

- Public `skills/` and `plugins/` are generated. Hand edits there are overwritten; contributors send issues or PRs, and changes are applied in the source.
- Public history is a list of export commits, not the real edit history.
- A new skill is published only after it is added to the allowlist and passes the scan.
- The personal denylist is never public, so public CI can only catch generic leaks. The private-side scan is the main gate.
