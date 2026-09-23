[English](memory-method.md) | 简体中文

# agent 记忆的写入闸

Hermes 每轮都会注入 `MEMORY.md` 和 `USER.md`。它们故意做得很小：默认 2,200 和 1,375 个字符（`memory.memory_char_limit`、`memory.user_char_limit`）。如果没有“什么能写进去”的规则，它们会被写满，然后被一次性大改压缩，接着又被写满。

本页是这里使用的规则。它是 agent 和人共同遵守的纪律，不改代码。Hermes 相关背景：[Persistent Memory](https://github.com/NousResearch/hermes-agent/blob/main/website/docs/user-guide/features/memory.md) 和 [Personality & SOUL.md](https://github.com/NousResearch/hermes-agent/blob/main/website/docs/user-guide/features/personality.md)。

## 内容放在哪一层

| 层 | 何时加载 | 存放 |
| --- | --- | --- |
| `SOUL.md` | 每轮，最先加载 | agent 是谁、语气、硬规则 |
| `USER.md` | 每轮 | 用户是谁、长期偏好、沟通禁区 |
| `MEMORY.md` | 每轮 | 跨会话稳定的规则、指向技能的短指针 |
| 技能 | 触发时 | 步骤、命令、防坑 |
| spec / 决策文档 | 被读取时 | 决策、触发条件、验收标准 |
| 缓存或状态文件 | 脚本读写 | 运行时状态：上次运行、一次性确认 |
| 会话历史（`session_search`） | 按需 | 所有只发生过一次的事 |

热层（`SOUL.md`、`USER.md`、`MEMORY.md`）每轮都消耗 token，其余各层用到时才有成本。

## 三个问题

往 `MEMORY.md` 加内容前，三个问题都要回答。任何一个答“否”，就不写进去。

1. **三个月后还成立吗？** 临时结论、某个 PR、当天状态：否。
2. **没有更合适的地方吗？** 可执行的步骤放技能，决策放 spec，“我是谁”放 `USER.md`。
3. **必须每轮都摆在 agent 面前吗？** 只是偶尔查一下，就用技能或 `session_search`。

允许写一行指针：`MEMORY.md` 可以写“做 X 时用技能 Y”，细节放在技能里。

## 不写进 MEMORY 时放哪

| 这类内容 | 放到 |
| --- | --- |
| 身份、长期偏好、沟通禁区 | `USER.md` |
| 步骤、命令、防坑 | 对应的技能（优先改已有技能） |
| 架构决策、触发条件、验收标准 | spec 或 ADR |
| cron 状态、一次性确认 | 记忆之外的缓存或状态文件 |
| 单次任务、PR 号、会话过程 | 不写（会话历史里已有） |

## 保持精简

- 加之前先找能合并的旧条目，用 `replace` 代替 `add`。
- 占用超过上限的 **60%**，先压缩再添加。
- 日常目标是低于 **50%**。
- 不要把技能正文复制进记忆。
- 条目写成短标题，加上存放细节的技能或 spec 名称。不要堆命令。

## 把写入闸本身写进记忆

agent 做决定时看得到，这道闸才有用。把它作为 `MEMORY.md` 的第一条，写成一行：

```text
写入闸：进 MEMORY 前三问——① 3 个月后仍成立？② 放技能/spec/USER 更合适？③ 必须每轮注入？任一否就降级。偏好→USER，步骤→技能，决策→spec，运行时状态→缓存，过程→不写。超过 60% 先压缩。
```

另见：[什么时候接入外部 memory provider](memory-provider-adoption-gate.zh-CN.md)（热、温、冷三层，以及为什么调大字符上限不是解法）。

## 模板

只有结构和虚构示例。复制到 `~/.hermes/` 后改写。

- [`MEMORY.example.md`](templates/MEMORY.example.md)
- [`USER.example.md`](templates/USER.example.md)
- [`SOUL.example.md`](templates/SOUL.example.md)

Hermes 用只含 `§` 的一行分隔记忆条目，模板沿用这个格式。
