import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import figma_copy as fc  # noqa: E402


def test_parse_figma_url_reads_key_and_node():
    url = "https://www.figma.com/design/LHKh/%E7%89%88?node-id=132337-127597&m=dev"
    assert fc.parse_figma_url(url) == ("LHKh", "132337:127597")


def test_parse_figma_url_prefers_branch_key():
    url = "https://www.figma.com/design/MAIN/branch/BR/x?node-id=1-2"
    assert fc.parse_figma_url(url) == ("BR", "1:2")


def test_parse_figma_url_requires_node_id():
    with pytest.raises(ValueError, match="node-id"):
        fc.parse_figma_url("https://www.figma.com/design/LHKh/x")


def test_collect_texts_skips_hidden_and_offsets_from_frame():
    frame = {"id": "1:1", "type": "FRAME", "name": "F", "absoluteBoundingBox": {"x": 100, "y": 50},
             "children": [
                 {"id": "1:2", "type": "TEXT", "name": "t", "characters": " Hello ",
                  "absoluteBoundingBox": {"x": 110, "y": 70}},
                 {"id": "1:3", "type": "TEXT", "characters": "Hidden", "visible": False},
                 {"id": "1:4", "type": "GROUP", "name": "card", "children": [
                     {"id": "1:5", "type": "TEXT", "characters": "¥99",
                      "absoluteBoundingBox": {"x": 100, "y": 50}}]},
             ]}
    texts = fc.collect_texts(frame)
    assert [t["id"] for t in texts] == ["1:2", "1:5"]
    assert texts[0]["text"] == "Hello" and texts[0]["offset"] == {"x": 10, "y": 20}
    assert texts[1]["path"] == "card" and texts[1]["dynamic"] is True


def test_main_language():
    assert fc.main_language(["我的影片", "Studio"]) == "zh"
    assert fc.main_language(["Generate New Video"]) == "en"
    assert fc.main_language(["30", "8"]) == "unknown"


def test_candidates_drops_exact_and_dynamic():
    design = [{"id": "a", "text": "Don’t Just Generate", "path": "", "dynamic": False},
              {"id": "b", "text": "Project", "path": "", "dynamic": False},
              {"id": "c", "text": "30", "path": "", "dynamic": True}]
    rows = fc.candidates(design, ["Don't just generate", "Projects", "Pricing", ""], top=1)
    assert [(r["id"], r["exact"]) for r in rows] == [("a", True), ("b", False)]
    assert rows[1]["candidates"][0]["live"] == "Projects"


def test_parse_exclude_accepts_chinese_separators():
    assert fc.parse_exclude("2、5，7 9") == {2, 5, 7, 9}
    assert fc.parse_exclude(None) == set()


def _design():
    return {"file_key": "K", "frame_id": "1:1", "texts": [
        {"id": "1:2", "text": "A", "offset": {"x": 1, "y": 2}},
        {"id": "1:3", "text": "C", "offset": {"x": 3, "y": 4}},
        {"id": "1:4", "text": "E", "offset": {"x": 5, "y": 6}}]}


def _plan(tmp_path):
    (tmp_path / "d.json").write_text(json.dumps(_design()))
    (tmp_path / "l.txt").write_text("B\nD\nF\n")
    plan = {"file_key": "K", "frame_id": "1:1",
            "design_file": str(tmp_path / "d.json"), "live_file": str(tmp_path / "l.txt"), "items": [
        {"n": 1, "node_id": "1:2", "design": "A", "live": "B", "offset": {"x": 1, "y": 2}},
        {"n": 2, "node_id": "1:3", "design": "C", "live": "D", "offset": {"x": 3, "y": 4}},
        {"n": 3, "node_id": "1:4", "design": "E", "live": "F", "offset": {"x": 5, "y": 6}}]}
    p = tmp_path / "plan.json"
    p.write_text(json.dumps(plan))
    return p


def test_post_excludes_and_skips_existing(tmp_path, monkeypatch):
    calls = []

    def fake_request(method, path, body=None):
        calls.append((method, path, body))
        if method == "GET":
            return {"comments": [{"message": fc.comment_message("A", "B")}]}
        return {}

    monkeypatch.setattr(fc, "_request", fake_request)
    fc.main(["post", str(_plan(tmp_path)), "--exclude", "3"])
    posts = [c for c in calls if c[0] == "POST"]
    assert len(posts) == 1
    assert posts[0][2] == {"message": "[文案校对机器人] 线上为：D（当前：C）",
                           "client_meta": {"node_id": "1:1", "node_offset": {"x": 3, "y": 4}}}


def test_post_dry_run_writes_nothing(tmp_path, monkeypatch):
    methods = []
    monkeypatch.setattr(fc, "_request", lambda m, p, b=None: methods.append(m) or {"comments": []})
    fc.main(["post", str(_plan(tmp_path)), "--dry-run"])
    assert methods == ["GET"]


def test_validate_plan_rejects_made_up_live_text():
    design = {"file_key": "K", "frame_id": "1:1", "texts": [
        {"id": "1:2", "text": "Project", "offset": {"x": 1, "y": 2}}]}
    plan = {"file_key": "K", "frame_id": "1:1", "items": [
        {"n": 1, "node_id": "1:2", "design": "Project", "live": "Projects", "offset": {"x": 1, "y": 2}}]}
    errors = fc.validate_plan(plan, design, ["Login", "Example Studio Projects"])
    assert errors == ["#1: live text 'Projects' is not on the captured page"]


def test_validate_plan_accepts_live_text_split_across_lines():
    design = {"file_key": "K", "frame_id": "1:1", "texts": [
        {"id": "1:2", "text": "Just Generate", "offset": {"x": 0, "y": 0}}]}
    plan = {"file_key": "K", "frame_id": "1:1", "items": [
        {"n": 1, "node_id": "1:2", "design": "Just Generate", "live": "Don’t Just Generate. Direct",
         "offset": {"x": 0, "y": 0}}]}
    assert fc.validate_plan(plan, design, ["Home", "Don’t Just Generate.", "Direct"]) == []


def test_validate_plan_rejects_wrong_layer_text_and_offset():
    design = {"file_key": "K", "frame_id": "1:1", "texts": [
        {"id": "1:2", "text": "A", "offset": {"x": 1, "y": 2}}]}
    plan = {"file_key": "K", "frame_id": "1:1", "items": [
        {"n": 1, "node_id": "1:2", "design": "Z", "live": "B", "offset": {"x": 0, "y": 0}},
        {"n": 2, "node_id": "9:9", "design": "A", "live": "B", "offset": {"x": 1, "y": 2}}]}
    errors = fc.validate_plan(plan, design, ["B", "B"])
    assert len(errors) == 3 and "9:9" in errors[2]


def test_post_refuses_when_plan_check_fails(tmp_path, monkeypatch):
    p = _plan(tmp_path)
    (tmp_path / "l.txt").write_text("nothing here\n")
    monkeypatch.setattr(fc, "_request", lambda *a, **k: pytest.fail("must not call Figma"))
    with pytest.raises(SystemExit, match="refusing to post"):
        fc.main(["post", str(p)])


def test_validate_plan_rejects_one_live_text_claimed_by_two_layers():
    design = {"file_key": "K", "frame_id": "1:1", "texts": [
        {"id": "1:2", "text": "Example Video", "offset": {"x": 0, "y": 0}},
        {"id": "1:3", "text": "Episode 1: Cat", "offset": {"x": 0, "y": 9}}]}
    plan = {"file_key": "K", "frame_id": "1:1", "items": [
        {"n": 1, "node_id": "1:2", "design": "Example Video", "live": "Last Shot", "offset": {"x": 0, "y": 0}},
        {"n": 2, "node_id": "1:3", "design": "Episode 1: Cat", "live": "Last Shot", "offset": {"x": 0, "y": 9}}]}
    errors = fc.validate_plan(plan, design, ["Last Shot", "View Project"])
    assert len(errors) == 1 and "paired with 2 layers" in errors[0]
    assert fc.validate_plan(plan, design, ["Last Shot", "Last Shot"]) == []


def _frame():
    return {"file_key": "K", "frame_id": "1:1", "frame_name": "Cover", "texts": [
        {"id": "1:2", "text": "Pick a Frame", "offset": {"x": 1, "y": 1}, "dynamic": False},
        {"id": "1:3", "text": "Cancel", "offset": {"x": 2, "y": 2}, "dynamic": False},
        {"id": "1:4", "text": "Episode 1: Cat", "offset": {"x": 3, "y": 3}, "dynamic": False},
        {"id": "1:5", "text": "0:12", "offset": {"x": 4, "y": 4}, "dynamic": True}]}


def test_validate_plan_requires_every_layer_classified():
    plan = {"file_key": "K", "frame_id": "1:1", "items": [
        {"n": 1, "node_id": "1:2", "design": "Pick a Frame", "live": "Choose video frame",
         "offset": {"x": 1, "y": 1}}]}
    errors = fc.validate_plan(plan, _frame(), ["Cancel", "Choose video frame"])
    assert errors == ["unclassified layer 1:4 'Episode 1: Cat': put it in items, unmatched or ignored"]
    plan["unmatched"] = [{"node_id": "1:4", "reason": ""}]
    assert fc.validate_plan(plan, _frame(), ["Cancel", "Choose video frame"]) == ["unmatched: 1:4 needs a reason"]


def test_render_report_keeps_unmatched_out_of_table():
    plan = {"file_key": "K", "frame_id": "1:1", "live_url": "https://x", "entry": "示例卡 → Export",
            "signed_in": True,
            "items": [{"n": 1, "node_id": "1:2", "design": "Pick a Frame", "live": "Choose video frame",
                       "offset": {"x": 1, "y": 1}, "where": "Replace 菜单"}],
            "unmatched": [{"node_id": "1:4", "reason": "线上无此控件"}]}
    text = fc.render_report(plan, _frame(), ["Cancel", "Choose video frame"])
    assert text.splitlines()[:3] == [
        "**[Cover](https://www.figma.com/design/K?node-id=1-1)** vs [https://x](https://x)",
        "来源：页面；入口：示例卡 → Export（已登录）", "一致 1 条，差异 1 条，未匹配 1 条。"]
    assert ("| [1](https://www.figma.com/design/K?node-id=1-2) | Pick a Frame "
            "| **Choose video** frame | Replace 菜单 |") in text
    assert "Episode 1: Cat" not in text.split("未匹配：")[0]
    assert text.endswith("未匹配：Episode 1: Cat（线上无此控件）")


def test_report_refuses_unchecked_plan(tmp_path):
    (tmp_path / "d.json").write_text(json.dumps(_frame()))
    (tmp_path / "l.txt").write_text("Cancel\n")
    plan = {"file_key": "K", "frame_id": "1:1", "design_file": str(tmp_path / "d.json"),
            "live_file": str(tmp_path / "l.txt"), "items": []}
    (tmp_path / "p.json").write_text(json.dumps(plan))
    with pytest.raises(SystemExit, match="plan check failed"):
        fc.main(["report", str(tmp_path / "p.json")])


def test_validate_plan_rejects_mismatch_for_text_already_on_page():
    design = {"file_key": "K", "frame_id": "1:1", "texts": [
        {"id": "1:2", "text": "Copy to My Projects", "offset": {"x": 0, "y": 0}}]}
    plan = {"file_key": "K", "frame_id": "1:1", "items": [
        {"n": 1, "node_id": "1:2", "design": "Copy to My Projects", "live": "Preview Project",
         "offset": {"x": 0, "y": 0}}]}
    errors = fc.validate_plan(plan, design, ["Preview Project", "Copy to My Projects"])
    assert len(errors) == 1 and "is on the page as-is" in errors[0]
    # Two design copies but one on the page: the second may genuinely differ.
    design["texts"].append({"id": "1:3", "text": "Copy to My Projects", "offset": {"x": 0, "y": 9}})
    plan["unmatched"] = [{"node_id": "1:3", "reason": "x"}]
    assert fc.validate_plan(plan, design, ["Preview Project", "Copy to My Projects"]) == []


def test_catalog_from_html_flattens_placeholders():
    data = {"props": {"pageProps": {"_extraProps": {"translation": {
        "a": ["Pick a Frame"], "b": [["count"], " episodes"], "c": ["Hi\n  there"],
        "d": ["Don’t Just Generate. <0>Direct</0>"]}}}}}
    html = f'<html><script id="__NEXT_DATA__" type="application/json">{json.dumps(data)}</script></html>'
    assert fc.catalog_from_html(html) == ["Don’t Just Generate. Direct", "Hi there", "Pick a Frame",
                                          "{count} episodes"]
    assert fc.catalog_from_html("<html></html>") is None


def test_catalog_matches_exact_and_placeholder_patterns_only_with_words():
    cat = fc.Catalog(["Pick a Frame", "{count} episodes", "{0}", "{0} video"])
    assert "pick a frame" in cat and "3 episodes" in cat
    assert "Choose video frame" not in cat
    assert "Example Video" not in cat and "anything" not in cat


def test_candidates_treats_catalog_entries_as_exact():
    design = [{"id": "a", "text": "Pick a Frame", "path": "", "dynamic": False},
              {"id": "b", "text": "Example Video", "path": "", "dynamic": False}]
    rows = fc.candidates(design, [], catalog=fc.Catalog(["Pick a Frame", "Example Videos"]))
    assert [(r["id"], r["exact"]) for r in rows] == [("a", True), ("b", False)]
    assert rows[1]["catalog_candidates"][0]["live"] == "Example Videos"


def test_validate_plan_checks_catalog_items_against_catalog():
    plan = {"file_key": "K", "frame_id": "1:1", "items": [
        {"n": 1, "node_id": "1:2", "design": "Pick a Frame", "live": "Choose video frame",
         "offset": {"x": 1, "y": 1}, "source": "catalog"}],
        "unmatched": [{"node_id": "1:4", "reason": "x"}]}
    catalog = ["Choose video frame", "Cancel", "Episode 1: Cat"]
    assert fc.validate_plan(plan, _frame(), [], catalog) == []
    plan["items"][0]["live"] = "Made up"
    assert fc.validate_plan(plan, _frame(), [], catalog) == ["#1: live text 'Made up' is not a Copy Catalog entry"]
    plan["items"][0]["live"] = "Choose video frame"
    errors = fc.validate_plan(plan, _frame(), [], catalog + ["Pick a Frame"])
    assert errors == ["#1: 'Pick a Frame' is in the Copy Catalog as-is, so it matches"]


def test_catalog_only_report_says_page_was_not_opened():
    plan = {"file_key": "K", "frame_id": "1:1", "live_url": "https://x", "items": [
        {"n": 1, "node_id": "1:2", "design": "Pick a Frame", "live": "Choose video frame",
         "offset": {"x": 1, "y": 1}, "source": "catalog", "where": "菜单"}]}
    text = fc.render_report(plan, _frame(), [], ["Cancel", "Choose video frame"])
    assert text.splitlines()[1] == "来源：线上文案目录（未打开页面）"
    assert "| 菜单（据文案目录） |" in text


def test_bold_changes_marks_only_changed_words():
    assert fc.bold_changes("Pick a Frame", "Pick a video frame") == "Pick a **video** frame"
    assert fc.bold_changes("Example Video", "Last Shot") == "Last Shot"
    assert fc.bold_changes("Pick a Frame", "Choose video frame") == "**Choose video** frame"


def test_report_marks_frame_image(tmp_path, capsys):
    pytest.importorskip("PIL")
    from PIL import Image
    design = _frame() | {"frame_size": {"w": 100, "h": 50}}
    design["texts"][0]["size"] = {"w": 30, "h": 10}
    (tmp_path / "d.json").write_text(json.dumps(design))
    (tmp_path / "c.txt").write_text("Cancel\nChoose video frame\nEpisode 1: Cat\n")
    Image.new("RGB", (200, 100), "white").save(tmp_path / "f.png")
    plan = {"file_key": "K", "frame_id": "1:1", "design_file": str(tmp_path / "d.json"),
            "catalog_file": str(tmp_path / "c.txt"), "frame_image": str(tmp_path / "f.png"),
            "items": [{"n": 1, "node_id": "1:2", "design": "Pick a Frame", "live": "Choose video frame",
                       "offset": {"x": 1, "y": 1}, "source": "catalog"}],
            "unmatched": [{"node_id": "1:4", "reason": "x"}]}
    (tmp_path / "p.json").write_text(json.dumps(plan))
    fc.main(["report", str(tmp_path / "p.json")])
    marked = tmp_path / "f.marked.png"
    assert capsys.readouterr().out.rstrip().endswith(f"MEDIA:{marked}")
    img = Image.open(marked)
    assert img.width == 200 and img.height > 100


def test_candidates_writes_plan_skeleton_and_keeps_classified_rows(tmp_path, capsys):
    design = _frame() | {"language": "en"}
    for t in design["texts"]:
        t["path"] = "dialog"
    (tmp_path / "d.json").write_text(json.dumps(design))
    (tmp_path / "c.txt").write_text("Cancel\nChoose video frame\n")
    plan = tmp_path / "p.json"
    argv = ["candidates", str(tmp_path / "d.json"), "--catalog", str(tmp_path / "c.txt"),
            "--plan", str(plan), "--live-url", "https://x"]
    fc.main(argv)
    skeleton = json.loads(plan.read_text())
    assert skeleton["live_url"] == "https://x" and skeleton["items"] == []
    assert [r["node_id"] for r in skeleton["todo"]] == ["1:2", "1:4"]
    assert fc.validate_plan(skeleton, _frame(), [], ["Cancel"])[-1].startswith("todo still has 2 row(s)")
    skeleton["unmatched"] = [{"node_id": "1:4", "reason": "x"}]
    plan.write_text(json.dumps(skeleton))
    capsys.readouterr()
    fc.main(argv + ["--refresh"])
    assert [r["node_id"] for r in json.loads(plan.read_text())["todo"]] == ["1:2"]
    assert json.loads(capsys.readouterr().out.splitlines()[0])["open_count"] == 1
    # A new run starts over instead of reusing an old plan's classification.
    fc.main(argv)
    assert [r["node_id"] for r in json.loads(plan.read_text())["todo"]] == ["1:2", "1:4"]


def test_catalog_only_plan_must_open_page_for_copy_not_in_catalog():
    plan = {"file_key": "K", "frame_id": "1:1", "items": [],
            "ignored": [{"node_id": "1:2", "reason": "占位"}, {"node_id": "1:4", "reason": "x"}]}
    errors = fc.validate_plan(plan, _frame(), [], ["Cancel"])
    assert errors == ["2 layer(s) are not in the Copy Catalog (Pick a Frame、Episode 1: Cat); open the page "
                      "(step 3) and add live_file before classifying them"]
    assert fc.validate_plan(plan, _frame(), ["Cancel", "Last Shot"], ["Cancel"]) == []
