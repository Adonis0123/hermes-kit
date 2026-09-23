---
name: cursor-cli
description: "Use when Hermes must run cursor-cli / cursor-agent (print, stream, model pick)."
license: MIT
metadata:
  author: Adonis0123
  version: "1.1.1"
  hermes:
    owner_local: true
    tags: [cursor, cursor-cli, cursor-agent, delegation]
    category: autonomous-ai-agents
    related_skills: [writing-with-cursor, claude-code, codex]
---

# cursor-cli（Hermes 调用 Cursor Agent）

Hermes 调 **Cursor Agent CLI** 的适配器。只管怎么启动、选模型、盯流式输出。

**不管**：写什么、写作口径、飞书写入 → 由调用方写作 skill 决定。

本机细节：若 `references/local-*.md` 存在，先读它（本机调用方 skill 与额外约束）。

## When to Use

- 用户或其它 skill 说 `cursor-cli` / `cursor-agent` / Cursor 再写一版
- 调用方写作 skill 的第一稿和改稿
- `writing-with-cursor`：成篇文案 / 文档润色
- 要把任务交给 Cursor CLI 而不是自己润色交差

**不要用**

- 操作 Cursor IDE 窗口 / 键鼠
- 只问「Cursor 是什么」
- 飞书短回复、确认、一句改（见 `writing-with-cursor`）

## Prerequisites

- 二进制：`~/.local/bin/cursor-agent`（login zsh 里 `cursor-cli` 是它的 alias）
- Hermes 默认 **非 login bash**，看不到 alias
- **调用必须 `zsh -lic`（硬·2026-09-21）**：解析用 `zsh -lic 'whence -v cursor-cli'`；真正跑也包进 `zsh -lic`，或直接 `~/.local/bin/cursor-agent`。禁止在非 login shell 里 `which cursor-cli` 后宣称没有，再空等 `--print`。
- **必须后台 `stream-json`**：禁止前台 `--output-format text` / 裸 `--print` 干等。jsonl 长时间 0 增长或只见 reconnect → kill。课例 2026-09-20 长文空转 34 分钟。

## How to Run

1. **选模型**（调用方没点名时走这条）：

```bash
python3 ${HERMES_SKILL_DIR}/scripts/pick_gemini_flash.py
# 打印一行，例如 gemini-3.8-flash-high；3.9 在 list 里就会打印 3.9
```

禁止写死带小版本的 Gemini id。picker 失败 → 告诉用户并按调用方降级。版本下限只在脚本 `FLOOR`，不要抄进 MEMORY。

2. **非交互 print + 流式**（长任务默认；**必须** `zsh -lic` 或绝对路径二进制）：

```
terminal(
  command="zsh -lic '~/.local/bin/cursor-agent --print --output-format stream-json --stream-partial-output --trust --force --sandbox disabled --model <id> --workspace <dir> --add-dir <extra> \"$(cat <prompt-file>)\"'",
  background=true
)
```

stdout 逐行落 jsonl；text delta 同步写调用方指定的 md。`notify` 盯结束。

3. **盯进度**：轮询 md/jsonl 体积。长时间 0 增长或只见 reconnect → kill 再跑。禁止 `--output-format text` 前台干等。
4. **超时（硬）**：墙钟 **12 分钟**仍无切干净的终稿 → kill，按调用方降级自己写，第一句标明「Cursor 超时」。不要空等到用户催。

## Quick Reference

| 要做 | 命令 |
|------|------|
| 解析入口 | `zsh -lic 'whence -v cursor-cli'` 或 `~/.local/bin/cursor-agent` |
| 列出模型 | `~/.local/bin/cursor-agent --list-models` |
| 最新 Gemini Flash-high | `python3 ${HERMES_SKILL_DIR}/scripts/pick_gemini_flash.py` |
| 只读问答 / 改稿润色 | 加 `--mode ask`（现稿塞进 prompt，不扫仓） |
| 只规划 | 加 `--mode plan` |

## Procedure

1. 写好 prompt 文件（调用方给契约；本 skill 不发明写作口径）。
2. 解析二进制；没有 → 停，让调用方降级。
3. 取 `--model`：调用方指定 **或** `pick_gemini_flash.py`。
4. 后台 stream-json；workspace / `--add-dir` 由调用方给。
5. 从产物里切干净终稿（掉 prompt 回显、过程句、重复全文）。
6. 完成标准：md 有调用方要的终稿，且 jsonl 不再增长。

## Pitfalls

| 坑 | 处理 |
|----|------|
| 非 login shell `which cursor-cli` 说没有 | `zsh -lic` 或直接 `~/.local/bin/cursor-agent`；禁止空等 `--print`（课例 2026-09-20 空转 34 分钟） |
| 前台等 `--print` text，日志一直空 | 后台 + stream-json + delta 写 md；jsonl 不增长就 kill |
| 写死 `gemini-3.8-flash` / 用 IDE 短名 | CLI id 带 `-high`；用 picker |
| 自己润色却说是 Cursor 稿 | 必须真跑 cursor-agent |
| 流式把 prompt/过程句当终稿 | 按调用方标记切干净 |

## Verification

- [ ] `~/.local/bin/cursor-agent --list-models` 有输出
- [ ] picker 打印的 id 出现在 `--list-models` 里，且是最高 `gemini-*.flash-high`（下限见脚本 `FLOOR`）
- [ ] 后台 jsonl 有 text delta，不是空转 reconnect
- [ ] 终稿文件不是 Hermes 自己改写的第一稿冒充
