
import streamlit as st
from datetime import datetime
from io import BytesIO
from pathlib import Path
import re

from modules.document_reader import read_document
from modules.document_authenticity import check_authenticity
from modules.information_verification import verify_information
from modules.duplicate_detection import (
    find_duplicates,
    find_similar_invoices,
)
from modules.cross_document_check import (
    compare_documents,
    compare_invoice_payments,
)
from modules.audit_report import create_pdf_report
from modules.financial_verification import verify_financial_file


# --------------------------------------------------
# HELPER FUNCTIONS
# --------------------------------------------------

def to_findings_list(value):
    if value is None:
        return ["No findings were returned by this check."]
    if isinstance(value, str):
        return [value]
    try:
        return [str(item) for item in value]
    except TypeError:
        return [str(value)]


def remove_repeated_findings(findings):
    unique = []
    seen = set()

    for finding in findings:
        finding = str(finding).strip()
        if finding and finding not in seen:
            unique.append(finding)
            seen.add(finding)

    return unique or ["No findings were returned."]


def add_result(results, section, findings):
    results[section] = remove_repeated_findings(
        to_findings_list(findings)
    )


def extract_invoice_id(finding):
    patterns = [
        r"\bInvoice:\s*([A-Za-z0-9_-]+)",
        r"\b(INV[A-Za-z0-9_-]*)\s*:",
    ]

    for pattern in patterns:
        match = re.search(pattern, str(finding), re.IGNORECASE)
        if match:
            return match.group(1).strip().upper()

    return "Not specified"


def build_audit_summary(results):
    """Collect financial issues from the detailed findings."""
    issues = []

    for section, findings in results.items():
        if not section.lower().endswith((".csv", ".xlsx")):
            continue

        for finding in findings:
            upper = finding.upper()

            if "POSSIBLE CALCULATION ERROR" in upper:
                issues.append({
                    "type": "Calculation Discrepancy",
                    "invoice": extract_invoice_id(finding),
                    "details": finding,
                })

    payment_findings = results.get(
        "Invoice-Payment Verification", []
    )

    for finding in payment_findings:
        upper = finding.upper()

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
            "details": finding,
        })

    # Remove repeated copies of the same financial issue.
    unique = []
    seen = set()

    for issue in issues:
        key = (
            issue["type"],
            issue["invoice"],
            issue["details"],
        )
        if key not in seen:
            unique.append(issue)
            seen.add(key)

    return unique


def build_category_summary(results, financial_issues):
    """Calculate separate financial, duplicate, and document counts."""

    # Financial issue count and unique invoices.
    financial_invoices = {
        issue["invoice"]
        for issue in financial_issues
        if issue["invoice"] != "Not specified"
    }

    # Duplicate invoice IDs: use a set to avoid counting the same
    # invoice twice when several modules report the same duplicate.
    duplicate_invoices = set()

    for section, findings in results.items():
        if section not in (
            "Duplicate Detection",
            "Similar-Invoice Detection",
        ):
            continue

        for finding in findings:
            upper = finding.upper()

            if (
                "POSSIBLE DUPLICATE INVOICE" in upper
                or "POSSIBLE REPEATED INVOICE ID" in upper
                or "REPEATED INVOICE IDENTIFIERS FOUND" in upper
            ):
                invoice_id = extract_invoice_id(finding)

                if invoice_id != "Not specified":
                    duplicate_invoices.add(invoice_id)

    # Count document warnings from authenticity findings only.
    # Missing metadata is a warning, not proof of tampering.
    document_warnings = set()
    warning_terms = (
        "WARNING",
        "MISSING",
        "COULD NOT BE READ",
        "COULD NOT READ",
        "ENCRYPTED",
        "NO SELECTABLE TEXT",
        "INVALID PDF",
        "EMPTY FILE",
        "UNREADABLE",
    )

    for section, findings in results.items():
        in_authenticity_section = False

        for finding in findings:
            upper = finding.upper()

            if "DOCUMENT AUTHENTICITY INDICATORS" in upper:
                in_authenticity_section = True
                continue

            if "INFORMATION VERIFICATION" in upper:
                in_authenticity_section = False

            if (
                in_authenticity_section
                and any(term in upper for term in warning_terms)
            ):
                # Count the warning once per file and finding.
                document_warnings.add((section, finding))

    return {
        "financial_issue_count": len(financial_issues),
        "financial_invoice_count": len(financial_invoices),
        "duplicate_invoice_count": len(duplicate_invoices),
        "duplicate_invoice_ids": sorted(duplicate_invoices),
        "document_warning_count": len(document_warnings),
    }


def get_information_text(file_name, file_bytes, extracted_text):
    """Use original file text for TXT and CSV files when possible."""
    extension = Path(file_name).suffix.lower()

    if extension in (".csv", ".txt"):
        try:
            return file_bytes.decode("utf-8-sig")
        except UnicodeDecodeError:
            try:
                return file_bytes.decode("latin-1")
            except Exception:
                pass

    return "" if extracted_text is None else str(extracted_text)


# --------------------------------------------------
# PAGE CONFIGURATION
# --------------------------------------------------

st.set_page_config(
    page_title="FinSight | Intelligent Audit Platform",
    page_icon="🔎",
    layout="wide",
)

css_path = Path("static/style.css")

if css_path.exists():
    st.markdown(
        f"<style>{css_path.read_text(encoding='utf-8')}</style>",
        unsafe_allow_html=True,
    )

st.markdown(
    """
    <style>
    .main-title {
        font-size: 2.5rem;
        font-weight: 800;
        color: #16324f;
    }
    .subtitle {
        color: #62748a;
        font-size: 1rem;
        margin-bottom: 1.5rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# --------------------------------------------------
# SIDEBAR AND HEADER
# --------------------------------------------------

st.sidebar.markdown("# 🔎 FinSight")
st.sidebar.caption("INTELLIGENT AUDIT PLATFORM")
st.sidebar.divider()

page = st.sidebar.radio(
    "NAVIGATION",
    ["Dashboard", "Verify Documents", "Verification Guide"],
)

st.sidebar.divider()
st.sidebar.subheader("System status")
st.sidebar.success("Application running")
st.sidebar.caption("Local development version")

st.markdown(
    '<div class="main-title">FinSight</div>',
    unsafe_allow_html=True,
)
st.markdown(
    '<div class="subtitle">'
    'AI-assisted financial document verification and audit review'
    '</div>',
    unsafe_allow_html=True,
)


# --------------------------------------------------
# DASHBOARD
# --------------------------------------------------

if page == "Dashboard":
    st.subheader("Audit Dashboard")

    col1, col2, col3 = st.columns(3)
    col1.metric("Verification Modules", "6")
    col2.metric("Report Format", "PDF")
    col3.metric("Review Mode", "Automated")

    st.markdown("### Available Features")

    left, right = st.columns(2)

    with left:
        st.info(
            "**Financial Calculation Verification**\n\n"
            "Checks quantity multiplied by unit price against "
            "the recorded total."
        )
        st.info(
            "**Invoice-Payment Verification**\n\n"
            "Compares invoice totals with payment records."
        )
        st.info(
            "**Exact Duplicate Detection**\n\n"
            "Finds files with identical contents."
        )

    with right:
        st.info(
            "**Similar-Invoice Detection**\n\n"
            "Flags potentially repeated or similar invoice records."
        )
        st.info(
            "**Cross-Document Comparison**\n\n"
            "Checks extracted text for exact matches."
        )
        st.info(
            "**PDF Audit Report**\n\n"
            "Generates a downloadable report of verification findings."
        )

    st.warning(
        "FinSight provides preliminary indicators for human review. "
        "Automated checks do not prove fraud or authenticity."
    )


# --------------------------------------------------
# VERIFY DOCUMENTS
# --------------------------------------------------

elif page == "Verify Documents":
    st.subheader("Upload Financial Documents")
    st.write(
        "Upload invoices, sales records, payment records, "
        "or other supported documents."
    )

    uploaded_files = st.file_uploader(
        "Choose documents",
        type=["pdf", "txt", "csv", "xlsx"],
        accept_multiple_files=True,
    )

    if not uploaded_files:
        st.info("Upload one or more documents to begin verification.")

    elif st.button("Run Verification", type="primary"):
        results = {}
        documents = {}
        file_data = []
        uploaded_data = {}

        progress = st.progress(0)
        status = st.empty()
        total_files = len(uploaded_files)

        for index, uploaded_file in enumerate(uploaded_files):
            file_name = uploaded_file.name
            normalized_name = file_name.lower()
            file_bytes = uploaded_file.getvalue()

            file_data.append((file_name, file_bytes))
            uploaded_data[normalized_name] = file_bytes
            status.write(f"Checking {file_name}...")

            findings = []

            try:
                extracted_text = read_document(file_name, file_bytes)
                if extracted_text is None:
                    extracted_text = ""

                documents[file_name] = str(extracted_text)

                findings.append("DOCUMENT AUTHENTICITY INDICATORS")
                authenticity_findings = check_authenticity(
                    file_name, file_bytes
                )
                findings.extend(to_findings_list(authenticity_findings))

                findings.append("INFORMATION VERIFICATION")
                information_text = get_information_text(
                    file_name, file_bytes, extracted_text
                )
                information_findings = verify_information(
                    file_name, information_text
                )
                findings.extend(to_findings_list(information_findings))

                if normalized_name.endswith((".csv", ".xlsx")):
                    findings.append("FINANCIAL CALCULATION VERIFICATION")
                    financial_findings = verify_financial_file(
                        file_name, file_bytes
                    )
                    findings.extend(to_findings_list(financial_findings))

                add_result(results, file_name, findings)

            except Exception as error:
                add_result(
                    results,
                    file_name,
                    [
                        "Could not process this file: "
                        f"{type(error).__name__}: {error}"
                    ],
                )

            progress.progress((index + 1) / total_files)

        status.success("Document processing completed.")

        # Exact duplicate detection.
        try:
            add_result(
                results, "Duplicate Detection", find_duplicates(file_data)
            )
        except Exception as error:
            add_result(
                results, "Duplicate Detection",
                [f"Duplicate detection failed: {error}"],
            )

        # Similar-invoice detection.
        try:
            add_result(
                results,
                "Similar-Invoice Detection",
                find_similar_invoices(file_data),
            )
        except Exception as error:
            add_result(
                results, "Similar-Invoice Detection",
                [f"Similar-invoice detection failed: {error}"],
            )

        # Cross-document comparison.
        try:
            add_result(
                results, "Cross-Document Comparison",
                compare_documents(documents),
            )
        except Exception as error:
            add_result(
                results, "Cross-Document Comparison",
                [f"Cross-document comparison failed: {error}"],
            )

        # Invoice-payment verification.
        sales_data = uploaded_data.get("sales.csv")
        payment_data = uploaded_data.get("payment_records.csv")

        if sales_data is not None and payment_data is not None:
            try:
                payment_findings = compare_invoice_payments(
                    sales_data, payment_data
                )
                add_result(
                    results,
                    "Invoice-Payment Verification",
                    payment_findings,
                )
            except Exception as error:
                add_result(
                    results,
                    "Invoice-Payment Verification",
                    [
                        "Invoice-payment comparison failed: "
                        f"{type(error).__name__}: {error}"
                    ],
                )
        else:
            add_result(
                results,
                "Invoice-Payment Verification",
                [
                    "Upload both sales.csv and payment_records.csv "
                    "to compare invoices with their payments."
                ],
            )

        # Build separate counts.
        audit_issues = build_audit_summary(results)
        category_summary = build_category_summary(results, audit_issues)

        # Combined summary.
        st.divider()
        st.subheader("📋 Combined Audit Summary")

        metric1, metric2, metric3 = st.columns(3)
        metric1.metric(
            "Financial Issues",
            category_summary["financial_issue_count"],
        )
        metric2.metric(
            "Possible Duplicate Invoices",
            category_summary["duplicate_invoice_count"],
        )
        metric3.metric(
            "Document Warnings",
            category_summary["document_warning_count"],
        )

        st.caption(
            f'Unique financial invoices flagged: '
            f'{category_summary["financial_invoice_count"]}'
        )

        if category_summary["duplicate_invoice_ids"]:
            st.caption(
                "Possible duplicate invoice IDs: "
                + ", ".join(category_summary["duplicate_invoice_ids"])
            )

        if audit_issues:
            st.markdown("### Financial Issues Requiring Review")
            for issue in audit_issues:
                with st.expander(
                    f'{issue["invoice"]} — {issue["type"]}',
                    expanded=True,
                ):
                    st.warning(issue["details"])
        else:
            st.success(
                "No calculation discrepancies or payment issues "
                "were detected by these checks."
            )

        st.caption(
            "These are preliminary audit indicators. Review the source "
            "documents before making financial decisions."
        )

        # Detailed findings.
        st.divider()
        st.subheader("Verification Findings")

        for section_name, findings in results.items():
            with st.expander(section_name, expanded=True):
                for finding in findings:
                    st.write(f"• {finding}")

        # PDF report.
        st.divider()
        st.subheader("Audit Report")

        try:
            pdf_report = create_pdf_report(results)

            if isinstance(pdf_report, BytesIO):
                pdf_bytes = pdf_report.getvalue()
            elif isinstance(pdf_report, bytes):
                pdf_bytes = pdf_report
            elif isinstance(pdf_report, bytearray):
                pdf_bytes = bytes(pdf_report)
            else:
                raise TypeError(
                    "create_pdf_report() must return bytes "
                    "or a BytesIO object."
                )

            if not pdf_bytes.startswith(b"%PDF"):
                raise ValueError("The generated content is not a valid PDF.")

            st.download_button(
                label="⬇️ Download PDF Audit Report",
                data=pdf_bytes,
                file_name=(
                    "FinSight_Audit_Report_"
                    + datetime.now().strftime("%Y%m%d_%H%M%S")
                    + ".pdf"
                ),
                mime="application/pdf",
                type="primary",
                use_container_width=True,
            )

            st.success("PDF audit report generated successfully.")

        except Exception as error:
            st.error(
                "Could not generate the PDF report. "
                "Check modules/audit_report.py. "
                f"Details: {error}"
            )

        st.caption(
            "Important: Automated findings do not, by themselves, "
            "prove fraud or document authenticity."
        )


# --------------------------------------------------
# VERIFICATION GUIDE
# --------------------------------------------------

elif page == "Verification Guide":
    st.subheader("Verification Guide")

    st.markdown(
        """
        ### 1. Financial Calculation Verification
        Checks whether quantity multiplied by unit price matches
        the recorded total.

        ### 2. Invoice-Payment Verification
        Compares invoice totals with payment records and highlights
        possible underpayments, overpayments, and missing records.

        ### 3. Exact Duplicate Detection
        Uses SHA-256 hashes to identify files with identical contents.

        ### 4. Similar-Invoice Detection
        Flags potentially repeated or similar invoice records.
        Review all matches manually.

        ### 5. Cross-Document Comparison
        Checks whether extracted document text is identical.

        ### 6. PDF Audit Report
        Creates a downloadable PDF containing verification findings.

        ### Current Limitations
        - Scanned PDFs may require OCR.
        - Advanced document authenticity checks are not implemented.
        - Similar-invoice results require manual review.
        - Keyword presence does not validate every field.
        - Automated findings require human review.
        """
    )