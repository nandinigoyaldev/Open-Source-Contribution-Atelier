"""
Celery tasks for PR review bot.
"""

from celery import shared_task
from django.core.cache import cache
import logging
from apps.pr_review_bot.services.code_analyzer import CodeAnalyzer
from apps.pr_review_bot.services.llm_analyzer import LLMAnalyzer
from apps.pr_review_bot.services.github_client import GitHubClient
from apps.pr_review_bot.models import PRReview, CodeIssue, ReviewConfig

logger = logging.getLogger(__name__)


@shared_task
def review_pr(repo: str, pr_number: int):
    """
    Review a PR asynchronously.
    """
    logger.info(f"Starting review for PR #{pr_number} in {repo}")
    
    # Check config
    config = ReviewConfig.objects.get(repository=repo)
    
    # Get PR info
    client = GitHubClient()
    pr_info = client.get_pr_info(repo, pr_number)
    pr_files = client.get_pr_files(repo, pr_number)
    
    if not pr_info or not pr_files:
        logger.error(f"Failed to fetch PR #{pr_number}")
        return {'error': 'Failed to fetch PR'}
    
    # Create review record
    review = PRReview.objects.create(
        pr_number=pr_number,
        repository=repo,
        pr_title=pr_info.get('title', ''),
        pr_description=pr_info.get('body', ''),
        pr_author=pr_info.get('user', {}).get('login', ''),
        pr_url=pr_info.get('html_url', ''),
        status='processing'
    )
    
    issues = []
    
    # Analyze each file
    for file in pr_files:
        filename = file.get('filename', '')
        patch = file.get('patch', '')
        
        if not patch or not filename:
            continue
        
        # Skip non-code files
        if not any(ext in filename for ext in ['.py', '.js', '.ts', '.jsx', '.tsx']):
            continue
        
        # Analyze code
        analyzer = CodeAnalyzer()
        file_issues = analyzer.analyze_python_code(patch, filename)
        
        for issue in file_issues:
            issues.append({
                **issue,
                'file_path': filename
            })
    
    # LLM analysis (if enabled)
    if getattr(settings, 'ENABLE_LLM_REVIEW', False):
        llm_analyzer = LLMAnalyzer()
        for file in pr_files:
            patch = file.get('patch', '')
            if patch:
                llm_result = llm_analyzer.analyze_code(patch, file.get('filename', ''))
                if llm_result:
                    for issue in llm_result.get('issues', []):
                        issues.append({
                            'type': 'llm',
                            'severity': issue.get('severity', 'warning'),
                            'title': issue.get('title', 'LLM suggestion'),
                            'description': issue.get('description', ''),
                            'file_path': file.get('filename', ''),
                            'suggestion': issue.get('suggestion', ''),
                        })
    
    # Save issues
    for issue_data in issues:
        CodeIssue.objects.create(
            review=review,
            **issue_data
        )
    
    # Calculate scores
    quality_score = max(0, 100 - len(issues) * 5)
    review.quality_score = quality_score
    review.status = 'completed'
    review.processed_at = timezone.now()
    review.save()
    
    # Post comments
    if config.auto_comment:
        post_review_comments.delay(repo, pr_number, str(review.id))
    
    logger.info(f"Review completed for PR #{pr_number}: {len(issues)} issues found")
    return {'review_id': str(review.id), 'issues_count': len(issues)}


@shared_task
def post_review_comments(repo: str, pr_number: int, review_id: str):
    """
    Post review comments on PR.
    """
    try:
        review = PRReview.objects.get(id=review_id)
    except PRReview.DoesNotExist:
        logger.error(f"Review {review_id} not found")
        return
    
    client = GitHubClient()
    
    # Get PR info for commit SHA
    pr_info = client.get_pr_info(repo, pr_number)
    commit_id = pr_info.get('head', {}).get('sha')
    
    # Post summary comment
    summary = review.summary or generate_summary(review)
    client.post_review(repo, pr_number, summary)
    
    # Post individual comments for critical issues
    critical_issues = review.issues.filter(severity='critical')
    for issue in critical_issues:
        body = f"""
### {issue.title}

**Severity:** {issue.severity}
**Description:** {issue.description}
**File:** {issue.file_path}
**Line:** {issue.line_number}

**Suggestion:** {issue.suggestion}

```python
{issue.suggested_code}