import re
import csv # Import the csv module
from io import StringIO
from pdfminer.converter import TextConverter
from pdfminer.layout import LAParams
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.pdfpage import PDFPage
from pdfminer.pdfparser import PDFParser

def extract_text_from_pdf(pdf_path):
    """
    Extracts text from the entire PDF file and removes form feed characters.
    """
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

def parse_fields_from_text(text):
    """
    Parses the extracted text to find sections and their field names and descriptions
    using the revised logic.
    """
    all_parsed_fields = []
    
    # Regex to find sections: "Figure X. ... Fields in the (SECTION_NAME) data file"
    section_pattern = re.compile(r"Figure \d+\..*?Fields in the\s+(.+?)\s+data file", re.IGNORECASE | re.DOTALL)
    all_figure_matches = list(section_pattern.finditer(text))

    if not all_figure_matches:
        # print("DEBUG: No 'Figure X...' patterns found.")
        return all_parsed_fields

    for i, current_figure_match in enumerate(all_figure_matches):
        section_name_raw = current_figure_match.group(1)
        section_name = ' '.join(section_name_raw.split()).strip()
        # print(f"\n--- Processing Section: '{section_name}' ---")

        current_section_text_start = current_figure_match.end()
        current_section_text_end = all_figure_matches[i+1].start() if i + 1 < len(all_figure_matches) else len(text)
        section_text = text[current_section_text_start:current_section_text_end]

        # Regex for the table header
        header_pattern = re.compile(
            r"Field\s+Name\s+Field\s+Description(?:\s+Format\s+Max\s+Size\s+May\s+be\s+NULL\s+Key|\s+Data\s+Type\s+Length\s+Nullable\s+Comments)?", 
            re.IGNORECASE | re.DOTALL 
        )
        header_match = header_pattern.search(section_text)
        if not header_match:
            # print(f"DEBUG: Header not found in section '{section_name}'.")
            continue
        
        table_text_start_index = header_match.end()
        table_text = section_text[table_text_start_index:]
        lines = table_text.split('\n')
        
        current_field_name = None
        current_description_parts = []
        section_fields = [] # Store fields for the current section
        
        # Field Name Regex: Uppercase, numbers, underscores, min 3 chars
        field_name_regex = r"^[A-Z0-9_]{3,}$" 
        # Format Keywords (case-insensitive matching)
        format_keywords = {"ALPHANUMERIC", "DATE", "NUMERIC", "CHARACTER", "VARCHAR", 
                           "INTEGER", "TEXT", "BOOLEAN", "DECIMAL"}
        # Other keywords that might appear in columns after description, signaling its end.
        # These are not field names and typically indicate the start of other columns.
        other_column_keywords = {"YES", "NO", "*"} 

        for line_num, line in enumerate(lines):
            stripped_line = line.strip()
            if not stripped_line:
                continue

            # Extract first word and rest of line
            parts = stripped_line.split(maxsplit=1)
            first_word = parts[0] if parts else ""
            rest_of_line = parts[1].strip() if len(parts) > 1 else ""

            # Determine token types
            # is_potential_field_name_token: Matches field name pattern.
            is_potential_field_name_token = bool(re.match(field_name_regex, first_word))
            # is_format_keyword_token: First word is a known format type.
            is_format_keyword_token = first_word.upper() in format_keywords
            # is_other_data_token: First word is "YES", "NO", "*", or a digit (likely Max Size).
            is_other_data_token = (first_word.upper() in other_column_keywords) or first_word.isdigit()


            # Logic for processing the line:
            # Scenario 1: New field name detected
            # A token is a new field name if it matches field_name_regex AND is NOT a format keyword AND is NOT other column data.
            if is_potential_field_name_token and not is_format_keyword_token and not is_other_data_token:
                # Finalize the previous field if one exists and has content
                if current_field_name and current_description_parts:
                    description = " ".join(current_description_parts).strip()
                    if description: # Only add if description is not empty
                        section_fields.append({
                            'Section': section_name,
                            'Field Name': current_field_name,
                            'Field Description': description
                        })
                
                # Start the new field
                current_field_name = first_word
                # Initialize description with the rest of the line, if any.
                current_description_parts = [rest_of_line] if rest_of_line else []
            
            # Scenario 2: Format keyword or other column data detected, signaling end of current field's description
            # This applies if a field is currently active (current_field_name is not None).
            elif (is_format_keyword_token or is_other_data_token) and current_field_name:
                # Finalize the current field as this line starts its format/other columns.
                if current_description_parts: # Check if there's any description collected
                    description = " ".join(current_description_parts).strip()
                    if description: # Only add if description is not empty
                        section_fields.append({
                            'Section': section_name,
                            'Field Name': current_field_name,
                            'Field Description': description
                        })
                elif not any(d['Field Name'] == current_field_name and d['Section'] == section_name for d in section_fields):
                    # If no description parts, but the field itself hasn't been added (e.g. field name was on a line alone before this column data line)
                    # Add it with an empty description.
                     section_fields.append({
                            'Section': section_name,
                            'Field Name': current_field_name,
                            'Field Description': "" 
                        })

                # Reset, as this line's content is not part of any description.
                current_field_name = None
                current_description_parts = []
            
            # Scenario 3: Continuation of the current field's description
            else:
                if current_field_name:
                    # Append the whole stripped line as part of the description.
                    # This handles cases where the description line itself might start with a word
                    # that could be misconstrued if only `rest_of_line` was used.
                    current_description_parts.append(stripped_line)
        
        # End of section: Finalize any pending field.
        if current_field_name: # Check if a field is active
            description = " ".join(current_description_parts).strip()
            if description: # Only add if description is not empty
                section_fields.append({
                    'Section': section_name,
                    'Field Name': current_field_name,
                    'Field Description': description
                })
            elif not any(d['Field Name'] == current_field_name and d['Section'] == section_name for d in section_fields):
                # If description is empty, but field was not added before (e.g. it was the last field and had no desc)
                 section_fields.append({
                    'Section': section_name,
                    'Field Name': current_field_name,
                    'Field Description': ""
                })

        all_parsed_fields.extend(section_fields)
            
    return all_parsed_fields

def write_to_csv(parsed_data, csv_filepath):
    """
    Writes the parsed data to a CSV file.

    Args:
        parsed_data (list): A list of dictionaries, where each dictionary contains
                            {'Section': section_name, 'Field Name': field_name, 
                             'Field Description': collected_description}.
        csv_filepath (str): The path for the output CSV file.
    """
    if not parsed_data: # Handle empty data case
        print("No data to write to CSV.")
        return

    fieldnames = ['Section', 'Field Name', 'Field Description']
    
    with open(csv_filepath, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(parsed_data)

if __name__ == "__main__":
    pdf_file_path = "Form_D.SEC.Data.Guide.pdf"
    print(f"Extracting text from '{pdf_file_path}'...")
    full_text_content = extract_text_from_pdf(pdf_file_path)

    # For debugging the full text extraction:
    # with open("debug_full_text.txt", "w", encoding="utf-8") as f:
    #     f.write(full_text_content)

    print("\nParsing fields from extracted text...")
    structured_data = parse_fields_from_text(full_text_content)
    
    if structured_data:
        output_csv_file = "form_d_fields.csv"
        write_to_csv(structured_data, output_csv_file)
        print(f"\nSuccessfully parsed {len(structured_data)} fields and wrote them to {output_csv_file}")
    else:
        print("\nNo data parsed. CSV file not created.")

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
```
