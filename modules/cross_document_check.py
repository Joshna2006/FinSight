
import pandas as pd
from io import BytesIO


def compare_documents(documents):
    """Compare extracted text from uploaded documents."""

    findings = []
    names = list(documents.keys())

    if len(names) < 2:
        return ["Upload at least two documents for comparison."]

    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            file1 = names[i]
            file2 = names[j]

            text1 = str(documents[file1]).strip()
            text2 = str(documents[file2]).strip()

            if text1 and text1 == text2:
                findings.append(
                    f"Identical extracted content found in "
                    f"{file1} and {file2}."
                )

    if not findings:
        findings.append(
            "No identical extracted text found between documents."
        )

    return findings


def compare_invoice_payments(sales_bytes, payment_bytes):
    """Compare recorded invoice totals with payment amounts."""

    findings = []

    try:
        sales = pd.read_csv(BytesIO(sales_bytes))
        payments = pd.read_csv(BytesIO(payment_bytes))

        # Normalize column names
        sales.columns = sales.columns.str.strip().str.lower()
        payments.columns = payments.columns.str.strip().str.lower()

        required_sales = {
            "invoice_number", "total_amount"
        }
        required_payments = {
            "invoice_number", "payment_amount"
        }

        if not required_sales.issubset(sales.columns):
            return [
                "Sales file must contain invoice_number "
                "and total_amount columns."
            ]

        if not required_payments.issubset(payments.columns):
            return [
                "Payment file must contain invoice_number "
                "and payment_amount columns."
            ]

        sales["invoice_number"] = (
            sales["invoice_number"].astype(str).str.strip().str.upper()
        )
        payments["invoice_number"] = (
            payments["invoice_number"].astype(str).str.strip().str.upper()
        )

        sales["total_amount"] = pd.to_numeric(
            sales["total_amount"], errors="coerce"
        )
        payments["payment_amount"] = pd.to_numeric(
            payments["payment_amount"], errors="coerce"
        )

        # Report repeated invoice IDs rather than silently combining them.
        duplicate_sales = sales[
            sales["invoice_number"].duplicated(keep=False)
        ]
        duplicate_payments = payments[
            payments["invoice_number"].duplicated(keep=False)
        ]

        if not duplicate_sales.empty:
            findings.append(
                "Review repeated invoice IDs in sales.csv: "
                + ", ".join(
                    duplicate_sales["invoice_number"].dropna().unique()
                )
            )

        if not duplicate_payments.empty:
            findings.append(
                "Review repeated invoice IDs in payment_records.csv: "
                + ", ".join(
                    duplicate_payments["invoice_number"].dropna().unique()
                )
            )

        # Compare only IDs that occur once in each file.
        sales_unique = sales[
            ~sales["invoice_number"].duplicated(keep=False)
        ]
        payments_unique = payments[
            ~payments["invoice_number"].duplicated(keep=False)
        ]

        sales_map = sales_unique.set_index("invoice_number")["total_amount"]
        payment_map = payments_unique.groupby(
            "invoice_number"
        )["payment_amount"].sum()

        for invoice_id, invoice_total in sales_map.items():
            if not invoice_id or invoice_id == "NAN":
                findings.append("A sales record has a missing invoice number.")
                continue

            if pd.isna(invoice_total):
                findings.append(
                    f"{invoice_id}: invalid or missing invoice total."
                )
                continue

            if invoice_id not in payment_map.index:
                findings.append(
                    f"{invoice_id}: no matching payment record found."
                )
                continue

            paid = payment_map[invoice_id]

            if pd.isna(paid):
                findings.append(
                    f"{invoice_id}: invalid or missing payment amount."
                )
                continue

            difference = round(float(invoice_total) - float(paid), 2)

            if difference > 0:
                findings.append(
                    f"{invoice_id}: POSSIBLE UNDERPAYMENT — "
                    f"invoice total {invoice_total:.2f}, "
                    f"paid {paid:.2f}, outstanding {difference:.2f}."
                )
            elif difference < 0:
                findings.append(
                    f"{invoice_id}: PAYMENT EXCEEDS RECORDED TOTAL — "
                    f"invoice total {invoice_total:.2f}, "
                    f"paid {paid:.2f}, excess {abs(difference):.2f}. "
                    "Review for overpayment or other adjustments."
                )
            else:
                findings.append(
                    f"{invoice_id}: MATCH — "
                    f"invoice total {invoice_total:.2f}, "
                    f"paid {paid:.2f}."
                )

        payment_only = set(payment_map.index) - set(sales_map.index)

        for invoice_id in sorted(payment_only):
            findings.append(
                f"{invoice_id}: payment record has no matching "
                "invoice in the sales file."
            )

        if not findings:
            findings.append("No invoice-payment records to compare.")

        return findings

    except Exception as error:
        return [f"Invoice-payment comparison failed: {error}"]
