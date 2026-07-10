import re

path = "apps/events/services/event_bus.py"
with open(path, "r") as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if "process_event.delay" in line:
        start = i - 1
        while start >= 0 and "try:" not in lines[start]:
            start -= 1
        end = i + 1
        while end < len(lines) and lines[end].strip() != "" and lines[end].startswith("        "):
            end += 1

        new_block = [
            "        try:\n",
            "            process_event.delay(str(event.id))\n",
            "        except Exception:\n",
            "            pass\n",
        ]
        lines[start:end] = new_block
        break

with open(path, "w") as f:
    f.writelines(lines)

print("Done - block replaced")
