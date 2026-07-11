import io
from django.core.files.base import ContentFile
from django.template.loader import render_to_string
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors


def generate_pdf_report(user, context_data):
    """
    Generates a PDF using reportlab.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=72,
        leftMargin=72,
        topMargin=72,
        bottomMargin=18,
    )

    styles = getSampleStyleSheet()
    title_style = styles["Heading1"]
    normal_style = styles["Normal"]

    Story = []

    # Title
    Story.append(Paragraph(f"Developer Portfolio: {user.username}", title_style))
    Story.append(Spacer(1, 12))

    # Profile Info
    profile = context_data.get("profile")
    if profile:
        Story.append(Paragraph("Profile Information", styles["Heading2"]))
        Story.append(
            Paragraph(f"Name: {user.get_full_name() or user.username}", normal_style)
        )
        Story.append(Paragraph(f"Email: {user.email}", normal_style))
        Story.append(Spacer(1, 12))

    # Badges
    badges = context_data.get("badges", [])
    if badges:
        Story.append(Paragraph("Badges Earned", styles["Heading2"]))
        for ub in badges:
            Story.append(
                Paragraph(
                    f"- {ub.badge.name} ({ub.earned_at.strftime('%Y-%m-%d')})",
                    normal_style,
                )
            )
        Story.append(Spacer(1, 12))

    # Certificates
    certs = context_data.get("certificates", [])
    if certs:
        Story.append(Paragraph("Certificates", styles["Heading2"]))
        for cert in certs:
            Story.append(
                Paragraph(
                    f"- {cert.course_name} (Issued: {cert.issued_at.strftime('%Y-%m-%d')})",
                    normal_style,
                )
            )
        Story.append(Spacer(1, 12))

    # Stats
    stats = context_data.get("stats")
    if stats:
        Story.append(Paragraph("Platform Statistics", styles["Heading2"]))
        data = [
            ["Total XP", str(stats.get("total_xp", 0))],
            ["Current Streak", f"{stats.get('current_streak', 0)} days"],
            ["Longest Streak", f"{stats.get('longest_streak', 0)} days"],
            ["Completed Lessons", str(stats.get("completed_lessons", 0))],
            ["Code Submissions", str(stats.get("code_submissions", 0))],
        ]
        t = Table(data)
        t.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                    ("TEXTCOLOR", (0, 0), (-1, -1), colors.black),
                    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                    ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
                    ("BACKGROUND", (0, 0), (0, -1), colors.lightgrey),
                ]
            )
        )
        Story.append(t)

    doc.build(Story)
    pdf_value = buffer.getvalue()
    buffer.close()

    return ContentFile(pdf_value)


def generate_html_report(user, context_data):
    """
    Generates an HTML report. We can just build a simple HTML string.
    """
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Portfolio - {user.username}</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; color: #333; }}
            h1 {{ color: #2563eb; }}
            h2 {{ color: #1e40af; border-bottom: 2px solid #e5e7eb; padding-bottom: 5px; }}
            .section {{ margin-bottom: 30px; }}
            .badge-list, .cert-list {{ list-style-type: none; padding: 0; }}
            .badge-list li, .cert-list li {{ background: #f3f4f6; margin: 5px 0; padding: 10px; border-radius: 5px; }}
            table {{ width: 100%; border-collapse: collapse; }}
            th, td {{ padding: 10px; border: 1px solid #e5e7eb; text-align: left; }}
            th {{ background: #f9fafb; }}
        </style>
    </head>
    <body>
        <h1>Developer Portfolio: {user.username}</h1>
        
        <div class="section">
            <h2>Profile Information</h2>
            <p><strong>Name:</strong> {user.get_full_name() or user.username}</p>
            <p><strong>Email:</strong> {user.email}</p>
        </div>
    """

    badges = context_data.get("badges", [])
    if badges:
        html_content += (
            '<div class="section"><h2>Badges Earned</h2><ul class="badge-list">'
        )
        for ub in badges:
            html_content += (
                f"<li>{ub.badge.name} ({ub.earned_at.strftime('%Y-%m-%d')})</li>"
            )
        html_content += "</ul></div>"

    certs = context_data.get("certificates", [])
    if certs:
        html_content += (
            '<div class="section"><h2>Certificates</h2><ul class="cert-list">'
        )
        for cert in certs:
            html_content += f"<li>{cert.course_name} (Issued: {cert.issued_at.strftime('%Y-%m-%d')})</li>"
        html_content += "</ul></div>"

    stats = context_data.get("stats")
    if stats:
        html_content += f"""
        <div class="section">
            <h2>Platform Statistics</h2>
            <table>
                <tr><th>Total XP</th><td>{stats.get('total_xp', 0)}</td></tr>
                <tr><th>Current Streak</th><td>{stats.get('current_streak', 0)} days</td></tr>
                <tr><th>Longest Streak</th><td>{stats.get('longest_streak', 0)} days</td></tr>
                <tr><th>Completed Lessons</th><td>{stats.get('completed_lessons', 0)}</td></tr>
                <tr><th>Code Submissions</th><td>{stats.get('code_submissions', 0)}</td></tr>
            </table>
        </div>
        """

    html_content += """
    </body>
    </html>
    """

    return ContentFile(html_content.encode("utf-8"))
