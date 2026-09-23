---
name: writing-with-cursor
description: "Use when drafting or polishing any multi-paragraph copy, docs, or weekly-report prose. Not for short Feishu replies."
license: MIT
metadata:
  author: Adonis0123
  version: "1.1.0"
  hermes:
    owner_local: true
    tags: [writing, cursor-cli, gemini, copy, docs]
    related_skills: [cursor-cli, shuorenhua]
---

# writing-with-cursor

长文案交给 cursor-cli 的最新 Gemini Flash-high。短回复自己写。

本 skill 住在 `~/.hermes/skills/`，**不要**写进 `hermes-agent` 源码仓（升级会冲掉）。下限版本只在 `pick_gemini_flash.py` 的 `FLOOR`。

调用步骤见 `cursor-cli`。

本机细节：若 `references/local-*.md` 存在，先读它（本机周报 skill、写作目录等）。

## When to Use

走 Cursor（`pick_gemini_flash.py` 选出的最新 Flash-high）：

- 周报等长稿：**第一稿和改稿**（贴回一段、嫌没写好、重写、改某模块）
- 成篇文档 / 对外文案 / 飞书长稿 / README 说明
- 用户说「优化文案 / 润色 / 说人话改写」且正文是成篇

**不要走**（自己写，保速度）：

- 飞书短回复、确认、进度、报错、一句是/否
- 代码、排障、查日志、跑命令
- 周报「把 [3] 改成 xxx」编号替换
- 只同步飞书、不改正文

## 三档（速度）

| 档 | 输入 | 模式 |
|----|------|------|
| 第一稿 | 扫仓 JSON + `--add-dir` skill | agent。超过 12 分钟无终稿 → 自己写并标明 Cursor 超时 |
| 改稿（措辞/结构） | 现稿 + 用户原话 | `--mode ask`。不 generate、不 `--add-dir` 整仓 |
| 改稿（要补事实，如「漏了 X」） | 本地先 `git log` / 已有 generate JSON 捞事实，塞进 prompt | 仍 `--mode ask`。不要整仓 add-dir |

**改稿速度（硬·课例 2026-09-21 01:23/01:32）**：同一会话已有现稿时，本轮**第一个工具**就必须启动 cursor-cli ask。禁止先 `skill_view` 一串、禁止先空等 `process_manage` 60 秒。Cursor 跑完只贴改稿，不要再开一轮解释。墙钟仍 12 分钟封顶。

## Pitfalls

| 坑 | 处理 |
|----|------|
| 用户贴回一段，自己用 grok 改 | 改稿走 cursor-cli ask |
| 每条飞书都开 Cursor | 短回复跳过 |
| 改稿再扫仓 / `--add-dir <整个工作目录>` | 现稿 + 必要时本地摘事实 |
| 改稿先读一堆 skill 再开 Cursor（5–16 分钟） | 第一下就 spawn ask；notify 到了只贴终稿 |
| 把规程抄进 MEMORY / AGENTS | 热层只留 USER 一行偏好 |
| 写进 `hermes-agent/skills/` | 升级回退；只改 `~/.hermes/skills/` |
