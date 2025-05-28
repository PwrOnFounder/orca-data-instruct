# PDF Form Data Extractor

## Description

This project is designed to extract structured data from specific sections of PDF documents, exemplified by its use with "Form_D.SEC.Data.Guide.pdf". The primary goal is to identify predefined sections within the PDF, parse field names and their corresponding descriptions from table-like structures, and output this structured data into a CSV file.

Key functionalities include:
*   **PDF Text Extraction**: Robustly extracts all text content from the input PDF document.
*   **Field Parsing**: Identifies sections based on "Figure X. ... Fields in the (SECTION_NAME) data file" titles and then parses "Field Name" and "Field Description" pairs from the text that follows.
*   **CSV Output**: Generates a CSV file with the columns: `Section`, `Field Name`, and `Field Description`.
*   **Utility Scripts**: Provides additional scripts for raw text extraction to console or a text file.

## Scripts Overview

*   **`pdf_parser.py`**: This is the main script of the project. It orchestrates the extraction of text from the specified PDF, parses the content to identify sections and their fields (name and description), and then saves this structured data into a CSV file.
*   **`extract_and_save_text.py`**: This script is a utility that extracts all raw text content from the provided PDF and saves it into a specified `.txt` file. This is useful for inspecting the full text content of the PDF.
*   **`extract_text.py`**: This utility script extracts all raw text content from the provided PDF and prints it directly to the console. This is helpful for quick previews or piping the text to other command-line tools.

## Setup and Installation

1.  **Clone the repository (optional)**:
    If you haven't already, clone the repository to your local machine:
    ```bash
    git clone <repository_url>
    cd <repository_directory>
    ```

2.  **Install dependencies**:
    The project relies on `pdfminer.six` for PDF text extraction. Install it using the provided `requirements.txt` file:
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
    Outputs a plain text (`.txt`) file (e.g., `extracted_full_text.txt`) containing all the text extracted from the input PDF. This includes headers, footers, and all content that `pdfminer.six` can extract.
```
