[English](0002-fork-overlay-via-rebase.md) | 简体中文

# ADR 0002：Hermes fork 保持 overlay 形态，用 rebase 重新叠加

- 状态：已采纳
- 日期：2026-09-23

## 背景

在用的 Hermes 安装在 [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent) 之上跑着几个补丁，主要是飞书行为（见 [feishu-customizations.zh-CN.md](../feishu-customizations.zh-CN.md)）。上游发版频繁，有些版本会重写同一批文件。这些补丁要公开在 [Adonis0123/hermes-agent](https://github.com/Adonis0123/hermes-agent)，方便别人使用，也方便单独向上游提交。

## 决定

- `upstream-main` 指向当前 overlay 所基于的上游提交，不做改动，每次同步时向前移动。
- `main` 是上游发版加一小串可读的 overlay 提交。
- 每次上游发版，把 overlay rebase 到新版本上，逐个提交解决冲突，跑测试，再 force-push `main`。
- 每次同步打一个标签，如 `v2026.9.21-adonis.1`，force-push 之后过去的状态仍可访问。
- fork 根目录的 `PATCHES.md` 和 `PATCHES.zh-CN.md` 说明每个补丁：目的、涉及文件、能否回馈上游。
- 补丁优先利用上游已有的扩展点（插件、CLI 注册、配置），少改核心文件。能挪进插件的补丁就挪进插件。

## 考虑过的方案

- **把上游 merge 进 `main`。** 不用 force-push，`git pull` 总能成功。但 overlay 会溶进合并提交里；几个版本之后没人说得清 fork 改了什么，要把某个补丁提给上游也得先理清历史。
- **安装时应用补丁文件（quilt 方式）。** 上游保持原样，但 Hermes 从 git checkout 安装和更新，用户需要一条定制的更新路径。
- **只做插件，不做 fork。** 能做到时优先这样，已经有补丁挪进了插件。其余改动涉及网关的流式循环，目前没有插件钩子。

## 影响

- 每次同步都会改写 `main` 的历史。`hermes update` 能处理：同一分支快进失败时，它先 stash 本地改动，再重置到 `origin/main`。在 fork 上叠自己提交的人也需要 rebase。
- overlay 补丁的提交 SHA 每次同步都会变。文档用 `PATCHES.md` 指向当前 SHA。
- overlay 保持小而可审，每个补丁都能作为单个提交提给上游。
- 同步按版本手工进行，打标签推送前先跑测试。
