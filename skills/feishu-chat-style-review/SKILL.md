---
name: feishu-chat-style-review
description: "Use when reviewing Feishu group reply style from history."
license: MIT
metadata:
  author: Adonis0123
---

# 飞书群聊回复风格复盘

从 **用户身份** 拉群消息，量化「日常怎么回」，输出可扫读改进点。  
依赖：`lark-hermes-user-access`（绑定/OAuth）+ 外部 `lark-im` shortcut。  
本 skill 只在 **`~/.hermes/skills/`**；勿写入 `~/.agents/skills`。  
本机细节：若 `references/local-*.md` 存在，先读它（本机 agent 机器人名、群分类、相关 skill）。

## 触发

- 「分析我怎么回复 / 群聊风格 / 沟通有什么问题」
- 「搜集各群消息，看日常回复」
- 「评价一下上面今天的聊天」→ **当天窗口**（见 `procedure-delta.md`）
- 复盘本人在群里的推进方式、闭环质量

## 边界

| 做 | 不做 |
|---|---|
| 近 N 天 **本人发出** 消息 + 少量会话上下文 | 承诺「读完全部历史」 |
| 统计模式 + 对照改写建议 | 评判同事对错 / 情绪攻击 |
| 飞书短结论：结论→表→≤3 改进 | 把原始 JSON/墙文贴回飞书 |

未 user 授权 → 先走 `lark-hermes-user-access`。

## 范围与长度（owner 硬偏好）

| 信号 | 做 |
|---|---|
| 「这个群 / 上面今天 / 当前群」 | **只评该群**；禁止扩全天多群 / Home p2p 当主样本 |
| 「别长篇 / 怎么又长 / 好好总结」 | **≤8–10 行**；1 句结论 + ≤5 要点 |
| 「记到记忆」 | 可复用结论写 memory；过程流水不写 |
| 默认全量五段模板 | 仅未收窄时；收窄后改用极短版（见 `sample-report-shape.md`） |

## Procedure

### 1. 样本窗口

- 默认 **近 14–21 天**；用户指定则从其指定
- 时区 `+08:00`：`--start YYYY-MM-DDT00:00:00+08:00 --end …T23:59:59+08:00`
- 从 `auth status --verify` 取 `user.openId` 作为 `--sender`

### 2. 拉数（Agent 执行，落盘）

```bash
# 活跃群（可选，用于选 Top 上下文）
LARKSUITE_CLI_NO_UPDATE_NOTIFIER=1 LARKSUITE_CLI_NO_SKILLS_NOTIFIER=1 \
  lark-cli im +chat-list --as user --types group --sort active_time --page-size 40 --format json \
  > /tmp/chat-list.json

# 本人群消息（跨会话）
LARKSUITE_CLI_NO_UPDATE_NOTIFIER=1 LARKSUITE_CLI_NO_SKILLS_NOTIFIER=1 \
  lark-cli im +messages-search --as user --query "" \
  --sender <open_id> --chat-type group \
  --start "<start>" --end "<end>" \
  --page-size 50 --page-limit 12 --no-reactions --format json \
  > /tmp/my-group-msgs.raw.json
```

- 用 `json.loads(..., strict=False)` 解析
- `has_more` → 续 `page_token` 直到够样本或用户收窄范围
- 大文件勿整段读进模型；用脚本聚合统计后再读摘要

### 3. 降噪

| 噪声 | 处理 |
|---|---|
| Agent 指令 `@<机器人名>` `/new` `/approve` | **单独计数**；风格结论以 `non_agent` 子集为主 |
| 纯 sticker / 系统卡 | 类型分布里报，不进文本模式 |
| 同一会话刷屏测试 | 可按 chat 降权或单列 |

### 4. 必算指标

| 指标 | 用途 |
|---|---|
| 总量 / 群分布 Top / msg_type | 样本是否偏斜 |
| 文本长度 min/p50/p90/avg | 双速（设计 vs 联调） |
| 时段·工作日 | 活跃峰 |
| `has_@` 占比 | 是否指向明确 |
| 短碎片 / ultra-short / 纯确认 ack | 推进句 vs 水话 |
| 链接·截图·文档信号 | 交付物导向 |
| 结构信号（对齐/总结/目标/边界） | 强项 |
| 开放环（我看看/等会改）无 ETA | 改进点 |
| 完成无证据（好了/发了/刷新下） | 改进点 |
| 无 Owner 祈使（加一下/看下） | 改进点 |

分桶可参考 `references/pattern-buckets.md`。

### 5. 上下文抽样

对 **发言量 Top 3–5 非 agent 群** 再拉近 7 天会话流：

```bash
lark-cli im +chat-messages-list --as user --chat-id oc_xxx \
  --start "..." --end "..." --order desc --page-size 50 --no-reactions --format json \
  > /tmp/ctx_<chat_id>.json
```

看：你是否接话、是否收束、他人是否跟得上短句。

### 6. 飞书输出形状（硬性）

1. **结论**一行（角色画像 + 最大改进）
2. **样本范围**表（天数、条数、群数——事实）
3. **画像**表（模式 | 证据 | 评价）
4. **典型对照**表（场景 | 现状 | 更好一档）— 各 1 句改写即可
5. **优先改进 ≤3**（可执行模板，非鸡汤）
6. **可保持** ≤3
7. 说明：基于发出消息 + 少量上下文，非全员质检

可选下一步：单群深挖 / 改写范例 / 短 checklist。

## 回复模板（对照改写）

| 场景 | 更好一档 |
|---|---|
| 联调完成 | `已修 <环境> · 路径/链接 · 验证点 · 请 @X 看 Y` |
| 开放环 | `我 <时刻> 前看，结论回这里` |
| 派活 | `@X <动作>；验收=<路径/标准>` |
| 会后收口 | `结论 1/2/3 · Owner · 截止`（已有结构时只补 Owner/ETA） |

## Pitfalls

| 坑 | 处理 |
|---|---|
| `auth status --format json` 失败 | 改 **`--json`**（auth 用 `--json`；im 用 `--format json`；见 `procedure-delta.md`） |
| 管道解析大 JSON 截断/SyntaxError | 重定向文件 + `strict=False` |
| shell 嵌套引号/f-string 转义炸 Python | 分析逻辑用 `execute_code` 或脚本文件，避免多层 shell 引号 |
| `create_time` 当 epoch → 全 None | 常为 **`"YYYY-MM-DD HH:MM"` 字符串**（`message-fields.md`） |
| 把 agent 群 / Home p2p 当真人协作主样本 | 分列 agent vs collab |
| 用户说「今天」仍拉 14 天 | 收窄当天；群薄再补 all-sender |
| 只列「好/不好」无改写 | 每条改进给 **填空模板** |
| 飞书贴上百条原文 | 禁止；证据用 1 句 paraphrased 示例 |
| 未授权就 search | 先 `lark-hermes-user-access` |
| 用户只点一群仍出多群长文 | 立刻改短版 + 只评该群 |
| 把「记记忆」做成第二篇长文 | 先短结论，再静默写 memory |

## 与相关 skill

| Skill | 关系 |
|---|---|
| `lark-hermes-user-access` | 授权与检索前置 |
| `lark-im`（external） | shortcut 参数细节，只读 |
| 周报类 skill（若有） | 周报挖 **git / 需求管理系统**；本 skill 挖 **飞书发言**，不混 |

## References

- `references/procedure-delta.md` — 单日窗口 / auth `--json` / agent_home 双轨（**先读**）
- `references/message-fields.md` — search/list 字段与 `create_time` 字符串
- `references/pattern-buckets.md` — 正则分桶与报表字段
- `references/sample-report-shape.md` — 扫读报告骨架
