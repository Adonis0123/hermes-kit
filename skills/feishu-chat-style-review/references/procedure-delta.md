# Procedure 增量（2026-07-29 会话沉淀）

`SKILL.md` 主流程仍有效；下列补丁在 **单日复盘 / 字段坑** 优先读，避免再踩。

## 窗口

- 默认 14–21 天
- **「今天 / 上面今天的聊天」** → 仅当天 `+08:00` 00:00–23:59

## openId

```bash
LARKSUITE_CLI_NO_UPDATE_NOTIFIER=1 LARKSUITE_CLI_NO_SKILLS_NOTIFIER=1 \
  lark-cli auth status --json --verify
# → data/identities.user.openId
```

- auth：**`--json`**（可叠加 `--verify`）
- **禁止** `auth status --format json` → `unknown flag`
- im shortcut 落盘仍用 `--format json`

## 拉数（单日建议双轨）

1. group：`--sender <openId> --chat-type group` → collab 主样本  
2. all：去掉 `--chat-type` → 含 Home p2p（agent_home）  
3. Top 群：`+chat-messages-list` 同日上下文

## 降噪补充

| 噪声 | 处理 |
|---|---|
| Home p2p / chat_name 空 | agent_home，不当群吐槽 |
| agent 机器人群 | agent_group，单独计数 |
| 单日 collab ≪ 15 | 标样本偏小，勿硬套双周阈值 |

## 字段

见 `message-fields.md`：`create_time` 字符串、`content` 已展开、`data.messages`。

## Pitfalls 补

| 坑 | 处理 |
|---|---|
| `auth status --format json` | 改 `--json` |
| `create_time` 当 epoch | 字符串排序 / 截 hour |
| 「今天」仍拉 14 天 | 收窄当天 |
| agent 当 collab | 分列 |
