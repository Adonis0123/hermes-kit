#!/usr/bin/env python3
import importlib.util
import json
import subprocess
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

MODULE_PATH = Path(__file__).with_name("digest.py")
spec = importlib.util.spec_from_file_location("digest", MODULE_PATH)
digest = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(digest)


class NormalizeUrlTests(unittest.TestCase):
    def test_removes_tracking_and_fragment(self):
        actual = digest.normalize_url(
            "https://github.com/Owner/Repo/?utm_source=x&ref=feed#readme"
        )
        self.assertEqual(actual, "https://github.com/Owner/Repo")

    def test_keeps_semantic_query_parameters(self):
        actual = digest.normalize_url(
            "https://example.com/search?q=agent&utm_campaign=daily"
        )
        self.assertEqual(actual, "https://example.com/search?q=agent")


class SeenHistoryTests(unittest.TestCase):
    def test_filters_only_links_seen_within_seven_days(self):
        now = datetime(2026, 8, 2, tzinfo=timezone.utc)
        items = [
            {"url": "https://github.com/a/new"},
            {"url": "https://github.com/a/recent?utm_source=x"},
            {"url": "https://github.com/a/old"},
        ]
        history = {
            "https://github.com/a/recent": (now - timedelta(days=2)).isoformat(),
            "https://github.com/a/old": (now - timedelta(days=8)).isoformat(),
        }
        kept = digest.filter_seen(items, history, now=now, days=7)
        self.assertEqual(
            [item["url"] for item in kept],
            ["https://github.com/a/new", "https://github.com/a/old"],
        )


class SelectionTests(unittest.TestCase):
    def test_rejects_over_limit_and_missing_fields(self):
        over = {
            "skills": [
                {"name": f"s{i}", "url": f"https://skills.sh/s{i}", "reason": "可用"}
                for i in range(6)
            ],
            "github": [],
            "news": [],
        }
        with self.assertRaisesRegex(ValueError, "skills.*5"):
            digest.validate_selection(over)

        missing = {
            "skills": [{"name": "x", "url": "https://skills.sh/x"}],
            "github": [],
            "news": [],
        }
        with self.assertRaisesRegex(ValueError, "reason"):
            digest.validate_selection(missing)

    def test_card_is_v2_grouped_and_contains_links(self):
        selected = {
            "skills": [
                {
                    "name": "Agent Browser",
                    "url": "https://skills.sh/example/agent-browser",
                    "reason": "适合自动化验证网页。",
                }
            ],
            "github": [
                {
                    "name": "owner/repo",
                    "url": "https://github.com/owner/repo",
                    "reason": "值得关注的 Agent 工具。",
                }
            ],
            "news": [
                {
                    "name": "模型发布",
                    "url": "https://example.com/news",
                    "reason": "影响 coding Agent。",
                }
            ],
        }
        card = digest.build_card(selected, title="AI 热点早报 · 测试")
        self.assertEqual(card["schema"], "2.0")
        self.assertFalse(card["config"].get("streaming_mode", False))
        self.assertEqual(card["header"]["template"], "blue")
        containers = [
            item
            for item in card["body"]["elements"]
            if item.get("tag") == "interactive_container"
        ]
        self.assertEqual(len(containers), 3)
        self.assertTrue(all(item.get("behaviors") for item in containers))
        metric_columns = card["body"]["elements"][0]["columns"]
        self.assertEqual(len(metric_columns), 3)
        self.assertTrue(all("corner_radius" not in column for column in metric_columns))
        encoded = json.dumps(card, ensure_ascii=False)
        self.assertIn("https://skills.sh/example/agent-browser", encoded)
        self.assertIn("https://github.com/owner/repo", encoded)
        self.assertIn("https://example.com/news", encoded)
        skill_text = json.dumps(containers[0], ensure_ascii=False)
        self.assertIn("**1. Agent Browser**", skill_text)
        self.assertIn("example", skill_text)
        self.assertIn("<font color='grey'>适合自动化验证网页。</font>", skill_text)
        self.assertIn("[查看 Skill →](https://skills.sh/example/agent-browser)", skill_text)
        self.assertNotIn("[Agent Browser]", skill_text)

    def test_skill_slug_is_rendered_as_complete_human_title(self):
        self.assertEqual(digest._humanize_title("agent-sdk"), "Agent SDK")
        selected = {
            "skills": [
                {
                    "name": "physical-ai-video-data-augmentation",
                    "url": "https://skills.sh/nvidia/skills/physical-ai-video-data-augmentation",
                    "reason": "适合视频数据管线。",
                }
            ],
            "github": [],
            "news": [],
        }
        encoded = json.dumps(digest.build_card(selected), ensure_ascii=False)
        self.assertIn("Physical AI Video Data Augmentation", encoded)
        self.assertIn("nvidia / skills", encoded)
        authored = {
            "skills": [
                {
                    "name": "Build Agents with eve",
                    "url": "https://skills.sh/vercel/vercel-plugin/build-agents",
                    "reason": "适合做可部署的 Agent。",
                }
            ],
            "github": [],
            "news": [],
        }
        authored_card = json.dumps(digest.build_card(authored), ensure_ascii=False)
        self.assertIn("Build Agents with eve", authored_card)
        self.assertNotIn("Build Agents With Eve", authored_card)


class FeedParsingTests(unittest.TestCase):
    def test_parses_anthropic_news_sitemap(self):
        xml = """<?xml version='1.0'?>
        <urlset xmlns='http://www.sitemaps.org/schemas/sitemap/0.9'>
          <url><loc>https://www.anthropic.com/news/test-release</loc><lastmod>2026-08-01</lastmod></url>
          <url><loc>https://www.anthropic.com/research/ignored</loc><lastmod>2026-08-01</lastmod></url>
        </urlset>"""
        items = digest.parse_feed_xml(xml, source="Anthropic", feed_url="https://www.anthropic.com/sitemap.xml")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["name"], "Test Release")
        self.assertEqual(items[0]["url"], "https://www.anthropic.com/news/test-release")


RSS_SAMPLE = (
    "<?xml version='1.0' encoding='utf-8'?><rss version='2.0'><channel>"
    "<item><title>Gemini 更新</title><link>https://deepmind.google/blog/x/</link>"
    "<pubDate>Tue, 03 Nov 2026 10:00:00 +0000</pubDate></item></channel></rss>"
)


def _fake_response(body, headers=None, status=200):
    from email.message import Message

    message = Message()
    for key, value in (headers or {}).items():
        message[key] = value
    response = MagicMock()
    response.__enter__.return_value = response
    response.__exit__.return_value = False
    response.read.return_value = body
    response.headers = message
    response.status = status
    return response


class HttpTextDecodingTests(unittest.TestCase):
    def _fetch(self, body, headers=None):
        with patch.object(digest.urllib.request, "urlopen", return_value=_fake_response(body, headers)):
            return digest._http_text("https://example.com/rss.xml")

    def test_gzip_body_with_content_encoding_is_decompressed(self):
        import gzip

        text = self._fetch(gzip.compress(RSS_SAMPLE.encode("utf-8")), {"Content-Encoding": "gzip"})
        items = digest.parse_feed_xml(text, source="Google DeepMind", feed_url="u")
        self.assertEqual([item["name"] for item in items], ["Gemini 更新"])

    def test_gzip_magic_without_header_is_decompressed(self):
        import gzip

        text = self._fetch(gzip.compress(RSS_SAMPLE.encode("utf-8")), {"Content-Type": "application/xml"})
        self.assertTrue(text.startswith("<?xml"))

    def test_deflate_body_is_decompressed(self):
        import zlib

        text = self._fetch(zlib.compress(RSS_SAMPLE.encode("utf-8")), {"Content-Encoding": "deflate"})
        self.assertTrue(text.startswith("<?xml"))

    def test_utf8_bom_is_stripped(self):
        text = self._fetch(b"\xef\xbb\xbf" + RSS_SAMPLE.encode("utf-8"), {"Content-Type": "application/xml; charset=utf-8"})
        self.assertTrue(text.startswith("<?xml"))
        self.assertEqual(len(digest.parse_feed_xml(text, source="s", feed_url="u")), 1)

    def test_declared_charset_is_used(self):
        body = RSS_SAMPLE.replace("Gemini 更新", "café").replace("utf-8", "iso-8859-1").encode("latin-1")
        text = self._fetch(body, {"Content-Type": "application/rss+xml; charset=ISO-8859-1"})
        self.assertIn("café", text)

    def test_parse_failure_records_status_and_head(self):
        html = b"<html><body>Service unavailable</body></html>" + b"x" * 400
        with patch.object(digest, "RSS_FEEDS", [("Google DeepMind", "https://deepmind.google/blog/rss.xml")]), \
             patch.object(digest.urllib.request, "urlopen", return_value=_fake_response(html, {"Content-Type": "text/html"}, 200)):
            errors = []
            items = digest.collect_rss(errors)

        self.assertEqual(items, [])
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0]["source"], "rss:Google DeepMind")
        self.assertEqual(errors[0]["status"], "200")
        self.assertEqual(errors[0]["head"], repr(html[:200]))
        self.assertIn("Service unavailable", errors[0]["head"])


class NetworkRetryTests(unittest.TestCase):
    def test_http_json_retries_transient_network_error(self):
        response = MagicMock()
        response.__enter__.return_value = response
        response.__exit__.return_value = False
        response.read.return_value = b'{"ok": true}'
        with patch.object(
            digest.urllib.request,
            "urlopen",
            side_effect=[digest.urllib.error.URLError("offline"), response],
        ) as urlopen, patch.object(digest.time, "sleep") as sleep:
            payload = digest._http_json("https://example.com")

        self.assertEqual(payload, {"ok": True})
        self.assertEqual(urlopen.call_count, 2)
        sleep.assert_called_once()

    def test_github_search_retries_transient_cli_failure(self):
        offline = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="network is unreachable"
        )
        success = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=json.dumps({"items": []}), stderr=""
        )
        with patch.object(digest.subprocess, "run", side_effect=[offline, success]) as run, patch.object(
            digest.time, "sleep"
        ) as sleep:
            payload = digest._gh_search("agent")

        self.assertEqual(payload, {"items": []})
        self.assertEqual(run.call_count, 2)
        sleep.assert_called_once()

    def test_publish_retries_card_before_markdown_fallback(self):
        selected = {
            "skills": [
                {"name": "Example Skill", "url": "https://skills.sh/example", "reason": "用于验收。"}
            ],
            "github": [],
            "news": [],
        }
        offline = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr=json.dumps({"ok": False, "error": "offline"})
        )
        success = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=json.dumps({"ok": True, "data": {"message_id": "om_retry"}}), stderr=""
        )
        with tempfile.TemporaryDirectory() as tmp:
            history_path = Path(tmp) / "history.json"
            with patch.object(digest.subprocess, "run", side_effect=[offline, success]) as run, patch.object(
                digest.time, "sleep"
            ):
                result = digest.send_selection(
                    selected, chat_id="oc_example", history_path=history_path, archive_dir=Path(tmp) / "archive"
                )

        self.assertEqual(run.call_count, 2)
        self.assertEqual(result["mode"], "interactive")
        self.assertEqual(result["message_id"], "om_retry")


class AcceptancePublishTests(unittest.TestCase):
    def test_acceptance_sends_one_card_without_writing_history(self):
        selected = {
            "skills": [
                {"name": "Example Skill", "url": "https://skills.sh/example", "reason": "用于验收。"}
            ],
            "github": [],
            "news": [],
        }
        response = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps({"ok": True, "data": {"message_id": "om_acceptance"}}),
            stderr="",
        )
        with tempfile.TemporaryDirectory() as tmp:
            history_path = Path(tmp) / "history.json"
            archive_dir = Path(tmp) / "archive"
            with patch.object(digest.subprocess, "run", return_value=response) as run:
                result = digest.send_selection(
                    selected,
                    chat_id="oc_example",
                    history_path=history_path,
                    archive_dir=archive_dir,
                    acceptance=True,
                )

            self.assertEqual(run.call_count, 1)
            self.assertFalse(archive_dir.exists())
            self.assertNotIn("archive_path", result)
            command = run.call_args.args[0]
            self.assertIn("interactive", command)
            self.assertTrue(any("acceptance" in part for part in command))
            self.assertFalse(history_path.exists())
            self.assertTrue(result["acceptance"])
            self.assertFalse(result["history_committed"])


class HistoryCommitTests(unittest.TestCase):
    def test_history_is_written_with_normalized_urls(self):
        selected = {
            "skills": [
                {
                    "name": "x",
                    "url": "https://skills.sh/x/?utm_source=test",
                    "reason": "x",
                }
            ],
            "github": [],
            "news": [],
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "history.json"
            digest.commit_history(selected, path=path, now=datetime(2026, 8, 2, tzinfo=timezone.utc))
            data = json.loads(path.read_text())
            self.assertIn("https://skills.sh/x", data["links"])


ARCHIVE_SELECTION = {
    "skills": [
        {"name": " Skill A ", "url": "https://skills.sh/a/?utm_source=x", "reason": " 理由 A "},
        {"name": "Skill B", "url": "https://skills.sh/b", "reason": "理由 B"},
    ],
    "github": [{"name": "owner/repo", "url": "https://github.com/owner/repo", "reason": "值得关注。"}],
    "news": [],
}


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _local(year: int, month: int, day: int) -> datetime:
    return datetime(year, month, day, 12, 0).astimezone()


class ArchiveTests(unittest.TestCase):
    def test_writes_monthly_jsonl_with_fields_and_rank(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive_dir = Path(tmp) / "archive"
            now = _local(2026, 8, 2)
            path = digest.archive_selection(
                ARCHIVE_SELECTION, message_id="om_1", mode="interactive", archive_dir=archive_dir, now=now
            )
            self.assertEqual(path, archive_dir / "2026-08.jsonl")
            raw = path.read_text(encoding="utf-8")
            self.assertIn("理由 A", raw)
            records = _read_jsonl(path)

        self.assertEqual(len(records), 3)
        first = records[0]
        self.assertEqual(
            set(first),
            {"v", "date", "at", "category", "rank", "name", "url", "reason", "message_id", "mode"},
        )
        self.assertEqual(first["v"], 1)
        self.assertEqual(first["date"], "2026-08-02")
        self.assertEqual(first["at"], now.isoformat())
        self.assertEqual(first["name"], "Skill A")
        self.assertEqual(first["reason"], "理由 A")
        self.assertEqual(first["url"], "https://skills.sh/a")
        self.assertEqual(first["message_id"], "om_1")
        self.assertEqual(first["mode"], "interactive")
        self.assertEqual(
            [(r["category"], r["rank"]) for r in records],
            [("skills", 1), ("skills", 2), ("github", 1)],
        )

    def test_rerun_with_same_message_id_does_not_duplicate(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive_dir = Path(tmp)
            now = _local(2026, 8, 2)
            for _ in range(2):
                digest.archive_selection(
                    ARCHIVE_SELECTION, message_id="om_1", mode="interactive", archive_dir=archive_dir, now=now
                )
            self.assertEqual(len(_read_jsonl(archive_dir / "2026-08.jsonl")), 3)
            digest.archive_selection(
                ARCHIVE_SELECTION, message_id="om_2", mode="post", archive_dir=archive_dir, now=now
            )
            self.assertEqual(len(_read_jsonl(archive_dir / "2026-08.jsonl")), 6)

    def test_prunes_whole_months_older_than_retention(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive_dir = Path(tmp)
            # today 2026-11-02, cutoff = 2026-08-04: July ends before it, August contains it.
            for name in ("2026-07.jsonl", "2026-06.jsonl", "2026-08.jsonl", "notes.txt", "2026-07.jsonl.bak"):
                (archive_dir / name).write_text("{}\n", encoding="utf-8")
            digest.archive_selection(
                ARCHIVE_SELECTION, message_id="om_1", mode="interactive", archive_dir=archive_dir,
                now=_local(2026, 11, 2), retention_days=90,
            )
            remaining = sorted(path.name for path in archive_dir.iterdir())

        self.assertEqual(
            remaining, ["2026-07.jsonl.bak", "2026-08.jsonl", "2026-11.jsonl", "notes.txt"]
        )

    def test_publish_succeeds_when_archive_fails(self):
        response = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=json.dumps({"ok": True, "data": {"message_id": "om_x"}}), stderr=""
        )
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(digest, "_run_lark", return_value=response), patch.object(
                digest, "archive_selection", side_effect=OSError("disk full")
            ) as archive:
                result = digest.send_selection(
                    ARCHIVE_SELECTION,
                    chat_id="oc_example",
                    history_path=Path(tmp) / "history.json",
                    archive_dir=Path(tmp) / "archive",
                )

        archive.assert_called_once()
        self.assertTrue(result["ok"])
        self.assertTrue(result["history_committed"])
        self.assertEqual(result["archive_error"], "disk full")
        self.assertNotIn("archive_path", result)

    def test_publish_writes_archive_on_success(self):
        response = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=json.dumps({"ok": True, "data": {"message_id": "om_ok"}}), stderr=""
        )
        with tempfile.TemporaryDirectory() as tmp:
            archive_dir = Path(tmp) / "archive"
            with patch.object(digest, "_run_lark", return_value=response):
                result = digest.send_selection(
                    ARCHIVE_SELECTION,
                    chat_id="oc_example",
                    history_path=Path(tmp) / "history.json",
                    archive_dir=archive_dir,
                )
            records = _read_jsonl(Path(result["archive_path"]))

        self.assertNotIn("archive_error", result)
        self.assertEqual(len(records), 3)
        self.assertTrue(all(r["message_id"] == "om_ok" and r["mode"] == "interactive" for r in records))

    def test_publish_cli_passes_archive_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            selection_path = Path(tmp) / "selection.json"
            selection_path.write_text(json.dumps(ARCHIVE_SELECTION), encoding="utf-8")
            with patch.object(digest, "send_selection", return_value={"ok": True}) as send, patch.object(
                digest, "_write_json"
            ):
                code = digest.main([
                    "publish", "--input", str(selection_path), "--chat-id", "oc_example",
                    "--archive-dir", str(Path(tmp) / "arc"), "--dry-run",
                ])
        self.assertEqual(code, 0)
        self.assertEqual(send.call_args.kwargs["archive_dir"], Path(tmp) / "arc")


class ConfigTests(unittest.TestCase):
    def test_env_overrides_local_config_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "local-config.json"
            path.write_text(json.dumps({"chat_id": "oc_file", "owner_open_id": "ou_file", "state_dir": tmp}))
            config = digest.load_config(env={"AI_HOTSPOT_CHAT_ID": "oc_env"}, config_path=path)
        self.assertEqual(config["chat_id"], "oc_env")
        self.assertEqual(config["owner_open_id"], "ou_file")
        self.assertEqual(config["state_dir"], tmp)

    def test_missing_config_leaves_targets_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = digest.load_config(env={"XDG_CACHE_HOME": tmp}, config_path=Path(tmp) / "absent.json")
        self.assertEqual(config["chat_id"], "")
        self.assertEqual(config["owner_open_id"], "")
        self.assertEqual(config["state_dir"], str(Path(tmp) / "ai-hotspot-digest"))

    def test_collect_deadline_returns_error_and_alerts_owner(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "candidates.json"
            with patch.object(digest, "collect_candidates", side_effect=digest.CollectDeadline("collect exceeded 90s")), \
                 patch.object(digest, "send_owner_alert", return_value={"ok": True}) as alert:
                code = digest.main(["collect", "--output", str(output), "--history", str(Path(tmp) / "history.json")])
            payload = json.loads(output.read_text())
        self.assertEqual(code, 1)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["errors"][0]["source"], "deadline")
        self.assertTrue(payload["owner_alerted"])
        alert.assert_called_once_with("早报没发：采集超时")

    def test_publish_without_chat_id_fails_before_sending(self):
        selected = {"skills": [{"name": "x", "url": "https://skills.sh/x", "reason": "x"}], "github": [], "news": []}
        with patch.object(digest.subprocess, "run") as run:
            with self.assertRaises(RuntimeError):
                digest.send_selection(selected, chat_id="", history_path=Path("/nonexistent/h.json"))
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
