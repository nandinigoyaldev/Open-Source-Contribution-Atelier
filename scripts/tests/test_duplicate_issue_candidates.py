import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from duplicate_issue_candidates import find_candidates, normalize_title, similarity


class TestNormalizeTitle(unittest.TestCase):
    def test_case_whitespace_punctuation(self):
        self.assertEqual(normalize_title("  Fix   Login-Page: Crash!! "), "fix login page crash")

    def test_prefixes_removed(self):
        self.assertEqual(normalize_title("[Bug] Navbar overlaps content"), "navbar overlaps content")
        self.assertEqual(normalize_title("fix(ui): Navbar overlaps content"), "navbar overlaps content")
        self.assertEqual(normalize_title("[NSoC][Feature] Add dark mode"), "add dark mode")

    def test_empty(self):
        self.assertEqual(normalize_title(""), "")
        self.assertEqual(normalize_title(None), "")


class TestFindCandidates(unittest.TestCase):
    issues = [
        {"number": 1, "title": "Navbar overlaps content on mobile"},
        {"number": 2, "title": "Add dark mode toggle to settings"},
        {"number": 3, "title": "Bug"},
    ]

    def test_prefix_and_punctuation_variant_matches(self):
        res = find_candidates("[Bug] navbar overlaps content on mobile!!", self.issues)
        self.assertEqual([c["number"] for c in res], [1])
        self.assertEqual(res[0]["score"], 1.0)

    def test_near_duplicate_matches(self):
        res = find_candidates("Navbar overlaps the content on mobile", self.issues)
        self.assertEqual([c["number"] for c in res], [1])

    def test_unrelated_not_matched(self):
        self.assertEqual(find_candidates("Improve database indexing for leaderboard", self.issues), [])

    def test_short_titles_not_fuzzy_matched(self):
        self.assertEqual(similarity("Fix bugs", "Fix bug"), 0.0)
        self.assertEqual(find_candidates("Bugs", self.issues), [])

    def test_identical_short_titles_match(self):
        self.assertEqual([c["number"] for c in find_candidates("[bug] Bug", self.issues)], [3])

    def test_excludes_self(self):
        res = find_candidates("Navbar overlaps content on mobile", self.issues, exclude_number=1)
        self.assertEqual(res, [])

    def test_deterministic_order(self):
        issues = [{"number": 9, "title": "Same title here"}, {"number": 4, "title": "same title here."}]
        first = find_candidates("Same title here", issues)
        self.assertEqual([c["number"] for c in first], [4, 9])
        self.assertEqual(first, find_candidates("Same title here", list(reversed(issues))))


if __name__ == "__main__":
    unittest.main()
