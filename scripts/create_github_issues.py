#!/usr/bin/env python3
"""
Create GitHub issues from markdown files in `.github/issues/`.

Usage:
  GITHUB_TOKEN=ghp_xxx python scripts/create_github_issues.py

This script will read each `.md` file, use the first line as the title,
the rest as body, and parse a "Labels:" line to attach labels.
"""
import os
import re
import requests
from pathlib import Path

TOKEN = os.getenv("GITHUB_TOKEN")
if not TOKEN:
    print("GITHUB_TOKEN not set. Export a token with repo scope and re-run.")
    exit(1)

repo_url = os.popen('git config --get remote.origin.url').read().strip()
if repo_url.endswith(".git"):
    repo_url = repo_url[:-4]
# Try to derive owner/repo from remote
m = re.search(r"[:/]([^/]+/[^/]+)$", repo_url)
if not m:
    print("Could not determine repo from git remote. Set REPO env (owner/repo).")
    repo = os.getenv("REPO")
else:
    repo = m.group(1)

if not repo:
    print("Repository not specified. Exiting.")
    exit(1)

API = f"https://api.github.com/repos/{repo}/issues"
HEADERS = {"Authorization": f"token {TOKEN}", "Accept": "application/vnd.github+json"}

issues_dir = Path(".github/issues")
files = sorted(issues_dir.glob("**/*-issue.md"))
if not files:
    print("No issue drafts found in .github/issues/**/*.md")
    exit(0)

for p in files:
    text = p.read_text()
    lines = text.strip().splitlines()
    if not lines:
        continue
    title = lines[0].lstrip('# ').strip()
    body = '\n'.join(lines[1:]).strip()

    # Parse metadata to generate labels
    difficulty_match = re.search(r"-\s*\*\*Difficulty\*\*:\s*(.+)", text)
    category_match = re.search(r"-\s*\*\*Category\*\*:\s*(.+)", text)
    beginner_match = re.search(r"-\s*\*\*Beginner Friendliness\*\*:\s*(.+)", text)

    labels = ["ssoc26"]
    if difficulty_match:
        diff = difficulty_match.group(1).strip().lower()
        if diff in ["easy", "medium", "hard"]:
            labels.append(diff)
    if category_match:
        cat = category_match.group(1).strip().lower()
        if "doc" in cat:
            labels.append("documentation")
        elif "ui" in cat or "ux" in cat:
            labels.append("ui/ux")
        elif "access" in cat or "aria" in cat:
            labels.append("accessibility")
        elif "test" in cat:
            labels.append("testing")
        elif "perf" in cat:
            labels.append("performance")
        elif "auth" in cat:
            labels.append("authentication")
        elif "deploy" in cat:
            labels.append("deployment")
        elif "gamification" in cat:
            labels.append("enhancement")
        elif "experience" in cat:
            labels.append("good first issue")
    if beginner_match:
        beg = beginner_match.group(1).strip().lower()
        if beg.startswith("yes") and "good first issue" not in labels:
            labels.append("good first issue")

    payload = {"title": title, "body": body, "labels": labels}
    resp = requests.post(API, json=payload, headers=HEADERS)
    if resp.status_code in (200, 201):
        print(f"Created: {title} with labels {labels}")
    else:
        print(f"Failed {p.name}: {resp.status_code} {resp.text}")
