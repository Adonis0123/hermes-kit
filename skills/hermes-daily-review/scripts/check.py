#!/usr/bin/env python3
"""Structural check for hermes-daily-review: review list must name existing skills."""
from pathlib import Path
import sys

SKILL = Path(__file__).resolve().parents[1] / "SKILL.md"
text = SKILL.read_text(encoding="utf-8")
needles = [
    "改哪条已有",
    "为何不新建",
    "禁止默认 `skill_manage create`",
    "skill-admission.md",
    "编号清单，**不用 markdown 表格**：问题 / 根因 / 建议 / 落点 / 改哪条已有",
]
missing = [n for n in needles if n not in text]
if missing:
    print("FAIL missing:", *missing, sep="\n- ")
    sys.exit(1)
# Feishu cards split markdown table columns evenly; long review cells scroll inside the cell.
if "编号表：" in text:
    print("FAIL review spec is a table again; use the numbered list (编号清单) under 可以改进")
    sys.exit(1)
print("ok", SKILL)
