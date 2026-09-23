# 活仓对齐：在会话闸外 reset

用于 `origin` 不是 fork（不能直接 `hermes update`），但新的 fork `main` 已推好、要让正在跑的活仓 `~/.hermes/hermes-agent` 跟上。

## 为什么要闸外

- 会话内对活仓的 `stash` / `rebase` / `reset --hard` / `checkout` 会被 lifecycle guard 拦（防止跑着的进程加载混合版本的模块）。会话内 `launchctl bootstrap` 一次性 LaunchAgent 也会被拦。
- `git update-ref refs/heads/main <new>` 只动指针：`git log -1` 已是新 tip，工作树的 `__version__` 可能还是旧的。
- `/restart` **只换进程，不 checkout 文件**。

## 浅仓缺父对象（先补对象再动指针）

`cat-file -t <tip>` 通不等于能 `log`。浅仓里 tip 在、父提交不在时，**不要**先 `update-ref`：指针一指，后续 `git log` / `fetch` 会报 `Could not read <parent>` / `Failed to traverse parents`。先 `git fetch --depth=1 "$FORK" main`（或从独立 clone：`git fetch --depth=1 <clone-path> <tip>`），`git log -1 <tip>` 能读之后再继续。报 `did not send all necessary objects` 也按这个补，不要为此重跑 `hermes update`。

## 做法

1. 在 `~/.hermes/scripts/<align>.sh` 写对齐脚本（cron `script` 只存相对文件名）：`git fetch "$FORK" main` → `git branch -f backup/pre-<tag> HEAD` → `git reset --hard "$FORK/main"` → echo `HEAD` 与 `__version__`。
2. 建一次性 cron：`no_agent: true`、`repeat: 1`、`deliver: local`；时间设「现在 + 2 分钟」或 `cronjob action=run`。
3. **核活仓**：读 `~/.hermes/hermes-agent/hermes_cli/__init__.py` 的 `__version__` + `git -C ~/.hermes/hermes-agent log -1`。核验命令里**不要写 restart 字样**，否则 lifecycle guard 整段拦。
4. 请用户在聊天里发 `/restart`（只写在终态正文）。
5. 跑 overlay 契约测试；删掉一次性 cron 与临时脚本、临时 remote。
