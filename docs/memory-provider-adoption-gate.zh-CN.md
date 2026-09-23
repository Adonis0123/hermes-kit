[English](memory-provider-adoption-gate.md) | 简体中文

# 什么时候接入外部 memory provider

Hermes 可以挂一个外部 memory provider（记忆插件，每轮按需召回场景或用户画像）。内置记忆快满时，很容易想加一个。本文是这里用的门槛：所有触发条件都满足前，只用内置记忆；满足后再小范围试点。

它和 [记忆写入门槛](memory-method.zh-CN.md) 配套：那篇决定什么内容能进 `MEMORY.md`。

## 热、温、冷三层

| 层 | 内容 | 何时加载 | 代价 |
| --- | --- | --- | --- |
| 热 | `SOUL.md`、`USER.md`、`MEMORY.md` | 每轮 | 每轮都花 token，有字符上限 |
| 温 | 外部 provider 召回的场景或画像 | 每轮，只取相关部分 | 一个 sidecar 进程、LLM 密钥、召回误差 |
| 冷 | `session_search` 查会话历史（SQLite FTS5）、skill、spec | 按需 | 不用就不花；历史不限量 |

热层只放稳定规则和长期事实。往事和过程放冷层，步骤放 skill。温层是可选增强，补冷层给不了的召回，不是热层满了的急救方案。

## 为什么不直接调大字符上限

`MEMORY.md` 满，多半是写入纪律松：重复条目、cron 状态、一次性发现。调大 `memory.memory_char_limit` 只是把垃圾桶变大，装的还是同样的东西，而且每多一个字符，每轮都要付费。先按 [写入门槛](memory-method.zh-CN.md) 压缩；压完仍然紧，再讨论调上限。

也要先弄清“记忆不够”指什么。模型上下文窗口、热层字符上限、会话历史是三种不同的容量。会话历史本来就不限量。

## 触发条件

下面**全部**满足才开始试点，缺一条就继续延后。

1. `MEMORY.md` 使用率稳定在上限的 **60%** 以下，持续至少 **两周**，而且没有靠堆条目续命。
2. 出现**可复现**的痛点：主人跨会话反复重讲同一个场景或决定，`session_search` 加 skill 解决不了。
3. 主人明确接受运维成本：sidecar 进程、provider 密钥、召回误差、排障。
4. 试点前定好成功标准，例如“某类私聊连续 5 次不用重讲背景”。

## 试点规则

| 项 | 规则 |
| --- | --- |
| 安装方式 | 按 provider 当前的 Hermes 文档挂到现有 Hermes 上，不为它重装 Hermes。 |
| 和内置记忆的关系 | 叠加。Hermes 的 provider 不替换 `MEMORY.md`。 |
| 不双写 | 热层只放铁律，provider 管场景，同一事实不写两处。 |
| 范围 | 先只开主人私聊。群聊身份隔离没验证前，不在群里开自动召回。 |
| 密钥 | provider 密钥放 `~/.hermes/.env` 或 provider 自己的目录，永不在聊天里回显。 |
| 回滚 | 关掉 provider（`hermes memory off` 或清空 `memory.provider`）并停掉 sidecar，热层不受影响。 |
| 验证 | `hermes memory status`、一次真实的跨会话召回测试、检查日志里没有泄露密钥。 |

## 目标形态（试点通过后）

```text
每轮：
  MEMORY.md / USER.md / SOUL.md    热：铁律，短
  + provider 预取本轮相关内容       温：相关场景 / 画像
  + session_search、provider 搜索   冷：按需深挖

写入：
  稳定偏好、安全规则   -> USER.md / MEMORY.md / SOUL.md
  对话场景             -> provider（由它维护）
  步骤和命令           -> skill
  cron 或一次性状态    -> 记忆之外的状态文件
```

## 放弃的方案

| 方案 | 原因 |
| --- | --- |
| 现在就接 provider | 增加运维，却没证明召回有缺口 |
| 只调大字符上限 | 垃圾桶变大；压缩之后仍紧再议 |
| 用 provider 替掉内置记忆 | Hermes 的 provider 设计就是叠加；铁律仍需要稳定的热层注入 |
| 照搬别的宿主集成里的工具名 | 各宿主工具名不同，以 provider 的 Hermes 文档为准 |

## 参考

- Hermes [Persistent Memory](https://github.com/NousResearch/hermes-agent/blob/main/website/docs/user-guide/features/memory.md)
- Hermes [Memory Providers](https://github.com/NousResearch/hermes-agent/blob/main/website/docs/user-guide/features/memory-providers.md)
- [记忆写入门槛](memory-method.zh-CN.md)
