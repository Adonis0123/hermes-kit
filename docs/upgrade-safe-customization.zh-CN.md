[English](upgrade-safe-customization.md) | 简体中文

# 让 Hermes 定制经得起升级

`hermes update` 和上游 rebase 会替换 Hermes 源码目录。放在里面的东西可能悄悄消失。本文列出哪些能保留、每类定制该放哪里，以及升级后怎样证明没丢东西。

fork 这一侧见 [ADR 0002](adr/0002-fork-overlay-via-rebase.zh-CN.md) 和 [Hermes fork](hermes-fork.zh-CN.md)。

## 升级后哪些还在

| 升级时会被替换 | 会保留 |
| --- | --- |
| 源码目录 `~/.hermes/hermes-agent/**`，包括其中自带的 `skills/` 和 `plugins/` | `~/.hermes/skills/`（你的 skill） |
| 源码目录里的本地改动（fast-forward 失败时，`hermes update` 会 stash 后重置到 `origin/main`） | `~/.hermes/plugins/`（你的插件） |
| 用 skills CLI 全局安装的 skill，被另一次同名安装覆盖 | `~/.hermes/memories/`、`SOUL.md`、`AGENTS.md`、`config.yaml`、`.env` |
| | 你放在 `~/.hermes/` 下的笔记和 spec |
| | 你自己 git 仓里备份的内容 |

自带 skill 会从源码目录同步到 `~/.hermes/skills/`。你改过的自带 skill 不会被覆盖，没改过的会更新到新版本。你自己的 skill 起名时不要和自带 skill 重名。

## 每类定制放哪里

| 定制 | 放这里 | 不要放 |
| --- | --- | --- |
| 规程：步骤、命令、坑 | `~/.hermes/skills/<name>/` 里的 skill | Hermes 源码目录；记忆 |
| 路由偏好（“长文走 skill X”） | `USER.md` 一行，或 `MEMORY.md` 里的指针 | 把步骤抄进记忆 |
| Hermes 代码的行为改动 | `~/.hermes/plugins/` 里的插件，或 fork 上的 overlay commit | 源码目录里未提交的改动 |
| 配置 | `config.yaml`、`.env` | 硬编码进源码 |
| 决策和理由 | 笔记里的 spec 或 ADR | 记忆 |

热层记忆那一行只是指针，规程在 skill 里。见 [记忆写入门槛](memory-method.zh-CN.md)。

## 例子：写作路由

[`writing-with-cursor`](../skills/writing-with-cursor/) 和 [`cursor-cli`](../skills/cursor-cli/) 这两个 skill 把长文写作交给另一个工具。

- 政策和适配器都放 `~/.hermes/skills/`，从不放 `~/.hermes/hermes-agent/skills/`。
- `USER.md` 只有一行偏好。`MEMORY.md` 只写 skill 名，不写步骤。`AGENTS.md` 不重复这条路由。
- 如果有版本下限，只写在一个地方：挑选模型的脚本里。文字里写“X 系列最新模型”，不写版本号。

## 用 overlay 测试做闸门

每次 `hermes update` 或 fork rebase 之后，跑一组本地测试，确认定制还接得上。例如：

- skill 目录还在 `~/.hermes/skills/` 下，`SKILL.md` 的名字正确；
- `USER.md` 或 `MEMORY.md` 里的指针行还在；
- 依赖的插件仍然启用；
- fork 独有的行为仍然正常（飞书用 [黑盒验收清单](feishu-gateway-blackbox-checklist.zh-CN.md)）。

这些测试放在你自己的仓库里，不放源码目录。测试红了就说明定制丢了：变绿之前，不要报告升级完成。

```bash
python3 ~/.hermes/tests/test_<customization>_overlay.py   # 你自己的测试，放在源码目录之外
```

## 动手定制前的检查

1. 能不能做成 skill、插件或配置项？能就这么做。
2. 真的需要改核心代码？那就做成 fork 上的 overlay commit，写进 `PATCHES.md`，并优先用上游已有的扩展点。见 [ADR 0002](adr/0002-fork-overlay-via-rebase.zh-CN.md)。
3. 有没有一个测试会在升级把它删掉时失败？没有就写一个。
