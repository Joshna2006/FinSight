import pandas as pd
import fitz
from docx import Document
from io import BytesIO


def read_document(file_name, file_bytes):
    name = file_name.lower()

    try:
        if name.endswith(".pdf"):
            pdf = fitz.open(stream=file_bytes, filetype="pdf")
            text = "\n".join(page.get_text() for page in pdf)
            return text

        elif name.endswith(".csv"):
            df = pd.read_csv(BytesIO(file_bytes))
            return df.to_string(index=False)

        elif name.endswith(".xlsx"):
            df = pd.read_excel(BytesIO(file_bytes))
            return df.to_string(index=False)

        elif name.endswith(".docx"):
            doc = Document(BytesIO(file_bytes))
            return "\n".join(p.text for p in doc.paragraphs)

        elif name.endswith((".png", ".jpg", ".jpeg")):
            return "Image uploaded. OCR will be added later."

        return "Unsupported file type."

    except Exception as error:
        return f"Could not read document: {error}"