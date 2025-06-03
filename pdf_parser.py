import re
import csv # Import the csv module
import argparse # Import the argparse module
import sys # Import sys for sys.exit()
from io import StringIO
from pdfminer.converter import TextConverter
from pdfminer.layout import LAParams
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.pdfpage import PDFPage
from pdfminer.pdfparser import PDFParser, PDFSyntaxError # For specific PDF errors
# from pdfminer.psparser import PSError # PSError could not be reinstated due to ImportError

def _finalize_and_add_field(field_name, description_parts, section_name, section_fields_list, line_num_debug, context_debug_msg):
    """Helper to finalize a field and add it to the section_fields_list."""
    description = " ".join(description_parts).strip()
    if description or not any(d['Field Name'] == field_name and d['Section'] == section_name for d in section_fields_list):
        field_to_add = {
            'Section': section_name,
            'Field Name': field_name,
            'Field Description': description
        }
        print(f"DEBUG: Line ~{line_num_debug} ({context_debug_msg}): Finalizing and Adding to section_fields: {field_to_add}")
        section_fields_list.append(field_to_add)
    else:
        print(f"DEBUG: Line ~{line_num_debug} ({context_debug_msg}): Field '{field_name}' already added or empty description not needed. Skipping.")

def extract_text_from_pdf(pdf_path):
    """
    Extracts text from all pages of the specified PDF file.
    Also removes form feed characters ('\f') from the extracted text.

    Args:
        pdf_path (str): The file path to the PDF.

    Returns:
        str or None: The extracted text content from the PDF, or None if an error occurs.
    """
    try:
        output_string = StringIO()
        with open(pdf_path, 'rb') as in_file:
            parser = PDFParser(in_file)
            doc = PDFDocument(parser)
            rsrcmgr = PDFResourceManager()
            device = TextConverter(rsrcmgr, output_string, laparams=LAParams())
            interpreter = PDFPageInterpreter(rsrcmgr, device)
            for page in PDFPage.create_pages(doc):
                interpreter.process_page(page)
        full_text = output_string.getvalue()
        full_text = full_text.replace('\f', '') 
        return full_text
    except FileNotFoundError:
        print(f"Error: Input PDF file not found: {pdf_path}")
        return None
    except PDFSyntaxError as e:
        print(f"Error processing PDF file '{pdf_path}': It might be corrupted or not a valid PDF. Details: {e}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred while processing PDF '{pdf_path}': {e}")
        return None

def parse_fields_from_text(text):
    print(f"DEBUG: Entered parse_fields_from_text. Text length: {len(text) if text else 'None'}")
    if not text:
        print("DEBUG: Text is empty or None. Returning empty list.")
        return []
    all_parsed_fields = []

    # Define format keywords (broad set for initial token type check)
    format_keywords = {"ALPHANUMERIC", "DATE", "NUMERIC", "CHARACTER", "VARCHAR",
                       "INTEGER", "TEXT", "BOOLEAN", "DECIMAL"}
    # Define a stricter set of keywords for splitting descriptions mid-line
    # This was the version from Turn 25 / v7
    # Modified in Turn 22 (Subtask 17) to be more restrictive
    strict_format_keywords_for_splitting = {"ALPHANUMERIC", "NUMERIC"}

    other_column_keywords = {"YES", "NO", "*"} # Keywords that might appear in other columns

    # Regex to find sections like "Figure 1. Fields in the FORMD SUBMISSION data file"
    # It captures the section name like "FORMD SUBMISSION"
    section_pattern = re.compile(r"Figure \d+\..*?Fields in the\s+(.+?)\s+data file", re.IGNORECASE | re.DOTALL)
    all_figure_matches = list(section_pattern.finditer(text)) # Use list to allow indexing
    print(f"DEBUG: Found {len(all_figure_matches)} 'Figure X...' section matches.")

    if not all_figure_matches:
        print("DEBUG: No 'Figure X...' patterns found. Returning empty list.")
        return all_parsed_fields

    for i, current_figure_match in enumerate(all_figure_matches):
        section_name_raw = current_figure_match.group(1)
        # Clean up section name: remove extra whitespace, newlines
        section_name = ' '.join(section_name_raw.split()).strip()

        current_section_text_start = current_figure_match.end()
        # Determine end of current section: start of next section or end of text
        current_section_text_end = all_figure_matches[i+1].start() if i + 1 < len(all_figure_matches) else len(text)
        section_text = text[current_section_text_start:current_section_text_end]

        # Regex for the header row of the table within each section
        header_pattern = re.compile(
            r"Field\s+Name\s+Field\s+Description(?:\s+Format\s+Max\s+Size\s+May\s+be\s+NULL\s+Key|\s+Data\s+Type\s+Length\s+Nullable\s+Comments)?", 
            re.IGNORECASE | re.DOTALL # DOTALL because description might span lines
        )
        header_match = header_pattern.search(section_text)

        print(f"DEBUG: Processing Section: '{section_name}'. Header found: {'Yes' if header_match else 'No'}")

        if not header_match:
            print(f"DEBUG: Header not found in section '{section_name}'. Skipping to next section.")
            continue
        
        table_text_start_index = header_match.end()
        table_text = section_text[table_text_start_index:]
        lines = table_text.split('\n')
        print(f"DEBUG: Section '{section_name}': table_text (first 200 chars) = '{table_text[:200]}'")
        
        current_field_name = None
        current_description_parts = []
        section_fields = [] # Holds dicts for fields in the current section
        pending_fields_queue = [] # Holds field dicts {'name': str, 'description_parts': list} for fields awaiting description lines
        
        field_name_regex = r"^[A-Z0-9_]{3,}$" # Field names are typically uppercase, numbers, underscores, min 3 chars

        for line_num, line in enumerate(lines):
            stripped_line = line.strip()
            if not stripped_line: # Skip empty lines
                continue

            # Try to identify the first token as a potential field name
            parts = stripped_line.split(maxsplit=1)
            first_word = parts[0] if parts else ""
            rest_of_line = parts[1].strip() if len(parts) > 1 else ""

            print(f"DEBUG: Line {line_num}: Raw Stripped Line: '{stripped_line}'")
            print(f"DEBUG: Line {line_num}: first_word='{first_word}', rest_of_line='{rest_of_line}', Queue: {[f['name'] for f in pending_fields_queue]}")

            is_potential_field_name_token = bool(re.match(field_name_regex, first_word))
            is_format_keyword_token = first_word.upper() in format_keywords
            is_other_data_token = (first_word.upper() in other_column_keywords) or first_word.isdigit()


            # Scenario 1: A new field name is identified
            if is_potential_field_name_token and not is_format_keyword_token and not is_other_data_token:
                newly_found_field_name = first_word
                print(f"DEBUG: Line {line_num}: Scenario 1: New field '{newly_found_field_name}' found. ROL: '{rest_of_line}'")

                # If there was a pending field in the queue, and this new field has ROL, finalize all pending.
                if rest_of_line and pending_fields_queue:
                    print(f"DEBUG: Line {line_num}:   New field '{newly_found_field_name}' has ROL. Finalizing ALL {len(pending_fields_queue)} in queue.")
                    for pf_to_finalize in pending_fields_queue:
                         _finalize_and_add_field(pf_to_finalize['name'], pf_to_finalize['description_parts'], section_name, section_fields, line_num, f"PendingQ for {pf_to_finalize['name']} (due to new field with ROL)")
                    pending_fields_queue = []

                # Finalize the previous field (if any) before starting a new one
                if current_field_name:
                    _finalize_and_add_field(current_field_name, current_description_parts, section_name, section_fields, line_num, f"ActiveField for {current_field_name} (new field found)")
                
                current_field_name = newly_found_field_name
                current_description_parts = []

                if rest_of_line:
                    earliest_keyword_index = -1
                    keyword_found_in_rol = None
                    for keyword in strict_format_keywords_for_splitting: # Use strict list for ROL splitting
                        match = re.search(r'\b' + re.escape(keyword) + r'\b', rest_of_line, re.IGNORECASE)
                        if match:
                            idx = match.start()
                            if earliest_keyword_index == -1 or idx < earliest_keyword_index:
                                earliest_keyword_index = idx
                                keyword_found_in_rol = keyword

                    if earliest_keyword_index != -1: # Keyword found in ROL
                        description_segment = rest_of_line[:earliest_keyword_index].strip()
                        if description_segment: #Only append if there's actual text
                            current_description_parts.append(description_segment)
                        print(f"DEBUG: Line {line_num}:   ROL for '{current_field_name}' contains keyword '{keyword_found_in_rol}'. Appended: '{description_segment}'. Finalizing.")
                        _finalize_and_add_field(current_field_name, current_description_parts, section_name, section_fields, line_num, f"ROL Keyword for {current_field_name}")
                        current_field_name = None # Field is done
                    else: # No keyword in ROL, ROL is pure description
                        current_description_parts.append(rest_of_line)
                        print(f"DEBUG: Line {line_num}:   No keyword in ROL for '{current_field_name}'. Appended ROL. Parts: {current_description_parts}")
                else: # No rest_of_line, so add this new field to pending_fields_queue
                    print(f"DEBUG: Line {line_num}:   '{current_field_name}' has empty ROL. Adding to pending_fields_queue.")
                    # If current_field_name was already processed and added (e.g. from ROL), this might lead to duplicates if not handled by _finalize_and_add_field
                    pending_fields_queue.append({'name': current_field_name, 'description_parts': []})
                    current_field_name = None # It's in the queue, not the active non-queued field

            # Scenario 2: Line starts with a format keyword or other data token (not a field name)
            elif is_format_keyword_token or is_other_data_token:
                print(f"DEBUG: Line {line_num}: Scenario 2: Line starts with keyword/data '{first_word}'.")
                if pending_fields_queue: # This keyword/data applies to the field at the head of the queue
                    field_from_queue = pending_fields_queue.pop(0) # Get and remove first item
                    print(f"DEBUG: Line {line_num}:   Finalizing '{field_from_queue['name']}' from queue due to keyword line. Desc parts: {field_from_queue['description_parts']}")
                    _finalize_and_add_field(field_from_queue['name'], field_from_queue['description_parts'], section_name, section_fields, line_num, f"PendingQ Keyword for {field_from_queue['name']}")
                elif current_field_name: # Or it applies to the current non-queued field
                    print(f"DEBUG: Line {line_num}:   Finalizing active non-queued field '{current_field_name}' due to keyword line. Desc parts: {current_description_parts}")
                    _finalize_and_add_field(current_field_name, current_description_parts, section_name, section_fields, line_num, f"ActiveField Keyword for {current_field_name}")
                current_field_name = None # Field is finalized
                current_description_parts = []
            
            # Scenario 3: Line is a continuation of a description
            else: # Not a new field name, not starting with a strong keyword
                print(f"DEBUG: Line {line_num}: Scenario 3 active for line: '{stripped_line}'")
                target_description_parts = None
                target_field_name_debug = None
                is_for_queued_field = False

                if pending_fields_queue: # If queue has items, this description belongs to Q[0]
                    target_description_parts = pending_fields_queue[0]['description_parts']
                    target_field_name_debug = pending_fields_queue[0]['name']
                    is_for_queued_field = True
                    print(f"DEBUG: Line {line_num}:   Line is for queued field '{target_field_name_debug}'.")
                elif current_field_name: # Otherwise, it belongs to the current non-queued field
                    target_description_parts = current_description_parts
                    target_field_name_debug = current_field_name
                    print(f"DEBUG: Line {line_num}:   Line is for active non-queued field '{target_field_name_debug}'.")

                if target_description_parts is not None:
                    earliest_keyword_index_sc3 = -1
                    keyword_found_sc3 = None
                    for keyword in strict_format_keywords_for_splitting: # Use strict list for mid-line splitting
                        match = re.search(r'\b' + re.escape(keyword) + r'\b', stripped_line, re.IGNORECASE)
                        if match and match.start() > 0: # Ensure keyword is not at the very beginning
                            idx = match.start()
                            if earliest_keyword_index_sc3 == -1 or idx < earliest_keyword_index_sc3:
                                earliest_keyword_index_sc3 = idx
                                keyword_found_sc3 = keyword

                    if earliest_keyword_index_sc3 != -1: # Mid-line keyword found
                        description_segment = stripped_line[:earliest_keyword_index_sc3].strip()
                        if description_segment:
                             target_description_parts.append(description_segment)
                        print(f"DEBUG: Line {line_num}:   Found mid-line keyword '{keyword_found_sc3}' for '{target_field_name_debug}'. Appended: '{description_segment}'. Finalizing.")
                        if is_for_queued_field:
                            field_to_finalize = pending_fields_queue.pop(0)
                            _finalize_and_add_field(field_to_finalize['name'], field_to_finalize['description_parts'], section_name, section_fields, line_num, f"PendingQ KeywordInDesc for {field_to_finalize['name']}")
                        elif current_field_name: # Should be true if not for queued field
                             _finalize_and_add_field(current_field_name, current_description_parts, section_name, section_fields, line_num, f"ActiveField KeywordInDesc for {current_field_name}")
                             current_field_name = None
                             current_description_parts = []
                    else: # No mid-line keyword, append whole line
                        target_description_parts.append(stripped_line)
                        print(f"DEBUG: Line {line_num}:   No mid-line keyword. Appended line to '{target_field_name_debug}'. Parts: {target_description_parts}")
                else:
                    print(f"DEBUG: Line {line_num}:   Orphaned description line (no active field or queue): '{stripped_line}'")

        # End of section: finalize any remaining field or queued fields
        if current_field_name:
            _finalize_and_add_field(current_field_name, current_description_parts, section_name, section_fields, line_num, f"EndOfSection ActiveField for {current_field_name}")
        for pf_to_finalize in pending_fields_queue: # Finalize any remaining in queue
            _finalize_and_add_field(pf_to_finalize['name'], pf_to_finalize['description_parts'], section_name, section_fields, line_num, f"EndOfSection PendingQ for {pf_to_finalize['name']}")

        all_parsed_fields.extend(section_fields)
    return all_parsed_fields

def write_to_csv(parsed_data, csv_filepath):
    if not parsed_data:
        print("No data to write to CSV.")
        return True
    fieldnames = ['Section', 'Field Name', 'Field Description']
    try:
        with open(csv_filepath, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(parsed_data)
        return True
    except IOError as e:
        print(f"Error: Could not write to CSV file '{csv_filepath}'. Details: {e}")
        return False
    except Exception as e:
        print(f"An unexpected error occurred while writing to CSV '{csv_filepath}': {e}")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract text from a PDF and parse fields into a CSV.")
    parser.add_argument("--pdf_file", type=str, required=True, help="Path to the input PDF file.")
    parser.add_argument("--csv_file", type=str, required=True, help="Path to the output CSV file.")
    args = parser.parse_args()

    print(f"Extracting text from '{args.pdf_file}'...")
    full_text_content = extract_text_from_pdf(args.pdf_file)

    if full_text_content is None:
        print("Text extraction failed. Exiting.")
        sys.exit(1)

    import os
    output_dir_for_raw = "output"
    if not os.path.exists(output_dir_for_raw):
        os.makedirs(output_dir_for_raw)
        print(f"Created directory: {output_dir_for_raw}")
    raw_text_path = os.path.join(output_dir_for_raw, "form_d_1-9_raw_text.txt")

    with open(raw_text_path, "w", encoding="utf-8") as f:
        f.write(full_text_content)
    print(f"Raw text saved to {raw_text_path}")

    csv_output_dir = os.path.dirname(args.csv_file)
    if csv_output_dir and not os.path.exists(csv_output_dir):
        os.makedirs(csv_output_dir)
        print(f"Created directory: {csv_output_dir}")

    print("\nParsing fields from extracted text...")
    structured_data = parse_fields_from_text(full_text_content)
    
    if structured_data:
        if write_to_csv(structured_data, args.csv_file):
            print(f"\nSuccessfully parsed {len(structured_data)} fields and wrote them to {args.csv_file}")
        else:
            print(f"\nFailed to write parsed data to {args.csv_file}. Exiting.")
            sys.exit(1)
    else:
        print("\nText extracted, but no structured data found according to parsing rules. CSV file not created.")
