---
name: feishu-ui-feedback
description: "Use when Feishu reply has UI screenshots to fix."
license: MIT
metadata:
  author: Adonis0123
---

# Feishu UI Feedback（截图 / 文案小改）

群/私聊里「回复 + 截图 + 改 UI/文案」时用。先拿**被回复原消息**的图，再定位代码；缺关键信息就 **@ 人**，别空转猜。

本机细节：若 `references/local-*.md` 存在，先读它（本机仓库的目录归属、热修闸门、轻量改码 skill）。

## When to Use

- 触发消息是 **回复**，正文含 `[Image]` / 改文案说明
- 本地 `~/.hermes/cache/images/` 最新图与说明对不上
- 代码搜不到截图里的空态 / tab 文案

## Procedure

1. **找 chat_id**（已知可跳过）  
   `lark-cli im +chat-search --as user --query "<群名关键词>"`
2. **搜原消息**（用截图旁关键词）  
   `lark-cli im +messages-search --as user --chat-id <oc_xxx> --query "<关键词>"`  
   身份：跨会话/搜历史 **必须 `--as user`**
3. **取 image key**  
   body 里 `![Image](img_v3_...)` → `message_id=om_...`，`file-key=img_v3_...`
4. **下载**（flag 是 `--output`，**相对路径**；绝对路径会 validation 拒）  
   ```bash
   cd /tmp && lark-cli im +messages-resources-download --as user \
     --message-id om_xxx --file-key img_v3_xxx --type image \
     --output ui-feedback/shot.jpg
   ```
5. **vision 读图** → 确认页面 / tab 顺序 / 空态文案 / SEO title·meta → 再改码  
   monorepo 里先确认截图属于哪个 app 目录，别误改主站。
6. **缺链接 / 验收口径 / 归属人** → 群里 **@ 对应同事** 要，不要长时间猜。

## Pitfalls

- 会话缓存图常是**别的任务**的，不能当证据。
- 默认已是 Video 仍可能要改 **视觉顺序**（左优先）+ 滑块位移条件。
- 空态文案可能只改主句（如 `No models match` → `No matching models`），副文案不动。
- SEO 插件截图（Title / Description）：先当 **head metadata**，不是 body 文案；常见是页面 metadata 函数里 **硬编码英文** title / description。
- 「运营位文案跟语种、**链接**不跟」：先查运营位配置的数据结构有没有按语种的 link 字段——常是配置契约，不是翻译 bug。
- 问「哪方问题」：用 systematic-debugging 拆 **数据模型 → 后端 → 前端渲染** 三层，结论先写责任边界，再可选改码；回复原反馈人用真 @（`feishu-delivery` true-at）。

## Related

- 轻量改码 / worktree / 交付、仓库热修闸门：见 `references/local-*.md`（本机 skill）
- 飞书 IM 能力：`lark-im`
- 飞书气泡排版：`feishu-delivery`
