import os
import urllib.request
import json
import ssl
from dotenv import load_dotenv

load_dotenv()

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

token = os.environ.get("GITHUB_TOKEN")
headers = {
    "Authorization": f"Bearer {token}",
    "Accept": "application/vnd.github.v3+json",
    "User-Agent": "python-urllib"
}

repo = "goyaljiiiiii/Open-Source-Contribution-Atelier"
url = f"https://api.github.com/repos/{repo}/issues?state=all&per_page=100"

issues = []
page = 1
while True:
    req = urllib.request.Request(f"{url}&page={page}", headers=headers)
    try:
        with urllib.request.urlopen(req, context=ctx) as response:
            data = json.loads(response.read().decode())
            if not data:
                break
            issues.extend(data)
            page += 1
    except Exception as e:
        print(f"Error fetching page {page}: {e}")
        break

def normalize_title(title):
    t = title.lower().strip()
    prefixes = ['[frontend]', '[backend]', 'feat:', 'fix:', 'docs:', 'perf:', 'feat/', 'build a', 'build', 'implement', 'add', 'create', 'setup', 'design']
    changed = True
    while changed:
        changed = False
        for p in prefixes:
            if t.startswith(p):
                t = t[len(p):].strip()
                changed = True
    return t

normalized_issues = []
for issue in issues:
    if 'pull_request' in issue:
        continue
    normalized_issues.append({
        'number': issue['number'],
        'title': normalize_title(issue['title']),
        'original_title': issue['title'],
        'state': issue['state']
    })

normalized_issues.sort(key=lambda x: x['number'])

seen_titles = {}
duplicates_to_close = []

for issue in normalized_issues:
    t = issue['title']
    if t in seen_titles:
        if issue['state'] == 'open':
            duplicates_to_close.append((issue, seen_titles[t]))
    else:
        seen_titles[t] = issue

print(f"Found {len(duplicates_to_close)} open duplicate issues. Closing them now...")

for dup, orig in duplicates_to_close:
    print(f"Closing #{dup['number']} as a duplicate of #{orig['number']}")
    
    # 1. Post a comment
    comment_url = f"https://api.github.com/repos/{repo}/issues/{dup['number']}/comments"
    comment_data = json.dumps({"body": f"Closing this as it is a duplicate of #{orig['number']}."}).encode("utf-8")
    req = urllib.request.Request(comment_url, data=comment_data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, context=ctx):
            pass
    except Exception as e:
        print(f"  -> Failed to add comment: {e}")
    
    # 2. Close the issue
    close_url = f"https://api.github.com/repos/{repo}/issues/{dup['number']}"
    close_data = json.dumps({"state": "closed", "state_reason": "not_planned"}).encode("utf-8")
    req = urllib.request.Request(close_url, data=close_data, headers=headers, method="PATCH")
    try:
        with urllib.request.urlopen(req, context=ctx):
            print(f"  -> Successfully closed #{dup['number']}")
    except Exception as e:
        print(f"  -> Failed to close #{dup['number']}: {e}")

