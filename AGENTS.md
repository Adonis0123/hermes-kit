# AGENTS.md

Guide for AI coding agents working with or installing from hermes-kit.

## What this repo is

Hermes Agent plugins, Hermes-oriented skills, and docs (patched Hermes fork, Feishu customizations, memory method). Human overview: [README.md](README.md).

## Install per host

| Host | Install | Update | Remove |
| --- | --- | --- | --- |
| Hermes, plugin | `hermes plugins install Adonis0123/hermes-kit/plugins/<name>` then `hermes plugins enable <name>` | `hermes plugins update <name>` | `hermes plugins remove <name>` |
| Hermes, plugin pinned | `hermes plugins install Adonis0123/hermes-kit/plugins/<name> --ref <40-char-sha>` | reinstall with `--force --ref <sha>` | `hermes plugins remove <name>` |
| Hermes, all skills (tap) | `hermes skills tap add Adonis0123/hermes-kit` then `hermes skills install <name>` | `hermes skills update` | `hermes skills tap remove <tap>` |
| Hermes, one skill | `hermes skills install Adonis0123/hermes-kit/skills/<name>` | `hermes skills update` | `hermes skills uninstall <name>` |
| Claude Code | `/plugin marketplace add Adonis0123/hermes-kit` then `/plugin install hermes-kit@hermes-kit` | `/plugin marketplace update hermes-kit` | `/plugin uninstall hermes-kit@hermes-kit` |
| Codex, Cursor, others | `npx skills add adonis0123/hermes-kit --skill <name>` (`--list` to list) | rerun the add command | remove the skill folder |
| Patched Hermes fork | see [docs/hermes-fork.md](docs/hermes-fork.md) | `hermes update` | see the same doc |

Details: [docs/install.md](docs/install.md).

## Layout

```text
.
├── plugins/<name>/          GENERATED. Hermes plugins: plugin.yaml + __init__.py with register(ctx)
├── skills/<name>/SKILL.md   GENERATED. Flat, one level deep (the Hermes tap only scans that)
├── docs/                    Hand-written docs, English + .zh-CN.md pairs
│   ├── adr/                 Architecture decision records
│   ├── assets/              README diagrams (light/dark, en/zh)
│   ├── templates/           Fictional MEMORY/USER/SOUL examples
│   └── <guide>.md           GENERATED guides (listed in .export-manifest.json)
├── .claude-plugin/marketplace.json
├── .gitleaks.toml           Generic privacy rules for CI (no personal words)
├── .privacy-allow           Known false positives for the pre-export scan
├── scripts/check-doc-pairs.mjs
├── CONTEXT.md               Glossary (EN + 中文 in one file)
├── AGENTS.md / CLAUDE.md / llms.txt
└── LICENSE
```

## Generated content: do not hand-edit

`skills/` and `plugins/` are produced by an export script from a private source repo (see [ADR 0001](docs/adr/0001-private-source-allowlist-export.md)). Each export replaces them in one commit. Edits made here directly are lost on the next export.

To change a skill or plugin: open an issue or a PR against this repo. The maintainer applies the change in the source and re-exports.

The guides under `docs/` that appear in `.export-manifest.json` are generated the same way. All other docs, CI, and root files are hand-written and can be edited here.

## Naming rules

- Skill directory name = `name` in `SKILL.md` frontmatter: lowercase `a-z0-9-`, at most 64 characters.
- `SKILL.md` frontmatter: `name`, `description` (at most 1024 characters), optional `license: MIT`.
- Plugin directory name = `name` in `plugin.yaml`. `plugin.yaml` has `name`, `version`, `description`.
- A skill may say "if `references/local-*.md` exists, read it". `local-*` files are never published; users create their own.
- No personal or company data in any file: no real chat or user IDs, emails, hostnames, home-directory paths, or people's names.

## Bilingual docs

- English is authoritative. Every `README.md` and `docs/**/*.md` has a `.zh-CN.md` pair next to it.
- First line of each: `English | [简体中文](x.zh-CN.md)` or `[English](x.md) | 简体中文`.
- Exempt: `AGENTS.md`, `CLAUDE.md`, `CONTEXT.md` (bilingual in one file), `llms.txt`, `LICENSE`, `docs/templates/`, `skills/`, `plugins/`.
- When you change an English page, update its pair in the same change.

## Validation

```bash
node scripts/check-doc-pairs.mjs                         # every doc has its .zh-CN.md pair
python3 -m json.tool .claude-plugin/marketplace.json     # marketplace JSON is valid
gitleaks detect --source . --config .gitleaks.toml       # privacy scan, same as CI
hermes plugins doctor plugins/<name>                     # plugin contract check (needs Hermes)
```

CI runs the pair check ([docs-pair-check.yml](.github/workflows/docs-pair-check.yml)) and gitleaks ([privacy-scan.yml](.github/workflows/privacy-scan.yml)) on every push and PR.

## Docs index

| Doc | Kind | Topic |
| --- | --- | --- |
| [docs/install.md](docs/install.md) | hand-written | Install paths per host, pinning, updating |
| [docs/hermes-fork.md](docs/hermes-fork.md) | hand-written | The patched fork and how `hermes update` follows it |
| [docs/feishu-customizations.md](docs/feishu-customizations.md) | hand-written | Behavior and config keys of each fork patch |
| [docs/memory-method.md](docs/memory-method.md) | hand-written | Write gate for `MEMORY.md`, `USER.md`, `SOUL.md` |
| [docs/memory-provider-adoption-gate.md](docs/memory-provider-adoption-gate.md) | generated | When to adopt an external memory provider |
| [docs/feishu-gateway-blackbox-checklist.md](docs/feishu-gateway-blackbox-checklist.md) | generated | Six manual Feishu checks with message-id evidence |
| [docs/feishu-quiet-group-delivery.md](docs/feishu-quiet-group-delivery.md) | generated | Quiet group delivery: topics, cards, noise controls |
| [docs/hermes-lock-screen-design.md](docs/hermes-lock-screen-design.md) | generated | Design of the `hermes-lock-screen` plugin |
| [docs/cron-digest-pipeline-pattern.md](docs/cron-digest-pipeline-pattern.md) | generated | Daily digest from a cron job |
| [docs/upgrade-safe-customization.md](docs/upgrade-safe-customization.md) | generated | Customizing Hermes so upgrades don't undo it |
| [docs/adr/](docs/adr/) | hand-written | Architecture decision records |
| [CONTEXT.md](CONTEXT.md) | hand-written | Glossary |
