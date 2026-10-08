"""P5: PROJECT_STATE.md, its machine-readable twin state.json, and LESSONS.md keep their shape.

Run: python3 -m unittest discover .autodev/tests
"""

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs" / "autodev"
STATE_MD = DOCS / "PROJECT_STATE.md"
STATE_JSON = DOCS / "state.json"
LESSONS = DOCS / "LESSONS.md"
AUDITS = ROOT / "docs" / "audits"

SECTIONS = [
    "## Mốc",
    "## Mục tiêu và 3 điều cần kiểm chứng",
    "## Kiến trúc hiện nay",
    "## Quy tắc → test bảo vệ",
    "## Lỗ hổng mở",
    "## Quyết định gần đây",
    "## Tầm nhìn 3–5 mốc tới",
]
KEYS = {"updated", "milestones", "goals", "architecture", "rules", "open_gaps", "decisions", "outlook"}
TOP_LESSONS = [
    "Đừng tin báo cáo, kể cả của chính mình",
    "Người kiểm tra phải khác người làm và nhìn từ góc khác",
    "Tự động hoá phải có điểm dừng rõ ràng và quyền hạn có giới hạn",
    "Ngữ cảnh dài làm mất tầm nhìn tổng thể",
]
GAP_ROW = re.compile(r"^\|\s*(H-\d+)\s*\|.*\|\s*(mở|đóng[^|]*)\s*\|\s*$")


def latest_audit_gaps():
    """{H-xx: status} from the newest docs/audits/*.md (later rows of the same id win)."""
    files = sorted(AUDITS.glob("*.md"))
    if not files:
        return {}
    gaps = {}
    for line in files[-1].read_text(encoding="utf-8").splitlines():
        m = GAP_ROW.match(line)
        if m:
            gaps[m.group(1)] = m.group(2).strip()
    return gaps


class ProjectState(unittest.TestCase):
    def setUp(self):
        self.md = STATE_MD.read_text(encoding="utf-8")
        self.state = json.loads(STATE_JSON.read_text(encoding="utf-8"))

    def test_short(self):
        self.assertLess(len(self.md.splitlines()), 150)

    def test_sections_in_order(self):
        pos = [self.md.find(s) for s in SECTIONS]
        self.assertNotIn(-1, pos, f"thiếu mục: {[s for s, p in zip(SECTIONS, pos) if p < 0]}")
        self.assertEqual(pos, sorted(pos))

    def test_json_keys(self):
        self.assertEqual(KEYS - set(self.state), set())
        self.assertEqual(len(self.state["goals"]), 3)
        for g in self.state["goals"]:
            self.assertTrue(0 <= g["percent"] <= 100)
            self.assertTrue(g["evidence"])

    def test_rules_have_tests(self):
        for r in self.state["rules"]:
            self.assertIn("tests", r)  # empty list = rule not yet protected; shown as such in the md

    def test_open_gaps_shown_in_md(self):
        for gap in self.state["open_gaps"]:
            self.assertIn(gap["id"], self.md)

    def test_open_gaps_match_latest_audit(self):
        audit = latest_audit_gaps()
        if not audit:
            self.skipTest("chưa có audit")
        open_in_audit = {k for k, v in audit.items() if v == "mở"}
        self.assertEqual(open_in_audit, {g["id"] for g in self.state["open_gaps"]})

    def test_closed_gaps_name_a_test(self):
        for gid, status in latest_audit_gaps().items():
            if status.startswith("đóng"):
                self.assertRegex(status, r"đóng:\s*\S+", f"{gid} đóng mà không ghi test")


class Lessons(unittest.TestCase):
    def test_top_four_first(self):
        heads = re.findall(r"^### \d+\. (.+)$", LESSONS.read_text(encoding="utf-8"), flags=re.MULTILINE)
        self.assertGreaterEqual(len(heads), 10)
        for want, got in zip(TOP_LESSONS, heads[:4]):
            self.assertTrue(got.startswith(want), f"{got!r} != {want!r}")

    def test_each_lesson_has_three_parts(self):
        body = LESSONS.read_text(encoding="utf-8")
        for block in re.split(r"^### ", body, flags=re.MULTILINE)[1:]:
            for label in ("**Nguyên tắc:**", "**Ngộ ra từ:**", "**Đã thành:**"):
                self.assertIn(label, block, block.splitlines()[0])


if __name__ == "__main__":
    unittest.main()
