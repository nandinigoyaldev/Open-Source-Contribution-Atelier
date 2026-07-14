import logging
from celery import shared_task
from django.db.models import Sum
from .models import GeneratedPortfolio
from apps.progress.models import (
    UserBadge,
    LessonProgress,
    CodeSubmission,
    Certificate,
    StreakProfile,
    XPEvent,
)

logger = logging.getLogger(__name__)


@shared_task
def generate_portfolio_task(portfolio_id: str):
    """
    Celery task to generate the portfolio document.
    """
    try:
        portfolio = GeneratedPortfolio.objects.get(id=portfolio_id)
    except GeneratedPortfolio.DoesNotExist:
        logger.error(f"Portfolio {portfolio_id} does not exist.")
        return

    portfolio.status = GeneratedPortfolio.Status.PROCESSING
    portfolio.save(update_fields=["status"])

    try:
        user = portfolio.user
        sections = portfolio.sections_included

        # Gather data
        context_data = {
            "profile": True,
        }

        if sections.get("badges", True):
            context_data["badges"] = UserBadge.objects.filter(user=user).select_related(
                "badge"
            )

        if sections.get("certificates", True):
            context_data["certificates"] = Certificate.objects.filter(
                user=user, is_active=True
            )

        if sections.get("stats", True):
            # Calculate total XP
            total_xp = (
                XPEvent.objects.filter(user=user).aggregate(total=Sum("xp_delta"))[
                    "total"
                ]
                or 0
            )

            # Get Streak
            try:
                streak = StreakProfile.objects.get(user=user)
                current_streak = streak.current_streak
                longest_streak = streak.longest_streak
            except StreakProfile.DoesNotExist:
                current_streak = 0
                longest_streak = 0

            completed_lessons = LessonProgress.objects.filter(
                user=user, completed=True
            ).count()
            submissions = CodeSubmission.objects.filter(user=user).count()

            context_data["stats"] = {
                "total_xp": total_xp,
                "current_streak": current_streak,
                "longest_streak": longest_streak,
                "completed_lessons": completed_lessons,
                "code_submissions": submissions,
            }

        # Generate file
        from .utils import generate_pdf_report, generate_html_report

        if portfolio.format == GeneratedPortfolio.Format.PDF:
            file_content = generate_pdf_report(user, context_data)
            ext = "pdf"
        else:
            file_content = generate_html_report(user, context_data)
            ext = "html"

        # Save file to model
        filename = f"portfolio_{user.username}_{portfolio.id}.{ext}"
        portfolio.file.save(filename, file_content)

        portfolio.status = GeneratedPortfolio.Status.COMPLETED
        portfolio.save(update_fields=["status", "file"])

        # Send a real-time notification to the user
        from apps.notifications.services import NotificationService

        NotificationService.send_in_app_notification(
            user_id=user.id,
            notification_type="SYSTEM",
            title="Portfolio Ready",
            message=f"Your developer portfolio has been successfully generated.",
            link=f"/portfolio",
        )

    except Exception as e:
        logger.exception(f"Error generating portfolio {portfolio_id}: {e}")
        portfolio.status = GeneratedPortfolio.Status.FAILED
        portfolio.error_message = str(e)
        portfolio.save(update_fields=["status", "error_message"])
