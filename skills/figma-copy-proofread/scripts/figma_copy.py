#!/usr/bin/env python3
"""Figma side of the copy proofread: pull a frame's Design Copy, suggest
Copy Pair candidates against Live Copy, and post confirmed Proofread Comments.

  figma_copy.py extract <figma_url> --out design.json
  figma_copy.py render <figma_url> --out frame.png [--scale 2]
  figma_copy.py catalog <live_url> [<route_url> ...] --out catalog.txt
  figma_copy.py candidates design.json [live.txt] [--catalog catalog.txt] [--top 3]
                [--plan plan.json --live-url URL [--image frame.png] [--refresh]]
  figma_copy.py check plan.json
  figma_copy.py report plan.json [plan2.json ...]
  figma_copy.py post plan.json [--exclude 3,5] [--dry-run]

Needs FIGMA_API_KEY (personal access token with file_comments:write).
Stdlib only, except `report` marking frame images, which needs Pillow and is
skipped without it.
"""
from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter

API = "https://api.figma.com/v1"
MARKER = "[文案校对机器人]"
# Pure numbers, prices, dates, counts: never fixed copy.
_DYNAMIC_RE = re.compile(r"^[\s\d.,:%/+\-–—¥$€£x×|#()]*$")
_CJK_RE = re.compile(r"[぀-ヿ㐀-鿿가-힯]")
_LATIN_RE = re.compile(r"[A-Za-z]")


def parse_figma_url(url: str) -> tuple[str, str]:
    """Return (file_key, node_id) from a figma.com design URL; node_id uses ':'."""
    parsed = urllib.parse.urlparse(url)
    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) < 2 or parts[0] not in ("design", "file"):
        raise ValueError(f"not a Figma design URL: {url}")
    file_key = parts[1]
    if len(parts) >= 4 and parts[2] == "branch":
        file_key = parts[3]
    node = urllib.parse.parse_qs(parsed.query).get("node-id", [""])[0]
    if not node:
        raise ValueError("Figma URL has no node-id; copy the link of one frame")
    return file_key, node.replace("-", ":")


def _request(method: str, path: str, body: dict | None = None) -> dict:
    token = os.environ.get("FIGMA_API_KEY")
    if not token:
        sys.exit("FIGMA_API_KEY is not set")
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        API + path, data=data, method=method,
        headers={"X-Figma-Token": token, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        sys.exit(f"Figma API {method} {path} -> {e.code}: {e.read()[:300].decode(errors='replace')}")


def collect_texts(frame: dict) -> list[dict]:
    """Visible TEXT layers under *frame*, with frame-relative offsets."""
    origin = frame.get("absoluteBoundingBox") or {"x": 0, "y": 0}
    out: list[dict] = []

    def walk(node: dict, path: list[str]) -> None:
        if node.get("visible", True) is False:
            return
        if node.get("type") == "TEXT":
            text = (node.get("characters") or "").strip()
            box = node.get("absoluteBoundingBox") or origin
            if text:
                out.append({
                    "id": node["id"],
                    "text": text,
                    "path": " / ".join(path),
                    "offset": {"x": round(box["x"] - origin["x"], 1),
                               "y": round(box["y"] - origin["y"], 1)},
                    "size": {"w": round(box.get("width", 0), 1), "h": round(box.get("height", 0), 1)},
                    "dynamic": bool(_DYNAMIC_RE.match(text)),
                })
            return
        for child in node.get("children", []):
            walk(child, path + [node.get("name", "")] if node is not frame else path)

    walk(frame, [])
    return out


def main_language(texts: list[str]) -> str:
    """'zh' / 'en' / 'unknown' by which script dominates the characters."""
    joined = "".join(texts)
    cjk, latin = len(_CJK_RE.findall(joined)), len(_LATIN_RE.findall(joined))
    if not cjk and not latin:
        return "unknown"
    # Latin letters per word outnumber CJK chars ~5:1; weight so a Chinese
    # page with brand names still reads as zh.
    return "zh" if cjk * 5 >= latin else "en"


def cmd_extract(args) -> None:
    file_key, node_id = parse_figma_url(args.url)
    data = _request("GET", f"/files/{file_key}/nodes?ids={urllib.parse.quote(node_id)}")
    entry = (data.get("nodes") or {}).get(node_id)
    if not entry or not entry.get("document"):
        sys.exit(f"node {node_id} not found in file {file_key}")
    frame = entry["document"]
    texts = collect_texts(frame)
    result = {
        "file_key": file_key,
        "frame_id": node_id,
        "frame_name": frame.get("name", ""),
        "frame_size": {"w": (frame.get("absoluteBoundingBox") or {}).get("width", 0),
                       "h": (frame.get("absoluteBoundingBox") or {}).get("height", 0)},
        "language": main_language([t["text"] for t in texts if not t["dynamic"]]),
        "texts": texts,
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    print(f"{len(texts)} text layers ({result['language']}) from '{result['frame_name']}' -> {args.out}")


def cmd_render(args) -> None:
    """Save the frame as PNG so the agent can see which UI state it shows."""
    file_key, node_id = parse_figma_url(args.url)
    data = _request("GET", f"/images/{file_key}?ids={urllib.parse.quote(node_id)}&format=png&scale={args.scale}")
    url = (data.get("images") or {}).get(node_id)
    if not url:
        sys.exit(f"Figma returned no image for {node_id}: {data.get('err')}")
    with urllib.request.urlopen(url, timeout=120) as resp, open(args.out, "wb") as f:
        f.write(resp.read())
    print(f"frame image -> {args.out}")


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.replace("’", "'").replace("‘", "'")).strip().lower()


_NEXT_DATA_RE = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)


def flatten_message(parts) -> str:
    """A compiled lingui message (["Hi ", ["name"], "!"]) as text with {name} slots."""
    if isinstance(parts, str):
        return parts
    out = []
    for p in parts:
        out.append(p if isinstance(p, str) else "{" + str(p[0] if p else "") + "}")
    # Rich-text markers (<0>Direct</0>) wrap styled spans; the user sees only the words.
    text = re.sub(r"</?\d+>", "", "".join(out))
    return re.sub(r"\s+", " ", text).strip()


def catalog_from_html(html: str) -> list[str] | None:
    """The Copy Catalog a Next.js page ships in __NEXT_DATA__ (pageProps._extraProps.translation)."""
    m = _NEXT_DATA_RE.search(html)
    if not m:
        return None
    try:
        props = json.loads(m.group(1))["props"]["pageProps"]
        translation = props["_extraProps"]["translation"]
    except (KeyError, TypeError, ValueError):
        return None
    lines = (flatten_message(v) for v in translation.values())
    return sorted({l for l in lines if l})


def cmd_catalog(args) -> None:
    """Union of the Copy Catalogs the given pages ship; each page loads only its own route's copy."""
    merged: set[str] = set()
    counts = {}
    for url in args.urls:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Macintosh) figma-copy-proofread"})
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                html = resp.read().decode("utf-8", errors="replace")
        except (urllib.error.URLError, TimeoutError) as e:
            sys.exit(f"cannot fetch {url}: {e}")
        lines = catalog_from_html(html)
        if not lines:
            sys.exit(f"no Copy Catalog on {url}; capture the page with ego-browser instead")
        counts[url] = len(lines)
        merged.update(lines)
    lines = sorted(merged)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(json.dumps({"entries": len(lines), "per_url": counts, "language": main_language(lines),
                      "out": args.out}))


class Catalog:
    """Copy Catalog lookup: exact strings plus {placeholder} patterns ('{count} episodes')."""

    def __init__(self, lines: list[str]):
        self.lines = [l.strip() for l in lines if l.strip()]
        self.exact = {_norm(l) for l in self.lines}
        slot = re.compile(r"\{[^{}]*\}")
        self.patterns = [(re.compile("^" + ".+?".join(re.escape(part) for part in slot.split(_norm(l))) + "$"),
                          len(slot.sub("", l)))
                         for l in self.lines if slot.search(l)]

    def __contains__(self, text: str) -> bool:
        n = _norm(text)
        # A slot may only fill in a value: the fixed words must be most of the text,
        # or '{0} video' would swallow 'Example Video'.
        return n in self.exact or any(p.match(n) and fixed >= 0.6 * len(n) for p, fixed in self.patterns)


def candidates(design: list[dict], live_lines: list[str], top: int = 3,
               catalog: Catalog | None = None) -> list[dict]:
    """For each non-dynamic Design Copy, the closest Live Copy lines by similarity."""
    live = list(dict.fromkeys(l.strip() for l in live_lines if l.strip()))
    live_norm = {l: _norm(l) for l in live}
    cat_norm = {l: _norm(l) for l in catalog.lines} if catalog else {}

    def best(d: str, pool: dict) -> list[dict]:
        scored = sorted(((round(difflib.SequenceMatcher(None, d, n).ratio(), 2), l) for l, n in pool.items()),
                        reverse=True)[:top]
        return [{"live": l, "score": s} for s, l in scored]

    rows = []
    for t in design:
        if t["dynamic"]:
            continue
        d = _norm(t["text"])
        exact = d in live_norm.values() or (catalog is not None and t["text"] in catalog)
        row = {"id": t["id"], "text": t["text"], "path": t["path"], "offset": t.get("offset"), "exact": exact,
               "candidates": [] if exact else best(d, live_norm)}
        if catalog is not None and not exact:
            row["catalog_candidates"] = best(d, cat_norm)
        rows.append(row)
    return rows


def _read_lines(path: str | None) -> list[str]:
    if not path:
        return []
    with open(path, encoding="utf-8") as f:
        return f.read().splitlines()


def cmd_candidates(args) -> None:
    with open(args.design, encoding="utf-8") as f:
        design = json.load(f)
    if not args.live and not args.catalog:
        sys.exit("give live.txt, --catalog catalog.txt, or both")
    lines = _read_lines(args.live)
    catalog = Catalog(_read_lines(args.catalog)) if args.catalog else None
    live_lang = main_language(lines or catalog.lines)
    rows = candidates(design["texts"], lines, args.top, catalog)
    open_rows = [r for r in rows if not r["exact"]]
    if args.plan:
        open_rows = write_plan_skeleton(args, design, open_rows)
    print(json.dumps({
        "design_language": design["language"], "live_language": live_lang,
        "language_match": design["language"] == live_lang or "unknown" in (design["language"], live_lang),
        "exact_count": sum(r["exact"] for r in rows),
        "open_count": len(open_rows),
        "next": "report now, no page needed" if not open_rows else "classify the open rows below",
    }, ensure_ascii=False))
    for r in open_rows:
        print(json.dumps(r, ensure_ascii=False))


def write_plan_skeleton(args, design: dict, open_rows: list[dict]) -> list[dict]:
    """Write plan.json with every known field filled in, so the agent only moves
    the `todo` rows into items / unmatched / ignored. Without --refresh it starts
    over, so a plan left from an earlier run never leaks in. Returns the rows
    still unclassified."""
    plan = {}
    if args.refresh and os.path.exists(args.plan):
        with open(args.plan, encoding="utf-8") as f:
            plan = json.load(f)
    plan.update({"file_key": design["file_key"], "frame_id": design["frame_id"],
                 "design_file": os.path.abspath(args.design)})
    for key, value in (("live_url", args.live_url), ("catalog_file", args.catalog),
                       ("live_file", args.live), ("frame_image", args.image)):
        if value:
            plan[key] = value if key == "live_url" else os.path.abspath(value)
    for key in ("items", "unmatched", "ignored"):
        plan.setdefault(key, [])
    done = {e.get("node_id") for key in ("items", "unmatched", "ignored") for e in plan[key]}
    todo = [r for r in open_rows if r["id"] not in done]
    plan["todo"] = [{"node_id": r["id"], "text": r["text"], "offset": r["offset"]} for r in todo]
    with open(args.plan, "w", encoding="utf-8") as f:
        json.dump(plan, f, ensure_ascii=False, indent=1)
    return todo


def _live_phrases(lines: list[str], span: int = 3) -> Counter:
    """Normalized live lines plus runs of up to *span* adjacent lines, since the
    page often splits one copy across elements ('Don't Just Generate.' + 'Direct').
    Counts are per starting line, so they bound how many slots can claim a phrase."""
    clean = [l.strip() for l in lines if l.strip()]
    out: Counter = Counter()
    for i in range(len(clean)):
        forms = set()
        for j in range(i + 1, min(i + span, len(clean)) + 1):
            forms.add(_norm(" ".join(clean[i:j])))
            forms.add(_norm("".join(clean[i:j])))
        out.update(forms)
    return out


def validate_plan(plan: dict, design: dict, live_lines: list[str],
                  catalog_lines: list[str] | None = None) -> list[str]:
    """Reject items the model made up. A page item's live text must be on the
    captured page; a catalog item's live text must be a Copy Catalog entry.
    The design text must be the layer's actual characters."""
    layers = {t["id"]: t for t in design["texts"]}
    phrases = _live_phrases(live_lines)
    catalog = Catalog(catalog_lines or [])
    errors = []
    if plan.get("file_key") != design.get("file_key") or plan.get("frame_id") != design.get("frame_id"):
        errors.append("plan file_key/frame_id does not match design file")
    page_items = [i for i in plan.get("items", []) if i.get("source", "page") == "page"]
    used = Counter(_norm(i.get("live", "")) for i in page_items)
    for live, n in used.items():
        if live in phrases and n > phrases[live]:
            errors.append(f"live text {live!r} appears {phrases[live]}x on the page but is paired "
                          f"with {n} layers; keep the one in the same slot, move the rest to unmatched")
    design_copies = Counter(_norm(t["text"]) for t in design["texts"])
    for item in plan.get("items", []):
        n = item.get("n")
        source = item.get("source", "page")
        layer = layers.get(item.get("node_id"))
        if not layer:
            errors.append(f"#{n}: node_id {item.get('node_id')} is not a text layer of this frame")
            continue
        if _norm(item.get("design", "")) != _norm(layer["text"]):
            errors.append(f"#{n}: design text differs from the layer ({layer['text']!r})")
        if _norm(item.get("live", "")) == _norm(layer["text"]):
            errors.append(f"#{n}: design and live text are the same")
        own = _norm(layer["text"])
        if source == "catalog":
            if _norm(item.get("live", "")) not in catalog.exact:
                errors.append(f"#{n}: live text {item.get('live')!r} is not a Copy Catalog entry")
            if layer["text"] in catalog:
                errors.append(f"#{n}: {layer['text']!r} is in the Copy Catalog as-is, so it matches")
        elif source == "page":
            if not live_lines:
                errors.append(f"#{n}: source is page but the plan has no live_file")
            elif _norm(item.get("live", "")) not in phrases:
                errors.append(f"#{n}: live text {item.get('live')!r} is not on the captured page")
            if live_lines and phrases.get(own, 0) >= design_copies[own]:
                errors.append(f"#{n}: {layer['text']!r} is on the page as-is, so it matches; "
                              f"extra live items are not Mismatches, mention them as an observation")
        else:
            errors.append(f"#{n}: source must be 'catalog' or 'page'")
        if item.get("offset") != layer["offset"]:
            errors.append(f"#{n}: offset must be copied from the layer ({layer['offset']})")
    errors += _coverage_errors(plan, design, lambda t: _norm(t) in phrases or t in catalog)
    if not live_lines:
        # Only the page can say what sits where the catalog has nothing: a case
        # name, a missing control. Don't let those be guessed away.
        by_catalog = {i.get("node_id") for i in plan.get("items", []) if i.get("source") == "catalog"}
        unseen = [t for t in design["texts"] if not t.get("dynamic") and t["text"] not in catalog
                  and t["id"] not in by_catalog]
        if unseen:
            names = "、".join(t["text"][:30] for t in unseen[:8])
            errors.append(f"{len(unseen)} layer(s) are not in the Copy Catalog ({names}); open the page "
                          f"(step 3) and add live_file before classifying them")
    if plan.get("todo"):
        errors.append(f"todo still has {len(plan['todo'])} row(s): move each into items, unmatched or "
                      f"ignored, then delete todo")
    return errors


def _coverage_errors(plan: dict, design: dict, found) -> list[str]:
    """Every layer that is neither dynamic nor found verbatim live must be
    classified, so nothing is silently dropped and unmatched copy never poses as
    a Mismatch."""
    errors = []
    layers = {t["id"]: t for t in design["texts"]}
    classified: dict[str, str] = {}
    for key in ("items", "unmatched", "ignored"):
        for entry in plan.get(key, []):
            node = entry.get("node_id")
            if key != "items" and node not in layers:
                errors.append(f"{key}: node_id {node} is not a text layer of this frame")
            elif key != "items" and not entry.get("reason"):
                errors.append(f"{key}: {node} needs a reason")
            if node in classified and node in layers:
                errors.append(f"{node} is listed in both {classified[node]} and {key}")
            classified.setdefault(node, key)
    missing = [t for t in design["texts"]
               if not t.get("dynamic") and not found(t["text"]) and t["id"] not in classified]
    for t in missing:
        errors.append(f"unclassified layer {t['id']} {t['text']!r}: put it in items, unmatched or ignored")
    return errors


def figma_link(file_key: str, node_id: str) -> str:
    return f"https://www.figma.com/design/{file_key}?node-id={node_id.replace(':', '-')}"


def bold_changes(design: str, live: str) -> str:
    """Live text with the words that differ from the design in **bold**. A full
    rewrite is left plain: bolding everything says nothing."""
    tokens = re.findall(r"\S+|\s+", live)
    words = [(i, _norm(t)) for i, t in enumerate(tokens) if not t.isspace()]
    base = [_norm(w) for w in design.split()]
    sm = difflib.SequenceMatcher(None, base, [w for _, w in words], autojunk=False)
    changed = set()
    for op, _a1, _a2, b1, b2 in sm.get_opcodes():
        if op != "equal":
            changed.update(words[k][0] for k in range(b1, b2))
    if not changed or len(changed) == len(words):
        return live
    out, run = [], []
    for i, t in enumerate(tokens):
        # Whitespace between two changed words stays inside one bold run.
        if i in changed or (run and t.isspace() and i + 1 in changed):
            run.append(t)
            continue
        if run:
            out.append(f"**{''.join(run)}**")
            run = []
        out.append(t)
    if run:
        out.append(f"**{''.join(run)}**")
    return "".join(out)


def render_report(plan: dict, design: dict, live_lines: list[str],
                  catalog_lines: list[str] | None = None) -> str:
    """The Feishu reply for one frame: fixed layout, Mismatch table only."""
    phrases = _live_phrases(live_lines)
    catalog = Catalog(catalog_lines or [])
    same = sum(1 for t in design["texts"]
               if not t.get("dynamic") and (_norm(t["text"]) in phrases or t["text"] in catalog))
    items, unmatched = plan.get("items", []), plan.get("unmatched", [])
    name = design.get("frame_name") or plan["frame_id"]
    url = plan.get("live_url", "")
    out = [f"**[{name}]({figma_link(plan['file_key'], plan['frame_id'])})** vs [{url}]({url})"]
    if live_lines:
        state = "已登录" if plan.get("signed_in") else "未登录"
        source = "线上文案目录 + 页面" if catalog_lines else "页面"
        out.append(f"来源：{source}；入口：{plan.get('entry') or '整页'}（{state}）")
    else:
        out.append("来源：线上文案目录（未打开页面）")
    out += [f"一致 {same} 条，差异 {len(items)} 条，未匹配 {len(unmatched)} 条。", ""]
    if items:
        cell = lambda v: str(v).replace("|", "\\|").replace("\n", " ")
        out += ["| # | 设计稿 | 线上 | 位置 |", "|---|---|---|---|"]
        for i in items:
            where = i.get("where", "") + ("（据文案目录）" if i.get("source") == "catalog" else "")
            num = f"[{i['n']}]({figma_link(plan['file_key'], i['node_id'])})"
            out.append(f"| {num} | {cell(i['design'])} | {cell(bold_changes(i['design'], i['live']))} "
                       f"| {cell(where)} |")
    else:
        out.append("全部一致。")
    if unmatched:
        names = [f"{design_text(design, u['node_id'])}（{u['reason']}）" for u in unmatched]
        more = f"，另有 {len(names) - 10} 条未匹配" if len(names) > 10 else ""
        out += ["", "未匹配：" + "、".join(names[:10]) + more]
    return "\n".join(out)


def design_text(design: dict, node_id: str) -> str:
    return next((t["text"] for t in design["texts"] if t["id"] == node_id), node_id)


def _load_plan_files(plan: dict):
    """(design, page lines, catalog lines); a plan needs a live_file, a catalog_file, or both."""
    with open(plan["design_file"], encoding="utf-8") as f:
        design = json.load(f)
    if not plan.get("live_file") and not plan.get("catalog_file"):
        raise ValueError("plan has neither live_file nor catalog_file")
    return design, _read_lines(plan.get("live_file")), _read_lines(plan.get("catalog_file"))


def mark_frame(plan: dict, design: dict, out_path: str) -> bool:
    """Frame image with a numbered red box on each Mismatch's layer. False when
    Pillow or the image is missing, so the report still goes out without it."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print("note: Pillow missing, frame image not marked", file=sys.stderr)
        return False
    src = plan.get("frame_image")
    if not src or not os.path.exists(src):
        return False
    img = Image.open(src).convert("RGB")
    # Feishu rejects images over 10 MB; a 2x render of a long page is past that.
    img.thumbnail((2000, 2000))
    frame_w = (design.get("frame_size") or {}).get("w") or img.width
    k = img.width / frame_w
    band = max(40, int(img.width / 40))
    canvas = Image.new("RGB", (img.width, img.height + band), "white")
    canvas.paste(img, (0, band))
    draw = ImageDraw.Draw(canvas)

    def font(size):
        # CJK-capable first: frame names are often Chinese.
        for name in ("/System/Library/Fonts/Hiragino Sans GB.ttc", "/System/Library/Fonts/STHeiti Medium.ttc",
                     "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
                     "/System/Library/Fonts/Helvetica.ttc", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
            try:
                return ImageFont.truetype(name, size)
            except OSError:
                continue
        return ImageFont.load_default()

    draw.text((12, band // 5), f"{design.get('frame_name', '')}  差异 {len(plan.get('items', []))} 处",
              fill="black", font=font(int(band * 0.55)))
    layers = {t["id"]: t for t in design["texts"]}
    label = font(max(14, int(18 * k)))
    red = (230, 30, 30)
    for item in plan.get("items", []):
        layer = layers.get(item["node_id"])
        if not layer:
            continue
        x, y = layer["offset"]["x"] * k, layer["offset"]["y"] * k + band
        size = layer.get("size") or {"w": 80, "h": 20}
        pad = 4 * k
        box = (x - pad, y - pad, x + size["w"] * k + pad, y + size["h"] * k + pad)
        draw.rectangle(box, outline=red, width=max(2, int(2 * k)))
        r = max(11, int(11 * k))
        # Keep the number badge inside the image for layers at the frame's edge.
        cx = min(max(box[0], r), canvas.width - r)
        cy = min(max(box[1], band + r), canvas.height - r)
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=red)
        draw.text((cx, cy), str(item["n"]), fill="white", font=label, anchor="mm")
    canvas.save(out_path, optimize=True)
    return True


def cmd_report(args) -> None:
    blocks, images = [], []
    for path in args.plans:
        with open(path, encoding="utf-8") as f:
            plan = json.load(f)
        errors = _check_plan_files(plan)
        if errors:
            sys.exit(f"{path}: plan check failed, fix before reporting:\n" + "\n".join(errors))
        design, lines, catalog_lines = _load_plan_files(plan)
        blocks.append(render_report(plan, design, lines, catalog_lines))
        if plan.get("items") and plan.get("frame_image"):
            marked = re.sub(r"\.png$", "", plan["frame_image"]) + ".marked.png"
            if mark_frame(plan, design, marked):
                images.append(marked)
    print("\n\n".join(blocks))
    print("\n需要在 Figma 上加评论的话，回「加评论」（可加「去掉 2」）。")
    for img in images:
        print(f"MEDIA:{img}")
    print("note: send stdout to the user as-is (tables, links and MEDIA: lines); "
          "without the MEDIA: prefix the images are not sent", file=sys.stderr)


def _check_plan_files(plan: dict) -> list[str]:
    try:
        design, lines, catalog_lines = _load_plan_files(plan)
    except (KeyError, OSError, ValueError) as e:
        return [f"plan needs a readable design_file and a live_file or catalog_file: {e}"]
    return validate_plan(plan, design, lines, catalog_lines)


def cmd_check(args) -> None:
    with open(args.plan, encoding="utf-8") as f:
        plan = json.load(f)
    errors = _check_plan_files(plan)
    for e in errors:
        print(e)
    if errors:
        sys.exit(f"plan check failed: {len(errors)} problem(s)")
    print(f"plan ok: {len(plan['items'])} item(s)")


def parse_exclude(raw: str | None) -> set[int]:
    if not raw:
        return set()
    return {int(x) for x in re.split(r"[,\s，、]+", raw.strip()) if x}


def comment_message(design: str, live: str) -> str:
    return f"{MARKER} 线上为：{live}（当前：{design}）"


def cmd_post(args) -> None:
    with open(args.plan, encoding="utf-8") as f:
        plan = json.load(f)
    errors = _check_plan_files(plan)
    if errors:
        sys.exit("refusing to post, plan check failed:\n" + "\n".join(errors))
    file_key, frame_id = plan["file_key"], plan["frame_id"]
    exclude = parse_exclude(args.exclude)
    items = [i for i in plan["items"] if i["n"] not in exclude]
    existing = {c.get("message", "") for c in
                _request("GET", f"/files/{file_key}/comments").get("comments", [])}
    posted = skipped = 0
    for item in items:
        msg = comment_message(item["design"], item["live"])
        if msg in existing:
            skipped += 1
            print(f"#{item['n']} skip (already commented)")
            continue
        body = {"message": msg,
                "client_meta": {"node_id": frame_id, "node_offset": item["offset"]}}
        if args.dry_run:
            print(f"#{item['n']} dry-run: {json.dumps(body, ensure_ascii=False)}")
            continue
        _request("POST", f"/files/{file_key}/comments", body)
        existing.add(msg)
        posted += 1
        print(f"#{item['n']} posted")
    print(f"posted={posted} skipped={skipped} excluded={len(exclude)} dry_run={args.dry_run}")


def main(argv=None) -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("extract")
    e.add_argument("url")
    e.add_argument("--out", required=True)
    c = sub.add_parser("candidates")
    c.add_argument("design")
    c.add_argument("live", nargs="?")
    c.add_argument("--catalog")
    c.add_argument("--top", type=int, default=3)
    c.add_argument("--plan", help="write or refresh this plan skeleton")
    c.add_argument("--live-url")
    c.add_argument("--image")
    c.add_argument("--refresh", action="store_true", help="keep this run's classified rows in --plan")
    cat = sub.add_parser("catalog")
    cat.add_argument("urls", nargs="+")
    cat.add_argument("--out", required=True)
    r = sub.add_parser("render")
    r.add_argument("url")
    r.add_argument("--out", required=True)
    r.add_argument("--scale", type=float, default=1)
    rp = sub.add_parser("report")
    rp.add_argument("plans", nargs="+")
    ch = sub.add_parser("check")
    ch.add_argument("plan")
    po = sub.add_parser("post")
    po.add_argument("plan")
    po.add_argument("--exclude")
    po.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)
    {"extract": cmd_extract, "render": cmd_render, "catalog": cmd_catalog, "candidates": cmd_candidates,
     "check": cmd_check,
     "report": cmd_report,
     "post": cmd_post}[args.cmd](args)


if __name__ == "__main__":
    main()
