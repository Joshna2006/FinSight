
import re
from io import StringIO
from datetime import datetime

import pandas as pd


def verify_information(file_name, text):
    """Validate document information and basic field values."""

    findings = []

    if text is None or not str(text).strip():
        return [
            f"{file_name}: Document is empty or contains no extracted text."
        ]

    name = str(file_name).lower()
    content = str(text).strip()
    lower_content = content.lower()

    # --------------------------------------------------
    # 1. CSV INFORMATION VERIFICATION
    # --------------------------------------------------
    if name.endswith(".csv"):
        try:
            df = pd.read_csv(StringIO(content))

            df.columns = [
                str(col).strip().lower().replace(" ", "_")
                for col in df.columns
            ]

            if df.empty:
                findings.append("The CSV contains no data records.")
                return findings

            if df.columns.duplicated().any():
                findings.append("Duplicate column names were detected.")

            if "payment" in name:
                required = [
                    "invoice_number",
                    "payment_amount",
                    "payment_date",
                ]
            elif "sales" in name:
                required = [
                    "invoice_number",
                    "quantity",
                    "unit_price",
                    "total_amount",
                ]
            else:
                required = ["invoice_number"]

            missing = [col for col in required if col not in df.columns]

            if missing:
                findings.append(
                    "Missing required columns: " + ", ".join(missing)
                )
                return findings

            # Check empty required fields.
            empty_found = False

            for col in required:
                empty = (
                    df[col].isna()
                    | df[col].astype(str).str.strip().eq("")
                )
                count = int(empty.sum())

                if count:
                    empty_found = True
                    findings.append(
                        f"Missing values: {count} empty cell(s) in '{col}'."
                    )

            if not empty_found:
                findings.append("Required fields contain no empty values.")

            # Check repeated invoice identifiers.
            ids = df["invoice_number"].dropna().astype(str).str.strip()
            ids = ids[ids.ne("")]

            duplicates = ids[ids.duplicated(keep=False)].unique().tolist()

            if duplicates:
                findings.append(
                    "Repeated invoice identifiers found: "
                    + ", ".join(duplicates)
                )
            else:
                findings.append("No repeated invoice identifiers found.")

            # Check numeric fields.
            numeric_columns = [
                col for col in [
                    "quantity", "unit_price",
                    "total_amount", "payment_amount"
                ]
                if col in df.columns
            ]

            for col in numeric_columns:
                values = pd.to_numeric(df[col], errors="coerce")
                nonempty = df[col].notna() & df[col].astype(str).str.strip().ne("")

                if (values.isna() & nonempty).any():
                    findings.append(
                        f"Invalid numeric value(s) found in '{col}'."
                    )

                if col in ["quantity", "unit_price", "payment_amount"]:
                    if (values.dropna() < 0).any():
                        findings.append(
                            f"Negative value(s) found in '{col}'."
                        )

            # Check invoice arithmetic.
            needed = ["quantity", "unit_price", "total_amount"]

            if all(col in df.columns for col in needed):
                quantity = pd.to_numeric(df["quantity"], errors="coerce")
                price = pd.to_numeric(df["unit_price"], errors="coerce")
                total = pd.to_numeric(df["total_amount"], errors="coerce")

                valid = quantity.notna() & price.notna() & total.notna()
                mismatch = valid & (
                    (quantity * price - total).abs() > 0.01
                )

                if mismatch.any():
                    findings.append(
                        f"Calculation inconsistency: {int(mismatch.sum())} "
                        "record(s) do not match quantity × unit price."
                    )
                elif valid.any():
                    findings.append(
                        "Financial values passed the basic arithmetic check."
                    )

            # Validate dates only if a date column exists.
            date_columns = [
                col for col in df.columns if "date" in col
            ]

            for col in date_columns:
                values = df[col].dropna().astype(str).str.strip()
                invalid = []

                for value in values:
                    try:
                        parsed = pd.to_datetime(value, errors="raise")
                        if pd.isna(parsed):
                            invalid.append(value)
                    except (ValueError, TypeError, OverflowError):
                        invalid.append(value)

                if invalid:
                    findings.append(
                        f"Invalid date value(s) found in '{col}'."
                    )
                elif len(values):
                    findings.append(
                        f"Date values in '{col}' could be parsed."
                    )

            return findings or ["No issues found by basic information checks."]

        except Exception as exc:
            return [
                f"CSV information verification could not be completed: {exc}"
            ]

    # --------------------------------------------------
    # 2. EXCEL INFORMATION CHECKS
    # --------------------------------------------------
    if name.endswith((".xlsx", ".xls")):
        # This function receives extracted text, not the original workbook.
        # Check recognizable field names and values without requiring dates.
        if "invoice_number" in lower_content or re.search(
            r"\binv\d+\b", lower_content
        ):
            findings.append("Invoice information was found.")
        else:
            findings.append(
                "Invoice information could not be confirmed from extracted text."
            )

        if re.search(
            r"\b(total_amount|invoice_total|total|amount)\b",
            lower_content
        ):
            findings.append("An amount-related field was found.")
        else:
            findings.append(
                "No recognizable amount field was found in extracted text."
            )

        # Dates are optional for Excel invoice files.
        return findings

    # --------------------------------------------------
    # 3. TXT AND OTHER EXTRACTED DOCUMENT TEXT
    # --------------------------------------------------

    if re.search(r"\binv\d+\b|\binvoice(?:\s+number)?\b", lower_content):
        pass
    else:
        findings.append("Expected invoice information was not found.")

    # Validate dates when a date is present or explicitly labelled.
    date_pattern = (
        r"\b(?:\d{4}-\d{2}-\d{2}|\d{2}[-/]\d{2}[-/]\d{4})\b"
    )
    dates = re.findall(date_pattern, content)

    date_label_present = bool(
        re.search(r"\bdate\b", lower_content)
    )

    if dates:
        valid_date_found = False

        formats = [
            "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y",
            "%m-%d-%Y", "%m/%d/%Y"
        ]

        for value in dates:
            for fmt in formats:
                try:
                    datetime.strptime(value, fmt)
                    valid_date_found = True
                    break
                except ValueError:
                    continue

            if valid_date_found:
                break

        if not valid_date_found:
            findings.append(
                "A date was found, but its format or value needs review."
            )
    elif date_label_present:
        findings.append("A date field is present but no recognizable date was found.")

    # Recognize total_amount, total amount, invoice total and amount.
    amount_pattern = (
        r"\b(?:total[\s_]+amount|invoice[\s_]+total|total|amount)"
        r"\b\s*[:=-]?\s*(?:₹|rs\.?\s*)?"
        r"\s*\d[\d,]*(?:\.\d{1,2})?"
    )

    if not re.search(amount_pattern, content, re.IGNORECASE):
        findings.append("Expected total or amount information was not found.")

    if not findings:
        findings.append(
            "Basic information checks passed. Review field values manually."
        )

    return findings