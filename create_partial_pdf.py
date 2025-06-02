import argparse
from PyPDF2 import PdfReader, PdfWriter

def create_partial_pdf(input_pdf_path, output_pdf_path, start_page, end_page):
    """Creates a new PDF containing a specific range of pages from the input PDF."""
    try:
        reader = PdfReader(input_pdf_path)
        writer = PdfWriter()

        # Adjust for 0-indexed pages
        start_page_idx = start_page - 1
        end_page_idx = end_page - 1

        if start_page_idx < 0 or end_page_idx >= len(reader.pages) or start_page_idx > end_page_idx:
            print(f"Error: Page range {start_page}-{end_page} is invalid for a PDF with {len(reader.pages)} pages.")
            return

        for i in range(start_page_idx, end_page_idx + 1):
            writer.add_page(reader.pages[i])

        with open(output_pdf_path, 'wb') as outfile:
            writer.write(outfile)
        print(f"Successfully created '{output_pdf_path}' with pages {start_page}-{end_page} from '{input_pdf_path}'.")

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Create a partial PDF from a page range.')
    parser.add_argument('input_pdf', help='Path to the input PDF file.')
    parser.add_argument('output_pdf', help='Path for the output partial PDF file.')
    parser.add_argument('start_page', type=int, help='Start page number (1-indexed).')
    parser.add_argument('end_page', type=int, help='End page number (1-indexed).')

    args = parser.parse_args()

    create_partial_pdf(args.input_pdf, args.output_pdf, args.start_page, args.end_page)
