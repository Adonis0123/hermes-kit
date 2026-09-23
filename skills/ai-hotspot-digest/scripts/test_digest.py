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
                result = digest.send_selection(selected, chat_id="oc_example", history_path=history_path)

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
            with patch.object(digest.subprocess, "run", return_value=response) as run:
                result = digest.send_selection(
                    selected,
                    chat_id="oc_example",
                    history_path=history_path,
                    acceptance=True,
                )

            self.assertEqual(run.call_count, 1)
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

    def test_publish_without_chat_id_fails_before_sending(self):
        selected = {"skills": [{"name": "x", "url": "https://skills.sh/x", "reason": "x"}], "github": [], "news": []}
        with patch.object(digest.subprocess, "run") as run:
            with self.assertRaises(RuntimeError):
                digest.send_selection(selected, chat_id="", history_path=Path("/nonexistent/h.json"))
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
