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
    other_column_keywords_strict = {
        "ALPHANUMERIC", "NUMERIC", "DATE", "BOOLEAN", # Format column
        "EDGAR", "XBRL", # Source column
        # "YES", "NO" for "May be NULL" are tricky as they can be in descriptions
        # Max Size is usually a number, also tricky.
        # Key is usually "*" - also tricky.
    }
    # Regex for these, ensuring they are whole words and not at the start of the line for description splitting.
    # We'll use re.search(r'\b' + keyword + r'\b', ...) later

    other_potentially_column_start_keywords = {"YES", "NO", "*"} # Keywords that might appear in other columns, less reliable for splitting description

    # Regex to find sections like "Figure 1. Fields in the FORMD SUBMISSION data file"
    # Captures the specific dataset name like "SUB" or "TAG"
    section_start_pattern = re.compile(
        r"Figure \d+\.[^\n]*?Fields in the\s+([A-Z0-9_]+(?:\s+[A-Z0-9_]+)*)\s+data (?:file|set)",
        re.IGNORECASE | re.DOTALL
    )

    # Regex to find the beginning of *any* "Figure X." line, to delimit the end of a section's text.
    any_figure_line_pattern = re.compile(r"^\s*Figure \d+\.", re.MULTILINE | re.IGNORECASE)

    all_section_start_matches = list(section_start_pattern.finditer(text))
    print(f"DEBUG: Found {len(all_section_start_matches)} 'Fields in the...' section start matches.")

    if not all_section_start_matches:
        print("DEBUG: No 'Fields in the...' patterns found. Returning empty list.")
        return all_parsed_fields

    for i, current_section_start_match in enumerate(all_section_start_matches):
        section_name_raw = current_section_start_match.group(1)
        section_name = ' '.join(section_name_raw.split()).strip() # Clean up section name

        current_section_body_start_offset = current_section_start_match.end()

        # Determine end of current section's text:
        # Find the next "Figure \d+." line *after* the current section's definition.
        next_figure_line_match = None
        if i + 1 < len(all_section_start_matches):
            # If there's another "Fields in the..." match, use its start as a primary boundary
            next_section_start_offset = all_section_start_matches[i+1].start()
            # Look for any "Figure d." between current section's body start and next "Fields in the..."
            temp_next_figure_match = any_figure_line_pattern.search(text, current_section_body_start_offset, next_section_start_offset)
            if temp_next_figure_match:
                next_figure_line_match = temp_next_figure_match
            else: # Fallback if no "Figure d." found before next "Fields in the..."
                current_section_text_end = next_section_start_offset
        else:
            # This is the last "Fields in the..." section, search till end of text for any "Figure d."
            next_figure_line_match = any_figure_line_pattern.search(text, current_section_body_start_offset)
            current_section_text_end = len(text) # Default to end of text

        if next_figure_line_match:
            current_section_text_end = next_figure_line_match.start()

        section_text_content = text[current_section_body_start_offset:current_section_text_end]

        # Regex for the header row of the table within each section
        header_pattern = re.compile(
            r"Field\s+Name\s+Field\s+Description", # Simplified, as other columns are less reliable
            re.IGNORECASE | re.DOTALL
        )
        header_match = header_pattern.search(section_text_content)

        print(f"DEBUG: Processing Section: '{section_name}'. Text content length: {len(section_text_content)}. Header found: {'Yes' if header_match else 'No'}")

        if not header_match:
            print(f"DEBUG: Header not found in section '{section_name}'. Skipping to next section.")
            continue
        
        table_text_start_index = header_match.end()
        table_text = section_text_content[table_text_start_index:]
        lines = table_text.split('\n')
        print(f"DEBUG: Section '{section_name}': table_text (first 200 chars) = '{table_text[:200].replace(chr(10), chr(92) + chr(110))}'") # Escape newlines for print
        
        current_field_name = None
        current_description_parts = []
        section_fields = [] # Holds dicts for fields in the current section
        
        # Field names are typically uppercase, numbers, underscores.
        # Let's make it more specific to avoid common words.
        # Field names usually don't contain lowercase letters, except perhaps as part of an acronym like 'effDate'.
        # For MFRR.pdf, names like 'adsh', 'cik', 'name' are lowercase.
        # Let's assume a field name is a single word, possibly with underscores or numbers,
        # and not excessively long.
        field_name_regex = r"^[a-zA-Z0-9_]{2,30}$" # Adjusted for MFRR.pdf
        # Common words that might start a description but could be mistaken for field names
        # Expanded with typical table header terms to prevent them from becoming fields
        common_desc_start_words = {
            "THE", "A", "AN", "THIS", "IF", "FOR", "AND", "OF", "IN", "TO", "IS", "ARE", "AS", "FIELD",
            "MAX", "SIZE", "MAY", "BE", "NULL", "KEY", "SOURCE", "FORMAT", "DATA", "TYPE",
            "LENGTH", "COMMENTS", "NAME", "DESCRIPTION" # Added Name, Description
        }

        # Helper function to check for non-descriptive column data
        def is_likely_column_data(line_text, strict_kws, potential_kws):
            line_upper = line_text.upper()
            # Check if the entire line is just one of these keywords or a number
            if line_upper in strict_kws: return True
            if line_upper in potential_kws: return True
            if line_text.isdigit(): return True
            # Add more checks if needed, e.g. simple date patterns, CUSIP, etc.
            # Check if line primarily consists of such tokens (e.g. "NO * YES") - more complex
            tokens = line_text.split()
            if not tokens: return False
            # If all tokens are from these sets or are digits
            # This is a basic check; could be more sophisticated
            all_tokens_are_data = True
            for token in tokens:
                token_upper = token.upper()
                if not (token.isdigit() or token_upper in strict_kws or token_upper in potential_kws):
                    all_tokens_are_data = False
                    break
            if all_tokens_are_data: return True

            return False

        processed_lines = []
        for line_idx, line_content in enumerate(lines):
            # Pre-filter lines that are part of a *next* section's title/description appearing before its own table header
            # This is to prevent "Key No No No 5.4 CAL (Calculations)..."
            # if any_figure_line_pattern.match(line_content.strip()) and line_idx > 0: # Heuristic: if "Figure X." appears mid-table text
            #     # Check if this line is too far from what looks like field data
            #     # This is complex; for now, rely on the section end marker (any_figure_line_pattern) for section_text_content
            #     # A simpler check: if the line starts with "Figure X." and does not contain "Field Name Field Description"
            #     # it's likely a title for something else.
            if any_figure_line_pattern.match(line_content.strip()) and not header_pattern.search(line_content): # Corrected indentation
                print(f"DEBUG: Truncating lines at line {line_idx} due to new Figure line: '{line_content[:100]}'")
                break
            processed_lines.append(line_content) # Corrected indentation relative to the if

        lines = processed_lines # Use the potentially truncated list of lines


        for line_num, line in enumerate(lines):
            stripped_line = line.strip()
            if not stripped_line:
                continue

            parts = stripped_line.split(maxsplit=1)
            first_word = parts[0] if parts else ""
            rest_of_line = parts[1].strip() if len(parts) > 1 else ""

            print(f"DEBUG: Line {line_num}: Raw Stripped Line: '{stripped_line}'")
            print(f"DEBUG: Line {line_num}: first_word='{first_word}', rest_of_line='{rest_of_line}'")

            is_likely_field_name_start = bool(re.match(field_name_regex, first_word)) and \
                                         first_word.upper() not in common_desc_start_words and \
                                         not first_word.upper() in other_column_keywords_strict and \
                                         not first_word.upper() in other_potentially_column_start_keywords and \
                                         not first_word.isdigit()

            # Check if rest_of_line starts with a description or another column's data
            rol_starts_with_col_keyword = False
            if rest_of_line:
                for kw in other_column_keywords_strict:
                    if rest_of_line.upper().startswith(kw):
                        rol_starts_with_col_keyword = True
                        break

            # --- Check 1: Scenario C Special (e.g. "verbose" followed by "Verbose label...") ---
            # This handles the case where a field name (e.g. "verbose") is on one line,
            # and its description starts on the *next* line with a capitalized version of the field name.
            if current_field_name and not current_description_parts and \
               first_word.capitalize() == current_field_name.capitalize() and \
               bool(re.match(field_name_regex, first_word)) and \
               first_word.upper() not in common_desc_start_words:
                
                if first_word.upper() in other_column_keywords_strict: # e.g. current_field="format", line="Format Max..."
                     print(f"DEBUG: Line {line_num}: Scenario C Special candidate '{first_word}' is a strict keyword. Not merging. Finalizing '{current_field_name}'.")
                     _finalize_and_add_field(current_field_name, current_description_parts, section_name, section_fields, line_num, f"CSpecialKeywordFinalize for {current_field_name}")
                     current_field_name = None
                     current_description_parts = []
                     # Line is not consumed by 'continue', will be re-evaluated by subsequent rules (likely Scenario B or D)
                else:
                    print(f"DEBUG: Line {line_num}: Scenario C Special: Merging '{stripped_line}' into description of '{current_field_name}'.")

                    description_segment = stripped_line
                    earliest_keyword_index_special = -1
                    keyword_in_special = None
                    for keyword in other_column_keywords_strict:
                        match = re.search(r'\s+\b' + re.escape(keyword) + r'\b', description_segment, re.IGNORECASE)
                        if match:
                            idx = match.start()
                            if earliest_keyword_index_special == -1 or idx < earliest_keyword_index_special:
                                earliest_keyword_index_special = idx
                                keyword_in_special = keyword

                    if keyword_in_special:
                        description_segment = description_segment[:earliest_keyword_index_special].strip()
                        print(f"DEBUG: Line {line_num}:   CSpecial Desc for '{current_field_name}' split by strict keyword '{keyword_in_special}'. Desc: '{description_segment}'")

                    if description_segment:
                        current_description_parts.append(description_segment)

                    if keyword_in_special:
                        _finalize_and_add_field(current_field_name, current_description_parts, section_name, section_fields, line_num, f"CSpecialKeywordSplitFinalize for {current_field_name}")
                        current_field_name = None
                        current_description_parts = []
                    continue # Line consumed by Scenario C Special


            # --- Check 2: Strong Signal (e.g. "fieldkey Fielddescription" on the same line) ---
            is_strong_signal_line = False
            if first_word.islower() and len(rest_of_line.split()) > 0 and rest_of_line.split()[0][0].isupper() \
               and bool(re.match(field_name_regex, first_word)) \
               and first_word.upper() not in common_desc_start_words:
                first_rol_word = rest_of_line.split()[0].upper() if rest_of_line else ""
                if first_rol_word not in other_column_keywords_strict:
                    is_strong_signal_line = True

            if is_strong_signal_line:
                print(f"DEBUG: Line {line_num}: Strong signal interpreted: '{first_word}' as field, '{rest_of_line}' as its description start.")
                if current_field_name:
                     _finalize_and_add_field(current_field_name, current_description_parts, section_name, section_fields, line_num, f"StrongSignalNewField for {current_field_name}")

                current_field_name = first_word
                current_description_parts = []
                description_segment = rest_of_line

                earliest_keyword_index_rol = -1
                keyword_in_rol = None # Important to reset this for each line analysis
                for keyword in other_column_keywords_strict:
                    match = re.search(r'\s+\b' + re.escape(keyword) + r'\b', description_segment, re.IGNORECASE)
                    if match:
                        idx = match.start()
                        if earliest_keyword_index_rol == -1 or idx < earliest_keyword_index_rol:
                            earliest_keyword_index_rol = idx
                            keyword_in_rol = keyword

                if keyword_in_rol:
                    description_segment = description_segment[:earliest_keyword_index_rol].strip()
                    print(f"DEBUG: Line {line_num}:   Strong signal ROL for '{current_field_name}' split by strict keyword '{keyword_in_rol}'. Desc: '{description_segment}'")

                if description_segment:
                    current_description_parts.append(description_segment)

                if keyword_in_rol:
                    _finalize_and_add_field(current_field_name, current_description_parts, section_name, section_fields, line_num, f"StrongSignalROLKeywordFinalize for {current_field_name}")
                    current_field_name = None
                    current_description_parts = []
                continue

            # --- Check 3: General New Field (Scenario A/B) ---
            # (is_likely_field_name_start was calculated before C Special and Strong Signal checks)
            if is_likely_field_name_start and not rol_starts_with_col_keyword:
                potential_field_name_on_line = first_word # Use original first_word from line
                potential_description_start_on_line = rest_of_line # Use original rest_of_line

                if len(potential_field_name_on_line) <=2 and not potential_description_start_on_line and current_field_name: # Scenario A
                     print(f"DEBUG: Line {line_num}: Scenario A: Short first word '{potential_field_name_on_line}' with no ROL, treated as continuation for '{current_field_name}'.")
                     current_description_parts.append(stripped_line)
                else: # Scenario B proper
                    print(f"DEBUG: Line {line_num}: Scenario B: New field '{potential_field_name_on_line}' detected. Description starts with: '{potential_description_start_on_line[:50]}'")
                    if current_field_name:
                        _finalize_and_add_field(current_field_name, current_description_parts, section_name, section_fields, line_num, f"NewFieldFound for {current_field_name}")

                    current_field_name = potential_field_name_on_line
                    current_description_parts = []
                    description_segment = potential_description_start_on_line

                    earliest_keyword_index_rol_b = -1 # Use distinct var name
                    keyword_in_rol_b = None          # Use distinct var name
                    for keyword in other_column_keywords_strict:
                        match = re.search(r'\s+\b' + re.escape(keyword) + r'\b', description_segment, re.IGNORECASE)
                        if match:
                            idx = match.start()
                            if earliest_keyword_index_rol_b == -1 or idx < earliest_keyword_index_rol_b:
                                earliest_keyword_index_rol_b = idx
                                keyword_in_rol_b = keyword

                    if keyword_in_rol_b:
                        description_segment = description_segment[:earliest_keyword_index_rol_b].strip()
                        print(f"DEBUG: Line {line_num}:   ROL for '{current_field_name}' split by strict keyword '{keyword_in_rol_b}'. Desc: '{description_segment}'")

                    if description_segment:
                        current_description_parts.append(description_segment)

                    if keyword_in_rol_b:
                        _finalize_and_add_field(current_field_name, current_description_parts, section_name, section_fields, line_num, f"ROLStrictKeywordFinalize for {current_field_name}")
                        current_field_name = None
                        current_description_parts = []
                continue

            # --- Check 4: Scenario C (Main - if field active and line not consumed by above) ---
            if current_field_name:
                # Note: Scenario C Special (capitalized version) is handled as Check 1
                print(f"DEBUG: Line {line_num}: Scenario C (Main): Continuation or terminator for '{current_field_name}'. Line: '{stripped_line}'")
                line_starts_with_strict_keyword = False
                found_strict_keyword_at_start = None
                for keyword in other_column_keywords_strict:
                    if stripped_line.upper().startswith(keyword):
                         line_starts_with_strict_keyword = True
                         found_strict_keyword_at_start = keyword
                         break

                if line_starts_with_strict_keyword:
                    print(f"DEBUG: Line {line_num}:   Line starts with strict keyword '{found_strict_keyword_at_start}'. Finalizing '{current_field_name}'.")
                    _finalize_and_add_field(current_field_name, current_description_parts, section_name, section_fields, line_num, f"StrictKeywordStart for {current_field_name}")
                    current_field_name = None
                    current_description_parts = []
                elif is_likely_column_data(stripped_line, other_column_keywords_strict, other_potentially_column_start_keywords):
                    print(f"DEBUG: Line {line_num}:   Line '{stripped_line}' identified as column data. Finalizing '{current_field_name}'.")
                    _finalize_and_add_field(current_field_name, current_description_parts, section_name, section_fields, line_num, f"ColumnDataFinalize for {current_field_name}")
                    current_field_name = None
                    current_description_parts = []
                else:
                    if current_description_parts and current_description_parts[-1].strip().endswith(".") and stripped_line and stripped_line[0].isupper():
                        if len(stripped_line.split()) > 3 :
                            print(f"DEBUG: Line {line_num}:   Possible new sentence detected after period for '{current_field_name}'. Line: '{stripped_line[:60]}...'. Finalizing.")
                            _finalize_and_add_field(current_field_name, current_description_parts, section_name, section_fields, line_num, f"NewSentenceHeuristic for {current_field_name}")
                            current_field_name = None
                            current_description_parts = []
                            # This line might become an orphan if it doesn't match other rules after this.

                    if current_field_name:
                        description_segment = stripped_line
                        earliest_keyword_index_cont = -1
                        keyword_in_cont = None
                        for keyword in other_column_keywords_strict:
                            match = re.search(r'\s+\b' + re.escape(keyword) + r'\b', stripped_line, re.IGNORECASE)
                            if match:
                                idx = match.start()
                                if earliest_keyword_index_cont == -1 or idx < earliest_keyword_index_cont:
                                    earliest_keyword_index_cont = idx
                                    keyword_in_cont = keyword

                        if keyword_in_cont:
                            description_segment = stripped_line[:earliest_keyword_index_cont].strip()
                            print(f"DEBUG: Line {line_num}:   Continuation for '{current_field_name}' split by mid-line strict keyword '{keyword_in_cont}'. Desc: '{description_segment}'")

                        if description_segment:
                            current_description_parts.append(description_segment)

                        if keyword_in_cont:
                            _finalize_and_add_field(current_field_name, current_description_parts, section_name, section_fields, line_num, f"MidLineStrictKeywordFinalize for {current_field_name}")
                            current_field_name = None
                            current_description_parts = []
            
            # --- Check 5: Orphaned line (Scenario D) ---
            # This is reached if the line was not consumed by 'continue' and current_field_name is None
            # (either never set for this line, or set to None by Scenario C finalization).
            if not current_field_name:
                 print(f"DEBUG: Line {line_num}: Scenario D: Orphaned line: '{stripped_line}'")

        # End of section: finalize any remaining field
        if current_field_name:
            _finalize_and_add_field(current_field_name, current_description_parts, section_name, section_fields, line_num, f"EndOfSection for {current_field_name}")

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
