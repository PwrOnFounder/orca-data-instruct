import argparse # Import the argparse module
import sys # Import sys for sys.exit()
from pdf_parser import extract_text_from_pdf

# Example usage:
# python extract_text.py --pdf_file "Form_D.SEC.Data.Guide.pdf"
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Extract text from a PDF and print it to the console.")
    parser.add_argument("--pdf_file", type=str, required=True, help="Path to the input PDF file.")
    args = parser.parse_args()

    extracted_text = extract_text_from_pdf(args.pdf_file)
    
    if extracted_text is None:
        # Error message already printed by extract_text_from_pdf
        print(f"Failed to extract text from '{args.pdf_file}'. Exiting.")
        sys.exit(1)
        
    print(extracted_text)
