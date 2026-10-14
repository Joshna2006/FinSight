import pandas as pd
from io import BytesIO


def verify_financial_file(file_name, file_bytes):
    findings = []

    try:
        # Read the uploaded file
        if file_name.lower().endswith(".csv"):
            df = pd.read_csv(BytesIO(file_bytes))
        elif file_name.lower().endswith(".xlsx"):
            df = pd.read_excel(BytesIO(file_bytes))
        else:
            return [
                f"Source file: {file_name}",
                "Unsupported file type for financial verification."
            ]

        # Standardize column names
        df.columns = [
            str(col).strip().lower().replace(" ", "_")
            for col in df.columns
        ]

        findings.append(f"Source file: {file_name}")
        findings.append(f"Records examined: {len(df)}")

        # Check for missing invoice identifiers
        if "invoice_number" in df.columns:
            invoice_ids = (
                df["invoice_number"]
                .astype("string")
                .str.strip()
            )
            missing_ids = invoice_ids.isna() | invoice_ids.eq("")

            if missing_ids.any():
                findings.append(
                    f"WARNING: {int(missing_ids.sum())} record(s) "
                    "have missing invoice numbers."
                )

        # Identify invoice calculation records
        invoice_columns = {
            "quantity", "unit_price", "total_amount"
        }

        # Identify payment records
        payment_columns = {
            "invoice_number", "payment_amount"
        }

        if invoice_columns.issubset(df.columns):
            # Invoice calculation verification
            for column in invoice_columns:
                df[column] = pd.to_numeric(
                    df[column], errors="coerce"
                )

            missing_count = int(
                df[list(invoice_columns)].isna().sum().sum()
            )

            if missing_count:
                findings.append(
                    f"WARNING: {missing_count} missing or invalid "
                    "financial value(s) found."
                )
            else:
                findings.append(
                    "No missing or invalid values found in "
                    "required financial fields."
                )

            for index, row in df.iterrows():
                invoice = (
                    str(row["invoice_number"]).strip()
                    if "invoice_number" in df.columns
                    and pd.notna(row["invoice_number"])
                    else f"Row {index + 1}"
                )

                quantity = row["quantity"]
                price = row["unit_price"]
                recorded = row["total_amount"]

                if pd.isna(quantity) or pd.isna(price) or pd.isna(recorded):
                    findings.append(
                        f"REVIEW REQUIRED | File: {file_name} | "
                        f"Invoice: {invoice} | "
                        "Quantity, unit price, or total is missing "
                        "or invalid."
                    )
                    continue

                if quantity < 0 or price < 0 or recorded < 0:
                    findings.append(
                        f"REVIEW REQUIRED | File: {file_name} | "
                        f"Invoice: {invoice} | "
                        "Negative financial values found."
                    )
                    continue

                expected = float(quantity * price)
                difference = round(expected - float(recorded), 2)

                if abs(difference) > 0.02:
                    findings.append(
                        f"POSSIBLE CALCULATION ERROR | "
                        f"File: {file_name} | Invoice: {invoice} | "
                        f"Quantity: {quantity:g} | "
                        f"Unit price: {price:.2f} | "
                        f"Expected total: {expected:.2f} | "
                        f"Recorded total: {recorded:.2f} | "
                        f"Difference: {difference:.2f} | "
                        "Action: Review the source invoice."
                    )
                else:
                    findings.append(
                        f"CALCULATION MATCH | File: {file_name} | "
                        f"Invoice: {invoice} | "
                        f"Verified total: {recorded:.2f}"
                    )

        elif payment_columns.issubset(df.columns):
            # Payment records are checked separately against invoices
            df["payment_amount"] = pd.to_numeric(
                df["payment_amount"], errors="coerce"
            )

            invalid_count = int(df["payment_amount"].isna().sum())

            if invalid_count:
                findings.append(
                    f"WARNING: {invalid_count} payment amount(s) "
                    "are missing or invalid."
                )
            else:
                findings.append(
                    "Payment amounts are present and numeric. "
                    "Invoice-payment matching is handled by "
                    "Invoice-Payment Verification."
                )

            if (df["payment_amount"].dropna() < 0).any():
                findings.append(
                    "WARNING: Negative payment amount(s) found. "
                    "Review refunds or incorrect entries."
                )

        else:
            findings.append(
                "Financial calculation verification not applicable: "
                "the file does not contain invoice calculation fields "
                "(quantity, unit_price, total_amount) or recognized "
                "payment fields (invoice_number, payment_amount)."
            )

        # Check duplicate invoice identifiers
        if "invoice_number" in df.columns:
            invoice_ids = (
                df["invoice_number"]
                .dropna()
                .astype(str)
                .str.strip()
            )
            invoice_ids = invoice_ids[invoice_ids.ne("")]

            duplicates = invoice_ids[
                invoice_ids.duplicated(keep=False)
            ].unique()

            if len(duplicates):
                for invoice in duplicates:
                    findings.append(
                        f"POSSIBLE DUPLICATE INVOICE | "
                        f"File: {file_name} | Invoice: {invoice} | "
                        "Action: Check whether these records represent "
                        "the same invoice. Multiple payment records "
                        "may also be legitimate."
                    )
            else:
                findings.append(
                    f"No repeated invoice identifiers found in "
                    f"{file_name}."
                )
        else:
            findings.append(
                "Duplicate invoice check skipped: "
                "invoice_number column not found."
            )

    except Exception as error:
        findings.append(
            f"Financial verification failed for {file_name}: {error}"
        )

    return findings