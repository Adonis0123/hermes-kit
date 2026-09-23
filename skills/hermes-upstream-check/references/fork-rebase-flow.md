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
- 上游把补丁所在模块整个重写 → 按契约测试手工移植，不要硬解冲突。

## 3. range-diff

```bash
git range-diff "$OLD_BASE..$OLD_TIP" "$NEW_BASE..overlay"
```

每个旧补丁都要有对应的新补丁（`=` 相同，`!` 有改动要能解释）。只在左边出现 = 补丁丢了；只在右边出现 = 多了意外提交。

## 4. 测试

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

## 6. 活仓跟上

- `origin` = fork：`hermes update`（快进或 reset 到新的 fork `main`，未提交改动 autostash）。先确认活仓 `main` 没有未推到 fork 的提交。
- `origin` = upstream：不要 `hermes update`；按 `align-worktree-via-cron.md` 在会话闸外把活仓对齐到新的 fork `main`。
- 之后请用户发 `/restart`，再核活仓 `__version__`、`git log -1` 和 gateway 进程启动时间。
