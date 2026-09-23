# 模式分桶（飞书本人发言）

分析脚本用；阈值可按样本微调，改写时说明是启发式。

## 文本抽取

- `content` 为 str → 直接用
- 为 dict → 优先 `text`，否则 `json.dumps(ensure_ascii=False)`
- 长度统计只计 `msg_type in (text, post)`

## 建议 Counter 键

| key | 判定思路 |
|---|---|
| `has_@` | `mentions` 非空 |
| `has_link` | `https?://` / 团队需求系统与代码托管域名 / `feishu.cn` / `github.com` |
| `question` | `[?？]` 或 `吗$` / `怎么` / `如何` / `可以吗` |
| `short_ack` | 整句仅 `好/ok/收到/1/没问题/done` 等 |
| `ultra_short_<=8` | 文本长度 ≤8 |
| `fragment_short` | 长度≤30 且几乎无标点、非 ack |
| `long_>=80` | 长度 ≥80 |
| `structure_signal` | `先对齐|总结一下|结论|目标|边界|方案|todo|下一步` |
| `open_loop_no_eta` | 以 `我看看|我看下|等会改|稍后|再看看|处理中` 起头且无明确时刻 |
| `done_without_proof` | `好了|发了|改了|刷新下` 等且无链接/验收点 |
| `imperative_no_owner` | `加一下|看下|验收下|刷新试试` 且无 @ |
| `agent_cmd` | `@<机器人名>` / `/new` / `/approve` |
| `status_done` | `已…修/合/发/上/处理` 或 `fixed|merged|deployed` |
| `advice` | `建议|推荐|方案|取舍|优先|风险|坑|边界` |
| `incident_bug` | `阻塞|报错|失败|bug|复现|异常` |
| `eng_artifact` | `文档|PR|MR|CI|分支|需求单|spec` |

## 会话分桶（解读用）

| class | 例 |
|---|---|
| `agent` | 群名含 agent 机器人名的群 |
| `tech_design` | 技术预研群 / 组件库群 |
| `release_ops` | 发版群 / 联调群 |
| `small_collab` | 群名含多人逗号分隔的临时协作群 |
| `other` | 其余 |

风格主结论以 **non_agent** 文本为主；agent 指令单独报条数。

## 输出时

- 报 **count + % of text_msgs**
- 每类最多 3–5 条 ** paraphrased ** 示例，不贴隐私/密钥
- 双速：比较 `tech_design` vs `release_ops` 的 avg/p50 长度
