import re
import csv
import argparse
from PyPDF2 import PdfReader

def extract_text_from_pdf(pdf_path):
    """Extract text from PDF file."""
    text = ""
    with open(pdf_path, 'rb') as file:
        reader = PdfReader(file)
        for page in reader.pages:
            text += page.extract_text() + "\n"
    return text

def extract_fields(text):
    """Extract field names and descriptions from the text."""
    fields = []
    
    # Split text into sections based on "Figure X. Fields in the ... data file"
    sections = re.split(r'Figure \d+\.\s*Fields in the\s+(.*?)\s+data file', text, flags=re.IGNORECASE)
    
    # Process each section (skip the first item as it's text before the first section)
    for i in range(1, len(sections), 2):
        if i + 1 >= len(sections):
            break
            
        section_name = sections[i].strip()
        section_text = sections[i + 1]
        
        # Split section into lines
        lines = [line.strip() for line in section_text.split('\n') if line.strip()]
        
        # Find the header line
        header_line = next((i for i, line in enumerate(lines) 
                          if 'Field Name' in line and 'Field Description' in line), None)
        
        if header_line is None:
            continue
            
        # Process each line after the header
        current_field = None
        current_desc = []
        
        for line in lines[header_line + 1:]:
            # Skip lines that are part of the header or separators
            if not line or '----' in line or '...' in line:
                continue
                
            # Check if this line starts a new field (starts with an all-caps word)
            words = line.split()
            if words and words[0].isupper() and len(words[0]) >= 3:
                # Save previous field if exists
                if current_field and current_desc:
                    fields.append({
                        'Section': section_name,
                        'Field Name': current_field,
                        'Field Description': ' '.join(' '.join(part.split()) for part in current_desc)
                    })
                
                # Start new field
                current_field = words[0]
                current_desc = [' '.join(words[1:])] if len(words) > 1 else []
            elif current_field:
                # Continue current field's description
                current_desc.append(line)
        
        # Add the last field in the section
        if current_field and current_desc:
            fields.append({
                'Section': section_name,
                'Field Name': current_field,
                'Field Description': ' '.join(' '.join(part.split()) for part in current_desc)
            })
    
    return fields

def write_to_csv(fields, output_file):
    """Write fields to a CSV file."""
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['Section', 'Field Name', 'Field Description'])
        writer.writeheader()
        writer.writerows(fields)

def main():
    parser = argparse.ArgumentParser(description='Extract field names and descriptions from PDF')
    parser.add_argument('input_pdf', help='Input PDF file')
    parser.add_argument('output_csv', help='Output CSV file')
    args = parser.parse_args()
    
    print(f"Extracting text from {args.input_pdf}...")
    text = extract_text_from_pdf(args.input_pdf)
    
    print("Extracting fields...")
    fields = extract_fields(text)
    
    print(f"Writing {len(fields)} fields to {args.output_csv}")
    write_to_csv(fields, args.output_csv)
    print("Done!")

if __name__ == '__main__':
    main()
