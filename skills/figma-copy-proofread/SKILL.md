---
name: figma-copy-proofread
description: 批量比对 Figma 设计稿文案和线上页面文案，用表格列出不一致的词条（按线上为准）；用户明确要求时才在 Figma 对应文字上加评论。Use when someone sends a Figma frame link plus a live/test page URL and asks to proofread / 校对 / 比对文案, or says the design copy is behind the live copy.
version: 1.2.0
author: Adonis0123
platforms: [macos, linux]
prerequisites:
  env_vars: [FIGMA_API_KEY]
  commands: [python3]
required_environment_variables:
  - name: FIGMA_API_KEY
    prompt: Figma personal access token (needs file_content:read and file_comments:write)
    help: "Figma → Settings → Security → Personal access tokens."
metadata:
  hermes:
    tags: [Figma, Copy, Proofreading, Feishu]
    related_skills: [ego-browser]
---

# Figma 文案校对

线上文案是准的。把一个 Figma frame 的设计稿文案和一个线上 URL 的线上文案对位，找出差异，用表格回给用户。用户明确说「加评论」才在 Figma 上加校对评论。术语见同目录 `CONTEXT.md`。

脚本：`SCRIPT=~/.hermes/skills/productivity/figma-copy-proofread/scripts/figma_copy.py`
Python：`PY=$HOME/.hermes/hermes-agent/venv/bin/python; [ -x "$PY" ] || PY=python3`（venv 里有 Pillow，report 要用它在截图上画框）。
工作目录：每次校对新建一个，`WORK=${HERMES_HOME:-$HOME/.hermes}/cache/figma-copy-proofread/$(date +%Y%m%d-%H%M%S)`，`mkdir -p` 后把实际路径记下来，本次后续命令（包括用户随后说「加评论」）都用这个路径。**不要复用以前运行留下的文件**，旧的 live.txt / plan.json 是别的时间的线上状态。

总体顺序：先用 **Copy Catalog（线上文案目录）** 判断，几秒出结果，不用登录；目录判断不了的少数几条，才开 ego-browser 看页面。

## 输入规则

- 一次比对 = 一个带 `node-id` 的 Figma frame 链接 + 一个线上 URL。用户可以一次发多组，逐组执行，每组单独一份清单。
- Figma 链接没有 `node-id`：停下，请用户在 Figma 里右键 frame → Copy link to selection 再发。不要自己去整份文件里找页面。

## 步骤

### 1. 拉设计稿、渲染截图、取 Copy Catalog（一次跑完，所有 frame 一起）

```bash
# 每个 frame 一行 extract、一行 render，全部加 & 并行；catalog 每次校对取一次，所有 frame 共用
$PY $SCRIPT extract "<figma_url>" --out $WORK/<frame_id>.design.json &
$PY $SCRIPT render "<figma_url>" --out $WORK/<frame_id>.png &
$PY $SCRIPT catalog "<live_url>" [<route_url> ...] --out $WORK/catalog.txt &
wait
```

- frame_id 里的 `:` 换成 `-` 做文件名。所有 frame 写进同一个 terminal 调用。多个 frame 的线上 URL 相同时共用一份 `catalog.txt`；不同时按 URL 各取一份。
- `catalog` 读线上页面随 HTML 下发的文案目录（Next.js `__NEXT_DATA__` 里的翻译）：这个链接当前部署版本的全部文案，弹窗和 tooltip 也在。不需要登录，不开浏览器。
- 每个路由只下发自己的文案。设计稿画的弹窗或页面不在给的链接里时，按设计稿画的界面补上对应路由；不知道路由就在前端源码的页面目录里按文案搜（只读）。`references/local-*.md` 存在时先读，里面有本机站点默认要加的路由。
- 报错「no Copy Catalog」：这个站点没有目录，整张 frame 走第 3 步的浏览器抓取，第 2 步不带 `--catalog`。

### 2. 生成候选和计划骨架

```bash
$PY $SCRIPT candidates $WORK/<frame_id>.design.json --catalog $WORK/catalog.txt \
  --plan $WORK/<frame_id>.plan.json --live-url "<live_url>" --image $WORK/<frame_id>.png
```

- 第一行是摘要。`language_match` 为 false 时停下：告诉用户设计稿是 X 语言、线上是 Y 语言，请给同语言的线上 URL。不做跨语言比对。
- 它同时写好 `plan.json` 骨架：路径、frame、`live_url` 都填好了，目录里原样存在的文案已算一致，剩下的在 `todo` 里。**不要读 design.json**，摘要后面每行就是一条 todo，带 `offset` 和 `catalog_candidates`（目录里最像的几条）。
- **`next` 是 `report now, no page needed`：这个 frame 直接去第 5 步出报告，不看图、不开浏览器。**

其余每条 todo 分三类：

- **目录能定**：候选明显是同一处的新写法（`Pick a Frame` → `Choose video frame`）→ 差异，`source: "catalog"`。计数、价格等动态内容，设计稿画进去的活动角标（`NOW LIVE`）、中文占位名 → `ignored`。
- **要看页面**：设计稿写死的标题/占位，线上那里显示的是案例名或数据（`Example Video`、`示例视频名称`）；或者控件线上可能没有；或者目录里几条都像、定不了是哪句。只有这类才需要第 3 步。
- 分不清是哪类时，用视觉看一眼第 1 步的 PNG（`vision_analyze`），只看这一张。

### 3. 看页面（只为「要看页面」的条目）

浏览器一律用 **ego-browser**（用户的 Ego Lite，带用户的登录态），通过 `terminal` 跑 `ego-browser nodejs`。用法见外部 skill `ego-browser`（`skill_view ego-browser`）。不要用 `browser_exec` / `browser_navigate`：那是隔离浏览器，没有登录态。

**整次校对一个 TaskSpace**：第一次调用打印 `spaceId`，之后所有 frame 的调用都 `taskSpace(<spaceId>)` 复用，全部抓完再 `task.finish({ keep: [] })`。

**抓取统一用脚本**，不要手抄页面文字：

```bash
# url 非空：打开页面并关掉推广弹窗后抓；url 为 null：抓当前状态（你已经点开弹窗/菜单后）
# 参数文件固定放在缓存根目录（ego_capture.js 从那里读），out 指向本次的 $WORK
printf '%s' '{"space": null, "url": "<live_url>", "out": "'$WORK'/<frame_id>.live.txt"}' > ${HERMES_HOME:-$HOME/.hermes}/cache/figma-copy-proofread/ego-args.json
ego-browser nodejs < ~/.hermes/skills/productivity/figma-copy-proofread/scripts/ego_capture.js
```

输出 JSON：`spaceId`、`scope`（`page` 或 `dialog`/`menu`，打开了弹窗就只抓弹窗内）、`signedIn`、`hover`（自动抓到的 tooltip，已经追加进 live.txt）。

#### 3a. 登录

`signedIn` 为 false、而设计稿画的是登录后才有的内容（我的项目、账号菜单、项目右键菜单等）时：不要自己登录，不要调 `__BREEZE_DEV_ACCOUNT__.signIn`，不要找或填密码。回复用户「请在 Ego Lite 里登录 <域名> 后回我『好了』」，收到后用同一个 spaceId 从第 3 步重抓。只比未登录也能看到的部分时不用登录。

#### 3b. 自己找到设计稿对应的界面状态

用户不需要告诉你怎么打开弹窗或 hover。设计稿是弹窗、菜单或 hover 态时，自己在线上找到它（只为「要看页面」的那几条找，找到就停；目录已经定下的文案不用再去页面确认），每个 frame 最多尝试 10 次点击：

1. **拿设计稿文字当路标**：design.json 里的按钮/标题文字（如 `View Project`、`Episode Cover`、`Rename`）在线上页面里搜，能找到的元素就是入口或入口附近。
2. **按常见入口依次试**：卡片本身或卡片上的 `Preview …` 按钮 → 卡片上的 `More` / `⋯` 按钮（右键菜单）→ tab → 顶部按钮（如 `Export`）→ 进入详情页后的同类入口。每次点击后 `page.snapshot()` 看有没有出现设计稿里的文字。
3. **还是找不到**：在前端源码里搜设计稿文字，找弹窗组件和它的调用处，推出入口（只读；本机源码位置见 `references/local-*.md`）。
4. **hover 态**：`ego_capture.js` 已自动抓 tooltip。设计稿画的是某个元素的 hover 态时，用 `page.hover("<selector>")` 真实悬停后再用 `url: null` 抓。
5. 同一个弹窗常有多个入口（如项目内 Cover 和 Export → Edit Cover），文案可能不同。找到一个后，如果源码或页面显示还有别的入口，也打开抓一次；不同入口的文案不一样时，在报告里写明各入口各自的文案。
6. 找到后用 `url: null` 重新抓，并记下入口路径（如「示例卡 → View Project → Export → Edit Cover」）写进报告。10 次仍找不到：报告里写「未找到入口」和已试过的路径，这张 frame 只比能看到的部分。

**只做打开和查看类操作**：点卡片、预览、More/⋯、tab、Export 这类展开菜单、hover、滚动、关闭弹窗。**绝不点**会改数据或花钱的按钮：Delete、Rename 的确认、Copy to My Projects、Replace/Upload 后的确认、Generate、Create、Save、Submit、Buy/Upgrade/Pay、Publish。只读示例项目里点不开的，写「示例只读，无法打开」。

ego-browser 不可用时退回 `web_extract`，并在报告里注明「线上文案来自静态抓取，可能缺前端渲染和 hover 的内容」。

几个 frame 要看的是同一个页面时，共用一个 TaskSpace，一次打开页面分别抓。抓完带上 live.txt 和 `--refresh` 再跑一次第 2 步的命令（同一个 `--plan`），它会把 `live_file` 写进计划，保留你已经归好的类，只剩还没归类的 todo。不带 `--refresh` 会从头生成骨架：

```bash
$PY $SCRIPT candidates $WORK/<frame_id>.design.json $WORK/<frame_id>.live.txt --catalog $WORK/catalog.txt \
  --plan $WORK/<frame_id>.plan.json --live-url "<live_url>" --image $WORK/<frame_id>.png --refresh
```

### 4. 判断词条对

**同一链接当天已有终稿就复用，禁止再开浏览器。** 先在本机找同一 `fileKey` + node + 线上 URL 当天已写过的 `*.plan.json`（`~/.hermes/cache`、scratch、会话产物）。找到就直接用那份跑 `report`，不要新开 TaskSpace、不要再抓页面。条数以那份终稿为准，禁止从 2 处改口成 6 处。

没打开的入口（封面弹窗、登录后菜单等）写进 `unmatched`，理由「未核」。**禁止**把未打开的入口写成「全部一致」或放进 `items`。

对每条待判断文案，结合 `path`（图层路径，能看出是导航、按钮、卡片）和线上文字的前后顺序，判断它在线上有没有对应的同一处：

- **同一处且文字不同** → 差异。即使整句被改写（相似度很低）也可能是同一处，看位置和作用。
- **线上被拆成几段**（如 `Don’t Just Generate.` + `Direct`）→ 拼起来再比；拼起来只差空格/标点换行不算差异。
- **tooltip**：设计稿里的 tooltip 图层（路径常含 tooltip / 提示 / 气泡）和 `ego_capture.js` 输出的 `hover` 配对，用 `trigger` 判断是不是同一个元素的提示。
- **只差大小写、弯直引号、首尾空格** → 不算差异。
- **动态内容**：人名、价格、日期、计数（`3 episodes`）、用户起的项目名（登录后顶部的 `Steve Philip's Project` 这类）、`xxx` 这类占位 → 放 `ignored`。拿不准的列入清单，标「可能是动态内容」。
- **当前登录用户自己的数据**（右上角项目名 `Steve Philip's Project`、用户名、头像字母、自己的项目列表）→ 一律 `ignored`，即使设计稿写的是 `Project` 这类通用词。
- **线上多出来的项**（菜单多一项 `Preview Project`）→ 不是差异，不能拿设计稿里已经对得上的文字去配它；在 report 下面写一句观察。
- **固定文案 vs 线上的实例名**：设计稿写死的标题（如 `Example Video`），线上同一位置显示示例/案例名（如 `Last Shot`，不是当前用户的数据）→ 列为差异，标「线上此处显示案例名」，live 填线上实际看到的那个名字。
  - 多张卡用同一个占位（4 张卡都写 `示例视频名称`）：按顺序一一配对，设计稿第 1 张 ↔ 线上第 1 张、第 2 张 ↔ 第 2 张，每对各算一条差异；线上卡片不够的，多出来的设计稿卡归 `unmatched`，写「线上没有第 N 张卡」。不要合并成一条。
- **线上找不到对应** → 未匹配文案，只在报告里列，不评论。整个控件线上没有（如选集下拉）也归这里，写明「线上无此控件」。设计稿里有而线上没有，常见原因是登录态、空状态或新功能未上线。

### 5. 回复差异表（不写 Figma）

在第 2 步的骨架里把每条 todo 移进 `items` / `unmatched` / `ignored`，然后删掉 `todo`（用 `patch` 改，不要重写整个文件）。完成后的样子：

```json
{"file_key": "...", "frame_id": "132395:422638", "live_url": "<用户发的线上 URL>",
 "entry": "示例卡 → View Project → Export → Edit Cover", "signed_in": true,
 "design_file": "$WORK/<frame_id>.design.json", "catalog_file": "$WORK/catalog.txt",
 "live_file": "$WORK/<frame_id>.live.txt", "frame_image": "$WORK/<frame_id>.png",
 "items": [{"n": 1, "node_id": "...", "design": "Pick a Frame", "live": "Choose video frame",
            "offset": {"x": 0, "y": 0}, "where": "Replace 菜单第一项", "source": "catalog"}],
 "unmatched": [{"node_id": "...", "reason": "线上无此控件"}],
 "ignored": [{"node_id": "...", "reason": "动态内容：项目名"}]}
```

- `items` 只放差异：同一处、文字不同。`design`、`offset` 从 design.json 原样复制；`where` 写位置。
  - `source: "catalog"`：`live` 必须是 catalog.txt 里的一整条。
  - `source: "page"`：`live` 必须是 live.txt 里原文存在的文字（可以是相邻 2–3 行拼起来）。
- 开了页面才补 `entry`、`signed_in`。`entry` 只写点击路径（如「示例卡 → Preview Last Shot」），登录状态放 `signed_in`，report 会自己加「（已登录）」。`frame_image` 骨架已填，report 会在上面画编号红框。
- `unmatched`：线上找不到对应的（没这个控件、需登录、没找到入口）。**不要**把「未看到」写进 `items`。
- `ignored`：动态内容，以及只差大小写/引号的。
- 和线上完全相同的、脚本标成 dynamic 的不用列。`entry` 整页就写「整页」。

然后一次生成全部 frame 的回复：

```bash
$PY $SCRIPT report $WORK/<frame1>.plan.json $WORK/<frame2>.plan.json
```

它先对每份计划跑 check（编造的线上文字、一段线上文字配多处、漏归类的图层、目录里没有却没开页面就归类的文字，都会报错）。报错就改计划重跑，直到出表。

**回复 = report 的 stdout 原样贴出**：不要重写表格、不要删 `#` 列的链接、不要把 `MEDIA:` 行改成普通路径（去掉 `MEDIA:` 前缀图片就发不出去）。包括末尾的 `MEDIA:` 行（飞书会把它们作为图片发出：有差异的 frame 截图，差异处画了编号红框，编号和表格 `#` 一致，frame 名写在图顶部）。表格里 `#` 链接到 Figma 图层，线上列里改动的词已加粗。可以在最前面加一句总结论（如「3 个 frame 共 3 处差异」），在对应 frame 下面补一两句观察，但不要改表、不要另写列表代替表格。

### 6. 用户要求时才加评论

只照第 5 步的计划文件发（只发 `items`），**不要重新比对**：

```bash
$PY $SCRIPT post $WORK/<frame_id>.plan.json --exclude "2,5"   # 没有去掉的就不带 --exclude
```

- 用户没明确说「加评论」，不跑 post。
- 新会话里的「加评论」无效：旧计划作废，请用户重新发链接。
- 脚本会跳过已有同样内容的评论（重复跑不会刷屏），最后一行是 `posted= skipped=`，原样告诉用户数量。
- 评论内容固定为 `[文案校对机器人] 线上为：B（当前：A）`，钉在 frame 内对应文字的位置。评论以 token 主人的身份显示。

`post --dry-run` 只打印将要发的请求，不写 Figma，调试用。

## 边界

- 只读 Figma；用户要求时写评论。不改设计稿图层。
- 线上页面只读：不提交表单、不改数据、不登录、不登出。
- 不删、不回复、不 resolve 任何已有评论。
