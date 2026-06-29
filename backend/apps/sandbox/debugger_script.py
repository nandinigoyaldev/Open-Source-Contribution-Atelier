import sys
import json
import bdb
import traceback

class JSONDebugger(bdb.Bdb):
    def __init__(self, breakpoints):
        super().__init__()
        self.output_state = True
        self.setup_breakpoints(breakpoints)

    def setup_breakpoints(self, breakpoints):
        self.clear_all_breaks()
        for bp in breakpoints:
            self.set_break(sys.argv[1], bp)

    def print_state(self, event, frame):
        if not self.output_state:
            return
            
        # Only output state if we are in the target script
        if frame.f_code.co_filename != sys.argv[1]:
            return
            
        stack = []
        f = frame
        while f:
            if f.f_code.co_filename == sys.argv[1]:
                stack.append({
                    "function": f.f_code.co_name,
                    "line": f.f_lineno,
                    "file": f.f_code.co_filename
                })
            f = f.f_back
            
        # Get locals (filter out standard builtins)
        local_vars = {}
        for k, v in frame.f_locals.items():
            if k not in ['__builtins__', '__doc__', '__loader__', '__name__', '__package__', '__spec__', '__file__', '__cached__']:
                try:
                    local_vars[k] = repr(v)
                except Exception:
                    local_vars[k] = "<Error getting repr>"
                    
        state = {
            "type": "debug_state",
            "event": event,
            "line": frame.f_lineno,
            "locals": local_vars,
            "stack": stack[::-1]
        }
        print(json.dumps(state), flush=True)

    def user_line(self, frame):
        # We only care about lines in our script
        if frame.f_code.co_filename != sys.argv[1]:
            self.set_step()
            return
            
        self.print_state("line", frame)
        self.wait_for_command(frame)

    def user_return(self, frame, return_value):
        if frame.f_code.co_filename != sys.argv[1]:
            self.set_step()
            return
            
        self.print_state("return", frame)
        self.wait_for_command(frame)

    def user_exception(self, frame, exc_info):
        if frame.f_code.co_filename != sys.argv[1]:
            self.set_step()
            return
            
        exc_type, exc_value, exc_traceback = exc_info
        error_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        state = {
            "type": "debug_error",
            "error": error_msg,
            "line": frame.f_lineno
        }
        print(json.dumps(state), flush=True)
        self.wait_for_command(frame)

    def wait_for_command(self, frame):
        while True:
            cmd = sys.stdin.readline().strip()
            if cmd == "step":
                self.set_step()
                return
            elif cmd == "next":
                self.set_next(frame)
                return
            elif cmd == "continue":
                self.set_continue()
                return
            elif cmd == "quit":
                self.set_quit()
                sys.exit(0)
            elif cmd.startswith("break "):
                try:
                    line = int(cmd.split(" ")[1])
                    self.set_break(sys.argv[1], line)
                except ValueError:
                    pass
            elif cmd.startswith("clear "):
                try:
                    line = int(cmd.split(" ")[1])
                    self.clear_break(sys.argv[1], line)
                except ValueError:
                    pass

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python debugger_script.py <script_file> <breakpoints_json>")
        sys.exit(1)
        
    script_file = sys.argv[1]
    breakpoints = json.loads(sys.argv[2])
    
    debugger = JSONDebugger(breakpoints)
    
    with open(script_file, "r") as f:
        code = f.read()
        
    try:
        debugger.run(code, globals={"__name__": "__main__", "__file__": script_file})
    except bdb.BdbQuit:
        pass
    except Exception as e:
        error_msg = traceback.format_exc()
        print(json.dumps({"type": "debug_error", "error": error_msg}), flush=True)
        
    print(json.dumps({"type": "debug_end"}), flush=True)
