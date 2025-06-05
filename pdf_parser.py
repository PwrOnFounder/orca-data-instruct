import re
import csv # Import the csv module
import argparse # Import the argparse module
import sys # Import sys for sys.exit()
import logging
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

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def _finalize_and_add_field(field_name, description_parts, section_name, section_fields_list, line_num_debug, context_debug_msg):
    """Helper to finalize a field and add it to the section_fields_list."""
    description = " ".join(description_parts).strip()
    
    # Normalize field name
    normalized_field_name = _normalize_field_name(field_name)
    
    # Check for duplicates more robustly
    if not any(d['Field Name'] == normalized_field_name and d['Section'] == section_name for d in section_fields_list):
        field_to_add = {
            'Section': section_name,
            'Field Name': normalized_field_name,
            'Field Description': description
        }
        logger.debug(f"Line ~{line_num_debug} ({context_debug_msg}): Adding field: {field_to_add}")
        section_fields_list.append(field_to_add)
    else:
        logger.debug(f"Line ~{line_num_debug} ({context_debug_msg}): Field '{normalized_field_name}' already exists. Skipping.")

def _normalize_field_name(field_name):
    """Normalize field names for consistency."""
    if not field_name:
        return ""
    
    # Remove trailing digits and parenthetical content
    normalized = re.sub(r'\(\w+\)', '', field_name)  # Remove (Primary Issuer) etc.
    normalized = re.sub(r'\d+$', '', normalized)     # Remove trailing digits
    normalized = normalized.rstrip('_').strip()      # Remove trailing underscores and whitespace
    
    # Handle camelCase to UPPER_CASE conversion for consistency
    if any(c.islower() for c in normalized) and any(c.isupper() for c in normalized):
        # Convert camelCase to UPPER_CASE
        normalized = re.sub(r'([a-z])([A-Z])', r'\1_\2', normalized).upper()
    
    return normalized

def _is_valid_field_name(field_name):
    """Enhanced field name validation."""
    if not field_name or len(field_name) < 3:  # Changed from 2 to 3 to be more strict
        return False
    
    # Check for valid field name patterns
    patterns = [
        r'^[A-Z][A-Z0-9_]*$',          # Traditional uppercase (minimum 3 chars)
        r'^[a-z][a-zA-Z0-9_]{2,}$',    # camelCase starting with lowercase (minimum 3 chars total)
        r'^[A-Z][a-z]+[A-Z][a-zA-Z0-9_]*$'  # Mixed case (minimum 3 chars)
    ]
    
    return any(re.match(pattern, field_name) for pattern in patterns)

def _clean_description(description_parts):
    """Clean and normalize description text."""
    if not description_parts:
        return ""
    
    # Join and clean up the description
    description = " ".join(description_parts)
    
    # Remove excessive whitespace
    description = re.sub(r'\s+', ' ', description).strip()
    
    # Remove common formatting artifacts
    description = re.sub(r'\s*\.\s*$', '.', description)  # Fix spacing before period
    description = re.sub(r'\s*,\s*', ', ', description)   # Fix spacing around commas
    
    return description

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
        logger.info(f"Successfully extracted {len(full_text)} characters from PDF")
        return full_text
    except FileNotFoundError:
        logger.error(f"Input PDF file not found: {pdf_path}")
        return None
    except PDFSyntaxError as e:
        logger.error(f"PDF syntax error in '{pdf_path}': {e}")
        return None
    except PSError as e:
        logger.error(f"PostScript error in '{pdf_path}': {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error processing PDF '{pdf_path}': {e}")
        return None

def parse_fields_from_text(text):
    """Enhanced field parsing with improved accuracy."""
    logger.info(f"Starting field parsing. Text length: {len(text) if text else 'None'}")
    if not text:
        logger.warning("Text is empty or None. Returning empty list.")
        return []
    
    all_parsed_fields = []

    # Enhanced keyword sets for better detection
    other_column_keywords_strict = {
        "ALPHANUMERIC", "NUMERIC", "DATE", "BOOLEAN", "EDGAR", "XBRL", "TEXT",
        "VARCHAR", "INTEGER", "DECIMAL", "CHAR", "TIMESTAMP"
    }
    other_potentially_column_start_keywords = {"YES", "NO", "*", "NULL"}

    # More flexible field name patterns
    field_name_patterns = [
        r"^[A-Z0-9_]{3,}$",              # Traditional uppercase
        r"^[a-z][a-zA-Z0-9_]{2,}$",      # camelCase starting with lowercase
        r"^[A-Z][a-z]+[A-Z][a-zA-Z0-9_]*$"  # Mixed case
    ]
    
    # Keep known acronyms or specific case-sensitive names
    known_acronyms_or_case_sensitive_names = {
        "CIK", "XBRL", "EDGAR", "ABS", "CRS", "DEFRS", "MFRR", "SEC", "USD", "API"
    }

    common_desc_start_words = {
        "THE", "A", "AN", "THIS", "IF", "FOR", "AND", "OF", "IN", "TO", "IS", "ARE", "AS", "FIELD",
        "MAX", "SIZE", "MAY", "BE", "NULL", "KEY", "SOURCE", "FORMAT", "DATA", "TYPE",
        "LENGTH", "COMMENTS", "NAME", "DESCRIPTION", "FIELDNAME", "FIELDTYPE",
        "NOTE", "CONTINUATION", "CODE", "VALUE", "INDICATES", "PROVIDES", "CONTAINS"
    }

    # Enhanced section detection pattern
    section_start_pattern = re.compile(
        r"Figure\s+\d+\.\s*Fields\s+in\s+the\s+([A-Z0-9_]+(?:\s+[A-Z0-9_]+)*)\s+data\s+(?:file|set)",
        re.IGNORECASE | re.DOTALL
    )
    any_figure_line_pattern = re.compile(r"^\s*Figure\s+\d+\.", re.MULTILINE | re.IGNORECASE)

    all_section_start_matches = list(section_start_pattern.finditer(text))
    logger.info(f"Found {len(all_section_start_matches)} section start matches")

    if not all_section_start_matches:
        logger.warning("No section start patterns found")
        return all_parsed_fields

    for i, current_section_start_match in enumerate(all_section_start_matches):
        section_name_raw = current_section_start_match.group(1)
        section_name = ' '.join(section_name_raw.split()).strip()
        current_section_body_start_offset = current_section_start_match.end()
        
        # Determine section end
        if i + 1 < len(all_section_start_matches):
            next_section_start_offset = all_section_start_matches[i+1].start()
            temp_next_figure_match = any_figure_line_pattern.search(text, current_section_body_start_offset, next_section_start_offset)
            current_section_text_end = temp_next_figure_match.start() if temp_next_figure_match else next_section_start_offset
        else:
            next_figure_line_match = any_figure_line_pattern.search(text, current_section_body_start_offset)
            current_section_text_end = next_figure_line_match.start() if next_figure_line_match else len(text)

        section_text_content = text[current_section_body_start_offset:current_section_text_end]
        
        # Enhanced header detection
        header_patterns = [
            re.compile(r"Field\s+Name\s+Field\s+Description", re.IGNORECASE | re.DOTALL),
            re.compile(r"Field\s+Name\s+.*?Description", re.IGNORECASE | re.DOTALL),
            re.compile(r"Name\s+Description", re.IGNORECASE | re.DOTALL)
        ]
        
        header_match = None
        for pattern in header_patterns:
            header_match = pattern.search(section_text_content)
            if header_match:
                break

        logger.info(f"Processing Section: '{section_name}'. Content length: {len(section_text_content)}. Header found: {'Yes' if header_match else 'No'}")

        if header_match:
            table_text_start_index = header_match.end()
            table_text = section_text_content[table_text_start_index:]
        else:
            table_text = section_text_content

        lines = table_text.split('\n')
        logger.debug(f"Section '{section_name}': processing {len(lines)} lines")
        
        current_field_name = None
        current_description_parts = []
        section_fields = []
        
        def is_likely_column_data(line_text, strict_kws, potential_kws):
            line_upper = line_text.upper()
            if line_upper in strict_kws or line_upper in potential_kws or line_text.isdigit(): 
                return True
            tokens = line_text.split()
            if not tokens: 
                return False
            return all(t.isdigit() or t.upper() in strict_kws or t.upper() in potential_kws for t in tokens)

        # Process lines with improved logic
        for line_num, line in enumerate(lines):
            stripped_line = line.strip()
            if not stripped_line: 
                continue

            # Skip obvious non-data lines
            if any_figure_line_pattern.match(stripped_line) or '----' in stripped_line or '...' in stripped_line:
                continue

            parts = stripped_line.split(maxsplit=1)
            first_word = parts[0] if parts else ""
            rest_of_line = parts[1].strip() if len(parts) > 1 else ""
            
            logger.debug(f"Line {line_num}: '{stripped_line[:50]}...' | FW: '{first_word}' | ROL: '{rest_of_line[:30]}...'")

            # Enhanced field name detection
            is_likely_field_name = any(re.match(pattern, first_word) for pattern in field_name_patterns) and \
                                 first_word.upper() not in common_desc_start_words and \
                                 first_word.upper() not in other_column_keywords_strict and \
                                 not first_word.isdigit()

            rol_starts_with_col_keyword = any(rest_of_line.upper().startswith(kw) for kw in other_column_keywords_strict) if rest_of_line else False

            # Handle camelCase field continuation (e.g., "negated" + "Terse" = "negatedTerse")
            if current_field_name and not current_description_parts and \
               first_word and current_field_name.islower() and first_word[0].isupper() and \
               _is_valid_field_name(first_word) and first_word.upper() not in common_desc_start_words:
                
                combined_name = current_field_name + first_word
                if _is_valid_field_name(combined_name):
                    logger.debug(f"CamelCase combination: '{current_field_name}' + '{first_word}' = '{combined_name}'")
                    
                    # Remove previous short field if it was added
                    section_fields = [f for f in section_fields if not (f['Field Name'] == current_field_name and f['Section'] == section_name and not f['Field Description'])]
                    
                    current_field_name = combined_name
                    current_description_parts = []
                    
                    # Process rest of line as description
                    if rest_of_line:
                        desc_text = _extract_description_before_keywords(rest_of_line, other_column_keywords_strict)
                        if desc_text:
                            current_description_parts.append(desc_text)
                    continue

            # Strong signal detection (lowercase field + uppercase description)
            if first_word.islower() and _is_valid_field_name(first_word) and \
               rest_of_line and rest_of_line[0].isupper() and \
               first_word.upper() not in common_desc_start_words:
                
                logger.debug(f"Strong signal detected: Field='{first_word}', Desc='{rest_of_line[:30]}...'")
                
                if current_field_name:
                    _finalize_and_add_field(current_field_name, current_description_parts, section_name, section_fields, line_num, "StrongSignalNew")

                current_field_name = first_word
                current_description_parts = []
                
                desc_text = _extract_description_before_keywords(rest_of_line, other_column_keywords_strict)
                if desc_text:
                    current_description_parts.append(desc_text)
                continue

            # Regular field name detection
            if is_likely_field_name:
                if rol_starts_with_col_keyword:
                    # Field with no description
                    logger.debug(f"Field with no description: '{first_word}'")
                    if current_field_name:
                        _finalize_and_add_field(current_field_name, current_description_parts, section_name, section_fields, line_num, "NewFieldNoDesc")
                    _finalize_and_add_field(first_word, [], section_name, section_fields, line_num, "FieldNoDesc")
                    current_field_name = None
                    current_description_parts = []
                else:
                    # New field with potential description
                    logger.debug(f"New field detected: '{first_word}'")
                    if current_field_name:
                        _finalize_and_add_field(current_field_name, current_description_parts, section_name, section_fields, line_num, "NewField")
                    
                    current_field_name = first_word
                    current_description_parts = []
                    
                    if rest_of_line:
                        desc_text = _extract_description_before_keywords(rest_of_line, other_column_keywords_strict)
                        if desc_text:
                            current_description_parts.append(desc_text)
                continue

            # Handle continuation lines
            if current_field_name:
                if stripped_line.upper().startswith(tuple(other_column_keywords_strict)) or \
                   is_likely_column_data(stripped_line, other_column_keywords_strict, other_potentially_column_start_keywords):
                    # End of current field
                    logger.debug(f"End of field '{current_field_name}' due to column data")
                    _finalize_and_add_field(current_field_name, current_description_parts, section_name, section_fields, line_num, "ColumnDataEnd")
                    current_field_name = None
                    current_description_parts = []
                else:
                    # Continuation of description
                    desc_text = _extract_description_before_keywords(stripped_line, other_column_keywords_strict)
                    if desc_text:
                        current_description_parts.append(desc_text)
                        logger.debug(f"Added to '{current_field_name}': '{desc_text[:30]}...'")

        # Finalize any remaining field
        if current_field_name:
            _finalize_and_add_field(current_field_name, current_description_parts, section_name, section_fields, line_num, "EndOfSection")

        all_parsed_fields.extend(section_fields)
        logger.info(f"Section '{section_name}' processed: {len(section_fields)} fields found")

    logger.info(f"Total fields parsed: {len(all_parsed_fields)}")
    return all_parsed_fields

def _extract_description_before_keywords(text, keywords):
    """Extract description text before any format keywords."""
    if not text:
        return ""
    
    earliest_idx = len(text)
    for keyword in keywords:
        # Look for keyword boundaries
        pattern = r'\s+\b' + re.escape(keyword) + r'\b'
        match = re.search(pattern, text, re.IGNORECASE)
        if match and match.start() < earliest_idx:
            earliest_idx = match.start()
    
    result = text[:earliest_idx].strip()
    return " ".join(result.split()) if result else ""

def write_to_csv(parsed_data, csv_filepath):
    """Enhanced CSV writing with validation."""
    if not parsed_data:
        logger.warning("No data to write to CSV.")
        return True
    
    # Validate data structure
    required_fields = {'Section', 'Field Name', 'Field Description'}
    for i, record in enumerate(parsed_data):
        if not isinstance(record, dict):
            logger.error(f"Record {i} is not a dictionary: {type(record)}")
            return False
        if not required_fields.issubset(record.keys()):
            logger.error(f"Record {i} missing required fields. Has: {record.keys()}, Needs: {required_fields}")
            return False
    
    fieldnames = ['Section', 'Field Name', 'Field Description']
    try:
        with open(csv_filepath, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(parsed_data)
        logger.info(f"Successfully wrote {len(parsed_data)} records to {csv_filepath}")
        return True
    except IOError as e:
        logger.error(f"Could not write to CSV file '{csv_filepath}': {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error writing to CSV '{csv_filepath}': {e}")
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
