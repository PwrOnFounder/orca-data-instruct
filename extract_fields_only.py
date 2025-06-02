import re
import csv
import argparse
import pdfplumber

def extract_text_from_pdf(pdf_path):
    """Extract text from PDF file using pdfplumber, attempting layout=True for all pages with keep_blank_chars=False."""
    text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            total_pages = len(pdf.pages)
            print(f"Processing {total_pages} pages from PDF '{pdf_path}' (keep_blank_chars=False)...", flush=True)
            for i, page in enumerate(pdf.pages):
                page_num = i + 1
                page_text_content = None # Initialize for each page
                
                # print(f"  Attempting to process page {page_num}/{total_pages} with layout=True...", flush=True) # Less verbose
                try:
                    page_text_content = page.extract_text(x_tolerance=3, y_tolerance=3, layout=True, keep_blank_chars=False)
                    if page_text_content is not None:
                        print(f"    Successfully extracted {len(page_text_content)} chars from page {page_num}/{total_pages}.", flush=True)
                    else:
                        print(f"    page.extract_text() returned None for page {page_num}/{total_pages}. Adding placeholder.", flush=True)
                        page_text_content = f"[PAGE_EXTRACTION_RETURNED_NONE:{page_num}]\n"
                except Exception as page_e:
                    print(f"    Error extracting text from page {page_num}/{total_pages} (layout=True): {page_e}. Adding placeholder.", flush=True)
                    page_text_content = f"[ERROR_EXTRACTING_PAGE:{page_num}:{str(page_e).replace('\n', ' ')}]\n"

                # Ensure page_text_content is a string before appending
                if isinstance(page_text_content, str):
                    text += page_text_content
                    if not page_text_content.endswith('\n'): # Ensure newline separation
                        text += '\n'
                elif page_text_content is None:
                    print(f"    page_text_content was unexpectedly None for page {page_num}/{total_pages} after processing. Adding placeholder.", flush=True)
                    text += f"[UNEXPECTED_NONE_PAGE_CONTENT:{page_num}]\n"

        # print(f"[DEBUG extract_text_from_pdf] Total extracted text length: {len(text)}", flush=True) # Optional: less verbose
    except Exception as e:
        print(f"[DEBUG extract_text_from_pdf] General error during PDF processing: {e}", flush=True)
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
            
        # Get the position of 'Field Name', 'Field Description', and 'Format' in the header
        header = lines[header_line]
        name_start = header.find('Field Name')
        desc_start = header.find('Field Description')
        format_start = header.find('Format') # Find the start of the 'Format' column
        
        # Process each line after the header
        for line in lines[header_line + 1:]:
            # Skip lines that are part of the header or separators
            if not line or '----' in line or '...' in line:
                continue
                
            # Determine the chunk of the line that contains the field name and description.
            # This chunk starts at the 'Field Name' column (name_start from header)
            # and ends just before the 'Format' column (format_start from header, if it exists and is after name_start).
            name_desc_chunk_end_limit = format_start if format_start != -1 and format_start > name_start else len(line)

            field_name = ""
            field_desc = ""

            if name_start != -1 and name_start < name_desc_chunk_end_limit:
                name_desc_chunk_from_line = line[name_start:name_desc_chunk_end_limit].strip()
                
                field_name_collected_parts = []
                description_collected_words = []
                words_in_chunk = re.split(r'\s+', name_desc_chunk_from_line)
                
                collecting_name_parts = True
                for word in words_in_chunk:
                    if not word: # Skip empty strings if re.split produced any
                        continue
                    
                    if collecting_name_parts:
                        # Check if the word looks like a field name part (all caps, numbers, underscores)
                        if re.fullmatch(r'[A-Z0-9_]+', word):
                            field_name_collected_parts.append(word)
                        else:
                            # Word doesn't look like a field name part, switch to collecting description
                            collecting_name_parts = False
                            description_collected_words.append(word)
                    else:
                        description_collected_words.append(word)
                
                field_name = "".join(field_name_collected_parts) # Join without spaces
                field_desc = " ".join(description_collected_words)
            else:
                # Could not determine a valid chunk for field name and description based on header.
                pass # field_name and field_desc remain empty (already initialized as "")

            # Clean up the reconstructed field name
            if field_name: # Ensure field_name is not empty before processing
                field_name = field_name.split('(')[0]  # Remove parenthetical explanations like (Primary Issuer)
                field_name = re.sub(r'\d*$', '', field_name) # Remove trailing digits (e.g., NAME1 -> NAME)
                # field_name should not have leading/trailing spaces due to "".join and word processing
            else:
                field_name = "" # Ensure it's an empty string if no parts were collected
            
            # Only process if we have a valid field name (allow mixed case)
            if field_name and len(field_name) >= 2:
                fields.append({
                    'Section': section_name,
                    'Field Name': field_name,
                    'Field Description': ' '.join(field_desc.split())
                })
    
    return fields
    
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
    
    print("Extracting text from {}...".format(args.input_pdf), flush=True)
    text = extract_text_from_pdf(args.input_pdf)
    
    print("Extracting fields...", flush=True)
    fields = extract_fields(text)
    
    print(f"Writing {len(fields)} fields to {args.output_csv}", flush=True)
    write_to_csv(fields, args.output_csv)
    print("Done!", flush=True)

if __name__ == '__main__':
    main()
