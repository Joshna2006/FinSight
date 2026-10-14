from io import BytesIO
from pathlib import Path
import zipfile
import fitz
import pandas as pd


def check_authenticity(file_name, file_bytes):
    findings = []
    extension = Path(file_name).suffix.lower()

    if not file_bytes:
        return ["WARNING: File is empty."]

    try:
        if extension == ".pdf":
            with fitz.open(
                stream=file_bytes,
                filetype="pdf"
            ) as pdf:

                if pdf.is_encrypted:
                    return ["WARNING: PDF is encrypted."]

                if len(pdf) == 0:
                    findings.append("WARNING: PDF has no pages.")

                if not pdf.metadata.get("title"):
                    findings.append("PDF title metadata is missing.")

                if not pdf.metadata.get("author"):
                    findings.append("PDF author metadata is missing.")

                if not any(page.get_text().strip() for page in pdf):
                    findings.append(
                        "WARNING: No selectable text found. "
                        "The PDF may be scanned or image-based."
                    )

                if not findings:
                    findings.append(
                        "Basic PDF structure checks passed."
                    )

        elif extension == ".txt":
            text = file_bytes.decode("utf-8-sig")

            if not text.strip():
                findings.append("WARNING: Text file is empty.")
            else:
                findings.append("Text file is readable.")

        elif extension == ".csv":
            df = pd.read_csv(BytesIO(file_bytes))

            if df.empty:
                findings.append("WARNING: CSV has no data records.")
            else:
                findings.append(
                    f"CSV structure is readable: "
                    f"{len(df.columns)} columns and "
                    f"{len(df)} records."
                )

            if df.columns.duplicated().any():
                findings.append("WARNING: Duplicate column names found.")

            if df.isnull().any().any():
                findings.append("WARNING: Missing cell values found.")

        elif extension == ".xlsx":
            if not zipfile.is_zipfile(BytesIO(file_bytes)):
                return ["WARNING: Invalid or corrupted XLSX file."]

            with pd.ExcelFile(BytesIO(file_bytes)) as workbook:
                if not workbook.sheet_names:
                    findings.append("WARNING: No worksheets found.")
                else:
                    findings.append(
                        "Excel workbook is readable. Worksheets: "
                        + ", ".join(workbook.sheet_names)
                    )

        else:
            findings.append("WARNING: Unsupported file format.")

    except Exception as error:
        findings.append(
            f"WARNING: File could not be read. "
            f"Reason: {type(error).__name__}"
        )

    findings.append(
        "Limitation: These checks do not prove authenticity "
        "or detect every form of document tampering."
    )

    return findings