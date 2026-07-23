# backend/refactor_skeletons2.py
import argparse
import glob
import os
import re
from pathlib import Path


def get_default_skeletons_dir() -> Path:
    """Resolve frontend/src/components/ui/skeletons relative to this script,
    since backend/ and frontend/ are sibling directories at the repo root."""
    repo_root = Path(__file__).resolve().parent.parent
    return repo_root / "frontend" / "src" / "components" / "ui" / "skeletons"


def main():
    parser = argparse.ArgumentParser(
        description="Convert shimmer <div> skeletons (self-closing and open/close) to <Skeleton> components."
    )
    parser.add_argument(
        "--skeletons-dir",
        type=str,
        default=None,
        help="Override path to the skeletons directory (defaults to "
        "frontend/src/components/ui/skeletons relative to the repo root).",
    )
    args = parser.parse_args()

    skeletons_dir = Path(args.skeletons_dir) if args.skeletons_dir else get_default_skeletons_dir()

    if not skeletons_dir.is_dir():
        print(f"⚠️ Skeletons directory not found: {skeletons_dir}")
        return

    files = glob.glob(os.path.join(str(skeletons_dir), "*.tsx"))
    if not files:
        print(f"⚠️ No .tsx files found in {skeletons_dir}")
        return

    target_str = "bg-gradient-to-r from-surface-high via-surface-highest to-surface-high bg-[length:200%_100%] animate-shimmer"

    for file in files:
        with open(file, "r", encoding="utf-8") as f:
            content = f.read()

        if target_str in content:
            if 'import { Skeleton }' not in content:
                content = 'import { Skeleton } from "../Skeleton";\n' + content

            # We handle self closing: <div className="..." /> -> <Skeleton className="..." />
            # and standard closing: <div className="...">...</div> -> <Skeleton className="...">...</Skeleton>

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
                # match.group(0) is the entire `<div ...>...</div>`
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
            print(f"✅ Updated: {file}")


if __name__ == "__main__":
    main()