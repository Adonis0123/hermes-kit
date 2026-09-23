# messages-search / chat-messages-list 字段要点

风格复盘落盘后用；以本机 shortcut 实际输出为准（2026-07 实测）。

## 信封

```json
{ "ok": true, "identity": "user", "data": { "messages": [...], "has_more": false, "page_token": "", "total": N } }
```

- 成功看 **`ok == true`**，别用 OpenAPI 老 `code==0`
- 消息数组：`data.messages`（不是 `items`）

## 单条消息（常见键）

| 字段 | 形态 | 备注 |
|---|---|---|
| `message_id` | `om_…` | |
| `chat_id` / `chat_name` / `chat_type` | string | `group` / `p2p`；**p2p 常无 `chat_name`（null）** |
| `msg_type` | `text` / `post` / `sticker` / … | 长度统计只计 text/post |
| `content` | **已展开字符串**（search 结果） | 不是原始 OpenAPI 嵌套 JSON；sticker 可为 `[Sticker]` |
| `create_time` / `update_time` | **`"YYYY-MM-DD HH:MM"` 字符串** | **不是** epoch ms；勿 `int()` |
| `sender` | `{id, id_type, name, sender_type, …}` | 本人 openId 比对用 `sender.id` |
| `mentions` | `[{id, key, name}, …]` | 可含 bot `cli_…`；`has_@` 用此字段 |
| `deleted` / `updated` | bool | |

`+chat-messages-list` 同会话上下文同样是扁平字段 + 字符串时间。

## 解析时间

```python
# 好：字符串排序 / 截 hour
t = m.get("create_time")  # "2026-07-29 09:35"
hour = int(t[11:13]) if t and len(t) >= 13 else None

# 坏：当 epoch
# int(m["create_time"])  # 炸或全 None
```

## content 抽取

1. `content` 已是 str → 直接用（search 主路径）
2. 若为 dict → 优先 `text`，否则 `json.dumps(ensure_ascii=False)`
3. 偶发 str 内再包 JSON 时再 `json.loads(..., strict=False)`

## 子集标签（复盘用）

| 条件 | 标签 |
|---|---|
| `chat_type=="p2p"` 或 `chat_name` 空 | agent_home |
| `chat_name` 含本机 agent 机器人名 | agent_group |
| 其余 group | collab |

主结论以 **collab** 文本为主；agent_* 单独报条数与「对 Agent 推进」质量。
