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
- **脚本输出 `verdict=DOWNGRADE`** → 也当无更新，最终回复为空。这个 tag 的内容比本机基线旧，升上去等于降级，不报、不建议升。
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

`behind_by` 才是正式版多出来的提交数。fork 的 `main` 天然领先 upstream，`ahead_by` 会把插件目录和 overlay 一起算进来，不能当成要重放的跨度。只用 `.commits[-<behind_by>:]` 取正式版那一头；要判断会不会撞上 overlay，再对这几个提交单独查 `commits/<sha>` 的文件列表，不要用 compare 返回的 `files`（那里是空的）。

**跨度反了就停，改从正式版往回看**：`compare/<本机 sha>...<正式 tag>` 里 `ahead_by` 远大于 `behind_by`，说明本机基线比正式版旧很多，不是正式版只多了几十个提交。这时禁止用 `.commits[-<behind_by>:]` 当跨度，改跑 `git fetch <upstream url> tag <TAG>` 再 `git rev-list --count HEAD..<TAG>`。这个数上千也照样用 `hermes-fork-upgrade.sh prepare`，不要手搬。

**祖先关系不等于内容更新（硬·2026-10-17）**：`is-ancestor` 说「落后」不够，还要看内容。定时脚本 `===UPGRADE_SAFETY===` 段已经算好：`verdict=OK` 才算真有更新；`DOWNGRADE` 按静默规则处理；`UNKNOWN` 时手动跑 `git diff --shortstat origin/upstream-main "$TAG^{commit}"`，删除超过 2 万行且超过新增的两倍，就按降级处理。课例：v0.22.2 的发布提交把 v0.22.1 当父提交，内容却是更旧的 `release/0.22.1`。合进 `main` 后删了约 18.6 万行，网关的降级保护让网关停了约 30 小时。

**提交数对不上就不写数字（硬·2026-10-12）**：浅克隆 `rev-list`、compare 的 250 条上限、笔记里的旧跨度，都不是这次的提交数。对不上就写「提交数还没核对」，禁止写「约 2100 个」这类大数。课例 2026-10-11 09:31：把补丁版写成自 v0.21.5 起约 2100 个合并 PR。

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

**只用脚本，不手搬（硬·2026-10-23）**。本机入口是 fork 升级脚本 `hermes-fork-upgrade.sh`（路径见 `references/local-upgrade.md`），没有这个脚本时按 `references/fork-rebase-flow.md` 手做同样几步。课例：10-14、10-16、10-23 三次都是 agent 临场决定搬哪些补丁，每次都丢了飞书叠层。10-23 那次用 `git archive` 加孤儿提交、`reset --hard` 覆盖活仓，没跑闸门就报「已升到」。

```bash
S=<path-to>/hermes-fork-upgrade.sh   # 本机路径见 references/local-upgrade.md
$S check            # 只读：基点、目标正式版、内容是否倒退
$S prepare [TAG]    # 独立 worktree 里 rebase --onto TAG（--empty=stop --reapply-cherry-picks），成功后自动 verify
$S continue         # 冲突只在脚本打印的 worktree 里解决，git add 后跑这条
$S verify           # range-diff 核补丁数 + 叠层清单 + 闸门测试（worktree）
$S switch           # 打 tag、推 fork、活仓 hermes update 跟上、活仓完整闸门；红了自动回滚活仓和 fork
$S status | abort
```

- 每次停下，stderr 最后一行是 `UPGRADE_STOP=<步骤>`，照它前面的中文说明处理；成功是 `UPGRADE_OK=<步骤>`。
- 补丁真被上游吸收、提交变空：`git -C <worktree> rebase --skip`，并在 worktree 的 `PATCHES.md` 同一行写短 sha 和「已被上游吸收」。叠层清单 `hermes-overlay-manifest.tsv`（与升级脚本同目录）由 owner 改，agent 改不了。
- **冲突两边都要留时，先核对接线点再删 import**：上游新增的符号和本地替代实现同时出现，两边拼接，不要留一边丢一边。改 import 前先搜该符号在同一文件的调用点：只在冲突标记里出现、没有调用的丢掉；冲突区外还在用的保留。删掉正在用的 import 会让 rebase 继续走，但文件编译不过。
- `switch` 会自动推送（owner 2026-10-23 定）：只在 verify 绿之后推，`--force-with-lease` 对准开始时的 fork main；活仓闸门红了就把 fork main 推回去。
- **已有升级锁，后一条不再开一路（硬·2026-10-24）**：`~/.cache/hermes-upgrade/lock` 在，或已有 `hermes-fork-upgrade.sh` 在跑 → 只报「正在升到哪一版、停在哪一步」，不要再跑 check / prepare。课例 2026-10-23：09:33「升级吧」和 10:38「升级一下 hermers」各开一路，11:03 撞上同一把锁。
- **先对锁再说话（硬）**：用户说「重跑 check / prepare」时，先看 lock 和进程。锁还在、另一路已过 verify 并在 switch → 拒绝重跑并说明原因；重跑会打断正在换活仓的那一步。
- 换完只报脚本最后的结论，并请 owner `/restart`。

## 硬规则

- 活仓 `~/.hermes/hermes-agent` 对 agent 只读，由三层强制：Hermes `hooks.pre_tool_call` 守卫（`hermes-live-repo-guard.py`，`fail_closed`，路径见 `references/local-upgrade.md`）拦下 Hermes agent 的写命令；活仓 `reference-transaction` 钩子拒绝把 `main` 指到缺叠层的提交（对所有 agent 生效）；`post-checkout` / `post-rewrite` 发现文件缺叠层就私聊 owner。被拦时不要找绕法，改走上面的脚本。
- 换完代码，只有贴出 `hermes-fork-upgrade.sh switch` 的 `UPGRADE_OK=switch`（其中含闸门最后一行 `升级闸门通过。`），才能说「已升到 vX」。

- 会话内不跑 `hermes gateway restart`；请用户在聊天里发 `/restart`（只写在终态正文）。核验命令里别出现 restart 字样，lifecycle guard 会整段拦。
- 在 `/tmp/...` clone 里跑过的 `hermes --version` 会把 Install directory 指到 tmp，不能当活仓证据。
- 不要把 APFS 大小写碰撞改脏的 `contributors/emails/` 文件提交进 overlay。

## cron 注意

- `script` 字段是 `~/.hermes/scripts/` 下的**相对文件名**，不是内联源码（塞整段 bash → `Errno 63 File name too long`；绝对路径 / `~` 会被拒）。
- 报 `Skipped to prevent unintended spend: global inference config drifted` = 全局模型已换、任务记录的 provider/model 不一致，**不是脚本失败**。确认是 owner 批准的切换后：`hermes cron edit <job_id> --provider <p> --model <m>`，`cronjob action=list` 回读，`cronjob action=run job_id=<job_id>` 验证 `last_status=ok`。不要手改 `jobs.json`。
- 昨日复盘任务 → `hermes-daily-review`。
