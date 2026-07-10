from io import BytesIO
from django.contrib.auth.models import User
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

from apps.progress.models import (
    LessonProgress,
    UserBadge,
    Certificate,
    CodeSubmission,
    StreakProfile,
)


class PDFReportGenerator:
    """Service to generate PDF reports for user progress and achievements."""

    def __init__(self, user: User):
        self.user = user
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()

    def _setup_custom_styles(self):
        """Define custom paragraph styles for the PDF."""
        self.styles.add(
            ParagraphStyle(
                name="ReportTitle",
                parent=self.styles["Heading1"],
                fontSize=24,
                spaceAfter=20,
                textColor=colors.HexColor("#4F46E5"),
                alignment=1,  # Center
            )
        )
        self.styles.add(
            ParagraphStyle(
                name="SectionHeader",
                parent=self.styles["Heading2"],
                fontSize=16,
                spaceBefore=15,
                spaceAfter=10,
                textColor=colors.HexColor("#1F2937"),
                borderPadding=(0, 0, 4, 0),
                borderColor=colors.HexColor("#D1D5DB"),
                borderWidth=1,
            )
        )
        self.styles.add(
            ParagraphStyle(
                name="NormalText",
                parent=self.styles["Normal"],
                fontSize=11,
                spaceAfter=6,
                textColor=colors.HexColor("#4B5563"),
            )
        )

    def generate(self) -> bytes:
        """Generates the PDF document and returns it as a bytes payload."""
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=50,
            leftMargin=50,
            topMargin=50,
            bottomMargin=50,
        )

        elements = []

        # 1. Header
        elements.append(
            Paragraph("User Progress & Achievement Report", self.styles["ReportTitle"])
        )

        gen_date = timezone.now().strftime("%Y-%m-%d %H:%M")
        elements.append(
            Paragraph(f"<b>User:</b> {self.user.username}", self.styles["NormalText"])
        )
        elements.append(
            Paragraph(f"<b>Email:</b> {self.user.email}", self.styles["NormalText"])
        )
        elements.append(
            Paragraph(f"<b>Generated on:</b> {gen_date}", self.styles["NormalText"])
        )
        elements.append(Spacer(1, 20))

        # 2. Summary
        elements.append(Paragraph("Summary", self.styles["SectionHeader"]))

        streak_profile = StreakProfile.objects.filter(user=self.user).first()
        current_streak = streak_profile.current_streak if streak_profile else 0
        longest_streak = streak_profile.longest_streak if streak_profile else 0

        completed_lessons_count = LessonProgress.objects.filter(
            user=self.user, completed=True
        ).count()

        summary_data = [
            ["Current Streak", f"{current_streak} days"],
            ["Longest Streak", f"{longest_streak} days"],
            ["Completed Lessons", str(completed_lessons_count)],
        ]
        summary_table = Table(summary_data, colWidths=[150, 150])
        summary_table.setStyle(self._get_standard_table_style())
        elements.append(summary_table)
        elements.append(Spacer(1, 20))

        # 3. Learning Progress
        elements.append(Paragraph("Learning Progress", self.styles["SectionHeader"]))
        lessons = (
            LessonProgress.objects.filter(user=self.user)
            .select_related("lesson")
            .order_by("-updated_at")[:20]
        )

        if lessons:
            lesson_data = [["Lesson Name", "Status", "Score", "Last Attempt"]]
            for lp in lessons:
                status = "Completed" if lp.completed else "In Progress"
                date_str = (
                    lp.updated_at.strftime("%Y-%m-%d") if lp.updated_at else "N/A"
                )
                lesson_data.append(
                    [
                        lp.lesson.title[:40]
                        + ("..." if len(lp.lesson.title) > 40 else ""),
                        status,
                        str(lp.score),
                        date_str,
                    ]
                )

            lesson_table = Table(lesson_data, colWidths=[240, 90, 60, 100])
            lesson_table.setStyle(self._get_standard_table_style(has_header=True))
            elements.append(lesson_table)
        else:
            elements.append(
                Paragraph(
                    "No learning progress recorded yet.", self.styles["NormalText"]
                )
            )
        elements.append(Spacer(1, 20))

        # 4. Achievements & Badges
        elements.append(
            Paragraph("Achievements & Badges", self.styles["SectionHeader"])
        )
        badges = (
            UserBadge.objects.filter(user=self.user)
            .select_related("badge")
            .order_by("-earned_at")
        )

        if badges:
            badge_data = [["Badge Name", "Category", "Earned Date"]]
            for ub in badges:
                badge_data.append(
                    [
                        ub.badge.name,
                        ub.badge.category.title(),
                        ub.earned_at.strftime("%Y-%m-%d"),
                    ]
                )
            badge_table = Table(badge_data, colWidths=[200, 150, 140])
            badge_table.setStyle(self._get_standard_table_style(has_header=True))
            elements.append(badge_table)
        else:
            elements.append(
                Paragraph("No badges earned yet.", self.styles["NormalText"])
            )
        elements.append(Spacer(1, 20))

        # 5. Certificates
        elements.append(Paragraph("Certifications", self.styles["SectionHeader"]))
        certificates = Certificate.objects.filter(
            user=self.user, is_active=True
        ).order_by("-issued_at")

        if certificates:
            cert_data = [["Course Name", "Verification Hash", "Issued Date"]]
            for cert in certificates:
                cert_data.append(
                    [
                        cert.course_name,
                        cert.verification_hash[:16] + "...",
                        cert.issued_at.strftime("%Y-%m-%d"),
                    ]
                )
            cert_table = Table(cert_data, colWidths=[200, 150, 140])
            cert_table.setStyle(self._get_standard_table_style(has_header=True))
            elements.append(cert_table)
        else:
            elements.append(
                Paragraph("No active certificates found.", self.styles["NormalText"])
            )
        elements.append(Spacer(1, 20))

        # 6. Coding Activity
        elements.append(Paragraph("Coding Activity", self.styles["SectionHeader"]))
        submissions = CodeSubmission.objects.filter(user=self.user).order_by(
            "-created_at"
        )[:10]

        if submissions:
            sub_data = [["Title", "Status", "Submitted On"]]
            for sub in submissions:
                sub_data.append(
                    [
                        sub.title[:45] + ("..." if len(sub.title) > 45 else ""),
                        sub.get_status_display(),
                        sub.created_at.strftime("%Y-%m-%d"),
                    ]
                )
            sub_table = Table(sub_data, colWidths=[250, 120, 120])
            sub_table.setStyle(self._get_standard_table_style(has_header=True))
            elements.append(sub_table)
        else:
            elements.append(
                Paragraph("No code submissions found.", self.styles["NormalText"])
            )

        # Build Document
        doc.build(elements)
        pdf_bytes = buffer.getvalue()
        buffer.close()

        return pdf_bytes

    def _get_standard_table_style(self, has_header: bool = False) -> TableStyle:
        """Returns a consistent, clean table style."""
        commands = [
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
        ]

        if has_header:
            commands.extend(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F3F4F6")),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#111827")),
                ]
            )

        return TableStyle(commands)
