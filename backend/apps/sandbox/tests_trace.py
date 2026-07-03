import json
import os
import sys
import tempfile
import asyncio
import unittest

# We need to run the trace_script.py directly or import it and call run_trace.
# It's cleaner to import it and call run_trace directly for testing.
from apps.sandbox.trace_script import run_trace, safe_serialize

class TracerEngineTests(unittest.TestCase):

    def test_basic_trace(self):
        code = """
x = 5
y = 10
z = x + y
        """
        events = run_trace(code)
        
        # Filter out the initial 'call' or 'line' setup events if needed
        # Just check that it captured the final state correctly
        self.assertGreater(len(events), 0)
        final_event = events[-1]
        self.assertIn("locals", final_event)
        self.assertEqual(final_event["locals"].get("z"), 15)
        self.assertEqual(final_event["locals"].get("x"), 5)

    def test_safe_serialize_primitives(self):
        self.assertEqual(safe_serialize(42), 42)
        self.assertEqual(safe_serialize("hello"), "hello")
        self.assertEqual(safe_serialize(True), True)
        self.assertEqual(safe_serialize(None), None)

    def test_safe_serialize_complex(self):
        # Nested list
        nested = [1, [2, [3, [4]]]]
        serialized = safe_serialize(nested)
        # Should truncate at depth 2 (0, 1, 2)
        self.assertEqual(serialized, [1, [2, ['...', '...']]])

        # Class instance
        class MyClass:
            def __repr__(self):
                return "MyClassInstance"
        
        obj = MyClass()
        self.assertEqual(safe_serialize(obj), "MyClassInstance")

    def test_syntax_error(self):
        code = """
def bad_syntax()
    pass
        """
        events = run_trace(code)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event"], "error")
        self.assertIn("syntax", events[0]["error"].lower())

    def test_runtime_error(self):
        code = """
x = 5
y = 0
z = x / y
        """
        events = run_trace(code)
        error_events = [e for e in events if e["event"] == "error"]
        self.assertEqual(len(error_events), 1)
        self.assertIn("ZeroDivisionError", error_events[0]["error"])
        
    def test_infinite_loop_prevention(self):
        # We can't actually test an infinite loop easily without hanging the test runner,
        # but the subprocess execution in services.py handles timeouts.
        # We'll just test a long loop to ensure it doesn't crash safe_serialize.
        code = """
my_list = []
for i in range(100):
    my_list.append(i)
        """
        events = run_trace(code)
        self.assertGreater(len(events), 100)
        # Check that list truncation works (max 50 items)
        final_list = events[-1]["locals"].get("my_list")
        self.assertTrue(isinstance(final_list, list))
        self.assertEqual(len(final_list), 50) # Should be truncated

    def test_stdout_capture(self):
        code = """
print("Hello")
print("World")
        """
        events = run_trace(code)
        final_event = events[-1]
        self.assertEqual(final_event["stdout"], "Hello\\nWorld\\n".replace("\\n", "\n"))
