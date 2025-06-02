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
from pdfminer.psparser import PSError # Corrected import for PSError

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
    except (PDFSyntaxError, PSError) as e:
        print(f"Error processing PDF file '{pdf_path}': It might be corrupted or not a valid PDF. Details: {e}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred while processing PDF '{pdf_path}': {e}")
        return None

def parse_fields_from_text(text):
    """
    Parses the extracted text to find sections (based on "Figure" titles),
    and within each section, extracts field names and their descriptions from a table-like structure.

    The logic assumes that field names are typically uppercase, alphanumeric with underscores,
    and are followed by their descriptions. Descriptions can span multiple lines.
    The end of a description is inferred when a line starts with a data type keyword (e.g., "NUMERIC"),
    common table values (e.g., "YES", "NO"), or another potential field name.
    """
    all_parsed_fields = []
    
    # Regex to identify section titles.
    # It looks for patterns like "Figure X. ... Fields in the SECTION_NAME data file".
    # - `Figure \d+\.`: Matches "Figure" followed by digits and a period (e.g., "Figure 1.").
    # - `.*?`: Non-greedily matches any characters (including newlines due to re.DOTALL)
    #           between the "Figure X." part and "Fields in the". This handles variability in text.
    # - `Fields in the\s+`: Matches "Fields in the " (with trailing space).
    # - `(.+?)\s+data file`: Non-greedily captures the section name (this is group 1).
    #                       It expects " data file" to follow the section name.
    # `re.IGNORECASE` makes the match case-insensitive.
    # `re.DOTALL` allows `.` to match newline characters.
    section_pattern = re.compile(r"Figure \d+\..*?Fields in the\s+(.+?)\s+data file", re.IGNORECASE | re.DOTALL)
    all_figure_matches = list(section_pattern.finditer(text))

    if not all_figure_matches:
        # If no section titles matching the pattern are found, no further parsing is possible.
        # Debug print: print("DEBUG: No 'Figure X...' patterns found.")
        return all_parsed_fields

    for i, current_figure_match in enumerate(all_figure_matches):
        section_name_raw = current_figure_match.group(1)
        # Clean up the extracted section name (remove extra internal and leading/trailing whitespace).
        section_name = ' '.join(section_name_raw.split()).strip()
        # Debug print: print(f"\n--- Processing Section: '{section_name}' ---")

        # Determine the text block for the current section.
        # It starts after the matched section title and ends before the next section title (or end of text).
        current_section_text_start = current_figure_match.end()
        current_section_text_end = all_figure_matches[i+1].start() if i + 1 < len(all_figure_matches) else len(text)
        section_text = text[current_section_text_start:current_section_text_end]

        # Regex to find the table header within the section text.
        # - `Field\s+Name\s+Field\s+Description`: Matches the mandatory start of the header.
        # - `(?: ... )?`: This is an optional non-capturing group for different sets of subsequent column names.
        #   - `\s+Format\s+Max\s+Size\s+May\s+be\s+NULL\s+Key`: One variation of columns.
        #   - `\s+Data\s+Type\s+Length\s+Nullable\s+Comments`: Another variation.
        # This pattern helps locate where the actual field definitions begin.
        header_pattern = re.compile(
            r"Field\s+Name\s+Field\s+Description(?:\s+Format\s+Max\s+Size\s+May\s+be\s+NULL\s+Key|\s+Data\s+Type\s+Length\s+Nullable\s+Comments)?", 
            re.IGNORECASE | re.DOTALL 
        )
        header_match = header_pattern.search(section_text)
        if not header_match:
            # If no header is found in this section, skip to the next section.
            # Debug print: print(f"DEBUG: Header not found in section '{section_name}'.")
            continue
        
        # The actual table data (field names and descriptions) starts after the header.
        table_text_start_index = header_match.end()
        table_text = section_text[table_text_start_index:]
        lines = table_text.split('\n') # Process the table line by line.
        
        current_field_name = None          # Holds the name of the field currently being processed.
        current_description_parts = []     # Accumulates lines that form the description of the current field.
        section_fields = []                # Stores all fields found in the current section.
        
        # Regex for validating a potential field name.
        # - `^`: Start of the string (applied to the first word of a line).
        # - `[A-Z0-9_]{3,}`: Requires at least 3 uppercase alphanumeric characters or underscores.
        # - `$`: End of the string.
        # This regex is strict. Depending on the PDF's actual field naming conventions (e.g., shorter names,
        # case-insensitivity, other special characters), it might need adjustment.
        field_name_regex = r"^[A-Z0-9_]{3,}$" 
        
        # Keywords that usually indicate data type or format information.
        # If a line's first word matches one of these (case-insensitively), it's likely not a new field name
        # or continuation of a description, but the start of columns like "Format", "Data Type", etc.
        format_keywords = {"ALPHANUMERIC", "DATE", "NUMERIC", "CHARACTER", "VARCHAR", 
                           "INTEGER", "TEXT", "BOOLEAN", "DECIMAL"}
                           
        # Other keywords or values that often appear in columns after the description,
        # such as "Nullable" (YES/NO) or "Key" (*), or numeric values for "Max Size".
        # These also help determine the end of a field's description.
        # Matching is case-insensitive for "YES", "NO", "*".
        other_column_keywords = {"YES", "NO", "*"} 

        for line_num, line in enumerate(lines):
            stripped_line = line.strip()
            if not stripped_line: # Skip empty lines.
                continue

            # Extract the first word and the rest of the line.
            # `first_word` is a candidate for a field name or a keyword.
            # `rest_of_line` is potentially the start of a description.
            parts = stripped_line.split(maxsplit=1)
            first_word = parts[0] if parts else ""
            rest_of_line = parts[1].strip() if len(parts) > 1 else ""

            # Determine the nature of the `first_word`.
            # - `is_potential_field_name_token`: True if `first_word` matches `field_name_regex`.
            # - `is_format_keyword_token`: True if `first_word` (uppercase) is in `format_keywords`.
            # - `is_other_data_token`: True if `first_word` (uppercase) is in `other_column_keywords` 
            #                          or if `first_word` is a digit (e.g., for a "Max Size" column).
            is_potential_field_name_token = bool(re.match(field_name_regex, first_word))
            is_format_keyword_token = first_word.upper() in format_keywords
            is_other_data_token = (first_word.upper() in other_column_keywords) or first_word.isdigit()

            # ----- Core Parsing Logic: Deciding if a line starts a new field, ends a field, or continues a description -----

            # Scenario 1: A new field name is identified.
            # This occurs if the `first_word` looks like a field name (matches `field_name_regex`) 
            # AND it's NOT a format keyword AND it's NOT other column data (like "YES", "NO", or a number).
            # This aims to prevent misinterpreting parts of a description as new field names.
            if is_potential_field_name_token and not is_format_keyword_token and not is_other_data_token:
                # If there's an active field being processed, finalize and save it before starting a new one.
                if current_field_name and current_description_parts:
                    description = " ".join(current_description_parts).strip()
                    if description: # Only add if the collected description is not empty.
                        section_fields.append({
                            'Section': section_name,
                            'Field Name': current_field_name,
                            'Field Description': description
                        })
                
                # Start the new field with `first_word` as its name.
                current_field_name = first_word
                # The `rest_of_line` is considered the beginning of its description.
                current_description_parts = [rest_of_line] if rest_of_line else []
            
            # Scenario 2: A format keyword or other column data is detected on the line.
            # This signals the end of the current field's description, as these tokens
            # are assumed to belong to subsequent columns in the table (e.g., "Format", "Nullable").
            # This logic only applies if a field is currently active (`current_field_name` is not None).
            elif (is_format_keyword_token or is_other_data_token) and current_field_name:
                # Finalize the current field being processed.
                if current_description_parts: # If any description parts were collected...
                    description = " ".join(current_description_parts).strip()
                    if description: # ...and the resulting description is not empty.
                        section_fields.append({
                            'Section': section_name,
                            'Field Name': current_field_name,
                            'Field Description': description
                        })
                # If no description parts were collected (e.g., field name was on a line by itself,
                # followed immediately by a line with format info), add the field with an empty description,
                # but only if it hasn't been added already (e.g. from a previous iteration).
                elif not any(d['Field Name'] == current_field_name and d['Section'] == section_name for d in section_fields):
                     section_fields.append({
                            'Section': section_name,
                            'Field Name': current_field_name,
                            'Field Description': ""  # Field exists but has no description text.
                        })

                # Reset current field tracking, as this line's content is not part of any field's description.
                # It belongs to other columns of the table.
                current_field_name = None
                current_description_parts = []
            
            # Scenario 3: Continuation of the current field's description.
            # This occurs if the line does not start a new field name (Scenario 1) and is not a
            # format/other data token line (Scenario 2), AND a field is currently active.
            else:
                if current_field_name:
                    # Append the whole stripped line as part of the description.
                    # This is important for multi-line descriptions. Using `stripped_line` (rather than `rest_of_line`)
                    # ensures that if a description line happens to start with a word that could be a field name
                    # but wasn't caught by Scenario 1 (e.g. too short, or matches a format keyword but contextually is description),
                    # it's still appended correctly.
                    current_description_parts.append(stripped_line)
        
        # After processing all lines in a section, finalize any pending field.
        # This is crucial for capturing the very last field in the table for the current section.
        if current_field_name: 
            description = " ".join(current_description_parts).strip()
            if description: # If there's a non-empty description.
                section_fields.append({
                    'Section': section_name,
                    'Field Name': current_field_name,
                    'Field Description': description
                })
            # If description is empty, but the field name itself hasn't been added yet
            # (e.g., it was the last field and had no description text, or its description was just whitespace),
            # add it with an empty description.
            elif not any(d['Field Name'] == current_field_name and d['Section'] == section_name for d in section_fields):
                 section_fields.append({
                    'Section': section_name,
                    'Field Name': current_field_name,
                    'Field Description': ""
                })

        all_parsed_fields.extend(section_fields) # Add all fields found in this section to the global list.
            
    return all_parsed_fields

def write_to_csv(parsed_data, csv_filepath):
    """
    Writes the parsed data to a CSV file.

    Args:
        parsed_data (list): A list of dictionaries, where each dictionary contains
                            {'Section': section_name, 'Field Name': field_name, 
                             'Field Description': collected_description}.
        csv_filepath (str): The path for the output CSV file.
    Returns:
        bool: True if writing was successful, False otherwise.
    """
    if not parsed_data: # Handle empty data case
        print("No data to write to CSV.")
        return True # Technically not a write error, but nothing to write.

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

# Example usage:
# python pdf_parser.py --pdf_file "Form_D.SEC.Data.Guide.pdf" --csv_file "form_d_fields.csv"
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

    # For debugging the full text extraction:
    # with open("debug_full_text.txt", "w", encoding="utf-8") as f:
    #     f.write(full_text_content)

    print("\nParsing fields from extracted text...")
    # parse_fields_from_text does not have error handling specified for this task,
    # but if it did, we'd check its return value here.
    structured_data = parse_fields_from_text(full_text_content)
    
    if structured_data:
        if write_to_csv(structured_data, args.csv_file):
            print(f"\nSuccessfully parsed {len(structured_data)} fields and wrote them to {args.csv_file}")
        else:
            print(f"\nFailed to write parsed data to {args.csv_file}. Exiting.")
            sys.exit(1)
    elif not full_text_content: # If full_text_content was empty (but not None)
        print("\nNo text extracted from PDF (PDF might be empty or image-based without OCR). CSV not created.")
    else: # Text extracted, but no structured data found by parse_fields_from_text
        print("\nText extracted, but no structured data found according to parsing rules. CSV file not created.")

    # Example of a more detailed check for specific fields (can be useful for focused debugging)
    # print("\n--- Detailed Check for Specific Fields ---")
    # specific_fields_to_check = {
    #     "FORMDSUBMISSION": ["ACCESSIONNUMBER", "FILE_NUM", "FILING_DATE", "SIC_CODE", "SUBMISSIONTYPE"],
    #     "ISSUERS": ["CIK", "ENTITYNAME", "CITY", "STATEORCOUNTRY", "IS_PRIMARYISSUER_FLAG"],
    # }
    # for section_to_find, field_names_to_find in specific_fields_to_check.items():
    #     print(f"\nChecking Section: '{section_to_find}'")
    #     for field_name_to_find in field_names_to_find:
    #         found_item = False
    #         for item in structured_data: # Corrected variable name here
    #             if item['Section'] == section_to_find and item['Field Name'] == field_name_to_find:
    #                 print(f"  FOUND: Field='{item['Field Name']}', Desc='{item['Field Description'][:100]}...'")
    #                 found_item = True
    #                 break
    #         if not found_item:
    #             print(f"  NOT FOUND: Field='{field_name_to_find}'")
# Removed any trailing backticks.

