import re
import csv
import argparse
import sys
from PyPDF2 import PdfReader

def extract_text_from_pdf(pdf_path):
    """
    Extracts text from all pages of the specified PDF file using PyPDF2.
    
    Args:
        pdf_path (str): The file path to the PDF.

    Returns:
        str or None: The extracted text content from the PDF, or None if an error occurs.
    """
    try:
        text = ""
        with open(pdf_path, 'rb') as file:
            reader = PdfReader(file)
            for page in reader.pages:
                text += page.extract_text() + "\n"
        return text
    except Exception as e:
        print(f"An error occurred while extracting text from PDF: {e}")
        return None

def parse_fields_from_text(text):
    """
    Parses the extracted text to find sections and extract only the 'Field Name' and 'Field Description' columns.
    This version is specifically tailored for the Form D SEC Data Guide PDF format.
    """
    all_parsed_fields = []
    
    # Look for sections with pattern like "Figure X. Fields in the ... data file"
    section_pattern = re.compile(r"Figure \d+\.\s*Fields in the\s+(.+?)\s+data file", re.IGNORECASE)
    section_matches = list(section_pattern.finditer(text))
    
    if not section_matches:
        print("No sections found matching the expected pattern.")
        return all_parsed_fields
    
    # Process each section
    for i, match in enumerate(section_matches):
        section_name = ' '.join(match.group(1).split()).strip()
        print(f"Processing section: {section_name}")
        
        # Get the text for this section (from end of match to start of next match or end of text)
        section_start = match.end()
        section_end = section_matches[i+1].start() if i + 1 < len(section_matches) else len(text)
        section_text = text[section_start:section_end]
        
        # Split the section text into lines for line-by-line processing
        lines = [line.rstrip() for line in section_text.split('\n') if line.strip()]
        
        # Find the header line that contains "Field Name" and "Field Description"
        header_line = next((i for i, line in enumerate(lines) 
                          if 'Field Name' in line and 'Field Description' in line), None)
        
        if header_line is None:
            print(f"  Warning: Could not find table header in section '{section_name}'")
            continue
            
        # Process lines after the header
        current_field = None
        current_desc = []
        
        for line in lines[header_line + 1:]:
            # Skip lines that might be part of the header or separators
            if not line.strip() or '----' in line or '...' in line:
                continue
                
            # Check if this line starts with an all-caps word (potential new field)
            first_word = line.strip().split()[0] if line.strip() else ""
            
            if first_word.isupper() and len(first_word) >= 3:
                # If we have a current field, save it before starting a new one
                if current_field and current_desc:
                    # Join all description lines with spaces and clean up
                    full_desc = ' '.join(' '.join(part.split()) for part in current_desc)
                    all_parsed_fields.append({
                        'Section': section_name,
                        'Field Name': current_field,
                        'Field Description': full_desc
                    })
                
                # Start a new field
                current_field = first_word
                rest_of_line = line[len(first_word):].strip()
                current_desc = [rest_of_line] if rest_of_line else []
            elif current_field:
                # This is a continuation of the current field's description
                current_desc.append(line.strip())
        
        # Don't forget to add the last field
        if current_field and current_desc:
            full_desc = ' '.join(' '.join(part.split()) for part in current_desc)
            all_parsed_fields.append({
                'Section': section_name,
                'Field Name': current_field,
                'Field Description': full_desc
            })
    
    return all_parsed_fields

def write_to_csv(parsed_data, csv_filepath):
    """
    Writes the parsed data to a CSV file.
    
    Args:
        parsed_data (list): List of dictionaries with the parsed data.
        csv_filepath (str): Path to the output CSV file.
    """
    try:
        with open(csv_filepath, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['Section', 'Field Name', 'Field Description']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            writer.writeheader()
            for row in parsed_data:
                writer.writerow(row)
        print(f"Successfully wrote {len(parsed_data)} records to {csv_filepath}")
        return True
    except Exception as e:
        print(f"Error writing to CSV file: {e}")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract text from a PDF and parse fields into a CSV using PyPDF2.")
    parser.add_argument("--pdf_file", type=str, required=True, help="Path to the input PDF file.")
    parser.add_argument("--csv_file", type=str, required=True, help="Path to the output CSV file.")
    args = parser.parse_args()
    
    print(f"Extracting text from '{args.pdf_file}'...")
    full_text = extract_text_from_pdf(args.pdf_file)
    
    if full_text is None:
        print("Text extraction failed. Exiting.")
        sys.exit(1)
    
    # For debugging: save the extracted text to a file
    with open("debug_extracted_text.txt", "w", encoding="utf-8") as f:
        f.write(full_text)
    print("Saved extracted text to 'debug_extracted_text.txt' for inspection.")
    
    print("\nParsing fields from extracted text...")
    structured_data = parse_fields_from_text(full_text)
    
    if structured_data:
        if write_to_csv(structured_data, args.csv_file):
            print(f"\nSuccessfully parsed {len(structured_data)} fields and wrote them to {args.csv_file}")
        else:
            print(f"\nFailed to write parsed data to {args.csv_file}. Exiting.")
            sys.exit(1)
    else:
        print("No structured data found in the PDF. Please check the debug_extracted_text.txt file to see the extracted text and adjust the parsing logic if needed.")
        sys.exit(1)
