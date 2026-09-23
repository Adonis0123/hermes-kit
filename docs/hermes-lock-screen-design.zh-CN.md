[English](hermes-lock-screen-design.md) | 简体中文

# 设计：从飞书私聊远程锁定 Mac

[`hermes-lock-screen`](../plugins/hermes-lock-screen/) 插件的设计说明。主人不在 Mac 旁边，想从飞书私聊立刻锁屏，并且要有证据证明真的锁上了。

成功的标准是：回到桌面前 Mac 要求认证。息屏、屏保、没证明已锁的睡眠、“命令已接受”都不算。

## 两个入口，一条执行链

| 入口 | 触发方式 | 是否经过 LLM |
| --- | --- | --- |
| `/lock`（首选） | 主人在批准的私聊里只发 `/lock` | 不经过。它跳过模型，也不进飞书文本合并 |
| 自然语言 | 模型判断主人正在要求立刻锁屏，调用无参数的 `lock_screen` tool | 只判断意图，从不负责授权 |

两个入口构造同一个 `LockRequest`，走同一套授权、防重放、审计、固定 Shortcut 和锁态验证。执行函数只有一个，subprocess、审计、防重放逻辑都不复制。

为什么首选 `/lock`：飞书普通文本会有约 0.6 秒的 debounce，并按换行合并；以 `/` 开头的消息是命令，不进合并。确定性命令也不依赖模型是否选中 tool。

## 最小可信链路

1. 证明请求来自批准的主人私聊。
2. 自然语言入口里，模型选中 tool 代表意图；插件负责证明请求不是重放。
3. 用固定 argv 运行固定 Shortcut，不接受用户参数。
4. 读取系统锁态。Shortcut 退出码 0 只能证明“已调用”，不能证明“已锁定”。

## 授权（默认拒绝）

以下全部满足才放行：

1. 请求能对应到已知会话（`/lock` 来自网关的入站事件，tool 来自 `state.db`）。
2. 平台是 `feishu`。
3. 是私聊。
4. chat id 在 `owner_dm_chat_ids` 里。
5. 发送者（`user_id` 或 `user_id_alt`）在 `owner_user_ids` 里。
6. tool 没有参数；`/lock` 后面没有别的文字。
7. 这条触发消息还没有触发过锁屏。

主人 id 是配置，不是密钥。写在 `config.yaml`，不写进源码：

```yaml
plugins:
  entries:
    hermes-lock-screen:
      owner_user_ids: ["ou_xxx"]
      owner_dm_chat_ids: ["oc_xxx"]
```

飞书消息本身就是这一次的授权。桌面上不再弹第二次确认，因为场景就是没人坐在 Mac 前。

`lock_screen` toolset 只对飞书会话开启。CLI、其他平台、群聊、其他私聊、缺少上下文，一律拒绝。

## `/lock` 怎么拿到可信上下文

判断是不是主人需要发送者和 chat，但上游插件的 slash 命令只拿到原始参数字符串。考虑过两种方案：

| 方案 | 状态 |
| --- | --- |
| 扩展宿主：给声明 `accepts_context=True` 的命令处理函数传一个不可变的 `PluginCommandContext`（platform、chat id、chat type、user id、message id、session key），再加 `busy_policy="dispatch"`，让命令在 agent 忙时也能执行 | 最早的设计。它要改 Hermes 核心，只能放在 fork 里；这类补丁都列在 fork 的 [`PATCHES.md`](https://github.com/Adonis0123/hermes-agent/blob/main/PATCHES.md) |
| 用上游的 `pre_gateway_dispatch` 插件 hook，它在分发前能看到完整入站事件 | **现行方案。** 插件从事件里读发送者和 chat，在这里回应主人的 `/lock`，然后返回 `skip`。原版 Hermes 上就能用 |

用 hook 之后，不是主人的请求照常分发：先过网关自己的鉴权，再到注册的 `/lock` 命令；它没有可信上下文，按 `command_context_missing` 拒绝。hook 在忙碌检查之前运行，所以 agent 正在跑一轮时 `/lock` 也能执行，既不打断也不排队。

## 自然语言意图

- 只要是“现在锁”的请求就调用，包括自由表达和礼貌问句（“能帮我锁一下屏吗”“我要出门了，帮我锁一下”）。
- 纯能力咨询、讨论、否定、假设性的未来场景不调用。
- 插件不再重新解析句子。早期版本用 tool 的 `user_task` 字段去匹配固定句式，实际跑不通：Hermes 不把 `user_task` 传给普通 tool 处理函数，而且这个字段指原始任务，不是当前消息。现在 tool 被选中就映射为内部的 `model_intent` 标记。

## 执行

1. 校验参数、上下文和策略。
2. 写一条 `accepted` 审计。写不进去就失败。
3. 原子预留 `(session_id, message_id)`。重复请求不会再执行。
4. 按精确名称确认 Shortcut 存在。
5. 用 `shell=False` 和有上限的超时运行 `/usr/bin/shortcuts run "Hermes Lock Screen"`。名称是源码常量，从不作为参数传入。
6. 最多轮询 5 次锁态：读 I/O Registry 里 `IOConsoleUsers` 的 `CGSSessionScreenIsLocked`。
7. 返回一个结果。

| 结果 | 含义 | 回复主人 |
| --- | --- | --- |
| `locked`，`verified=true` | 系统状态证明已锁 | `🔒 已锁屏。` |
| `invoked_unverified` | Shortcut 跑了，但证明不了已锁 | `🔒 已执行锁屏。` |
| `failed` + 有限的原因 | 授权、可用性、超时、Shortcut 或审计失败 | 一句安全的失败提示 |

`invoked_unverified` 绝不能报成“已锁屏”。返回 `locked` 或 `invoked_unverified` 之后，任何入口都不能再报失败。

锁屏不会结束登录会话，所以网关继续运行，锁屏状态下也能把回复发出去。

## 审计

每次尝试在 `$HERMES_HOME/logs/lock-screen-audit.jsonl` 追加一行 JSONL，文件权限 `0600`：时间戳、session id、哈希后的 chat 和 user id、message id、授权结论、执行结果、验证结果、有限的错误类别。不记录消息正文、token、凭据、环境变量值和不限长的 subprocess 输出。

## 失败行为

| 失败 | 结果 |
| --- | --- |
| Mac 或网关离线 | 什么都不执行，也不会误报成功 |
| 平台、群、chat 或发送者不对 | 执行前拒绝 |
| 带了参数 | 执行前拒绝 |
| Shortcut 不存在或改了名 | `failed` |
| Shortcut 非零退出或超时 | `failed` |
| 无法证明已锁 | `invoked_unverified` |
| 同一条消息第二次 | 按重复拒绝 |

## 测试

自动测试从不锁真实 Mac。它们用临时 `HERMES_HOME`、临时会话数据库，mock 掉 subprocess 和锁态探测。覆盖：两个入口在主人私聊下执行；拒绝错误的发送者、chat、平台、群、参数、缺失的 message id 和 CLI；固定 argv 且 `shell=False`；重复拒绝；Shortcut 缺失、非零退出、超时、已验证和未验证的锁定；审计脱敏和文件权限。注册的 `/lock` 处理函数走真实的 adapter、结果分类和回复格式化，只 mock macOS subprocess，防止“实际执行了但回复说失败”。

最终验收由主人真机完成：在私聊发 `/lock`，看到真正的锁屏界面，本地解锁，核对飞书回复和审计记录与实际一致。

## 不做

- 不改 `computer_use` 的组合键拦截，不用 AppleScript，不模拟按键，不接受任意 Shortcut 名称或 shell 文本。
- 不做解锁、输密码、睡眠、注销、关机。
- 网关重载只通过飞书 `/restart`，不从本地会话重启。

回滚：禁用插件和 toolset，再 `/restart`。Shortcut 可以保留，不运行就什么都不做。

## 附录：Shortcut

插件依赖当前 macOS 用户会话里的一个 Apple 快捷指令。

1. 在“快捷指令”里新建一个名字恰好是 `Hermes Lock Screen` 的快捷指令，只放内置的 **锁定屏幕** 动作。
2. 手动运行一次。Mac 应在 2 秒内出现锁屏界面，自己解锁。
3. 确认 `shortcuts list` 里有 `Hermes Lock Screen`，解锁后还能再次运行。

不需要新增辅助功能权限。

为什么用快捷指令：

| 方案 | 结论 |
| --- | --- |
| 快捷指令内置的锁定屏幕动作 | 采用：Apple 自带动作，权限和维护成本最低 |
| 自写 Swift 小应用 | 要用私有 API，还要签名、公证、处理兼容 |
| AppleScript 发 Control-Command-Q | 本质上还是绕过组合键拦截 |
| `pmset`、屏保 | 证明不了系统真的锁了 |
