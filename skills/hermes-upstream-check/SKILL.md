---
name: hermes-upstream-check
description: "Use when checking Hermes Agent upstream for updates or rebasing a patched Hermes fork onto a new upstream release."
license: MIT
metadata:
  author: Adonis0123
  version: "2.0.0"
---

# Hermes 上游更新检查 + 打补丁 fork 的升级

适用于：Hermes 是 **git 安装**（默认 `~/.hermes/hermes-agent`），并且可能维护一个带本地补丁（overlay）的 fork。

本机细节：若 `references/local-*.md` 存在，先读它（真实 cron job id、本机 remote 现状、升级闸脚本、overlay 契约测试与冒烟步骤）。

## 名词

| 名词 | 含义 |
|------|------|
| upstream | 官方仓 `NousResearch/hermes-agent` |
| fork | 你的 fork；`main` = upstream 某个提交 + **线性 overlay**（每次升级用 rebase 重放） |
| `upstream-main` | fork 上指向当前 overlay 所基于的上游提交的分支，每次同步时向前移动，不放补丁 |
| overlay | fork `main` 相对 `upstream-main` 的几个补丁提交；在 fork 根目录 `PATCHES.md` / `PATCHES.zh-CN.md` 逐条记录（目的、文件、能否提给上游） |
| 同步 tag | `v<upstream-tag>-<fork-owner>.<n>`，例 `v2026.9.21-alice.1`；同一上游 tag 再次重放时 `n+1` |

## 触发

- 用户问 Hermes 有没有更新 / 值不值得更
- 定时「上游检查」
- 用户说「更新吧 / 升级吧」：默认 = **升 Hermes 本体**，不是只备份私有配置仓
- 准备执行 `hermes update` 或 rebase fork 前的只读评估

## 第 0 步：认 remote（不要假设名字）

remote 名字因机器而异（`origin` 可能是 upstream，也可能是 fork）。按 URL 认：

```bash
cd ~/.hermes/hermes-agent
UP=$(git remote -v | awk '$3=="(fetch)" && $2 ~ /[:\/]NousResearch\/hermes-agent(\.git)?$/ {print $1; exit}')
FORK=${FORK_REMOTE:-$(git remote -v | awk -v up="$UP" '$3=="(fetch)" && $1!=up && $2 ~ /github\.com[:\/][^\/]+\/hermes-agent(\.git)?$/ {print $1; exit}')}
ORIGIN_IS=$([ "$UP" = origin ] && echo upstream || { [ "$FORK" = origin ] && echo fork || echo other; })
echo "upstream=$UP fork=$FORK origin_is=$ORIGIN_IS"
```

`UP` 为空 → 先 `git remote add upstream https://github.com/NousResearch/hermes-agent.git`。临时 remote（指向 `/tmp/...` 的本地路径）不算 fork。

## 静默规则（定时任务）

- **无更新**（最新正式 Release tag 已是 HEAD 祖先）→ **最终回复为空**，不发「已是最新」。
- **有更新**才发中文短报：变更摘要 + 是否值得更 + 等 owner 决定。
- **禁止**自动升级 / 改配置 / 重启 gateway，除非 owner 明确说「更新」。
- **MEMORY 不是版本证据**：版本、落后多少、值不值得更，只认当场跑的 `hermes --version` / git / GitHub API。
- **终态再核一次 tag**：写卡片前再跑 `git merge-base --is-ancestor <stable_tag>^{} HEAD`。并行会话可能已升过；已含最新 tag 且 gateway 当日已重启 → 当无更新；代码齐但 gateway 没重启 → 只写「已齐，请 `/restart`」。
- 「落后 `main` tip」**不等于**落后正式版；fork 的 `main` 天然领先 upstream。正式版看最新非预发 Release tag 是否已是 HEAD 祖先。

## 检查步骤（必须真跑）

```bash
hermes --version
cd ~/.hermes/hermes-agent
git fetch "$UP" --tags --quiet
TAG=$(gh api repos/NousResearch/hermes-agent/releases --jq '[.[]|select(.prerelease==false and .draft==false)][0].tag_name')
git merge-base --is-ancestor "$TAG^{}" HEAD && echo "has $TAG" || echo "behind $TAG"
git log --oneline HEAD.."$TAG^{}" | head -40
```

`git fetch` 超时 / SSH 挂起：不要空等，改用 `gh api repos/NousResearch/hermes-agent/compare/<local-sha>...<tag>`（`ahead_by` / `behind_by` / commit 标题；约 250 条上限）。浅克隆里 `rev-list` 的 behind 数常是假大数，以 `merge-base --is-ancestor` 为准。归纳 `feat`/`fix`/`perf`，不编造 changelog。

## 有更新时的输出结构

1. **结论**：落后最新正式 tag；当前 `hermes --version` / hash vs tag
2. **更新了什么**：表/要点
3. **是否值得更新**：更新 / 观望 / 暂缓 + 理由
4. **风险**：跨度大、overlay 可能冲突的文件、gateway 需重启
5. **待你决定**：`更新` / `暂不`

## 什么时候可以直接 `hermes update`

`hermes update` 拉的是 `origin/<branch>`：能快进就快进；**不能快进时在同一分支上 `reset --hard origin/<branch>`**（未提交改动先 autostash）。它的 fork 同步只认名为 `upstream` 的 remote，fork 领先 upstream 时会**跳过**同步、保留 fork 提交。

| 情况 | `hermes update` |
|------|-----------------|
| `origin` = fork，overlay 已全部推到 fork `main`，本地 `main` 无未推提交 | **安全**：跟随 fork `main`；fork 被 force-push 后也会 reset 到新的 fork `main` |
| `origin` = fork，但本地 `main` 有未推到 fork 的提交 | **不安全**：reset 会丢掉它们；先推到 fork 或另开分支 |
| `origin` = upstream，工作树 / `main` 带本地 overlay | **不安全**：无法快进 → reset 到 upstream，overlay 丢失。走下方 fork 流程 |
| `origin` = upstream，无任何本地提交 | 安全（普通用户场景） |

检查未推提交：`git rev-list --count "$FORK/main..HEAD"` 必须为 0。autostash 恢复冲突时，工具会把仓库重置为干净新版并保留 `hermes-update-autostash-*`：先确认版本已升、stash 仍在，再逐文件解决，别把冲突提示当整单失败。

## fork 升级流程（owner 确认「更新」后）

细则与命令：`references/fork-rebase-flow.md`。概要：

1. **fetch**：`git fetch "$UP" --tags`、`git fetch "$FORK"`；选目标 = 最新正式 Release tag（或明确要跟的 upstream 提交）。
2. **记旧基点**：`OLD_BASE=$(git merge-base "$FORK/main" "$FORK/upstream-main")`（overlay 当前所在的 upstream 提交）。
3. **在独立 clone / worktree 里 rebase**，不在活仓里做：`git rebase --onto "$TAG^{}" "$OLD_BASE" <overlay-branch>`。
4. **`git range-diff "$OLD_BASE..$FORK/main" "$TAG^{}..HEAD"`**：每个补丁都要对得上；丢了、被上游吸收或意图变了都要说清。
5. **跑 overlay 契约测试**（`PATCHES.md` 列出）；整份测试文件绿**不够**——上游测试可能正好断言相反行为。
6. **更新 `PATCHES.md` + `PATCHES.zh-CN.md`**（补丁增删、被上游吸收的标注）。
7. **tag**：`git tag -a v<TAG>-<owner>.<n> -m "..."`。
8. **推送**：`upstream-main`（新基点）、`main`（`--force-with-lease=main:<旧 fork main sha>`）、tag。推完用 `gh api` 回读远端 `main` 与 tag。
9. **活仓跟上**：`origin` = fork → `hermes update`；否则按 `references/align-worktree-via-cron.md` 在会话闸外对齐。然后请用户 `/restart` gateway。
10. **核活仓**：只认活仓 `hermes_cli/__init__.py` 的 `__version__` + `git log -1`；gateway 进程启动时间要晚于切换时间。

## 硬规则

- 会话内不跑 `hermes gateway restart`；请用户在聊天里发 `/restart`（只写在终态正文）。核验命令里别出现 restart 字样，lifecycle guard 会整段拦。
- 在 `/tmp/...` clone 里跑过的 `hermes --version` 会把 Install directory 指到 tmp，不能当活仓证据。
- 不要把 APFS 大小写碰撞改脏的 `contributors/emails/` 文件提交进 overlay。

## cron 注意

- `script` 字段是 `~/.hermes/scripts/` 下的**相对文件名**，不是内联源码（塞整段 bash → `Errno 63 File name too long`；绝对路径 / `~` 会被拒）。
- 报 `Skipped to prevent unintended spend: global inference config drifted` = 全局模型已换、任务记录的 provider/model 不一致，**不是脚本失败**。确认是 owner 批准的切换后：`hermes cron edit <job_id> --provider <p> --model <m>`，`cronjob action=list` 回读，`cronjob action=run job_id=<job_id>` 验证 `last_status=ok`。不要手改 `jobs.json`。
- 昨日复盘任务 → `hermes-daily-review`。
