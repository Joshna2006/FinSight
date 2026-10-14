
from io import BytesIO
import re
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    KeepTogether,
)


# --------------------------------------------------
# EXTRACT INVOICE ID
# --------------------------------------------------

def extract_invoice_id(finding):
    patterns = [
        r"\bInvoice:\s*([A-Za-z0-9_-]+)",
        r"\b(INV[A-Za-z0-9_-]*)\s*:",
        r"\bInvoice\s+([A-Za-z0-9_-]+)\b",
    ]

    for pattern in patterns:
        match = re.search(pattern, str(finding), re.IGNORECASE)
        if match:
            return match.group(1).upper()

    return "Not specified"


# --------------------------------------------------
# FINANCIAL AUDIT SUMMARY
# --------------------------------------------------

def build_audit_summary(results):
    """Collect financial calculation and payment issues."""

    issues = []

    # Calculation discrepancies from CSV and Excel files.
    for section, findings in results.items():
        if not section.lower().endswith((".csv", ".xlsx", ".xls")):
            continue

        for finding in findings:
            if "POSSIBLE CALCULATION ERROR" in str(finding).upper():
                issues.append({
                    "type": "Calculation Discrepancy",
                    "invoice": extract_invoice_id(finding),
                    "details": str(finding),
                })

    # Payment verification issues.
    for finding in results.get("Invoice-Payment Verification", []):
        upper = str(finding).upper()

        if "POSSIBLE UNDERPAYMENT" in upper:
            issue_type = "Outstanding Payment"

        elif "PAYMENT EXCEEDS RECORDED TOTAL" in upper:
            issue_type = "Payment Exceeds Invoice Total"

        elif (
            "NO MATCHING PAYMENT RECORD" in upper
            or "NO MATCHING INVOICE" in upper
        ):
            issue_type = "Missing Matching Record"

        else:
            continue

        issues.append({
            "type": issue_type,
            "invoice": extract_invoice_id(finding),
            "details": str(finding),
        })

    # Remove identical issues.
    unique_issues = []
    seen = set()

    for issue in issues:
        key = (
            issue["type"],
            issue["invoice"],
            issue["details"],
        )

        if key not in seen:
            unique_issues.append(issue)
            seen.add(key)

    return unique_issues


# --------------------------------------------------
# DOCUMENT WARNING DETECTION
# --------------------------------------------------

def is_document_warning(section, finding):
    """Identify document warnings regardless of section name."""

    text = str(finding).strip().upper()
    section_name = str(section).strip().upper()

    # Ignore general disclaimers and headings.
    if text.startswith("LIMITATION:"):
        return False

    warning_phrases = (
        "PDF AUTHOR METADATA IS MISSING",
        "AUTHOR METADATA IS MISSING",
        "INVALID PDF",
        "PDF IS ENCRYPTED",
        "PDF IS PASSWORD PROTECTED",
        "NO SELECTABLE TEXT",
        "UNREADABLE FILE",
        "EMPTY FILE",
        "FILE IS EMPTY",
        "FILE COULD NOT BE READ",
        "FAILED TO READ FILE",
        "CORRUPTED PDF",
        "PDF HAS NO PAGES",
        "MISSING REQUIRED METADATA",
    )

    if any(phrase in text for phrase in warning_phrases):
        return True

    # Handle other warning messages produced by the
    # document-authenticity module.
    if "AUTHENTICITY" in section_name:
        if any(
            word in text
            for word in (
                "WARNING",
                "MISSING",
                "ENCRYPTED",
                "UNREADABLE",
                "INVALID",
                "CORRUPTED",
                "EMPTY FILE",
            )
        ):
            return True

    return False


# --------------------------------------------------
# CATEGORY SUMMARY
# --------------------------------------------------

def build_category_summary(results, financial_issues):
    """Count financial issues, duplicate invoices and warnings."""

    financial_invoices = {
        issue["invoice"]
        for issue in financial_issues
        if issue["invoice"] != "Not specified"
    }

    duplicate_invoices = set()

    duplicate_sections = (
        "Duplicate Detection",
        "Similar-Invoice Detection",
    )

    for section in duplicate_sections:
        for finding in results.get(section, []):
            upper = str(finding).upper()

            if any(phrase in upper for phrase in (
                "POSSIBLE DUPLICATE INVOICE",
                "POSSIBLE REPEATED INVOICE ID",
                "REPEATED INVOICE IDENTIFIERS FOUND",
            )):
                invoice_id = extract_invoice_id(finding)

                if invoice_id != "Not specified":
                    duplicate_invoices.add(invoice_id)

    # Count each distinct warning message once.
    warning_messages = set()

    for section, findings in results.items():
        for finding in findings:
            if is_document_warning(section, finding):
                warning_messages.add(str(finding).strip())

    return {
        "financial_issue_count": len(financial_issues),
        "financial_invoice_count": len(financial_invoices),
        "duplicate_invoice_count": len(duplicate_invoices),
        "duplicate_invoice_ids": sorted(duplicate_invoices),
        "document_warning_count": len(warning_messages),
    }


# --------------------------------------------------
# PDF REPORT GENERATION
# --------------------------------------------------

def create_pdf_report(results):
    """Generate a downloadable FinSight audit PDF."""

    buffer = BytesIO()

    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title="FinSight Intelligent Financial Audit Report",
        author="FinSight",
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "FinSightTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=22,
        leading=27,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#16324f"),
        spaceAfter=6,
    )

    subtitle_style = ParagraphStyle(
        "FinSightSubtitle",
        parent=styles["Normal"],
        fontSize=9,
        leading=13,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#62748a"),
        spaceAfter=14,
    )

    section_style = ParagraphStyle(
        "FinSightSection",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=17,
        textColor=colors.HexColor("#16324f"),
        spaceBefore=10,
        spaceAfter=7,
        keepWithNext=True,
    )

    body_style = ParagraphStyle(
        "FinSightBody",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        spaceAfter=5,
        wordWrap="LTR",
    )

    small_style = ParagraphStyle(
        "FinSightSmall",
        parent=body_style,
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#526174"),
    )

    def safe_text(value):
        """Escape special characters for ReportLab paragraphs."""
        return (
            str(value)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

    story = []

    # REPORT HEADER

    story.append(Paragraph("FinSight", title_style))

    story.append(
        Paragraph(
            "Intelligent Financial Audit Report",
            subtitle_style,
        )
    )

    story.append(
        Paragraph(
            "Generated on: "
            + datetime.now().strftime("%d-%m-%Y %H:%M:%S"),
            body_style,
        )
    )

    story.append(Spacer(1, 8))

    # COMBINED AUDIT SUMMARY

    story.append(
        Paragraph("Combined Audit Summary", section_style)
    )

    issues = build_audit_summary(results)
    summary = build_category_summary(results, issues)

    # Diagnostic output in the VS Code terminal.
    print("AUDIT SUMMARY:", issues)
    print("CATEGORY SUMMARY:", summary)

    print("AUTHOR METADATA FINDINGS:", [
        (section, finding)
        for section, findings in results.items()
        for finding in findings
        if "author metadata" in str(finding).lower()
    ])

    summary_data = [
        ["Summary Measure", "Count"],
        [
            "Financial issues requiring review",
            str(summary["financial_issue_count"]),
        ],
        [
            "Unique financial invoices flagged",
            str(summary["financial_invoice_count"]),
        ],
        [
            "Possible duplicate invoices",
            str(summary["duplicate_invoice_count"]),
        ],
        [
            "Document warnings",
            str(summary["document_warning_count"]),
        ],
    ]

    summary_table = Table(
        summary_data,
        colWidths=[115 * mm, 35 * mm],
        repeatRows=1,
    )

    summary_table.setStyle(
        TableStyle([
            (
                "BACKGROUND",
                (0, 0),
                (-1, 0),
                colors.HexColor("#16324f"),
            ),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            (
                "GRID",
                (0, 0),
                (-1, -1),
                0.5,
                colors.HexColor("#d6dee8"),
            ),
            (
                "BACKGROUND",
                (0, 1),
                (-1, -1),
                colors.HexColor("#f3f6fa"),
            ),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 7),
            ("RIGHTPADDING", (0, 0), (-1, -1), 7),
            ("TOPPADDING", (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ])
    )

    story.append(summary_table)
    story.append(Spacer(1, 8))

    if summary["duplicate_invoice_ids"]:
        story.append(
            Paragraph(
                "Possible duplicate invoice IDs: "
                + safe_text(
                    ", ".join(summary["duplicate_invoice_ids"])
                ),
                body_style,
            )
        )

    # FINANCIAL ISSUES

    story.append(
        Paragraph(
            "Financial Issues Requiring Review",
            section_style,
        )
    )

    if issues:
        for issue in issues:
            issue_title = (
                f'{issue["invoice"]} — {issue["type"]}'
            )

            story.append(
                KeepTogether([
                    Paragraph(
                        safe_text(issue_title),
                        styles["Heading3"],
                    ),
                    Paragraph(
                        safe_text(issue["details"]),
                        body_style,
                    ),
                    Spacer(1, 5),
                ])
            )
    else:
        story.append(
            Paragraph(
                "No calculation discrepancies or payment issues "
                "were detected by these checks.",
                body_style,
            )
        )

    # DETAILED VERIFICATION FINDINGS

    story.append(Spacer(1, 8))

    story.append(
        Paragraph(
            "Detailed Verification Findings",
            section_style,
        )
    )

    for section_name, findings in results.items():
        story.append(
            Paragraph(
                safe_text(section_name),
                styles["Heading3"],
            )
        )

        for finding in findings:
            story.append(
                Paragraph(
                    "• " + safe_text(finding),
                    body_style,
                )
            )

        story.append(Spacer(1, 5))

    # DISCLAIMER

    story.append(Spacer(1, 10))

    story.append(
        Paragraph(
            "Review note: Automated findings are preliminary "
            "indicators for human review. They do not independently "
            "prove fraud or document authenticity.",
            small_style,
        )
    )

    # PAGE NUMBERS

    def add_page_number(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#62748a"))

        canvas.drawRightString(
            A4[0] - 18 * mm,
            10 * mm,
            f"Page {doc.page}",
        )

        canvas.restoreState()

    document.build(
        story,
        onFirstPage=add_page_number,
        onLaterPages=add_page_number,
    )

    buffer.seek(0)
    return buffer