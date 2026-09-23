#!/usr/bin/env python3
"""Structural check for hermes-daily-review: review table must name existing skills."""
from pathlib import Path
import sys

SKILL = Path(__file__).resolve().parents[1] / "SKILL.md"
text = SKILL.read_text(encoding="utf-8")
needles = [
    "改哪条已有",
    "为何不新建",
    "禁止默认 `skill_manage create`",
    "skill-admission.md",
    "编号表：问题 / 根因 / 建议 / 落点 / 改哪条已有",
]
missing = [n for n in needles if n not in text]
if missing:
    print("FAIL missing:", *missing, sep="\n- ")
    sys.exit(1)
# Old 4-col header without the admission column must not remain as the only table spec.
if "编号表：问题 / 根因 / 建议 / 落点\n" in text and "改哪条已有" not in text.split("编号表：问题 / 根因 / 建议 / 落点", 1)[1][:80]:
    print("FAIL old 4-col review table still present")
    sys.exit(1)
print("ok", SKILL)
