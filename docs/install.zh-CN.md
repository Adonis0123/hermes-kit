[English](install.md) | 简体中文

# 安装

本页按宿主列出 hermes-kit 的所有用法。命令取自上游 `v2026.9.21` 的 Hermes CLI（`hermes plugins --help`、`hermes skills --help`）。

## Hermes：插件

插件放在 `plugins/<name>/`，按子目录从本 monorepo 安装。

```bash
hermes plugins install Adonis0123/hermes-kit/plugins/hermes-lock-screen
hermes plugins enable hermes-lock-screen
```

- `--enable` 装完直接启用，不再询问；`--no-enable` 装成停用状态。
- `hermes plugins list` 查看已安装和已启用的插件。
- 启用后重启网关，正在运行的网关才会加载它（比如在聊天里发 `/restart`）。

### 锁定到某个提交

传入完整的 40 位 commit SHA，就只安装那一版：

```bash
hermes plugins install Adonis0123/hermes-kit/plugins/hermes-lock-screen --ref <40-char-sha>
```

锁定的插件不会随 `hermes plugins update` 变化。要换版本，用 `--force --ref <new-sha>` 重装。

### 更新、停用、卸载

```bash
hermes plugins update hermes-lock-screen    # 子目录安装会按记录的来源重新 clone
hermes plugins disable hermes-lock-screen   # 保留文件，不再加载
hermes plugins remove hermes-lock-screen    # 别名：rm、uninstall
```

## Hermes：技能

Hermes 的 skill tap（技能源）只扫描一层深的 `skills/<name>/SKILL.md`，所以这里的技能是平铺的，没有分类目录。

### 把整个仓库加为 tap

```bash
hermes skills tap add Adonis0123/hermes-kit
hermes skills search cursor          # tap 里的技能会出现在搜索结果里
hermes skills install <name>
```

用 `hermes skills tap list` 和 `hermes skills tap remove <name>` 查看或移除 tap。

### 直接安装单个技能

```bash
hermes skills install Adonis0123/hermes-kit/skills/cursor-cli
```

`--category <folder>` 把技能放进技能目录下的某个分类文件夹。

### 更新和卸载

```bash
hermes skills check                  # 查看哪些 hub 安装的技能有更新
hermes skills update
hermes skills uninstall cursor-cli
```

## Claude Code

仓库根目录有 [`.claude-plugin/marketplace.json`](../.claude-plugin/marketplace.json)，把 `skills/` 下的全部技能作为一个插件暴露出来。

```text
/plugin marketplace add Adonis0123/hermes-kit
/plugin install hermes-kit@hermes-kit
```

更新用 `/plugin marketplace update hermes-kit`，卸载用 `/plugin uninstall hermes-kit@hermes-kit`。

有几个技能默认运行在 Hermes 里（网关、飞书、`hermes` CLI）。它们在 Claude Code 里能加载，但只有与宿主无关的技能（比如 `convert-documents-to-markdown`）在那里有用。

## Codex、Cursor 和其他 agent

使用 [skills CLI](https://github.com/vercel-labs/skills)：

```bash
npx skills add adonis0123/hermes-kit --list            # 列出本仓库的技能
npx skills add adonis0123/hermes-kit --skill cursor-cli
```

## 打过补丁的 Hermes fork

fork 不是插件，它会替换你的 Hermes 安装。见 [hermes-fork.zh-CN.md](hermes-fork.zh-CN.md)。

## 技能里的本地细节

有些技能写着“如果 `references/local-*.md` 存在就读取”。这些文件不公开。你可以在已安装的技能里新建 `references/local-<topic>.md`，写入自己的 ID、路径或团队规则，不用改 `SKILL.md`。更新可能会替换整个技能目录，所以请在目录外保留一份 `local-*` 文件。
