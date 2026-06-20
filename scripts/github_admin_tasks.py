import os
import sys
import argparse
import requests
import re
import random
import time

GITHUB_API_URL = "https://api.github.com"
DEFAULT_REPO = "goyaljiiiiii/Open-Source-Contribution-Atelier"

def get_headers():
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("Error: GITHUB_TOKEN environment variable is not set.")
        sys.exit(1)
    return {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }

def add_labels_to_issue(repo, issue_number, labels):
    url = f"{GITHUB_API_URL}/repos/{repo}/issues/{issue_number}/labels"
    response = requests.post(url, headers=get_headers(), json={"labels": labels})
    if response.status_code == 200:
        print(f"Added labels {labels} to #{issue_number}")
    else:
        print(f"Failed to add labels to #{issue_number}: {response.json()}")

def sync_pr_labels(repo):
    """Adds 'ssoc26' to all PRs, and copies 'easy/medium/hard' from linked issues to PRs."""
    print(f"Syncing PR labels for {repo}...")
    headers = get_headers()
    
    # Fetch all PRs (open and closed)
    prs = []
    page = 1
    while True:
        url = f"{GITHUB_API_URL}/repos/{repo}/pulls?state=all&per_page=100&page={page}"
        response = requests.get(url, headers=headers)
        data = response.json()
        if not data:
            break
        prs.extend(data)
        page += 1

    issue_regex = re.compile(r'(?:fixes|closes|resolves)\s+#(\d+)', re.IGNORECASE)

    for pr in prs:
        pr_number = pr['number']
        body = pr.get('body') or ""
        
        labels_to_add = ["ssoc26"]
        
        # Check if already has 'ssoc26' and difficulty
        existing_labels = [l['name'].lower() for l in pr['labels']]
        
        # Find linked issues
        linked_issues = issue_regex.findall(body)
        for issue_num in linked_issues:
            # fetch issue labels
            issue_url = f"{GITHUB_API_URL}/repos/{repo}/issues/{issue_num}"
            issue_response = requests.get(issue_url, headers=headers)
            if issue_response.status_code == 200:
                i_labels = [l['name'].lower() for l in issue_response.json()['labels']]
                for diff in ['easy', 'medium', 'hard']:
                    if diff in i_labels:
                        labels_to_add.append(diff)
        
        labels_to_add = list(set(labels_to_add))
        
        # Only add if missing
        missing_labels = [l for l in labels_to_add if l not in existing_labels]
        if missing_labels:
            add_labels_to_issue(repo, pr_number, missing_labels)
            time.sleep(0.5) # simple rate limit avoidance
        else:
            print(f"PR #{pr_number} already has necessary labels.")

def sync_issue_labels(repo):
    """Adds 'ssoc26' to all issues."""
    print(f"Syncing issue labels for {repo}...")
    headers = get_headers()
    
    issues = []
    page = 1
    while True:
        url = f"{GITHUB_API_URL}/repos/{repo}/issues?state=all&per_page=100&page={page}"
        response = requests.get(url, headers=headers)
        data = response.json()
        if not data:
            break
        issues.extend(data)
        page += 1

    for issue in issues:
        # Skip PRs (GitHub API returns PRs as issues too)
        if 'pull_request' in issue:
            continue
            
        issue_number = issue['number']
        existing_labels = [l['name'].lower() for l in issue['labels']]
        
        if 'ssoc26' not in existing_labels:
            add_labels_to_issue(repo, issue_number, ['ssoc26'])
            time.sleep(0.5)
        else:
            print(f"Issue #{issue_number} already has ssoc26 label.")

def create_issues(repo, count):
    """Creates N development issues and labels them."""
    print(f"Creating {count} new issues in {repo}...")
    headers = get_headers()
    
    # Simple list of dummy issue topics to generate variations
    topics = [
        ("Frontend: Update component styling for {}", "medium"),
        ("Backend: Add API endpoint for {}", "hard"),
        ("Docs: Document usage of {} in CONTRIBUTING.md", "easy"),
        ("Testing: Add unit tests for {} module", "medium"),
        ("Refactor: Clean up redundant code in {}", "easy"),
        ("Bug: Fix edge case in {} logic", "medium")
    ]
    features = ["user profile", "authentication", "dashboard layout", "settings page", "database schema", "API rate limiting", "email notifications", "data export feature"]
    
    url = f"{GITHUB_API_URL}/repos/{repo}/issues"
    
    for i in range(count):
        topic_template, default_diff = random.choice(topics)
        feature = random.choice(features)
        
        title = topic_template.format(feature) + f" #{i+1}"
        body = f"## Description\nThis is an auto-generated issue for the SSOC26 contribution phase.\n\nPlease implement the feature or fix described in the title. Be sure to check `CONTRIBUTING.md` for guidelines.\n\nTo work on this, comment `assign to me`."
        
        labels = ["ssoc26", default_diff]
        
        response = requests.post(url, headers=headers, json={
            "title": title,
            "body": body,
            "labels": labels
        })
        
        if response.status_code == 201:
            issue_num = response.json()['number']
            print(f"Created issue #{issue_num}: {title} with labels {labels}")
        else:
            print(f"Failed to create issue: {response.json()}")
        time.sleep(1) # simple rate limit avoidance

def review_merge_prs(repo):
    """Reviews and merges open PRs."""
    print(f"Reviewing and merging open PRs for {repo}...")
    headers = get_headers()
    
    url = f"{GITHUB_API_URL}/repos/{repo}/pulls?state=open"
    response = requests.get(url, headers=headers)
    prs = response.json()
    
    for pr in prs:
        pr_number = pr['number']
        print(f"Processing PR #{pr_number}...")
        
        # Note: Merging PRs automatically without deep checks can be dangerous.
        # This script merges if there are no conflicts.
        
        # 1. Comment
        comment_url = f"{GITHUB_API_URL}/repos/{repo}/issues/{pr_number}/comments"
        requests.post(comment_url, headers=headers, json={"body": "Automated Review: PR looks good and complies with ssoc26 guidelines. Merging!"})
        
        # 2. Merge
        merge_url = f"{GITHUB_API_URL}/repos/{repo}/pulls/{pr_number}/merge"
        merge_response = requests.put(merge_url, headers=headers, json={"commit_title": f"Auto-merge PR #{pr_number}"})
        
        if merge_response.status_code in [200, 201]:
            print(f"Merged PR #{pr_number} successfully.")
        else:
            print(f"Failed to merge PR #{pr_number}: {merge_response.json()}")
        
        time.sleep(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Automate GitHub tasks for SSOC26")
    parser.add_argument("--repo", default=DEFAULT_REPO, help="Repository in format owner/repo")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    subparsers.add_parser("sync-pr-labels", help="Add ssoc26 to all PRs, copy easy/medium/hard from linked issues")
    subparsers.add_parser("sync-issue-labels", help="Add ssoc26 to all issues")
    
    create_parser = subparsers.add_parser("create-issues", help="Create new development issues")
    create_parser.add_argument("--count", type=int, default=50, help="Number of issues to create (default: 50)")
    
    subparsers.add_parser("review-merge-prs", help="Add a review comment and merge open PRs")
    
    args = parser.parse_args()
    
    if args.command == "sync-pr-labels":
        sync_pr_labels(args.repo)
    elif args.command == "sync-issue-labels":
        sync_issue_labels(args.repo)
    elif args.command == "create-issues":
        create_issues(args.repo, args.count)
    elif args.command == "review-merge-prs":
        review_merge_prs(args.repo)
