from github.service import github_service
from github.auth import refresh_github_token
import time
import logging

logger = logging.getLogger(__name__)


class NotificationsWorker:
    """Handles GitHub notifications using App authentication"""

    def __init__(self):
        self.service = github_service

    def process_notification(self, notification_data: dict) -> dict:
        """Process a single notification"""
        try:
            notification_type = notification_data.get("type")

            if notification_type == "issue_comment":
                return self._handle_issue_comment(notification_data)
            elif notification_type == "pull_request":
                return self._handle_pull_request(notification_data)
            else:
                logger.info(
                    f"Ignoring unhandled notification type: {notification_type}"
                )
                return {"status": "ignored", "type": notification_type}

        except Exception as e:
            logger.error(f"Failed to process notification: {e}")
            return {"status": "error", "error": str(e)}

    def _handle_issue_comment(self, data: dict) -> dict:
        """Handle issue comment notifications"""
        owner = data.get("repository", {}).get("owner", {}).get("login")
        repo = data.get("repository", {}).get("name")
        issue_number = data.get("issue", {}).get("number")
        comment_body = data.get("comment", {}).get("body")

        if not all([owner, repo, issue_number]):
            return {"status": "error", "message": "Missing required data"}

        # Create a reply
        reply_body = f"Thanks for your comment! This is an automated response from the GitHub App."

        try:
            response = github_service.create_issue_comment(
                owner, repo, issue_number, reply_body
            )
            return {
                "status": "success",
                "comment_id": response.get("id"),
                "message": "Reply posted successfully",
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _handle_pull_request(self, data: dict) -> dict:
        """Handle pull request notifications"""
        owner = data.get("repository", {}).get("owner", {}).get("login")
        repo = data.get("repository", {}).get("name")
        pr_number = data.get("pull_request", {}).get("number")

        if not all([owner, repo, pr_number]):
            return {"status": "error", "message": "Missing required data"}

        try:
            # Get PR details
            pr = github_service.get_pull_request(owner, repo, pr_number)

            # Add a review comment
            review_body = "Thank you for your contribution! We'll review this shortly."

            response = github_service.create_pull_request_review(
                owner, repo, pr_number, body=review_body, event="COMMENT"
            )

            return {
                "status": "success",
                "review_id": response.get("id"),
                "message": "Review posted successfully",
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def refresh_auth(self):
        """Refresh GitHub authentication"""
        return refresh_github_token()
