import unittest
from anti_cheat.detector import AntiCheatDetector

class TestAntiCheatDetector(unittest.TestCase):
    def setUp(self):
        self.detector = AntiCheatDetector(cpm_threshold=2000)

    def test_paste_event_does_not_trigger_suspicious_flag(self):
        # Large chunk inserted via paste should be discounted from raw typing CPM
        events = [
            {"type": "paste", "length": 500},
            {"type": "keypress", "length": 5, "interval_ms": 200}
        ]
        result = self.detector.analyze_submission(events)
        self.assertFalse(result["is_suspicious"])
        self.assertEqual(result["chars_pasted"], 500)

    def test_synthetic_fast_typing_triggers_flag(self):
        # Rapid raw keypresses exceeding threshold should trigger the flag
        events = [
            {"type": "keypress", "length": 100, "interval_ms": 10}
        ]
        result = self.detector.analyze_submission(events)
        self.assertTrue(result["is_suspicious"])

if __name__ == "__main__":
    unittest.main()
