#!/usr/bin/env python3
"""Pick the newest Gemini Flash-high from cursor-agent --list-models.

Floor is 3.8 so a 3.7 leftover is never chosen. 3.9 / 4.0 win automatically.
Does not hardcode a version id.
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

FLOOR = (3, 8)
MODEL_RE = re.compile(r"^gemini-(\d+)(?:\.(\d+))?-flash-high$")
DEFAULT_BIN = Path.home() / ".local" / "bin" / "cursor-agent"


def parse_id(token: str) -> tuple[int, int] | None:
    m = MODEL_RE.match(token.strip())
    if not m:
        return None
    major = int(m.group(1))
    minor = int(m.group(2) or 0)
    return (major, minor)


def ids_from_list_text(text: str) -> list[str]:
    out: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.lower().startswith("available") or line.lower().startswith("tip:"):
            continue
        token = line.split()[0]
        if parse_id(token) is not None:
            out.append(token)
    return out


def pick(ids: list[str], floor: tuple[int, int] = FLOOR) -> str | None:
    ranked: list[tuple[tuple[int, int], str]] = []
    for model_id in ids:
        ver = parse_id(model_id)
        if ver is None or ver < floor:
            continue
        ranked.append((ver, model_id))
    if not ranked:
        return None
    ranked.sort()
    return ranked[-1][1]


def resolve_bin(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit).expanduser()
    env = os.environ.get("CURSOR_AGENT_BIN")
    if env:
        return Path(env).expanduser()
    if DEFAULT_BIN.is_file():
        return DEFAULT_BIN
    found = shutil.which("cursor-agent")
    if found:
        return Path(found)
    raise FileNotFoundError(
        "cursor-agent not found. Use ~/.local/bin/cursor-agent or zsh -lic 'whence -v cursor-cli'."
    )


def list_models(bin_path: Path) -> str:
    proc = subprocess.run(
        [str(bin_path), "--list-models"],
        capture_output=True,
        text=True,
        check=False,
    )
    text = (proc.stdout or "") + (("\n" + proc.stderr) if proc.stderr else "")
    if proc.returncode != 0 and not text.strip():
        raise RuntimeError(f"{bin_path} --list-models failed rc={proc.returncode}")
    return text


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from-text", action="store_true", help="read --list-models text from stdin")
    parser.add_argument("--bin", help="cursor-agent path")
    args = parser.parse_args(argv)

    if args.from_text:
        text = sys.stdin.read()
    else:
        try:
            text = list_models(resolve_bin(args.bin))
        except (FileNotFoundError, RuntimeError) as exc:
            print(str(exc), file=sys.stderr)
            return 2

    chosen = pick(ids_from_list_text(text))
    if not chosen:
        print("no gemini-*.flash-high >= 3.8 in --list-models", file=sys.stderr)
        return 2
    print(chosen)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
