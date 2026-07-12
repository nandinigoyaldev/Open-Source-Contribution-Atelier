import contextlib
import io
import json
import sys


def safe_serialize(obj, max_depth=2, current_depth=0):
    if current_depth > max_depth:
        return "..."
    if isinstance(obj, (int, float, str, bool, type(None))):
        return obj
    if isinstance(obj, list):
        return [safe_serialize(item, max_depth, current_depth + 1) for item in obj[:50]]
    if isinstance(obj, dict):
        return {
            str(k): safe_serialize(v, max_depth, current_depth + 1)
            for k, v in list(obj.items())[:50]
        }
    if isinstance(obj, set):
        return [
            safe_serialize(item, max_depth, current_depth + 1)
            for item in list(obj)[:50]
        ]
    if isinstance(obj, tuple):
        return tuple(
            safe_serialize(item, max_depth, current_depth + 1) for item in obj[:50]
        )

    # Fallback to repr
    try:
        r = repr(obj)
        if len(r) > 100:
            return r[:97] + "..."
        return r
    except Exception:
        return "<unserializable>"


def run_trace(code_str):
    events = []
    output_stream = io.StringIO()

    # Track how much stdout has been generated at each step
    def get_current_stdout():
        return output_stream.getvalue()

    def trace_calls(frame, event, arg):
        if event == "call":
            # Only trace within our execution namespace
            if frame.f_code.co_filename != "<string>":
                return None
            return trace_lines
        return None

    def trace_lines(frame, event, arg):
        if event not in ("line", "return"):
            return trace_lines

        if frame.f_code.co_filename != "<string>":
            return trace_lines

        locals_copy = {}
        for k, v in frame.f_locals.items():
            if not k.startswith("__"):
                locals_copy[k] = safe_serialize(v)

        events.append(
            {
                "step": len(events),
                "line": frame.f_lineno,
                "event": event,
                "locals": locals_copy,
                "stdout": get_current_stdout(),
            }
        )
        return trace_lines

    # Compile the code
    try:
        compiled_code = compile(code_str, "<string>", "exec")
    except SyntaxError as e:
        events.append(
            {
                "step": 0,
                "line": e.lineno,
                "event": "error",
                "locals": {},
                "stdout": "",
                "error": str(e),
            }
        )
        return events

    # Execute with trace
    namespace = {}
    sys.settrace(trace_calls)

    try:
        with contextlib.redirect_stdout(output_stream):
            exec(compiled_code, namespace)
    except Exception as e:
        events.append(
            {
                "step": len(events),
                "line": (
                    sys.exc_info()[2].tb_next.tb_lineno
                    if sys.exc_info()[2] and sys.exc_info()[2].tb_next
                    else 0
                ),
                "event": "error",
                "locals": {
                    k: safe_serialize(v)
                    for k, v in namespace.items()
                    if not k.startswith("__")
                },
                "stdout": get_current_stdout(),
                "error": f"{type(e).__name__}: {str(e)}",
            }
        )
    finally:
        sys.settrace(None)

    return events


if __name__ == "__main__":
    # Expects code to be passed via stdin or as an argument (file path)
    if len(sys.argv) > 1:
        with open(sys.argv[1], "r") as f:
            code = f.read()
    else:
        code = sys.stdin.read()

    trace_events = run_trace(code)
    print(json.dumps(trace_events))
