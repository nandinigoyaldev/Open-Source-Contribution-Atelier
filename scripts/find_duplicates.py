import urllib.request
import json
import ssl

ctx = ssl.create_default_context()

url = "https://api.github.com/repos/goyaljiiiiii/Open-Source-Contribution-Atelier/issues?state=all&per_page=100"
req = urllib.request.Request(url)
with urllib.request.urlopen(req, context=ctx) as response:
    data = json.loads(response.read().decode())

# Collect all titles and normalize
issues = []
for issue in data:
    title = issue["title"].lower().strip()
    # Remove common prefixes like [frontend], [backend], feat:, fix:, etc.
    prefixes_to_strip = [
        "[frontend]",
        "[backend]",
        "feat:",
        "fix:",
        "docs:",
        "perf:",
        "feat/",
    ]
    for p in prefixes_to_strip:
        if title.startswith(p):
            title = title[len(p) :].strip()
    issues.append(
        {
            "number": issue["number"],
            "title": title,
            "original_title": issue["title"],
            "state": issue["state"],
            "url": issue["html_url"],
        }
    )

duplicates = {}
for i, issue in enumerate(issues):
    for j in range(i + 1, len(issues)):
        other = issues[j]
        # Check for similarity
        if issue["title"] == other["title"]:
            key = issue["title"]
            if key not in duplicates:
                duplicates[key] = [issue, other]
            elif other not in duplicates[key]:
                duplicates[key].append(other)

for title, dups in duplicates.items():
    print(f"\nDuplicate group: {title}")
    for dup in dups:
        print(f"  #{dup['number']} ({dup['state']}): {dup['original_title']}")
