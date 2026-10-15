# fork 升级：rebase 线性 overlay

前提：fork `main` = upstream 某提交 + 几个线性 overlay 提交；`upstream-main` = 当前 overlay 所基于的 upstream 提交（每次同步向前移动）；补丁在 `PATCHES.md` / `PATCHES.zh-CN.md` 记录。`$UP` / `$FORK` 按 SKILL「第 0 步」从 URL 认出。

## 1. 独立工作目录

活仓（正在跑的 `~/.hermes/hermes-agent`）不做 rebase / reset / checkout：进程在跑，会话 lifecycle guard 也会拦。用独立 clone：

```bash
W=/tmp/hermes-rebase-<tag>
git clone --no-tags "$(git -C ~/.hermes/hermes-agent remote get-url "$FORK")" "$W"
cd "$W"
git remote rename origin fork
git remote add upstream https://github.com/NousResearch/hermes-agent.git
git fetch upstream main --tags
git fetch fork main upstream-main
```

活仓是浅克隆时不要 `clone --no-local` 活仓（常报 `Could not read <sha>`）；直接从 GitHub clone。macOS APFS 大小写不敏感，`contributors/emails/` 里只差大小写的文件会让工作树一直是脏的：用 `git checkout -f`，别把这些文件提交。

## 2. 选目标并 rebase

```bash
TAG=<latest-stable-tag>                      # gh api .../releases，prerelease=false && draft=false
NEW_BASE=$(git rev-parse "$TAG^{commit}")
OLD_BASE=$(git merge-base fork/main fork/upstream-main)
OLD_TIP=$(git rev-parse fork/main)
git switch -c overlay fork/main
git rebase --onto "$NEW_BASE" "$OLD_BASE" overlay
```

冲突处理原则：

- import 块、上游重构过的函数签名 → 以上游为准，再把补丁意图叠回去。
- 补丁本身的行为 → 保留补丁侧；两边都需要的逻辑（上游新增分支 + 补丁条件）合并成一个条件，不要二选一。
- 上游已经实现了补丁的效果 → 丢掉该补丁（`git rebase --skip` 前确认），并在 `PATCHES.md` 标「已被上游吸收」。
- 上游把补丁所在模块整个重写 → 按契约测试手工移植，不要硬解冲突。先读新版的调用点再搬行为：旧测试引用的导出名不再存在时，改测试去调现在的函数，不要把旧名字加回新模块。
- 补丁依赖的整段接法在新版里找不到（不是改了名，是文件里已经没有这类调用）→ 停在临时目录，不要 `reset` 活仓、不要把旧模块贴回新版。先告诉哪块定制接不上，等用户选「等下一版」还是「这块先放掉」。

## 3. range-diff

```bash
git range-diff "$OLD_BASE..$OLD_TIP" "$NEW_BASE..overlay"
```

每个旧补丁都要有对应的新补丁（`=` 相同，`!` 有改动要能解释）。只在左边出现 = 补丁丢了；只在右边出现 = 多了意外提交。

## 4. 测试

**验收只有四项，整次升级约 15 分钟（硬·2026-10-15）**：overlay 契约测试 → 升级闸门 → `hermes update` → 冒烟跑一次依赖 agent 的 cron 任务（job id 见 `references/local-upgrade.md`，没有该文件就挑一个本机已有的 agent cron）。冒烟选「没新内容就静默」的任务，例如本 skill 的上游检查：刚升完它应输出 `[SILENT]`，看 cron output 文件即可。不要跑每天投卡、等用户确认的任务（如昨日复盘），否则群里会多一张重复卡。超过 20 分钟先停下告诉用户卡在哪。禁止以下加项（课例 2026-10-15 v0.22.1：三项加起来多花约 1 小时，用户催了才停）：

- 不跑 `tests/` 全量。一遍约 26 分钟；上游基线自带约 130 个失败，跑完也说明不了补丁好坏。
- 不另建 venv（`uv sync --all-extras` 超过 10 分钟）。依赖和 Python 运行时由 `hermes pm` 和 `hermes update` 管理，不用重新研究。契约测试直接用 `scripts/run_tests.sh`。
- clone 或 worktree 放在 `~/.hermes` 之外。worktree 的 `.git` 元数据在 `~/.hermes` 下会触发 `home_io_guard` 误报（`TEST BUG: file I/O against the REAL hermes home`），这不是补丁回归。

- 跑 `PATCHES.md` 列出的 overlay 契约测试（每个补丁至少一条断言其行为的测试）。文件不在或有红 = 未完成。
- 整份模块测试全绿不够：上游测试可能按上游行为断言，补丁行为照样丢。测试与上游行为冲突时，保留断言补丁行为的测试。
- 单条红：在干净的 `$TAG` worktree 上复跑同一用例。干净 tag 也红 = 上游基线问题，不是 overlay 回归，写明即可。

```bash
git worktree add --detach /tmp/hermes-clean-<tag> "$TAG"
```

## 5. PATCHES.md、tag、推送

```bash
# 改 PATCHES.md / PATCHES.zh-CN.md 后作为 overlay 的一部分提交（或并入文档补丁）
N=1   # 同一上游 tag 第几次重放
git tag -a "v${TAG#v}-<owner>.$N" -m "overlay on $TAG"
git push --force-with-lease=upstream-main fork "$NEW_BASE:refs/heads/upstream-main"   # upstream-main = new overlay base
git push --force-with-lease="main:$OLD_TIP" fork overlay:main
git push fork "v${TAG#v}-<owner>.$N"
gh api repos/<owner>/hermes-agent/commits/main --jq .sha
```

`--force-with-lease` 带上旧 tip：别人（或另一个会话）在你之后推过 fork `main`，推送会被拒，而不是覆盖。被拒就重新 fetch、重做 range-diff。

## Git 拉不下来

`git clone` / `git fetch` 超时或 SSH 挂起时，不要在活仓上硬 rebase。改用 `gh api repos/<owner>/hermes-agent/tarball/<ref>` 下两份压缩包：fork 打当前 `main`，上游打目标 tag。下完必须 `gzip -t` 通过；不完整的包删掉重下，不要当源码用。

压缩包没有提交历史，不能 `git rebase`。先在上游目录里 `git init`，用 `git add -A -f` 提交一次，再逐个 `git am --3way` overlay 提交。必须加 `-f`：上游的 `.gitignore` 会忽略它自己强制提交过的文件（`web/public/fonts/`、`export*`、`data/` 等），普通 `git add -A` 会漏掉。提交后核对文件数：`git ls-files | wc -l` 要等于 `gh api "repos/NousResearch/hermes-agent/git/trees/$TAG?recursive=1" --jq '[.tree[]|select(.type=="blob")]|length'`（课例 v0.21.7：漏了字体、桌面类型、p5js 等 13 个文件，却报了已换版）。某个 overlay 提交失败就 `git am --abort`，改按该提交的意图手工搬：

- 先读新版调用点。上游已经做掉的分支（例如登录轮询已经对 408/429/5xx 退避）只补它没盖住的那一支，不要把旧函数整段贴回去。
- 旧测试不能原样跑时，改测试去调新导出，再用活仓 `.venv` 的 pytest 跑。`scripts/run_tests.sh` 会先重建测试环境，卡住不要当测试失败。
- 活仓与新版是两段无关历史时，`merge --ff-only` 会拒。先建 `backup/pre-<ver>-<sha>`，再 `git reset --hard` 到已推上 fork 的那一版。没有备份分支不要 reset。
- `--force-with-lease=main:<sha>` 要用活仓 `rev-parse` 出来的完整哈希。临时目录里的短哈希解析不了，推送会报解析错而不是拒绝。
- `git push` 挂起或 SSH 中途断开时，先用 `gh api .../commits/main` 确认远端没动。整仓历史不相关、包又很大时，不要重复推、也不要把同一份包再上传再下载：把临时目录当本地 remote（`git remote add <name> <tmp>/.git && git fetch <name>`），活仓已有 `backup/pre-<ver>-<sha>` 后 `git reset --hard <name>/<branch>`。

## 6. 活仓跟上

- `origin` = fork：`hermes update`（快进或 reset 到新的 fork `main`，未提交改动 autostash）。先确认活仓 `main` 没有未推到 fork 的提交。
- `origin` = upstream：不要 `hermes update`；按 `align-worktree-via-cron.md` 在会话闸外把活仓对齐到新的 fork `main`。
- 之后请用户发 `/restart`，再核活仓 `__version__`、`git log -1` 和 gateway 进程启动时间。
