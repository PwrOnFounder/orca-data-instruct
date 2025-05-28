import argparse # Import the argparse module
import sys # Import sys for sys.exit()
from pdf_parser import extract_text_from_pdf

# Example usage:
# python extract_and_save_text.py --pdf_file "Form_D.SEC.Data.Guide.pdf" --txt_file "extracted_text_sample.txt"
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Extract text from a PDF and save it to a text file.")
    parser.add_argument("--pdf_file", type=str, required=True, help="Path to the input PDF file.")
    parser.add_argument("--txt_file", type=str, required=True, help="Path to the output text file.")
    args = parser.parse_args()

    extracted_text = extract_text_from_pdf(args.pdf_file) 
    
    if extracted_text is None:
        # Error message already printed by extract_text_from_pdf
        print(f"Failed to extract text from '{args.pdf_file}'. Exiting.")
        sys.exit(1)
        
    try:
        with open(args.txt_file, 'w', encoding='utf-8') as out_file:
            out_file.write(extracted_text)
        print(f"Text extracted from '{args.pdf_file}' and saved to '{args.txt_file}'")
    except IOError as e:
        print(f"Error: Could not write to output file '{args.txt_file}'. Details: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred while writing to file '{args.txt_file}': {e}")
        sys.exit(1)
