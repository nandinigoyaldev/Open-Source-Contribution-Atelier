class AntiCheatDetector:
    def __init__(self, cpm_threshold: int = 2000):
        self.cpm_threshold = cpm_threshold

    def analyze_submission(self, events: list[dict]) -> dict:
        total_chars_typed = 0
        total_chars_pasted = 0
        timed_intervals = []

        for event in events:
            event_type = event.get("type")
            length = event.get("length", 1)

            if event_type == "paste":
                # Aggregate pasted character count separately
                total_chars_pasted += length
            elif event_type == "keypress":
                total_chars_typed += length
                timed_intervals.append(event.get("interval_ms", 100))

        # Calculate CPM using only raw typed characters
        total_time_minutes = sum(timed_intervals) / 60000.0 if timed_intervals else 1.0
        effective_cpm = (total_chars_typed / total_time_minutes) if total_time_minutes > 0 else 0

        is_suspicious = effective_cpm > self.cpm_threshold

        return {
            "is_suspicious": is_suspicious,
            "effective_cpm": round(effective_cpm, 2),
            "chars_typed": total_chars_typed,
            "chars_pasted": total_chars_pasted,
        }
