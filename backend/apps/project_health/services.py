"""
GitHub API Analyzer and Health Score computation service.
Uses the public GitHub REST API (no authentication required for public repos).
"""
import re
from datetime import datetime, timezone
from urllib.parse import urlparse

import requests

GITHUB_API = "https://api.github.com"


def _parse_repo_url(repo_url: str) -> tuple[str, str]:
    """Extract (owner, repo_name) from a GitHub URL."""
    parsed = urlparse(repo_url.rstrip("/"))
    parts = parsed.path.strip("/").split("/")
    if len(parts) < 2:
        raise ValueError(f"Cannot parse owner/repo from URL: {repo_url}")
    return parts[0], parts[1]


def _github_get(path: str, token: str = None) -> dict | list:
    """Make a GET request to the GitHub API."""
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    response = requests.get(f"{GITHUB_API}{path}", headers=headers, timeout=10)
    response.raise_for_status()
    return response.json()


def _sentiment_label(score: float) -> str:
    if score > 0.1:
        return "positive"
    if score < -0.1:
        return "negative"
    return "neutral"


def _compute_health_score(data: dict) -> tuple[int, list, list]:
    """
    Compute a health score (0-100) from raw metrics.
    Returns (score, red_flags, green_flags).
    """
    score = 50  # Baseline
    red_flags = []
    green_flags = []

    # Recency
    last_commit_days = data.get("last_commit_days_ago")
    if last_commit_days is not None:
        if last_commit_days > 365:
            score -= 20
            red_flags.append("🔴 Project appears abandoned (no commits in over a year).")
        elif last_commit_days > 90:
            score -= 10
            red_flags.append("🟡 Low activity (last commit was over 3 months ago).")
        else:
            score += 15
            green_flags.append("✅ Actively maintained (recent commits).")

    # PR responsiveness
    avg_pr_days = data.get("avg_pr_close_days")
    if avg_pr_days is not None:
        if avg_pr_days < 7:
            score += 15
            green_flags.append("✅ Excellent PR response time (< 1 week).")
        elif avg_pr_days < 30:
            score += 5
            green_flags.append("✅ Reasonable PR response time (< 1 month).")
        else:
            score -= 10
            red_flags.append("🟡 Slow PR response time (> 30 days on average).")

    # Issue ratio
    open_issues = data.get("open_issues", 0)
    closed_issues = data.get("closed_issues", 0)
    total_issues = open_issues + closed_issues
    if total_issues > 0:
        close_ratio = closed_issues / total_issues
        if close_ratio > 0.7:
            score += 10
            green_flags.append(f"✅ Good issue resolution rate ({int(close_ratio * 100)}% closed).")
        elif close_ratio < 0.3:
            score -= 10
            red_flags.append(f"🔴 Low issue resolution rate ({int(close_ratio * 100)}% closed).")

    # Contributor diversity
    contributors = data.get("contributor_count", 0)
    if contributors > 50:
        score += 10
        green_flags.append(f"✅ Large contributor community ({contributors} contributors).")
    elif contributors < 5:
        score -= 5
        red_flags.append("🟡 Low contributor count – bus-factor risk.")

    # Sentiment
    sentiment = data.get("sentiment_score")
    if sentiment is not None:
        if sentiment > 0.2:
            score += 10
            green_flags.append("✅ Community communication appears positive and welcoming.")
        elif sentiment < -0.1:
            score -= 15
            red_flags.append("🔴 Community communications appear negative or toxic.")

    return max(0, min(score, 100)), red_flags, green_flags


def analyze_repository(repo_url: str, token: str = None) -> dict:
    """
    Fetch GitHub data, run sentiment analysis, compute health score.
    Returns a dict of all metrics ready to store in RepoHealthScore.
    """
    owner, repo_name = _parse_repo_url(repo_url)

    # Fetch basic repo info
    try:
        repo_data = _github_get(f"/repos/{owner}/{repo_name}", token=token)
    except requests.HTTPError as e:
        raise ValueError(f"Repository not found or inaccessible: {e}")

    # Last commit date
    last_commit_days = None
    try:
        commits = _github_get(
            f"/repos/{owner}/{repo_name}/commits?per_page=1", token=token
        )
        if commits:
            date_str = commits[0]["commit"]["committer"]["date"]
            last_commit_dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            last_commit_days = (datetime.now(tz=timezone.utc) - last_commit_dt).days
    except Exception:
        pass

    # PR stats (closed, last 30)
    avg_pr_close_days = None
    try:
        closed_prs = _github_get(
            f"/repos/{owner}/{repo_name}/pulls?state=closed&per_page=30", token=token
        )
        if closed_prs:
            durations = []
            for pr in closed_prs:
                if pr.get("merged_at") and pr.get("created_at"):
                    created = datetime.fromisoformat(pr["created_at"].replace("Z", "+00:00"))
                    merged = datetime.fromisoformat(pr["merged_at"].replace("Z", "+00:00"))
                    durations.append((merged - created).days)
            if durations:
                avg_pr_close_days = sum(durations) / len(durations)
    except Exception:
        pass

    # Open PR count
    open_pr_count = 0
    try:
        open_prs = _github_get(
            f"/repos/{owner}/{repo_name}/pulls?state=open&per_page=1", token=token
        )
        open_pr_count = len(open_prs)
    except Exception:
        pass

    # Contributor count
    contributor_count = 0
    try:
        contributors = _github_get(
            f"/repos/{owner}/{repo_name}/contributors?per_page=100", token=token
        )
        contributor_count = len(contributors)
    except Exception:
        pass

    # Sentiment from recent PR comments (lightweight approach without TextBlob)
    sentiment_score = None
    sentiment_lbl = ""
    try:
        comments_data = _github_get(
            f"/repos/{owner}/{repo_name}/issues/comments?per_page=50&sort=created&direction=desc",
            token=token,
        )
        if comments_data:
            # Simple keyword-based sentiment (no external dependency needed)
            positive_words = {"great", "thanks", "awesome", "nice", "good", "excellent", "love", "perfect"}
            negative_words = {"terrible", "broken", "worst", "hate", "bug", "wrong", "bad", "useless", "toxic"}
            polarity_sum = 0
            for comment in comments_data:
                body = comment.get("body", "").lower()
                words = set(re.findall(r"\w+", body))
                polarity_sum += len(words & positive_words) - len(words & negative_words)
            sentiment_score = polarity_sum / len(comments_data) if comments_data else 0
            sentiment_lbl = _sentiment_label(sentiment_score)
    except Exception:
        pass

    data = {
        "repo_owner": owner,
        "repo_name": repo_name,
        "open_issues": repo_data.get("open_issues_count", 0),
        "closed_issues": 0,  # Not directly available without search API
        "open_prs": open_pr_count,
        "closed_prs": len(closed_prs) if avg_pr_close_days is not None else 0,
        "avg_pr_close_days": avg_pr_close_days,
        "contributor_count": contributor_count,
        "last_commit_days_ago": last_commit_days,
        "sentiment_score": sentiment_score,
        "sentiment_label": sentiment_lbl,
    }

    score, red_flags, green_flags = _compute_health_score(data)
    data["health_score"] = score
    data["red_flags"] = red_flags
    data["green_flags"] = green_flags

    return data


class BurnoutAnalyzer:
    """
    Analyzes the workload profile of a maintainer and computes a burnout risk score.
    """

    @classmethod
    def compute_risk_score(cls, profile):
        """
        Calculates and updates the burnout risk score based on simple thresholds.
        High Risk:
        - Active PRs assigned > 15
        - Avg time to review > 72 hours
        - Recent issue volume > 20
        """
        score = 0
        if profile.active_prs_assigned > 15:
            score += 2
        elif profile.active_prs_assigned > 5:
            score += 1

        if profile.avg_time_to_review_hours > 72:
            score += 2
        elif profile.avg_time_to_review_hours > 48:
            score += 1

        if profile.recent_issue_volume > 20:
            score += 2
        elif profile.recent_issue_volume > 10:
            score += 1

        if score >= 5:
            profile.burnout_risk_score = "High"
        elif score >= 3:
            profile.burnout_risk_score = "Medium"
        else:
            profile.burnout_risk_score = "Low"

        profile.save()
        return profile.burnout_risk_score
