from io import BytesIO
from django.core.files.base import ContentFile
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from .models import Invoice


def generate_invoice_pdf_task(invoice_id):
    """Generates the PDF invoice and updates the database file field."""
    try:
        invoice = Invoice.objects.get(id=invoice_id)
    except Invoice.DoesNotExist:
        return

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=54,
        leftMargin=54,
        topMargin=54,
        bottomMargin=54,
    )

    elements = []
    styles = getSampleStyleSheet()

    # Define custom styles
    title_style = ParagraphStyle(
        name="InvoiceTitle",
        parent=styles["Heading1"],
        fontSize=26,
        spaceAfter=15,
        textColor=colors.HexColor("#4F46E5"),
        alignment=0,  # Left
    )
    section_header = ParagraphStyle(
        name="SectionHeader",
        parent=styles["Heading2"],
        fontSize=14,
        spaceBefore=15,
        spaceAfter=10,
        textColor=colors.HexColor("#1F2937"),
        borderColor=colors.HexColor("#E5E7EB"),
        borderWidth=1,
        borderPadding=(0, 0, 4, 0),
    )
    text_style = ParagraphStyle(
        name="NormalText",
        parent=styles["Normal"],
        fontSize=10,
        spaceAfter=4,
        textColor=colors.HexColor("#4B5563"),
    )
    bold_text_style = ParagraphStyle(
        name="BoldText",
        parent=styles["Normal"],
        fontSize=10,
        spaceAfter=4,
        fontName="Helvetica-Bold",
        textColor=colors.HexColor("#1F2937"),
    )

    # 1. Title & Header
    elements.append(Paragraph("INVOICE", title_style))
    elements.append(Spacer(1, 10))

    # 2. Metadata Columns (Metadata on Left, Billing info on Right)
    invoice_date = (
        invoice.created_at.strftime("%Y-%m-%d %H:%M")
        if invoice.created_at
        else timezone.now().strftime("%Y-%m-%d %H:%M")
    )

    metadata_left = [
        Paragraph(
            f"<b>Invoice ID:</b> {invoice.stripe_invoice_id or invoice.id}", text_style
        ),
        Paragraph(f"<b>Date:</b> {invoice_date}", text_style),
        Paragraph(
            (
                f"<b>Status:</b> <font color='green'><b>{invoice.status.upper()}</b></font>"
                if invoice.status == "paid"
                else f"<b>Status:</b> {invoice.status.upper()}"
            ),
            text_style,
        ),
    ]
    metadata_right = [
        Paragraph(f"<b>Billed To:</b>", bold_text_style),
        Paragraph(f"Username: {invoice.user.username}", text_style),
        Paragraph(f"Email: {invoice.user.email}", text_style),
    ]

    col_widths = [250, 250]
    meta_table_data = [[metadata_left, metadata_right]]
    meta_table = Table(meta_table_data, colWidths=col_widths)
    meta_table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    elements.append(meta_table)
    elements.append(Spacer(1, 20))

    # 3. Line Items Table
    elements.append(Paragraph("Line Items", section_header))

    # Description mapping based on user plan
    sub_profile = getattr(invoice.user, "subscription", None)
    plan_name = (
        sub_profile.plan.name
        if sub_profile and sub_profile.plan
        else "Pro Plan Subscription"
    )

    table_data = [
        ["Description", "Quantity", "Unit Price", "Total"],
        [
            f"Open Source Contribution Atelier - {plan_name}",
            "1",
            f"${invoice.amount:.2f}",
            f"${invoice.amount:.2f}",
        ],
    ]

    item_table = Table(table_data, colWidths=[280, 60, 80, 80])
    item_table.setStyle(
        TableStyle(
            [
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("ALIGN", (1, 0), (-1, -1), "CENTER"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F3F4F6")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#111827")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    elements.append(item_table)
    elements.append(Spacer(1, 20))

    # 4. Summary Totals
    summary_data = [
        ["Subtotal:", f"${invoice.amount:.2f}"],
        ["Tax (0%):", "$0.00"],
        ["Total Amount:", f"${invoice.amount:.2f}"],
    ]
    summary_table = Table(summary_data, colWidths=[100, 80])
    summary_table.setStyle(
        TableStyle(
            [
                ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (0, 2), (-1, 2), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LINEABOVE", (0, 2), (1, 2), 1, colors.HexColor("#111827")),
            ]
        )
    )

    # Align the summary table to the right
    align_table = Table([[Spacer(1, 1), summary_table]], colWidths=[320, 180])
    align_table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    elements.append(align_table)
    elements.append(Spacer(1, 40))

    # 5. Footer note
    elements.append(
        Paragraph(
            "Thank you for supporting Open Source Contribution Atelier!",
            bold_text_style,
        )
    )
    elements.append(
        Paragraph(
            "If you have any questions about this billing statement, please reach out to billing@atelier.dev.",
            text_style,
        )
    )

    # Build Document
    doc.build(elements)
    pdf_bytes = buffer.getvalue()
    buffer.close()

    # Save content to FileField
    filename = f"invoice_{invoice.stripe_invoice_id or invoice.id}.pdf"
    invoice.pdf_file.save(filename, ContentFile(pdf_bytes), save=True)
