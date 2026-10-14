import hashlib
import re
from difflib import SequenceMatcher
from io import BytesIO

import pandas as pd


# --------------------------------------------------
# EXACT DUPLICATE FILE DETECTION
# --------------------------------------------------

def get_file_hash(file_bytes):
    """Generate a SHA-256 hash for a file."""
    return hashlib.sha256(file_bytes).hexdigest()


def find_duplicates(files):
    """Detect files with identical contents."""
    seen = {}
    duplicates = []

    for file_name, file_bytes in files:
        file_hash = get_file_hash(file_bytes)

        if file_hash in seen:
            duplicates.append(
                f"{file_name} is an exact copy of "
                f"{seen[file_hash]}."
            )
        else:
            seen[file_hash] = file_name

    if not duplicates:
        return ["No exact duplicate files detected."]

    return duplicates


# --------------------------------------------------
# INVOICE ID NORMALIZATION
# --------------------------------------------------

def normalize_invoice(value):
    """Normalize invoice IDs for comparison."""
    if pd.isna(value):
        return ""

    return re.sub(
        r"[^A-Z0-9]",
        "",
        str(value).upper()
    )


# --------------------------------------------------
# SIMILAR-INVOICE DETECTION
# --------------------------------------------------

def find_similar_invoices(files):
    """
    Detect repeated invoice IDs and possible similar invoices.

    Payment files are excluded.
    Comparisons are performed within each invoice CSV.
    """

    findings = []
    records_by_file = {}

    for file_name, file_bytes in files:
        lower_name = file_name.lower()

        # Only process CSV invoice files.
        if not lower_name.endswith(".csv"):
            continue

        # Exclude payment records.
        if "payment" in lower_name:
            continue

        try:
            df = pd.read_csv(BytesIO(file_bytes))

            df.columns = [
                str(col).strip().lower().replace(" ", "_")
                for col in df.columns
            ]

            if "invoice_number" not in df.columns:
                continue

            amount_column = next(
                (
                    col for col in (
                        "total_amount",
                        "invoice_total",
                        "amount",
                    )
                    if col in df.columns
                ),
                None,
            )

            if amount_column is None:
                findings.append(
                    f"Invoice duplicate check could not compare "
                    f"amounts in {file_name}: no recognized amount "
                    "column was found."
                )
                continue

            records = []

            for row_index, row in df.iterrows():
                invoice_id = normalize_invoice(
                    row["invoice_number"]
                )

                if not invoice_id:
                    findings.append(
                        f"REVIEW REQUIRED | File: {file_name} | "
                        f"Row: {row_index + 2} | "
                        "Invoice number is missing."
                    )
                    continue

                amount = pd.to_numeric(
                    row[amount_column],
                    errors="coerce",
                )

                if pd.isna(amount):
                    findings.append(
                        f"REVIEW REQUIRED | File: {file_name} | "
                        f"Row: {row_index + 2} | "
                        f"Invoice: {invoice_id} | "
                        "Invoice amount is missing or invalid."
                    )
                    continue

                records.append({
                    "file": file_name,
                    "row": row_index + 2,
                    "invoice": invoice_id,
                    "amount": float(amount),
                })

            records_by_file[file_name] = records

        except Exception as error:
            findings.append(
                f"Could not check similar invoices in "
                f"{file_name}: {error}"
            )

    # Compare records within each invoice file.
    for file_name, records in records_by_file.items():
        for i in range(len(records)):
            first = records[i]

            for j in range(i + 1, len(records)):
                second = records[j]

                id1 = first["invoice"]
                id2 = second["invoice"]
                amount1 = first["amount"]
                amount2 = second["amount"]

                # Same normalized invoice ID.
                if id1 == id2:
                    if abs(amount1 - amount2) <= 0.02:
                        findings.append(
                            "POSSIBLE DUPLICATE INVOICE | "
                            f"File: {file_name} | Invoice: {id1} | "
                            f"Rows: {first['row']} and "
                            f"{second['row']} | "
                            f"Amounts: {amount1:.2f} and "
                            f"{amount2:.2f}. "
                            "The invoice ID and amount match; "
                            "review the source records."
                        )
                    else:
                        findings.append(
                            "REPEATED INVOICE ID WITH DIFFERENT "
                            "AMOUNTS | "
                            f"File: {file_name} | Invoice: {id1} | "
                            f"Rows: {first['row']} and "
                            f"{second['row']} | "
                            f"Amounts: {amount1:.2f} and "
                            f"{amount2:.2f}. "
                            "Check for corrections, partial records, "
                            "or duplicate entries."
                        )

                    continue

                # Compare different invoice IDs.
                similarity = SequenceMatcher(
                    None, id1, id2
                ).ratio()

                largest = max(abs(amount1), abs(amount2), 1.0)

                amounts_close = (
                    abs(amount1 - amount2) / largest <= 0.05
                )

                if similarity >= 0.90 and amounts_close:
                    findings.append(
                        "POSSIBLE SIMILAR INVOICE | "
                        f"File: {file_name} | "
                        f"IDs: {id1} and {id2} | "
                        f"Rows: {first['row']} and "
                        f"{second['row']} | "
                        f"Amounts: {amount1:.2f} and "
                        f"{amount2:.2f} | "
                        f"ID similarity: {similarity:.0%}. "
                        "Review manually."
                    )

    if not findings:
        findings.append(
            "No possible repeated or similar invoice records "
            "detected within the uploaded invoice files."
        )

    findings.append(
        "Payment records are excluded from invoice duplicate "
        "detection. Use Invoice-Payment Verification to compare "
        "payments with invoice totals."
    )

    findings.append(
        "Duplicate and similarity findings are preliminary "
        "indicators and require manual review."
    )

    return findings