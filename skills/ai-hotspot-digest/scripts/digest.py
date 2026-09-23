#!/usr/bin/env python3
"""Collect, render, and publish the AI hotspot group digest."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Iterable

SKILL_DIR = Path(__file__).resolve().parents[1]
LOCAL_CONFIG_PATH = SKILL_DIR / "references" / "local-config.json"


def load_config(
    env: dict[str, str] | None = None, config_path: Path | None = None
) -> dict[str, str]:
    """Resolve delivery targets: env vars win, then references/local-config.json.

    Keys: chat_id, owner_open_id, state_dir. Env vars: AI_HOTSPOT_CHAT_ID,
    AI_HOTSPOT_OWNER_OPEN_ID, AI_HOTSPOT_STATE_DIR.
    """
    env = os.environ if env is None else env
    path = LOCAL_CONFIG_PATH if config_path is None else config_path
    file_config: dict[str, Any] = {}
    if path.is_file():
        file_config = json.loads(path.read_text(encoding="utf-8"))
    default_state = Path(env.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "ai-hotspot-digest"
    return {
        "chat_id": env.get("AI_HOTSPOT_CHAT_ID") or str(file_config.get("chat_id") or ""),
        "owner_open_id": env.get("AI_HOTSPOT_OWNER_OPEN_ID") or str(file_config.get("owner_open_id") or ""),
        "state_dir": str(
            Path(env.get("AI_HOTSPOT_STATE_DIR") or file_config.get("state_dir") or default_state).expanduser()
        ),
    }


CONFIG = load_config()
CHAT_ID = CONFIG["chat_id"]
OWNER_OPEN_ID = CONFIG["owner_open_id"]
STATE_DIR = Path(CONFIG["state_dir"])
HISTORY_PATH = STATE_DIR / "history.json"
LIMITS = {"skills": 5, "github": 5, "news": 3}
TRACKING_KEYS = {
    "fbclid",
    "gclid",
    "igshid",
    "mc_cid",
    "mc_eid",
    "ref",
    "ref_src",
    "source",
}
USER_AGENT = "ai-hotspot-digest/1.0 (+Hermes Agent)"
NETWORK_ATTEMPTS = 3
NETWORK_BACKOFF_SECONDS = (2, 5)
TRANSIENT_NETWORK_MARKERS = (
    "connection",
    "network",
    "offline",
    "resolve",
    "timed out",
    "timeout",
    "temporary failure",
    "try again",
    "unreachable",
)

SKILL_QUERIES = (
    "coding agent",
    "claude code",
    "codex",
    "multi agent",
    "react typescript",
    "frontend testing",
    "github workflow",
    "ai video",
)
GITHUB_QUERIES = (
    "agentic coding in:name,description,readme pushed:>=2026-07-01",
    "claude code OR codex in:name,description,readme pushed:>=2026-07-01",
    "agent skill in:name,description,readme pushed:>=2026-07-01",
    "AI React TypeScript in:name,description,readme pushed:>=2026-07-01",
    "AI video generation in:name,description,readme pushed:>=2026-07-01",
)
HN_QUERIES = ("AI agent", "Claude Code", "Codex", "open source AI")
RSS_FEEDS = (
    ("OpenAI", "https://openai.com/news/rss.xml"),
    ("Anthropic", "https://www.anthropic.com/sitemap.xml"),
    ("Google DeepMind", "https://deepmind.google/blog/rss.xml"),
    ("Google AI", "https://blog.google/technology/ai/rss/"),
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def normalize_url(url: str) -> str:
    """Return a stable URL key without fragments or common tracking params."""
    url = (url or "").strip()
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return url
    query = []
    for key, value in urllib.parse.parse_qsl(parsed.query, keep_blank_values=True):
        lower = key.lower()
        if lower.startswith("utm_") or lower in TRACKING_KEYS:
            continue
        query.append((key, value))
    path = re.sub(r"/{2,}", "/", parsed.path or "/")
    if path != "/":
        path = path.rstrip("/")
    return urllib.parse.urlunsplit(
        (parsed.scheme.lower(), parsed.netloc.lower(), path, urllib.parse.urlencode(query), "")
    )


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = parsedate_to_datetime(value)
        except (TypeError, ValueError, OverflowError):
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def load_history(path: Path = HISTORY_PATH) -> dict[str, str]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    links = data.get("links", data) if isinstance(data, dict) else {}
    return links if isinstance(links, dict) else {}


def filter_seen(
    items: Iterable[dict[str, Any]],
    history: dict[str, str],
    *,
    now: datetime | None = None,
    days: int = 7,
) -> list[dict[str, Any]]:
    now = now or utc_now()
    cutoff = now - timedelta(days=days)
    recent = {
        normalize_url(url)
        for url, timestamp in history.items()
        if (parsed := _parse_datetime(timestamp)) is not None and parsed >= cutoff
    }
    return [item for item in items if normalize_url(str(item.get("url", ""))) not in recent]


def _selection_links(selection: dict[str, Any]) -> list[str]:
    links: list[str] = []
    for section in LIMITS:
        for item in selection.get(section, []):
            url = normalize_url(str(item.get("url", "")))
            if url:
                links.append(url)
    return links


def commit_history(
    selection: dict[str, Any],
    *,
    path: Path = HISTORY_PATH,
    now: datetime | None = None,
) -> None:
    now = now or utc_now()
    links = load_history(path)
    cutoff = now - timedelta(days=30)
    links = {
        normalize_url(url): timestamp
        for url, timestamp in links.items()
        if (parsed := _parse_datetime(timestamp)) is not None and parsed >= cutoff
    }
    for url in _selection_links(selection):
        links[url] = now.isoformat()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"updated_at": now.isoformat(), "links": dict(sorted(links.items()))}
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


def _retry_network(operation: Any) -> Any:
    for attempt in range(NETWORK_ATTEMPTS):
        try:
            return operation()
        except urllib.error.HTTPError:
            raise
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            if attempt == NETWORK_ATTEMPTS - 1:
                raise
            time.sleep(NETWORK_BACKOFF_SECONDS[attempt])
    raise RuntimeError("network retry exhausted")


def _is_transient_network_error(error: str) -> bool:
    text = error.lower()
    return any(marker in text for marker in TRANSIENT_NETWORK_MARKERS)


def _http_json(url: str, timeout: int = 20) -> Any:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})

    def fetch() -> Any:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.load(response)

    return _retry_network(fetch)


def _http_text(url: str, timeout: int = 20) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})

    def fetch() -> str:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read().decode("utf-8", errors="replace")

    return _retry_network(fetch)


def _dedupe(items: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in items:
        url = normalize_url(str(item.get("url", "")))
        if not url or url in seen:
            continue
        seen.add(url)
        normalized = dict(item)
        normalized["url"] = url
        output.append(normalized)
    return output


def collect_skills(errors: list[dict[str, str]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for query in SKILL_QUERIES:
        url = "https://www.skills.sh/api/search?" + urllib.parse.urlencode({"q": query})
        try:
            data = _http_json(url)
            for item in data.get("skills", [])[:12]:
                source = str(item.get("source", "")).strip("/")
                skill_id = str(item.get("skillId") or item.get("name") or "").strip("/")
                if not source or not skill_id:
                    continue
                output.append(
                    {
                        "name": str(item.get("name") or skill_id),
                        "url": f"https://skills.sh/{source}/{skill_id}",
                        "source": source,
                        "installs": int(item.get("installs") or 0),
                        "discovered_by": query,
                    }
                )
        except Exception as exc:  # source isolation is intentional
            errors.append({"source": f"skills.sh:{query}", "error": str(exc)[:240]})
    return sorted(_dedupe(output), key=lambda item: item.get("installs", 0), reverse=True)


def _gh_search(query: str) -> dict[str, Any]:
    command = [
        "gh",
        "api",
        "-X",
        "GET",
        "search/repositories",
        "-f",
        f"q={query}",
        "-f",
        "sort=updated",
        "-f",
        "order=desc",
        "-f",
        "per_page=20",
    ]
    for attempt in range(NETWORK_ATTEMPTS):
        result = subprocess.run(command, capture_output=True, text=True, timeout=35, check=False)
        if result.returncode == 0:
            return json.loads(result.stdout)
        error = result.stderr.strip() or f"gh exited {result.returncode}"
        if attempt == NETWORK_ATTEMPTS - 1 or not _is_transient_network_error(error):
            raise RuntimeError(error)
        time.sleep(NETWORK_BACKOFF_SECONDS[attempt])
    raise RuntimeError("GitHub network retry exhausted")


def collect_github(errors: list[dict[str, str]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for query in GITHUB_QUERIES:
        try:
            data = _gh_search(query)
            for item in data.get("items", []):
                if item.get("archived") or item.get("fork"):
                    continue
                output.append(
                    {
                        "name": item.get("full_name"),
                        "url": item.get("html_url"),
                        "description": item.get("description") or "",
                        "stars": int(item.get("stargazers_count") or 0),
                        "language": item.get("language") or "",
                        "pushed_at": item.get("pushed_at"),
                        "topics": item.get("topics") or [],
                        "discovered_by": query,
                    }
                )
        except Exception as exc:
            errors.append({"source": f"github:{query}", "error": str(exc)[:240]})
    return sorted(
        _dedupe(output),
        key=lambda item: (str(item.get("pushed_at") or ""), int(item.get("stars") or 0)),
        reverse=True,
    )


def collect_hn(errors: list[dict[str, str]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    cutoff = int((utc_now() - timedelta(days=3)).timestamp())
    for query in HN_QUERIES:
        params = urllib.parse.urlencode(
            {
                "tags": "story",
                "query": query,
                "hitsPerPage": 20,
                "numericFilters": f"created_at_i>{cutoff}",
            }
        )
        try:
            data = _http_json(f"https://hn.algolia.com/api/v1/search?{params}")
            for item in data.get("hits", []):
                url = item.get("url") or f"https://news.ycombinator.com/item?id={item.get('objectID')}"
                output.append(
                    {
                        "name": item.get("title") or "Hacker News",
                        "url": url,
                        "source": "Hacker News",
                        "points": int(item.get("points") or 0),
                        "comments": int(item.get("num_comments") or 0),
                        "published_at": item.get("created_at"),
                        "hn_url": f"https://news.ycombinator.com/item?id={item.get('objectID')}",
                        "discovered_by": query,
                    }
                )
        except Exception as exc:
            errors.append({"source": f"hn:{query}", "error": str(exc)[:240]})
    return sorted(
        _dedupe(output),
        key=lambda item: (int(item.get("points") or 0), int(item.get("comments") or 0)),
        reverse=True,
    )


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def _child_text(element: ET.Element, names: set[str]) -> str:
    for child in list(element):
        if _local_name(child.tag) in names and child.text:
            return child.text.strip()
    return ""


def parse_feed_xml(xml_text: str, *, source: str, feed_url: str) -> list[dict[str, Any]]:
    root = ET.fromstring(xml_text)
    if _local_name(root.tag) == "urlset":
        output: list[dict[str, Any]] = []
        for node in list(root):
            link = _child_text(node, {"loc"})
            if source == "Anthropic" and "/news/" not in link:
                continue
            published = _child_text(node, {"lastmod"})
            slug = urllib.parse.urlsplit(link).path.rstrip("/").rsplit("/", 1)[-1]
            title = urllib.parse.unquote(slug).replace("-", " ").strip().title()
            if title and link:
                output.append(
                    {
                        "name": title,
                        "url": link,
                        "source": source,
                        "published_at": published,
                        "description": "",
                    }
                )
        return output

    output = []
    entries = [node for node in root.iter() if _local_name(node.tag) in {"item", "entry"}]
    for entry in entries[:20]:
        title = _child_text(entry, {"title"})
        link = _child_text(entry, {"link"})
        if not link:
            for child in list(entry):
                if _local_name(child.tag) == "link" and child.attrib.get("href"):
                    link = child.attrib["href"]
                    break
        published = _child_text(entry, {"pubdate", "published", "updated"})
        summary = _child_text(entry, {"description", "summary"})
        if title and link:
            output.append(
                {
                    "name": title,
                    "url": link,
                    "source": source,
                    "published_at": published,
                    "description": re.sub(r"<[^>]+>", " ", summary).strip()[:500],
                }
            )
    return output


def collect_rss(errors: list[dict[str, str]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for source, feed_url in RSS_FEEDS:
        try:
            output.extend(parse_feed_xml(_http_text(feed_url), source=source, feed_url=feed_url))
        except Exception as exc:
            errors.append({"source": f"rss:{source}", "error": str(exc)[:240]})
    return _dedupe(output)


def collect_candidates(history_path: Path = HISTORY_PATH) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    history = load_history(history_path)
    skills = filter_seen(collect_skills(errors), history)
    github = filter_seen(collect_github(errors), history)
    news = filter_seen(collect_rss(errors) + collect_hn(errors), history)
    news = sorted(
        _dedupe(news),
        key=lambda item: (
            _parse_datetime(str(item.get("published_at") or "")) or datetime(1970, 1, 1, tzinfo=timezone.utc),
            int(item.get("points") or 0),
        ),
        reverse=True,
    )
    return {
        "collected_at": utc_now().isoformat(),
        "history_path": str(history_path),
        "errors": errors,
        "skills": skills[:50],
        "github": github[:50],
        "news": news[:50],
    }


def validate_selection(selection: dict[str, Any]) -> None:
    if not isinstance(selection, dict):
        raise ValueError("selection must be an object")
    for section, limit in LIMITS.items():
        items = selection.get(section, [])
        if not isinstance(items, list):
            raise ValueError(f"{section} must be a list")
        if len(items) > limit:
            raise ValueError(f"{section} exceeds limit {limit}")
        for index, item in enumerate(items):
            if not isinstance(item, dict):
                raise ValueError(f"{section}[{index}] must be an object")
            for field in ("name", "url", "reason"):
                if not str(item.get(field, "")).strip():
                    raise ValueError(f"{section}[{index}] missing {field}")
            parsed = urllib.parse.urlsplit(str(item["url"]))
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ValueError(f"{section}[{index}] invalid url")


def _clean_text(value: str, limit: int) -> str:
    value = re.sub(r"\s+", " ", str(value)).strip()
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip() + "…"


def _escape_md(value: str) -> str:
    return re.sub(r"([\\\[\]*_`])", r"\\\1", _clean_text(value, 160))


def _humanize_title(value: str) -> str:
    """Turn a machine slug into a readable title while preserving common product names."""
    words = re.split(r"[-_\s]+", _clean_text(value, 120))
    special = {
        "ai": "AI",
        "api": "API",
        "ci": "CI",
        "cli": "CLI",
        "codex": "Codex",
        "github": "GitHub",
        "git": "Git",
        "mcp": "MCP",
        "pr": "PR",
        "react": "React",
        "typescript": "TypeScript",
        "ui": "UI",
        "ux": "UX",
    }
    return " ".join(special.get(word.lower(), word.capitalize()) for word in words if word)


def _item_identity(section: str, item: dict[str, Any]) -> tuple[str, str]:
    name = _clean_text(item["name"], 120)
    url = normalize_url(item["url"])
    parsed = urllib.parse.urlsplit(url)
    path_parts = [urllib.parse.unquote(part) for part in parsed.path.strip("/").split("/") if part]
    if section == "skills":
        title = _humanize_title(name)
        source = " / ".join(path_parts[:-1]) if len(path_parts) > 1 else parsed.netloc
        return title, source
    if section == "github":
        return name, "GitHub 仓库"
    return name, parsed.netloc.removeprefix("www.")


def _item_container(section: str, index: int, item: dict[str, Any], *, last: bool) -> dict[str, Any]:
    title, meta = _item_identity(section, item)
    url = normalize_url(item["url"])
    reason = _escape_md(item["reason"])
    styles = {
        "skills": ("blue-100", "blue-50", "查看 Skill →"),
        "github": ("green-100", "green-50", "查看 GitHub →"),
        "news": ("orange-100", "orange-50", "查看新闻原文 →"),
    }
    border, background, action = styles[section]
    return {
        "tag": "interactive_container",
        "element_id": f"item_{section}_{index}",
        "behaviors": [{"type": "open_url", "default_url": url}],
        "width": "fill",
        "has_border": True,
        "border_color": border,
        "corner_radius": "8px",
        "background_style": background,
        "padding": "12px 12px 10px 12px",
        "vertical_spacing": "4px",
        "margin": "0px 0px 14px 0px" if last else "0px 0px 8px 0px",
        "elements": [
            {
                "tag": "markdown",
                "element_id": f"name_{section}_{index}",
                "content": f"**{index}. {_escape_md(title)}**",
            },
            {
                "tag": "markdown",
                "element_id": f"meta_{section}_{index}",
                "content": f"<font color='grey'>{_escape_md(meta)}</font>",
                "text_size": "caption",
            },
            {
                "tag": "markdown",
                "element_id": f"reason_{section}_{index}",
                "content": f"<font color='grey'>{reason}</font>",
            },
            {
                "tag": "markdown",
                "element_id": f"link_{section}_{index}",
                "content": f"[{action}]({url})",
                "text_size": "caption",
            },
        ],
    }


def _section_elements(section: str, title: str, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    icons = {"skills": "🧩", "github": "⌘", "news": "◉"}
    elements: list[dict[str, Any]] = [
        {
            "tag": "markdown",
            "element_id": f"section_{section}",
            "content": f"### {icons[section]} {title} · {len(items)} 条",
            "margin": "4px 0px 8px 0px",
        }
    ]
    if not items:
        elements.append(
            {
                "tag": "markdown",
                "element_id": f"empty_{section}",
                "content": "<font color='grey'>今日没有达到推荐门槛的内容。</font>",
                "margin": "0px 0px 14px 0px",
            }
        )
        return elements
    elements.extend(
        _item_container(section, index, item, last=index == len(items))
        for index, item in enumerate(items, 1)
    )
    return elements


def build_card(selection: dict[str, Any], *, title: str = "AI 热点早报") -> dict[str, Any]:
    validate_selection(selection)
    counts = {section: len(selection.get(section, [])) for section in LIMITS}
    total = sum(counts.values())
    metric_columns = []
    for section, label, color in (
        ("skills", "Skills", "blue"),
        ("github", "GitHub", "green"),
        ("news", "AI 新闻", "orange"),
    ):
        metric_columns.append(
            {
                "tag": "column",
                "width": "weighted",
                "weight": 1,
                "background_style": "grey-50",
                "padding": "8px",
                "vertical_spacing": "2px",
                "elements": [
                    {"tag": "markdown", "content": f"## <font color='{color}'>{counts[section]}</font>", "text_align": "center"},
                    {"tag": "markdown", "content": f"<font color='grey'>{label}</font>", "text_align": "center", "text_size": "caption"},
                ],
            }
        )
    metric = {
        "tag": "column_set",
        "element_id": "summary",
        "flex_mode": "none",
        "horizontal_spacing": "8px",
        "margin": "0px 0px 12px 0px",
        "columns": metric_columns,
    }
    elements = [metric]
    elements.extend(_section_elements("skills", "Skills", selection.get("skills", [])))
    elements.extend(_section_elements("github", "GitHub", selection.get("github", [])))
    elements.extend(_section_elements("news", "AI 新闻", selection.get("news", [])))
    local_date = datetime.now().astimezone().strftime("%Y-%m-%d")
    return {
        "schema": "2.0",
        "config": {
            "update_multi": True,
            "width_mode": "default",
            "enable_forward": True,
            "streaming_mode": False,
            "summary": {"content": f"{title} · {total} 条精选"},
            "style": {
                "text_size": {
                    "caption": {"default": "notation", "pc": "notation", "mobile": "notation"}
                }
            },
        },
        "header": {
            "title": {"tag": "plain_text", "content": _clean_text(title, 60)},
            "subtitle": {"tag": "plain_text", "content": f"{local_date} · 工具、项目与重要动态"},
            "template": "blue",
            "icon": {"tag": "standard_icon", "token": "ai-common_colorful"},
            "text_tag_list": [
                {"tag": "text_tag", "text": {"tag": "plain_text", "content": "每日 09:00"}, "color": "blue"}
            ],
        },
        "body": {
            "direction": "vertical",
            "padding": "12px 12px 20px 12px",
            "vertical_spacing": "0px",
            "elements": elements,
        },
    }


def build_markdown(selection: dict[str, Any], *, title: str) -> str:
    validate_selection(selection)
    lines = [f"# {title}"]
    for section, label in (("skills", "Skills"), ("github", "GitHub"), ("news", "AI 新闻")):
        lines.extend(["", f"## {label}"])
        items = selection.get(section, [])
        if not items:
            lines.append("- 今日没有达到推荐门槛的内容。")
        for item in items:
            lines.append(f"- [{item['name']}]({normalize_url(item['url'])})：{item['reason']}")
    return "\n".join(lines)


def _parse_lark_result(result: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    text = result.stdout.strip() if result.returncode == 0 else result.stderr.strip()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"lark-cli returned non-JSON: {text[:300]}") from exc
    if result.returncode != 0 or payload.get("ok") is not True:
        raise RuntimeError(json.dumps(payload, ensure_ascii=False)[:800])
    return payload


def _run_lark(command: list[str], *, timeout: int) -> subprocess.CompletedProcess[str]:
    env = {
        **os.environ,
        "LARKSUITE_CLI_NO_UPDATE_NOTIFIER": "1",
        "LARKSUITE_CLI_NO_SKILLS_NOTIFIER": "1",
    }
    last_result: subprocess.CompletedProcess[str] | None = None
    for attempt in range(NETWORK_ATTEMPTS):
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
                env=env,
            )
        except (subprocess.TimeoutExpired, OSError) as exc:
            if attempt == NETWORK_ATTEMPTS - 1:
                raise RuntimeError(f"lark-cli network retry exhausted: {exc}") from exc
            time.sleep(NETWORK_BACKOFF_SECONDS[attempt])
            continue
        last_result = result
        if result.returncode == 0:
            return result
        error = f"{result.stderr}\n{result.stdout}"
        if attempt == NETWORK_ATTEMPTS - 1 or not _is_transient_network_error(error):
            return result
        time.sleep(NETWORK_BACKOFF_SECONDS[attempt])
    if last_result is None:
        raise RuntimeError("lark-cli network retry exhausted")
    return last_result


def _message_id(payload: dict[str, Any]) -> str:
    data = payload.get("data") or {}
    for key in ("message_id", "messageId"):
        if data.get(key):
            return str(data[key])
    message = data.get("message") or data.get("item") or {}
    for key in ("message_id", "messageId"):
        if message.get(key):
            return str(message[key])
    return ""


def send_selection(
    selection: dict[str, Any],
    *,
    chat_id: str = CHAT_ID,
    title: str = "AI 热点早报",
    history_path: Path = HISTORY_PATH,
    dry_run: bool = False,
    acceptance: bool = False,
) -> dict[str, Any]:
    validate_selection(selection)
    if not chat_id and not dry_run:
        raise RuntimeError("chat_id missing: set AI_HOTSPOT_CHAT_ID or references/local-config.json")
    card = build_card(selection, title=title)
    digest_hash = hashlib.sha256(json.dumps(selection, sort_keys=True).encode()).hexdigest()[:10]
    key_kind = "acceptance" if acceptance else "daily"
    key = f"ai-digest-{key_kind}-{datetime.now().astimezone():%Y%m%d}-{digest_hash}"[:50]
    card_command = [
        "lark-cli", "im", "+messages-send", "--as", "bot", "--chat-id", chat_id,
        "--msg-type", "interactive", "--content", json.dumps(card, ensure_ascii=False),
        "--idempotency-key", key,
    ]
    if dry_run:
        return {"ok": True, "dry_run": True, "mode": "interactive", "card": card, "command": card_command[:8] + ["<card_json>"]}
    result = _run_lark(card_command, timeout=45)
    try:
        payload = _parse_lark_result(result)
        mode = "interactive"
    except RuntimeError as card_error:
        if acceptance:
            raise RuntimeError(f"acceptance card failed: {card_error}") from card_error
        markdown = build_markdown(selection, title=title)
        fallback_command = [
            "lark-cli", "im", "+messages-send", "--as", "bot", "--chat-id", chat_id,
            "--markdown", markdown, "--idempotency-key", f"{key}-md"[:50],
        ]
        fallback = _run_lark(fallback_command, timeout=45)
        try:
            payload = _parse_lark_result(fallback)
        except RuntimeError as fallback_error:
            raise RuntimeError(f"card failed: {card_error}; fallback failed: {fallback_error}") from fallback_error
        mode = "post"
    if not acceptance:
        commit_history(selection, path=history_path)
    return {
        "ok": True,
        "mode": mode,
        "message_id": _message_id(payload),
        "counts": {section: len(selection.get(section, [])) for section in LIMITS},
        "history_path": str(history_path),
        "acceptance": acceptance,
        "history_committed": not acceptance,
        "raw": payload,
    }


def send_owner_alert(text: str, *, owner_open_id: str = OWNER_OPEN_ID) -> dict[str, Any]:
    if not owner_open_id:
        raise RuntimeError("owner_open_id missing: set AI_HOTSPOT_OWNER_OPEN_ID or references/local-config.json")
    command = [
        "lark-cli", "im", "+messages-send", "--as", "bot", "--user-id", owner_open_id,
        "--text", _clean_text(text, 1000),
    ]
    result = _run_lark(command, timeout=30)
    return _parse_lark_result(result)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path | None, payload: Any) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    collect_parser = sub.add_parser("collect")
    collect_parser.add_argument("--output", type=Path)
    collect_parser.add_argument("--history", type=Path, default=HISTORY_PATH)

    render_parser = sub.add_parser("render")
    render_parser.add_argument("--input", type=Path, required=True)
    render_parser.add_argument("--output", type=Path)
    render_parser.add_argument("--title", default="AI 热点早报")

    publish_parser = sub.add_parser("publish")
    publish_parser.add_argument("--input", type=Path, required=True)
    publish_parser.add_argument("--chat-id", default=CHAT_ID)
    publish_parser.add_argument("--title", default="AI 热点早报")
    publish_parser.add_argument("--history", type=Path, default=HISTORY_PATH)
    publish_mode = publish_parser.add_mutually_exclusive_group()
    publish_mode.add_argument("--dry-run", action="store_true")
    publish_mode.add_argument("--acceptance", action="store_true")

    alert_parser = sub.add_parser("alert-owner")
    alert_parser.add_argument("--text", required=True)

    args = parser.parse_args(argv)
    try:
        if args.command == "collect":
            payload = collect_candidates(args.history)
            _write_json(args.output, payload)
        elif args.command == "render":
            selection = _load_json(args.input)
            _write_json(args.output, build_card(selection, title=args.title))
        elif args.command == "publish":
            selection = _load_json(args.input)
            _write_json(
                None,
                send_selection(
                    selection,
                    chat_id=args.chat_id,
                    title=args.title,
                    history_path=args.history,
                    dry_run=args.dry_run,
                    acceptance=args.acceptance,
                ),
            )
        elif args.command == "alert-owner":
            _write_json(None, send_owner_alert(args.text))
        return 0
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
