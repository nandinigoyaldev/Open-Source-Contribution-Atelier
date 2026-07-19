#!/usr/bin/env python
"""
Script to analyze issue quality in CI pipeline.
"""

import os
import sys
import json
import django

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.issue_quality_ci.services.quality_scorer_ci import IssueQualityScorerCI
from apps.issue_quality_ci.models import IssueQualityRecord
import argparse
import requests


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--issue-number', type=int, required=True)
    parser.add_argument('--repository', type=str, required=True)
    parser.add_argument('--event', type=str, default='issues')
    args = parser.parse_args()

    # Fetch issue data from GitHub
    token = os.environ.get('GITHUB_TOKEN')
    headers = {'Authorization': f'token {token}'}
    
    url = f"https://api.github.com/repos/{args.repository}/issues/{args.issue_number}"
    response = requests.get(url, headers=headers)
    
    if response.status_code != 200:
        print(f"Failed to fetch issue: {response.status_code}")
        sys.exit(1)
    
    data = response.json()
    
    # Analyze quality
    scorer = IssueQualityScorerCI()
    result = scorer.score_issue(
        title=data.get('title', ''),
        body=data.get('body', ''),
        issue_number=args.issue_number
    )
    
    # Save to database
    record = IssueQualityRecord.objects.create(
        issue_id=str(data.get('id')),
        repository=args.repository,
        issue_number=args.issue_number,
        issue_title=data.get('title', ''),
        issue_body=data.get('body', ''),
        issue_author=data.get('user', {}).get('login', ''),
        **result
    )
    
    # Save as JSON for GitHub Action
    with open('quality_report.json', 'w') as f:
        json.dump(result, f, indent=2)
    
    print(f"✅ Quality analysis saved: {record.id}")


if __name__ == '__main__':
    main()