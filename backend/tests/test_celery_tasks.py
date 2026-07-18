import pytest
from unittest.mock import patch, MagicMock
from tasks import example_task, MonitoredTask
from apps.portfolio.tasks import generate_portfolio_task
from apps.portfolio.models import GeneratedPortfolio
from django.contrib.auth import get_user_model

User = get_user_model()


class TestCeleryTasks:
    @patch("tasks.monitor.track_task")
    def test_example_task(self, mock_track):
        result = example_task(data={})
        assert result == {"status": "completed"}
        mock_track.assert_called_once()
        args = mock_track.call_args[0]
        assert args[0] == example_task.name
        assert args[2] == "success"

    @patch("tasks.monitor.track_task")
    def test_example_task_failure(self, mock_track):
        class FailingTask(MonitoredTask):
            def run(self, *args, **kwargs):
                raise ValueError("Test error")

        task = FailingTask()
        task.name = "failing_task"
        
        with pytest.raises(ValueError, match="Test error"):
            task()
            
        mock_track.assert_called_once()
        args = mock_track.call_args[0]
        assert args[0] == "failing_task"
        assert args[2] == "failed"
        assert args[3] == "Test error"

    @pytest.mark.django_db
    @patch("apps.portfolio.tasks.generate_pdf_report")
    @patch("apps.portfolio.tasks.NotificationService.send_in_app_notification")
    def test_generate_portfolio_task_pdf(self, mock_notify, mock_generate_pdf):
        mock_generate_pdf.return_value = b"mock pdf content"
        user = User.objects.create(username="portfoliouser", email="p@example.com")
        portfolio = GeneratedPortfolio.objects.create(
            user=user,
            format=GeneratedPortfolio.Format.PDF,
            sections_included={"stats": True, "badges": True, "certificates": True},
        )

        generate_portfolio_task(str(portfolio.id))
        
        portfolio.refresh_from_db()
        assert portfolio.status == GeneratedPortfolio.Status.COMPLETED
        assert portfolio.file.name.endswith(".pdf")
        assert portfolio.file.name.startswith("portfolio_portfoliouser_")
        
        mock_generate_pdf.assert_called_once()
        mock_notify.assert_called_once()

    @pytest.mark.django_db
    def test_generate_portfolio_task_not_found(self):
        # Should not raise exception but return cleanly
        generate_portfolio_task("invalid-id")

    @pytest.mark.django_db
    @patch("apps.portfolio.tasks.GeneratedPortfolio.objects.get")
    def test_generate_portfolio_task_exception(self, mock_get):
        user = User.objects.create(username="portfoliouser2", email="p2@example.com")
        portfolio = GeneratedPortfolio.objects.create(
            user=user,
            format=GeneratedPortfolio.Format.PDF,
            sections_included={},
        )
        mock_get.side_effect = Exception("Random error")
        # Wait, if get fails, it just logs error and returns
        generate_portfolio_task(str(portfolio.id))
        # No status change because it failed on get.
        portfolio.refresh_from_db()
        assert portfolio.status == GeneratedPortfolio.Status.PENDING

    @pytest.mark.django_db
    @patch("apps.portfolio.tasks.generate_pdf_report")
    def test_generate_portfolio_task_generation_error(self, mock_generate_pdf):
        mock_generate_pdf.side_effect = Exception("PDF Gen Error")
        user = User.objects.create(username="portfoliouser3", email="p3@example.com")
        portfolio = GeneratedPortfolio.objects.create(
            user=user,
            format=GeneratedPortfolio.Format.PDF,
            sections_included={},
        )

        generate_portfolio_task(str(portfolio.id))
        
        portfolio.refresh_from_db()
        assert portfolio.status == GeneratedPortfolio.Status.FAILED
        assert portfolio.error_message == "PDF Gen Error"
