English | [简体中文](install.zh-CN.md)

# Install

This page lists every way to use hermes-kit, per host. The commands come from the Hermes CLI (`hermes plugins --help`, `hermes skills --help`) at upstream `v2026.9.21`.

## Hermes: plugins

Plugins live in `plugins/<name>/` and install from this monorepo by subdirectory.

```bash
hermes plugins install Adonis0123/hermes-kit/plugins/hermes-lock-screen
hermes plugins enable hermes-lock-screen
```

- `--enable` enables the plugin right after install and skips the prompt. `--no-enable` installs it disabled.
- `hermes plugins list` shows what is installed and enabled.
- Restart the gateway after enabling a plugin so a running gateway loads it (for example `/restart` from chat).

### Pin to a commit

Pass a full 40-character commit SHA to install exactly that tree:

```bash
hermes plugins install Adonis0123/hermes-kit/plugins/hermes-lock-screen --ref <40-char-sha>
```

A pinned plugin does not move on `hermes plugins update`. To move it, reinstall with `--force --ref <new-sha>`.

### Update, disable, uninstall

```bash
hermes plugins update hermes-lock-screen    # re-clones the recorded source for subdirectory installs
hermes plugins disable hermes-lock-screen   # keep files, stop loading
hermes plugins remove hermes-lock-screen    # aliases: rm, uninstall
```

## Hermes: skills

The Hermes skill tap scans `skills/<name>/SKILL.md` one level deep. That is why skills here are flat, without category folders.

### Add the whole repo as a tap

```bash
hermes skills tap add Adonis0123/hermes-kit
hermes skills search cursor          # skills from the tap show up in search
hermes skills install <name>
```

List or remove taps with `hermes skills tap list` and `hermes skills tap remove <name>`.

### Install one skill directly

```bash
hermes skills install Adonis0123/hermes-kit/skills/cursor-cli
```

`--category <folder>` puts the skill in a category folder under your skills directory.

### Update and uninstall

```bash
hermes skills check                  # which hub-installed skills have updates
hermes skills update
hermes skills uninstall cursor-cli
```

## Claude Code

The repo root has a [`.claude-plugin/marketplace.json`](../.claude-plugin/marketplace.json) that exposes every skill in `skills/` as one plugin.

```text
/plugin marketplace add Adonis0123/hermes-kit
/plugin install hermes-kit@hermes-kit
```

Update with `/plugin marketplace update hermes-kit`. Remove with `/plugin uninstall hermes-kit@hermes-kit`.

Several skills here assume a Hermes runtime (gateway, Feishu, `hermes` CLI). They load in Claude Code, but only the host-neutral ones (for example `convert-documents-to-markdown`) are useful there.

## Codex, Cursor, and other agents

Use the [skills CLI](https://github.com/vercel-labs/skills):

```bash
npx skills add adonis0123/hermes-kit --list            # list skills in this repo
npx skills add adonis0123/hermes-kit --skill cursor-cli
```

## The patched Hermes fork

The fork is not a plugin. It replaces your Hermes install. See [hermes-fork.md](hermes-fork.md).

## Local specifics in skills

Some skills say "if `references/local-*.md` exists, read it". Those files are not published. Create your own `references/local-<topic>.md` inside the installed skill to add your IDs, paths, or team rules without editing `SKILL.md`. An update may replace the skill folder, so keep a copy of your `local-*` files outside it.
