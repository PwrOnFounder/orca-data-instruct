# PDF Form Data Extractor

## Description

This project provides a suite of tools for extracting structured data and text from PDF documents, with a particular focus on forms like "Form_D.SEC.Data.Guide.pdf". It offers various methods for text extraction (using `pdfminer.six`, `pdfplumber`, `PyPDF2`) and utilities for processing PDF files. The primary goal is to identify predefined sections within PDFs, parse field names and their descriptions, and output this structured data into CSV files.

Key functionalities include:
*   **Versatile PDF Text Extraction**: Employs multiple libraries (`pdfminer.six`, `pdfplumber`, `PyPDF2`) for robust text extraction from PDF documents.
*   **Targeted Field Parsing**: Identifies sections (e.g., based on "Figure X. ... Fields in the (SECTION_NAME) data file" titles) and parses "Field Name" and "Field Description" pairs.
*   **Structured Data Output**: Generates CSV files with columns: `Section`, `Field Name`, and `Field Description`.
*   **Raw Text Extraction**: Offers scripts to extract all text content to the console or a `.txt` file for inspection.
*   **PDF Manipulation Utilities**: Includes tools to create partial PDFs from a range of pages.

## Scripts Overview

*   **`pdf_parser.py`**: The primary script using `pdfminer.six` to extract text, parse sections and fields (name/description), and save structured data to a CSV file.
*   **`extract_fields_only.py`**: A script utilizing `pdfplumber` for text extraction, specifically focused on identifying and extracting field names and descriptions into a CSV. Its parsing approach may differ from `pdf_parser.py`.
*   **`pdf_parser_pypdf2.py`**: An alternative parsing script that uses `PyPDF2` for text extraction before parsing field names and descriptions into a CSV.
*   **`extract_and_save_text.py`**: A utility script to extract all raw text from a PDF using `pdfminer.six` and save it to a `.txt` file. Useful for full-text inspection.
*   **`extract_text.py`**: A utility script to extract all raw text from a PDF using `pdfminer.six` and print it to the console. Helpful for quick previews or piping.
*   **`create_partial_pdf.py`**: A utility script that uses `PyPDF2` to create a new PDF document containing a specified range of pages from an input PDF.

## Setup and Installation

1.  **Clone the repository (optional)**:
    If you haven't already, clone the repository to your local machine:
    ```bash
    git clone <repository_url>
    cd <repository_directory>
    ```

2.  **Install dependencies**:
    The project relies on several Python libraries for PDF processing, including `pdfminer.six`, `pdfplumber`, and `PyPDF2`. Install all dependencies using the provided `requirements.txt` file:
    ```bash
    pip install -r requirements.txt
    ```

## Usage

Ensure you are in the root directory of the project when running these commands. Replace `"path/to/your/..."` placeholders with actual file paths relevant to your setup. It's recommended to use a sample PDF like "Form_D.SEC.Data.Guide.pdf" (if available in your project or downloaded separately) to test the scripts.

*   **`pdf_parser.py`**:
    This script extracts structured data and saves it to a CSV file.
    ```bash
    python pdf_parser.py --pdf_file "path/to/your/Form_D.SEC.Data.Guide.pdf" --csv_file "output/parsed_data.csv"
    ```
    *   `--pdf_file`: (Required) Path to the input PDF file you want to process.
    *   `--csv_file`: (Required) Path where the output CSV file will be saved. Ensure the output directory (e.g., `output/`) exists or adjust the path accordingly.

*   **`extract_and_save_text.py`**:
    This script extracts raw text and saves it to a `.txt` file.
    ```bash
    python extract_and_save_text.py --pdf_file "path/to/your/Form_D.SEC.Data.Guide.pdf" --txt_file "output/extracted_full_text.txt"
    ```
    *   `--pdf_file`: (Required) Path to the input PDF file.
    *   `--txt_file`: (Required) Path where the output text file will be saved.

*   **`extract_text.py`**:
    This script extracts raw text and prints it to the console.
    ```bash
    python extract_text.py --pdf_file "path/to/your/Form_D.SEC.Data.Guide.pdf"
    ```
    *   `--pdf_file`: (Required) Path to the input PDF file.

*   **`extract_fields_only.py`**:
    Extracts field names and descriptions using `pdfplumber` and saves them to a CSV file. This script uses positional arguments.
    ```bash
    python extract_fields_only.py "path/to/your/Form_D.SEC.Data.Guide.pdf" "output/extracted_fields_pdfplumber.csv"
    ```
    *   `input_pdf`: (Required) Path to the input PDF file.
    *   `output_csv`: (Required) Path where the output CSV file will be saved.

*   **`create_partial_pdf.py`**:
    Creates a new PDF document from a specified page range of an input PDF. This script uses positional arguments.
    ```bash
    python create_partial_pdf.py "path/to/your/Full_Document.pdf" "output/Partial_Document_pages_1-5.pdf" 1 5
    ```
    *   `input_pdf`: (Required) Path to the input PDF file.
    *   `output_pdf`: (Required) Path for the output partial PDF file.
    *   `start_page`: (Required) Start page number (1-indexed).
    *   `end_page`: (Required) End page number (1-indexed).

*   **`pdf_parser_pypdf2.py`**:
    An alternative script that extracts structured data using `PyPDF2` for text extraction and saves it to a CSV file.
    ```bash
    python pdf_parser_pypdf2.py --pdf_file "path/to/your/Form_D.SEC.Data.Guide.pdf" --csv_file "output/parsed_data_pypdf2.csv"
    ```
    *   `--pdf_file`: (Required) Path to the input PDF file.
    *   `--csv_file`: (Required) Path where the output CSV file will be saved.

## Testing

Unit tests are provided for the core parsing logic in `pdf_parser.py`. To run the tests, navigate to the root directory of the project and use one of the following commands:

*   **Discover and run all tests in the `tests` directory**:
    ```bash
    python -m unittest discover tests
    ```
*   **Run tests from a specific test file**:
    ```bash
    python -m unittest tests.test_pdf_parser
    ```

## Output

*   **`pdf_parser.py`**:
    The primary output is a CSV file (e.g., `parsed_data.csv`) with the following columns:
    *   `Section`: The name of the section extracted from "Figure X..." titles (e.g., "FORMDSUBMISSION", "ISSUERS").
    *   `Field Name`: The name of the field as identified in the PDF (e.g., "ACCESSIONNUMBER", "CIK").
    *   `Field Description`: The description associated with the field.

*   **`extract_and_save_text.py`**:
    Outputs a plain text (`.txt`) file (e.g., `extracted_full_text.txt`) containing all text extracted by `pdfminer.six` from the input PDF, including headers, footers, and all other content.

*   **`extract_fields_only.py`**:
    Outputs a CSV file (e.g., `extracted_fields_pdfplumber.csv`) with the columns: `Section`, `Field Name`, and `Field Description`. Content may vary from `pdf_parser.py` due to the use of `pdfplumber` and potentially different parsing logic.

*   **`create_partial_pdf.py`**:
    Outputs a new PDF file (e.g., `Partial_Document_pages_1-5.pdf`) containing only the specified range of pages from the input PDF.

*   **`pdf_parser_pypdf2.py`**:
    Outputs a CSV file (e.g., `parsed_data_pypdf2.csv`) with the columns: `Section`, `Field Name`, and `Field Description`. Results may differ from `pdf_parser.py` due to `PyPDF2`'s text extraction capabilities.
```
