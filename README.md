# FinSight – Intelligent Audit Platform

## Introduction
FinSight is a Python-based financial document verification and audit review platform developed using Streamlit. It helps users review financial records, identify calculation inconsistencies, compare invoice totals with payments, detect possible duplicate invoices, and generate PDF audit reports.

## Objectives
- Verify financial calculations in sales and invoice records.
- Identify possible discrepancies in recorded totals.
- Compare invoice amounts with corresponding payment records.
- Detect possible duplicate invoice records.
- Perform basic document and information checks.
- Generate downloadable PDF audit reports.

## Features
1. **Financial Calculation Verification:** Checks whether quantity multiplied by unit price matches the recorded total.
2. **Invoice-Payment Verification:** Compares invoice totals with payment amounts and highlights possible outstanding payments.
3. **Exact Duplicate Detection:** Identifies files with identical content.
4. **Similar-Invoice Detection:** Flags possible repeated invoice records for manual review.
5. **Document Authenticity Indicators:** Checks basic document characteristics and available metadata.
6. **Information Verification:** Checks required fields and basic information consistency.
7. **Cross-Document Comparison:** Checks extracted document text for exact matches.
8. **PDF Audit Report:** Generates a downloadable report of verification findings.

## Technologies Used
- Python
- Streamlit
- Pandas
- ReportLab
- CSV and Excel file processing
- PDF document processing

## Project Structure
```text
FinSight/
├── app.py
├── requirements.txt
├── modules/
│   ├── audit_report.py
│   ├── cross_document_check.py
│   ├── document_authenticity.py
│   ├── document_reader.py
│   ├── duplicate_detection.py
│   ├── financial_verification.py
│   └── information_verification.py
├── sample_documents/
│   ├── sales.csv
│   └── payment_records.csv
└── static/
    └── style.css
```

## How to Run the Project Locally

### Prerequisites
- Python installed
- Git installed (optional, for cloning the repository)

### Installation
1. Clone the repository:
   ```bash
   git clone https://github.com/Joshna2006/FinSight.git
   ```
2. Open the project folder:
   ```bash
   cd FinSight
   ```
3. Install the required dependencies:
   ```bash
   python -m pip install -r requirements.txt
   ```
4. Start the application:
   ```bash
   python -m streamlit run app.py
   ```
5. Open the local URL shown in the terminal.

## Live Application
https://finsight-xnbfqjdxgqcpjqefgvx7s5.streamlit.app/

## GitHub Repository
https://github.com/Joshna2006/FinSight

## Limitations
FinSight provides preliminary audit indicators to support human review. A flagged discrepancy or duplicate does not prove fraud, and basic document checks do not establish document authenticity. Users should verify findings against the original records before making financial decisions.

## Future Enhancements
- Support for additional document formats.
- More advanced invoice matching.
- Improved audit analytics and visual summaries.
- Enhanced verification rules and reporting.