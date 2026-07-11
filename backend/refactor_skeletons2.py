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

        # We handle self closing: <div className="..." /> -> <Skeleton className="..." />
        # and standard closing: <div className="..."></div> -> <Skeleton className="..."></Skeleton>

        # 1. Self closing
        def repl_self_closing(match):
            full = match.group(0)
            return (
                full.replace("<div", "<Skeleton")
                .replace(target_str, "")
                .replace("  ", " ")
            )

        content = re.sub(
            r'<div\s+className="[^"]*animate-shimmer[^"]*"\s*/>',
            repl_self_closing,
            content,
        )

        # 2. Open/Close tags
        def repl_open_close(match):
            # match.group(1) is the inner part of <div ...>
            # match.group(0) is the entire `<div ...></div>`
            full = match.group(0)
            new_full = full.replace("<div", "<Skeleton").replace(
                "</div>", "</Skeleton>"
            )
            new_full = new_full.replace(target_str, "").replace("  ", " ")
            return new_full

        content = re.sub(
            r'<div\s+className="[^"]*animate-shimmer[^"]*"\s*>.*?</div>',
            repl_open_close,
            content,
            flags=re.DOTALL,
        )

        with open(file, "w", encoding="utf-8") as f:
            f.write(content)
