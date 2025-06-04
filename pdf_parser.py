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
from pdfminer.pdfparser import PDFParser, PDFSyntaxError
try:
    from pdfminer.psparser import PSSyntaxError as PSError  # compatibility alias
except Exception:  # pragma: no cover
    class PSError(Exception):
        """Fallback when pdfminer does not expose PSError."""
        pass

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
    except PSError as e:
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

    other_column_keywords_strict = {
        "ALPHANUMERIC", "NUMERIC", "DATE", "BOOLEAN", "EDGAR", "XBRL", "TEXT",
        "VARCHAR", "INTEGER"
    }
    other_potentially_column_start_keywords = {"YES", "NO", "*"}

    # Made more permissive for field names like 'series', 'total', 'verbose'
    field_name_regex = r"^[A-Z0-9_]{3,}$"
    # Keep known acronyms or specific case-sensitive names in a set to prevent lowercasing them.
    known_acronyms_or_case_sensitive_names = {"CIK", "XBRL", "EDGAR", "ABS", "CRS", "DEFRS", "MFRR"} # Add more if needed

    common_desc_start_words = {
        "THE", "A", "AN", "THIS", "IF", "FOR", "AND", "OF", "IN", "TO", "IS", "ARE", "AS", "FIELD",
        "MAX", "SIZE", "MAY", "BE", "NULL", "KEY", "SOURCE", "FORMAT", "DATA", "TYPE",
        "LENGTH", "COMMENTS", "NAME", "DESCRIPTION", "FIELDNAME", "FIELDTYPE",
        "NOTE", "CONTINUATION", "CODE"
    }

    section_start_pattern = re.compile(
        r"Figure \d+\.[^\n]*?Fields in the\s+([A-Z0-9_]+(?:\s+[A-Z0-9_]+)*)\s+data (?:file|set)",
        re.IGNORECASE | re.DOTALL
    )
    any_figure_line_pattern = re.compile(r"^\s*Figure \d+\.", re.MULTILINE | re.IGNORECASE)

    all_section_start_matches = list(section_start_pattern.finditer(text))
    print(f"DEBUG: Found {len(all_section_start_matches)} 'Fields in the...' section start matches.")

    if not all_section_start_matches:
        return all_parsed_fields

    for i, current_section_start_match in enumerate(all_section_start_matches):
        section_name_raw = current_section_start_match.group(1)
        section_name = ' '.join(section_name_raw.split()).strip()
        current_section_body_start_offset = current_section_start_match.end()
        next_figure_line_match = None
        if i + 1 < len(all_section_start_matches):
            next_section_start_offset = all_section_start_matches[i+1].start()
            temp_next_figure_match = any_figure_line_pattern.search(text, current_section_body_start_offset, next_section_start_offset)
            current_section_text_end = temp_next_figure_match.start() if temp_next_figure_match else next_section_start_offset
        else:
            next_figure_line_match = any_figure_line_pattern.search(text, current_section_body_start_offset)
            current_section_text_end = next_figure_line_match.start() if next_figure_line_match else len(text)

        section_text_content = text[current_section_body_start_offset:current_section_text_end]
        header_pattern = re.compile(r"Field\s+Name\s+Field\s+Description", re.IGNORECASE | re.DOTALL)
        header_match = header_pattern.search(section_text_content)

        print(f"DEBUG: Processing Section: '{section_name}'. Text content length: {len(section_text_content)}. Header found: {'Yes' if header_match else 'No'}")

        if header_match:
            table_text_start_index = header_match.end()
            table_text = section_text_content[table_text_start_index:]
        else:
            # Fallback: treat entire section text as table when standard header is missing
            table_text = section_text_content

        lines = table_text.split('\n')
        print(f"DEBUG: Section '{section_name}': table_text (first 200 chars) = '{table_text[:200].replace(chr(10), chr(92) + chr(110))}'")
        
        current_field_name = None
        current_description_parts = []
        section_fields = []
        
        def is_likely_column_data(line_text, strict_kws, potential_kws):
            line_upper = line_text.upper()
            if line_upper in strict_kws or line_upper in potential_kws or line_text.isdigit(): return True
            tokens = line_text.split()
            if not tokens: return False
            return all(t.isdigit() or t.upper() in strict_kws or t.upper() in potential_kws for t in tokens)

        processed_lines = []
        for line_idx, line_content in enumerate(lines):
            if any_figure_line_pattern.match(line_content.strip()) and not header_pattern.search(line_content):
                print(f"DEBUG: Truncating lines at line {line_idx} due to new Figure line: '{line_content[:100]}'")
                break
            processed_lines.append(line_content)
        for line_num, line in enumerate(lines):
            stripped_line = line.strip()
            if not stripped_line: continue

            parts = stripped_line.split(maxsplit=1)
            first_word = parts[0] if parts else ""
            rest_of_line = parts[1].strip() if len(parts) > 1 else ""
            print(f"DEBUG: Line {line_num}: Raw: '{stripped_line}' | FW: '{first_word}' | ROL: '{rest_of_line}'")

            # Calculate this once, based on original first_word
            is_likely_field_name_start_original = bool(re.match(field_name_regex, first_word)) and \
                                         first_word.upper() not in common_desc_start_words and \
                                         not first_word.upper() in other_column_keywords_strict and \
                                         not first_word.upper() in other_potentially_column_start_keywords and \
                                         not first_word.isdigit() and \
                                         not first_word.islower()
            rol_starts_with_col_keyword = any(rest_of_line.upper().startswith(kw) for kw in other_column_keywords_strict) if rest_of_line else False

            # --- Check 1: Scenario C Special (e.g. "verbose" on line N, then "Verbose label..." on line N+1) ---
            if current_field_name and not current_description_parts and \
               first_word and current_field_name.islower() and first_word[0].isupper() and \
               first_word.lower() == current_field_name and \
               bool(re.match(field_name_regex, first_word)) and first_word.upper() not in common_desc_start_words:
                if first_word.upper() in other_column_keywords_strict:
                     print(f"DEBUG: CSpecial Finalize: '{current_field_name}' (keyword '{first_word}')")
                     _finalize_and_add_field(current_field_name, [], section_name, section_fields, line_num, "CSpecialKeywordFinalize")
                     current_field_name = None; current_description_parts = []
                     # Fall through to re-evaluate this line.
                else:
                    print(f"DEBUG: CSpecial Merge: '{stripped_line}' to '{current_field_name}'")
                    desc_seg = stripped_line; earliest_idx = -1; found_kw = None
                    for kw in other_column_keywords_strict:
                        m = re.search(r'\s+\b' + re.escape(kw) + r'\b', desc_seg, re.IGNORECASE)
                        if m and (earliest_idx == -1 or m.start() < earliest_idx): earliest_idx, found_kw = m.start(), kw
                    if found_kw: desc_seg = desc_seg[:earliest_idx].strip()
                    if desc_seg: current_description_parts.append(" ".join(desc_seg.split()))
                    if found_kw:
                        _finalize_and_add_field(current_field_name, current_description_parts, section_name, section_fields, line_num, "CSpecialSplitFinalize")
                        current_field_name = None; current_description_parts = []
                    continue

            # --- Check 1.5: Camel Case Field Name Construction (e.g., "negated" then "Terse") ---
            if current_field_name and current_field_name.islower() and not current_description_parts and \
               first_word and first_word[0].isupper() and first_word.lower() != current_field_name and \
               first_word.upper() not in common_desc_start_words and first_word.upper() not in other_column_keywords_strict and \
               not is_likely_column_data(first_word, [], []) and bool(re.match(r"^[A-Z][a-zA-Z0-9_]*$", first_word)):

                combined_name_cand = current_field_name + first_word
                if bool(re.match(r"^[a-z]+[A-Z][a-zA-Z0-9_]*$", combined_name_cand)):
                    print(f"DEBUG: CamelCase: Form '{combined_name_cand}' from '{current_field_name}' + '{first_word}'")

                    original_field_found_idx = -1
                    for i_f, field_f in enumerate(section_fields):
                        if field_f['Field Name'] == current_field_name and field_f['Section'] == section_name and not field_f['Field Description']:
                            original_field_found_idx = i_f; break
                    if original_field_found_idx != -1:
                        print(f"DEBUG:   Removing previously added short field '{current_field_name}'.")
                        section_fields.pop(original_field_found_idx)

                    current_field_name = combined_name_cand
                    current_description_parts = []
                    description_segment = rest_of_line

                    earliest_keyword_index_cc = -1; keyword_in_cc = None
                    for keyword_cc_loopvar in other_column_keywords_strict:
                        match_cc = re.search(r'\s+\b' + re.escape(keyword_cc_loopvar) + r'\b', description_segment, re.IGNORECASE)
                        if match_cc:
                            idx_cc = match_cc.start()
                            if earliest_keyword_index_cc == -1 or idx_cc < earliest_keyword_index_cc:
                                earliest_keyword_index_cc = idx_cc; keyword_in_cc = keyword_cc_loopvar
                    if keyword_in_cc:
                        description_segment = description_segment[:earliest_keyword_index_cc].strip()
                    if description_segment: current_description_parts.append(" ".join(description_segment.split()))
                    if keyword_in_cc:
                        _finalize_and_add_field(current_field_name, current_description_parts, section_name, section_fields, line_num, f"CamelCaseKeywordFinalize for {current_field_name}")
                        current_field_name = None; current_description_parts = []
                    continue

            # --- Check 2: Strong Signal (lowercase field, uppercase description on same line) ---
            is_strong_signal_line = False
            if first_word.islower() and bool(re.match(field_name_regex, first_word)) and \
               first_word.upper() not in common_desc_start_words and \
               rest_of_line and rest_of_line[0].isupper() and \
               (len(rest_of_line.split()) > 0 and rest_of_line.split()[0].upper() not in other_column_keywords_strict):
                 is_strong_signal_line = True

            if is_strong_signal_line:
                print(f"DEBUG: StrongSignal: Field='{first_word}', Desc='{rest_of_line}'")
                if current_field_name: _finalize_and_add_field(current_field_name, current_description_parts, section_name, section_fields, line_num, "StrongSignalNew")

                current_field_name = first_word # Preserve case from strong signal
                current_description_parts = []
                desc_seg = rest_of_line; earliest_idx = -1; found_kw = None
                for kw in other_column_keywords_strict:
                    m = re.search(r'\s+\b' + re.escape(kw) + r'\b', desc_seg, re.IGNORECASE)
                    if m and (earliest_idx == -1 or m.start() < earliest_idx): earliest_idx, found_kw = m.start(), kw
                if found_kw: desc_seg = desc_seg[:earliest_idx].strip()
                if desc_seg: current_description_parts.append(" ".join(desc_seg.split()))
                if found_kw:
                    _finalize_and_add_field(current_field_name, current_description_parts, section_name, section_fields, line_num, "StrongSignalSplit")
                    current_field_name = None; current_description_parts = []
                continue

            # --- Check 3: General New Field (Scenario A/B) ---
            if is_likely_field_name_start_original and rol_starts_with_col_keyword:
                processed_field_name = first_word
                print(f"DEBUG: Scenario B0: New field '{processed_field_name}' with no description")
                if current_field_name:
                    _finalize_and_add_field(current_field_name, current_description_parts, section_name, section_fields, line_num, "NewFieldBeforeColumn")
                _finalize_and_add_field(processed_field_name, [], section_name, section_fields, line_num, "NewFieldBeforeColumnAdd")
                current_field_name = None
                current_description_parts = []
                continue

            if is_likely_field_name_start_original and not rol_starts_with_col_keyword:
                # Field Name Casing: store lowercase if not an acronym or known mixed case.
                processed_field_name = first_word
                if first_word.upper() not in known_acronyms_or_case_sensitive_names and not (any(c.islower() for c in first_word) and any(c.isupper() for c in first_word)):
                    if not first_word.isupper(): # Don't lowercase if all UPPER (likely acronym)
                        processed_field_name = first_word.lower()

                if len(first_word) <=2 and not rest_of_line and current_field_name: # Scenario A
                     print(f"DEBUG: Scenario A: Short cont for '{current_field_name}': '{first_word}'")
                     current_description_parts.append(" ".join(stripped_line.split()))
                else: # Scenario B
                    print(f"DEBUG: Scenario B: New field '{processed_field_name}' (from '{first_word}'), ROL: '{rest_of_line[:30]}'")
                    if current_field_name: _finalize_and_add_field(current_field_name, current_description_parts, section_name, section_fields, line_num, "NewField")
                    current_field_name = processed_field_name
                    current_description_parts = []
                    desc_seg = rest_of_line; earliest_idx = -1; found_kw = None
                    for kw in other_column_keywords_strict:
                        m = re.search(r'\s+\b' + re.escape(kw) + r'\b', desc_seg, re.IGNORECASE)
                        if m and (earliest_idx == -1 or m.start() < earliest_idx): earliest_idx, found_kw = m.start(), kw
                    if found_kw: desc_seg = desc_seg[:earliest_idx].strip()
                    if desc_seg: current_description_parts.append(" ".join(desc_seg.split()))
                    if found_kw:
                        _finalize_and_add_field(current_field_name, current_description_parts, section_name, section_fields, line_num, "ROLSplit")
                        current_field_name = None; current_description_parts = []
                continue

            # --- Check 4: Scenario C (Main continuation/termination) ---
            if current_field_name:
                print(f"DEBUG: Scenario C: Cont/Term for '{current_field_name}', Line: '{stripped_line}'")
                if stripped_line.upper().startswith(tuple(other_column_keywords_strict)):
                    print(f"DEBUG:   StrictKeyword Start: Finalizing '{current_field_name}'")
                    _finalize_and_add_field(current_field_name, current_description_parts, section_name, section_fields, line_num, "StrictKeywordStart")
                    current_field_name = None; current_description_parts = []
                elif is_likely_column_data(stripped_line, other_column_keywords_strict, other_potentially_column_start_keywords):
                    print(f"DEBUG:   Column Data Line: Finalizing '{current_field_name}'")
                    _finalize_and_add_field(current_field_name, current_description_parts, section_name, section_fields, line_num, "ColumnDataFinalize")
                    current_field_name = None; current_description_parts = []
                else:
                    # Restore NewSentenceHeuristic
                    if current_description_parts and current_description_parts[-1].strip().endswith(".") and \
                       stripped_line and stripped_line[0].isupper() and \
                       first_word.upper() not in common_desc_start_words and \
                       not (is_likely_field_name_start_original and not rol_starts_with_col_keyword) and \
                       first_word.isalpha():
                        if len(stripped_line.split()) > 2 :
                            print(f"DEBUG:   NewSentenceHeuristic: Finalizing '{current_field_name}' before appending '{stripped_line[:30]}...'")
                            _finalize_and_add_field(current_field_name, current_description_parts, section_name, section_fields, line_num, "NewSentenceHeuristic")
                            current_field_name = None ; current_description_parts = []

                    if current_field_name: # If not finalized by heuristic
                        desc_seg = stripped_line; earliest_idx = -1; found_kw = None
                        for kw_c in other_column_keywords_strict:
                            m = re.search(r'\s+\b' + re.escape(kw_c) + r'\b', desc_seg, re.IGNORECASE)
                            if m and (earliest_idx == -1 or m.start() < earliest_idx): earliest_idx, found_kw = m.start(), kw_c
                        if found_kw: desc_seg = desc_seg[:earliest_idx].strip()
                        if desc_seg: current_description_parts.append(" ".join(desc_seg.split()))
                        print(f"DEBUG:   Appended to '{current_field_name}': '{desc_seg[:50]}...' (orig: '{stripped_line[:50]}...')")
                        if found_kw:
                            print(f"DEBUG:   MidLineKeyword Finalizing '{current_field_name}'")
                            _finalize_and_add_field(current_field_name, current_description_parts, section_name, section_fields, line_num, "MidLineSplitFinalize")
                            current_field_name = None; current_description_parts = []

            # --- Check 5: Orphaned line (Scenario D) ---
            if not current_field_name:
                 print(f"DEBUG: Scenario D: Orphaned line: '{stripped_line}'")

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
