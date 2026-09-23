#!/usr/bin/env python3
"""Unit tests for pick_gemini_flash. No live cursor-agent."""
from __future__ import annotations

import unittest

from pick_gemini_flash import ids_from_list_text, pick

SAMPLE = """
Available models

auto - Auto (default)
composer-2.5 - Composer 2.5
gemini-3.7-flash-high - Gemini 3.7 Flash
gemini-3.8-flash-low - Gemini 3.8 Flash Low
gemini-3.8-flash-medium - Gemini 3.8 Flash Medium
gemini-3.8-flash-high - Gemini 3.8 Flash High
gemini-3.6-flash-high - Gemini 3.6 Flash
Tip: use --model <id>
"""

SAMPLE_WITH_39 = SAMPLE.replace(
    "gemini-3.8-flash-high - Gemini 3.8 Flash High",
    "gemini-3.8-flash-high - Gemini 3.8 Flash High\ngemini-3.9-flash-high - Gemini 3.9 Flash High",
)


class PickGeminiFlashTest(unittest.TestCase):
    def test_picks_38_high_not_composer_or_medium(self):
        self.assertEqual(pick(ids_from_list_text(SAMPLE)), "gemini-3.8-flash-high")

    def test_newer_flash_wins(self):
        self.assertEqual(pick(ids_from_list_text(SAMPLE_WITH_39)), "gemini-3.9-flash-high")

    def test_ignores_below_floor(self):
        text = "gemini-3.7-flash-high - Gemini 3.7 Flash\n"
        self.assertIsNone(pick(ids_from_list_text(text)))

    def test_accepts_major_only_id(self):
        text = "gemini-3.8-flash-high x\ngemini-4-flash-high y\n"
        self.assertEqual(pick(ids_from_list_text(text)), "gemini-4-flash-high")

    def test_empty(self):
        self.assertIsNone(pick(ids_from_list_text("auto - Auto\n")))


if __name__ == "__main__":
    unittest.main()
