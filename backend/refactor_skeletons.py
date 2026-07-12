import os
import glob
import re

skeletons_dir = r"c:\Users\LENOVO\OneDrive\Desktop\SSOC\Open-Source-Contribution-Atelier\frontend\src\components\ui\skeletons"
files = glob.glob(os.path.join(skeletons_dir, "*.tsx"))

target_str = "bg-gradient-to-r from-surface-high via-surface-highest to-surface-high bg-[length:200%_100%] animate-shimmer"

for file in files:
    with open(file, "r", encoding="utf-8") as f:
        content = f.read()

    if target_str in content:
        if "import { Skeleton }" not in content:
            content = 'import { Skeleton } from "../Skeleton";\n' + content

        def repl(match):
            full_match = match.group(0)
            new_match = (
                full_match.replace("<div", "<Skeleton")
                .replace(target_str, "")
                .replace("  ", " ")
            )
            return new_match

        content = re.sub(
            r'<div\s+className="[^"]*animate-shimmer[^"]*"\s*/>', repl, content
        )

        with open(file, "w", encoding="utf-8") as f:
            f.write(content)
