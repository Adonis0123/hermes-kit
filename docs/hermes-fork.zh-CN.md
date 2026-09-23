[English](hermes-fork.md) | 简体中文

# 打过补丁的 Hermes fork

[Adonis0123/hermes-agent](https://github.com/Adonis0123/hermes-agent) 是 [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent) 的 fork，内容是上游加一小组 overlay（叠加补丁），主要面向飞书。每个补丁对用户的影响见 [feishu-customizations.zh-CN.md](feishu-customizations.zh-CN.md)。

## 分支和标签

| 引用 | 含义 |
| --- | --- |
| `main` | 上游发版加 overlay。安装用这个。 |
| `upstream-main` | 当前 overlay 所基于的上游提交，不含 overlay，每次同步时向前移动。 |
| `vYYYY.M.D-adonis.N` | 每次同步打一个标签，例如 `v2026.9.21-adonis.1` 表示在上游 `v2026.9.21` 上叠的第 1 版 overlay。 |

每次上游发版，overlay 用 rebase 重新叠到最新上游之上，然后 force-push `main`。原因见 [ADR 0002](adr/0002-fork-overlay-via-rebase.zh-CN.md)。维护者按 `PATCHES.zh-CN.md` 的“同步流程”操作，其中 `origin` = 本 fork，`upstream` = NousResearch。

每个补丁的目的、涉及文件、能否回馈上游，都列在 fork 根目录的 [`PATCHES.zh-CN.md`](https://github.com/Adonis0123/hermes-agent/blob/main/PATCHES.zh-CN.md)。

## 适合谁

如果你把 Hermes 当飞书群机器人用，并且想要下面这些效果，就用 fork：

- 少打扰：`@所有人` 不算提及，表情回应默认不转给 agent；
- 回复进话题，话题内的追问不用再 @ 也会回答；
- 每个回答一张 CardKit 流式卡片，不再拆成多个气泡。

不用飞书就留在上游。除了 `/new` 提示语选项，overlay 对其他平台没有增加功能。

## 全新安装

> UNVERIFIED：这条路径依据安装脚本源码整理，尚未在干净机器上完整跑过。

官方安装脚本会 clone 上游。但如果 `$HERMES_HOME/hermes-agent`（默认 `~/.hermes/hermes-agent`）已经有 checkout，脚本会保留它，并从它自己的 `origin` 原地更新。所以先把 fork clone 到这里，再从 checkout 里运行安装脚本：

```bash
git clone -b main https://github.com/Adonis0123/hermes-agent ~/.hermes/hermes-agent
bash ~/.hermes/hermes-agent/scripts/install.sh
```

`--skip-setup`、`--skip-browser`、`--hermes-home <path>` 等选项和上游一致。不要用 `--dir` 指向别的路径，否则脚本会在那里 clone 上游。

## 把现有安装切到 fork

> UNVERIFIED：依据 `hermes update` 处理被改写的 `origin/main` 的逻辑推断。

```bash
git -C ~/.hermes/hermes-agent remote set-url origin https://github.com/Adonis0123/hermes-agent.git
hermes update
```

fork 的 `main` 无法从上游 `main` fast-forward（快进）。`hermes update` 会先 stash 本地改动，把 checkout 重置到 `origin/main`，再重装依赖、重启网关。

## `hermes update` 怎样跟随 fork

- 它拉取 `origin/main`，能快进就快进。
- fork rebase 并 force-push 后，快进会失败。同一分支上，`hermes update` 会先 stash 本地改动，再重置到 `origin/main`。
- 因为 `origin` 不是官方仓库，`hermes update` 可能提示添加 `upstream` remote。之后它发现 fork 有上游没有的提交，就跳过上游同步。这是预期行为。
- 不要执行它建议的 `git pull upstream main`。那会把上游合并进你的 checkout，让你停在一条 fork 永远不会有的历史上。

## 切回上游

```bash
git -C ~/.hermes/hermes-agent remote set-url origin https://github.com/NousResearch/hermes-agent.git
hermes update
```

走的是同一条重置路径。fork 专用的配置项（见 [feishu-customizations.zh-CN.md](feishu-customizations.zh-CN.md)）会留在 `config.yaml` 和 `.env` 里。上游代码不读它们，想要干净配置就手动删掉。

## 报告问题

只在 fork 上出现的 bug，请到 [Adonis0123/hermes-agent](https://github.com/Adonis0123/hermes-agent/issues) 提 issue，附上 `git -C ~/.hermes/hermes-agent describe --tags` 的输出。上游也能复现的，请报给 [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent/issues)。
