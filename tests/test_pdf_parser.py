import unittest
from unittest.mock import patch, mock_open, MagicMock, call # call is needed for checking multiple calls

# Assuming pdf_parser.py is in the parent directory or accessible via PYTHONPATH
# For this environment, it's in the root, so direct import should work if tests are run from root.
# If running with `python -m unittest discover tests`, this needs adjustment or __init__.py.
# For now, let's assume direct import path is fine or will be handled by test runner context.
# Add parent directory to sys.path to allow direct import of pdf_parser
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from pdf_parser import (
    extract_text_from_pdf,
    parse_fields_from_text,
    write_to_csv,
    PDFSyntaxError, # Make sure to import this if you're testing for it specifically
    PSError         # And this one too
)

class TestExtractTextFromPdf(unittest.TestCase):
    @patch('pdf_parser.PDFPage.create_pages')
    @patch('pdf_parser.PDFPageInterpreter')
    @patch('pdf_parser.TextConverter')
    @patch('pdf_parser.PDFResourceManager')
    @patch('pdf_parser.PDFDocument')
    @patch('pdf_parser.PDFParser')
    @patch('builtins.open', new_callable=mock_open)
    def test_extract_text_success(self, mock_file_open, MockPDFParser, MockPDFDocument,
                                  MockPDFResourceManager, MockTextConverter,
                                  MockPDFPageInterpreter, MockPDFPageCreatePages):
        # Configure mocks
        mock_pdf_parser_instance = MockPDFParser.return_value
        mock_pdf_document_instance = MockPDFDocument.return_value
        mock_text_converter_instance = MockTextConverter.return_value
        mock_pdf_page_interpreter_instance = MockPDFPageInterpreter.return_value
        
        # Mock create_pages to return a couple of mock pages
        mock_page1 = MagicMock()
        mock_page2 = MagicMock()
        MockPDFPageCreatePages.return_value = [mock_page1, mock_page2]

        # Mock the output of the text converter
        # The StringIO object used by TextConverter will have `getvalue()` called on it.
        # We need to ensure our mock_text_converter_instance (which is what `device` becomes)
        # is associated with a StringIO-like object whose `getvalue` we can control.
        # TextConverter's constructor is TextConverter(rsrcmgr, outfp, laparams)
        # So, when MockTextConverter is called, the second arg `outfp` is the StringIO.
        # We can capture this `outfp` or make `getvalue` a method of `mock_text_converter_instance`.
        
        # Simpler: The actual StringIO is internal to extract_text_from_pdf.
        # We need to make process_page write to it, or make `getvalue` available.
        # The `TextConverter`'s `outfp` (which is `output_string` in the function)
        # is what `getvalue()` is called on.
        # Let's make the `getvalue` method of the `output_string` (which is `mock_text_converter_instance.outfp`)
        # return our desired text.
        # However, TextConverter itself doesn't store the text directly. It writes to `outfp`.
        # The `device` (TextConverter instance) is passed to PDFPageInterpreter.
        # The `interpreter.process_page(page)` calls methods on `device` which writes to `device.outfp`.
        
        # Let's simulate that `output_string.getvalue()` returns the desired text.
        # The `device` is `mock_text_converter_instance`.
        # `extract_text_from_pdf` creates its own `StringIO()`.
        # The `TextConverter` is initialized with this `StringIO` instance.
        # We need to make `mock_text_converter_instance.outfp.getvalue()` return the text.
        # This is tricky because `outfp` is passed *into* TextConverter.
        
        # Alternative: We can mock the `StringIO` directly if we knew how it was used.
        # Instead, let's assume `process_page` populates it, and `getvalue()` gives "Text with\fform feed."
        # The easiest way is to patch the StringIO instance that is created within the function.
        
        # Let's refine the mocking of TextConverter.
        # When TextConverter is initialized, its second argument is `output_string` (a StringIO instance).
        # We can make `getvalue` a method of this `output_string` mock.
        
        # Mocking `StringIO` that is locally created in the function:
        mock_string_io_instance = MagicMock()
        mock_string_io_instance.getvalue.return_value = "Text with\fform feed."

        # Patching StringIO locally to the module where it's used.
        with patch('pdf_parser.StringIO', return_value=mock_string_io_instance):
            extracted_text = extract_text_from_pdf("dummy.pdf")

        self.assertEqual(extracted_text, "Text withform feed.") # \f should be removed
        mock_file_open.assert_called_once_with("dummy.pdf", 'rb')
        MockPDFParser.assert_called_once_with(mock_file_open.return_value)
        MockPDFDocument.assert_called_once_with(mock_pdf_parser_instance)
        MockPDFResourceManager.assert_called_once()
        # TextConverter is called with rsrcmgr_instance, the StringIO instance, and laparams
        MockTextConverter.assert_called_once() # Check it was called
        self.assertIsInstance(MockTextConverter.call_args[0][1], MagicMock) # Arg 2 is our StringIO mock

        MockPDFPageInterpreter.assert_called_once()
        MockPDFPageCreatePages.assert_called_once_with(mock_pdf_document_instance)
        
        # Check process_page was called for each page
        mock_pdf_page_interpreter_instance.process_page.assert_has_calls([
            call(mock_page1),
            call(mock_page2)
        ])
        mock_string_io_instance.getvalue.assert_called_once()


    @patch('builtins.open', side_effect=FileNotFoundError("File not found"))
    def test_extract_text_file_not_found(self, mock_file_open):
        # `extract_text_from_pdf` should catch FileNotFoundError, print, and return None
        with patch('builtins.print') as mock_print:
            result = extract_text_from_pdf("non_existent.pdf")
        self.assertIsNone(result)
        mock_print.assert_called_with("Error: Input PDF file not found: non_existent.pdf")
        mock_file_open.assert_called_once_with("non_existent.pdf", 'rb')

    @patch('pdf_parser.PDFParser', side_effect=PDFSyntaxError("Syntax error"))
    @patch('builtins.open', new_callable=mock_open)
    def test_extract_text_pdf_syntax_error(self, mock_file_open, MockPDFParser):
        # `extract_text_from_pdf` should catch PDFSyntaxError, print, and return None
        with patch('builtins.print') as mock_print:
            result = extract_text_from_pdf("bad_syntax.pdf")
        self.assertIsNone(result)
        mock_print.assert_called_with("Error processing PDF file 'bad_syntax.pdf': It might be corrupted or not a valid PDF. Details: Syntax error")
        mock_file_open.assert_called_once_with("bad_syntax.pdf", 'rb')
        MockPDFParser.assert_called_once_with(mock_file_open.return_value)

    @patch('pdf_parser.PDFPage.create_pages', side_effect=PSError("PS error"))
    @patch('pdf_parser.PDFPageInterpreter') # These still need to be mocked
    @patch('pdf_parser.TextConverter')
    @patch('pdf_parser.PDFResourceManager')
    @patch('pdf_parser.PDFDocument')
    @patch('pdf_parser.PDFParser')
    @patch('builtins.open', new_callable=mock_open)
    def test_extract_text_ps_error(self, mock_file_open, MockPDFParser, MockPDFDocument,
                                   MockPDFResourceManager, MockTextConverter,
                                   MockPDFPageInterpreter, MockPDFPageCreatePages):
        # `extract_text_from_pdf` should catch PSError, print, and return None
        with patch('builtins.print') as mock_print:
            result = extract_text_from_pdf("ps_error.pdf")
        self.assertIsNone(result)
        mock_print.assert_called_with("Error processing PDF file 'ps_error.pdf': It might be corrupted or not a valid PDF. Details: PS error")
        mock_file_open.assert_called_once_with("ps_error.pdf", 'rb')
        # Ensure other mocks are called up to the point of failure
        MockPDFParser.assert_called_once()
        MockPDFDocument.assert_called_once()
        MockPDFResourceManager.assert_called_once()
        MockTextConverter.assert_called_once()
        MockPDFPageInterpreter.assert_called_once()
        MockPDFPageCreatePages.assert_called_once()
        
    @patch('pdf_parser.PDFParser', side_effect=Exception("Generic error")) # Test a generic exception
    @patch('builtins.open', new_callable=mock_open)
    def test_extract_text_generic_error(self, mock_file_open, MockPDFParser):
        with patch('builtins.print') as mock_print:
            result = extract_text_from_pdf("generic_error.pdf")
        self.assertIsNone(result)
        mock_print.assert_called_with("An unexpected error occurred while processing PDF 'generic_error.pdf': Generic error")


class TestParseFieldsFromText(unittest.TestCase):
    def test_empty_text(self):
        self.assertEqual(parse_fields_from_text(""), [])

    def test_no_sections(self):
        text = "This is some text without any Figure sections."
        self.assertEqual(parse_fields_from_text(text), [])

    def test_simple_section_and_fields(self):
        text = """
Figure 1. Fields in the TEST_SECTION data file
Some introductory text.
Field Name Field Description Format
FIELD_ONE  Description for field one. ALPHANUMERIC
FIELD_TWO  Description for field two. NUMERIC
"""
        expected = [
            {'Section': 'TEST_SECTION', 'Field Name': 'FIELD_ONE', 'Field Description': 'Description for field one.'},
            {'Section': 'TEST_SECTION', 'Field Name': 'FIELD_TWO', 'Field Description': 'Description for field two.'}
        ]
        self.assertEqual(parse_fields_from_text(text), expected)

    def test_multi_line_description(self):
        text = """
Figure 1. Fields in the MULTILINE_SECTION data file
Field Name Field Description
FIELD_ML   This is a description
             that spans multiple
             lines.
             ALPHANUMERIC
"""
        expected = [
            {'Section': 'MULTILINE_SECTION', 'Field Name': 'FIELD_ML', 
             'Field Description': 'This is a description that spans multiple lines.'}
        ]
        # The parser joins lines with a space, so we need to adjust the expected description.
        # Current logic: current_description_parts.append(stripped_line), then " ".join()
        # So, "that spans multiple" and "lines." will be joined with a space.
        # "This is a description that spans multiple lines." is what the current code produces.
        self.assertEqual(parse_fields_from_text(text), expected)


    def test_fields_with_empty_description(self):
        text = """
Figure 1. Fields in the EMPTY_DESC_SECTION data file
Field Name Field Description Format Max Size
FIELD_EMPTY NUMERIC 10
FIELD_WITH_DESC Description here. ALPHANUMERIC 20
FIELD_EMPTY_TOO DATE
"""
        # Based on current logic: if a line starts with a format keyword (like NUMERIC or DATE)
        # and a field is active, it finalizes the current field.
        # If current_description_parts is empty, it checks if the field was already added.
        # If not, it adds with an empty description.
        expected = [
            {'Section': 'EMPTY_DESC_SECTION', 'Field Name': 'FIELD_EMPTY', 'Field Description': ""},
            {'Section': 'EMPTY_DESC_SECTION', 'Field Name': 'FIELD_WITH_DESC', 'Field Description': 'Description here.'},
            {'Section': 'EMPTY_DESC_SECTION', 'Field Name': 'FIELD_EMPTY_TOO', 'Field Description': ""}
        ]
        self.assertEqual(parse_fields_from_text(text), expected)

    def test_multiple_sections(self):
        text = """
Figure 1. Fields in the FIRST_SECTION data file
Field Name Field Description
FIELD_A    Description A.

Figure 2. Fields in the SECOND_SECTION data file
Data Type Length Nullable
FIELD_B    Description B. VARCHAR
FIELD_C    Description C. INTEGER
"""
        expected = [
            {'Section': 'FIRST_SECTION', 'Field Name': 'FIELD_A', 'Field Description': 'Description A.'},
            {'Section': 'SECOND_SECTION', 'Field Name': 'FIELD_B', 'Field Description': 'Description B.'},
            {'Section': 'SECOND_SECTION', 'Field Name': 'FIELD_C', 'Field Description': 'Description C.'}
        ]
        self.assertEqual(parse_fields_from_text(text), expected)

    def test_section_header_variations(self):
        text_v1 = """
Figure 1. Fields in the HEADER_V1 data file
Field Name Field Description Format Max Size May be NULL Key
FIELD_V1   Description V1. ALPHANUMERIC 10 YES *
"""
        text_v2 = """
Figure 2. Fields in the HEADER_V2 data file
Field Name Field Description Data Type Length Nullable Comments
FIELD_V2   Description V2. VARCHAR 255 NO Some comments
"""
        expected_v1 = [
            {'Section': 'HEADER_V1', 'Field Name': 'FIELD_V1', 'Field Description': 'Description V1.'}
        ]
        expected_v2 = [
            {'Section': 'HEADER_V2', 'Field Name': 'FIELD_V2', 'Field Description': 'Description V2.'}
        ]
        self.assertEqual(parse_fields_from_text(text_v1), expected_v1)
        self.assertEqual(parse_fields_from_text(text_v2), expected_v2)
        
    def test_field_name_not_matching_regex(self):
        # Field names "F1" (too short) and "field_lower" (lowercase) should be ignored
        # or treated as part of description if a field is active.
        text = """
Figure 1. Fields in the REGEX_FAIL_SECTION data file
Field Name Field Description
FIELD_GOOD Description for good field.
F1         This should be part of FIELD_GOOD's description or ignored.
field_lower And this too.
ANOTHER_FIELD Another description.
"""
        # Current logic: "F1" and "field_lower" will be appended to FIELD_GOOD's description
        # because they don't match `field_name_regex` and are not format/other keywords.
        expected = [
            {'Section': 'REGEX_FAIL_SECTION', 'Field Name': 'FIELD_GOOD', 
             'Field Description': "Description for good field. F1 This should be part of FIELD_GOOD's description or ignored. field_lower And this too."},
            {'Section': 'REGEX_FAIL_SECTION', 'Field Name': 'ANOTHER_FIELD', 'Field Description': 'Another description.'}
        ]
        self.assertEqual(parse_fields_from_text(text), expected)

    def test_description_line_starting_with_non_field_uppercase_word(self):
        # "CODE is part of description" - CODE is uppercase but not >=3 chars or not a new field.
        # "VALID_START but actually description" - VALID_START could be a field name.
        # The current logic relies on `is_potential_field_name_token and not is_format_keyword_token and not is_other_data_token`
        # If "VALID_START" looks like a field and is not a keyword, it *will* be treated as a new field.
        # This test highlights the behavior of the current logic.
        text = """
Figure 1. Fields in the DESC_EDGE_CASE data file
Field Name Field Description
FIELD_X    The first line.
           CODE is part of description.
           This is still FIELD_X.
VALID_START This should be a new field.
FIELD_Y     Another line.
            YES this is part of FIELD_Y description because YES is an other_column_keyword,
            so the previous field (VALID_START) should have been finalized without this line.
            Ah, no, "YES" would terminate VALID_START and then this line would be orphaned or part of FIELD_Y?
            Let's simplify:
FIELD_Z    Description for Z.
           NOTE: This is important.
"""
        # Current logic:
        # "CODE is part of description." -> appended to FIELD_X desc. (CODE is not field like by default regex A-Z0-9_]{3,})
        # "VALID_START This should be a new field." -> VALID_START becomes a new field.
        # "NOTE: This is important." -> "NOTE" is not a field (by default regex), so appended to FIELD_Z.
        # If field_name_regex was r"^[A-Z]{2,}$", then CODE would be a field name.
        # If "NOTE" was in format_keywords or other_column_keywords, it would terminate FIELD_Z's description.

        expected = [
            {'Section': 'DESC_EDGE_CASE', 'Field Name': 'FIELD_X', 
             'Field Description': 'The first line. CODE is part of description. This is still FIELD_X.'},
            {'Section': 'DESC_EDGE_CASE', 'Field Name': 'VALID_START', 'Field Description': 'This should be a new field.'},
            {'Section': 'DESC_EDGE_CASE', 'Field Name': 'FIELD_Y', 'Field Description': 'Another line.'},
            # The "YES" line:
            # 1. FIELD_Y is active. "YES" is an `other_column_keyword`.
            # 2. Scenario 2 applies: (is_format_keyword_token or is_other_data_token) and current_field_name.
            # 3. FIELD_Y is finalized with "Another line."
            # 4. current_field_name becomes None.
            # 5. The rest of the "YES..." line is effectively ignored for description purposes.
            # 6. "Ah, no..." line: current_field_name is None. This line is ignored for descriptions.
            # 7. "FIELD_Z" starts a new field.
            {'Section': 'DESC_EDGE_CASE', 'Field Name': 'FIELD_Z', 'Field Description': 'Description for Z. NOTE: This is important.'}
        ]
        # Re-evaluating the "YES" part for FIELD_Y based on code:
        # FIELD_Y active, desc_parts = ["Another line."]
        # Line: "YES this is part of FIELD_Y..." -> first_word="YES", is_other_data_token=True.
        # Scenario 2: (True or ...) and FIELD_Y -> True.
        #   Finalize FIELD_Y with "Another line." -> section_fields.append({'FIELD_Y', 'Another line.'})
        #   current_field_name = None. current_description_parts = [].
        # Line: "Ah, no..." -> first_word="Ah,". is_potential_field_name=False.
        # Scenario 3: else: if current_field_name: (it's None now) -> so this line is skipped.
        # Line: "FIELD_Z Description for Z." -> New field FIELD_Z. desc_parts = ["Description for Z."]
        # Line: "NOTE: This is important." -> first_word="NOTE:". Assume "NOTE:" doesn't match field_name_regex.
        # Scenario 3: else: if current_field_name (FIELD_Z): current_description_parts.append("NOTE: This is important.")
        # So the expected for FIELD_Y should just be "Another line."

        # The provided `text` for this test is a bit complex and leads to behavior
        # that might be subtly different from natural language expectation unless carefully traced.
        # Let's simplify the test text to be more direct for "description line starting with non_field_uppercase_word".
        text_simplified = """
Figure 1. Fields in the DESC_EDGE_CASE data file
Field Name Field Description
FIELD_ONE  Primary description.
           CONTINUATION of description.
           NOTE this is also part of description.
FIELD_TWO  Second field.
"""
        # In text_simplified:
        # "CONTINUATION" does not match `^[A-Z0-9_]{3,}$` if it's not all caps or contains other chars.
        # Assuming "CONTINUATION" and "NOTE" are not field-like according to `field_name_regex` and not keywords.
        expected_simplified = [
            {'Section': 'DESC_EDGE_CASE', 'Field Name': 'FIELD_ONE', 
             'Field Description': 'Primary description. CONTINUATION of description. NOTE this is also part of description.'},
            {'Section': 'DESC_EDGE_CASE', 'Field Name': 'FIELD_TWO', 'Field Description': 'Second field.'}
        ]
        self.assertEqual(parse_fields_from_text(text_simplified), expected_simplified)


    def test_no_fields_after_header(self):
        text = """
Figure 1. Fields in the NO_FIELDS_SECTION data file
Field Name Field Description Format
"""
        self.assertEqual(parse_fields_from_text(text), [])

    def test_text_ends_mid_description(self):
        text = """
Figure 1. Fields in the MID_DESC_END_SECTION data file
Field Name Field Description
FIELD_ONE  This description
           is abruptly cut off.
"""
        # The last active field (FIELD_ONE) should be captured.
        expected = [
            {'Section': 'MID_DESC_END_SECTION', 'Field Name': 'FIELD_ONE', 
             'Field Description': 'This description is abruptly cut off.'}
        ]
        self.assertEqual(parse_fields_from_text(text), expected)

    def test_field_name_is_format_keyword(self):
        # If a field name is "TEXT", and "TEXT" is in `format_keywords`.
        # Current logic: `is_potential_field_name_token and not is_format_keyword_token`
        # If `field_name_regex` matches "TEXT" (it does), `is_potential_field_name_token` is True.
        # If "TEXT" is in `format_keywords`, `is_format_keyword_token` is True.
        # So, `True and not True` is `False`. It will not be recognized as a field name.
        # This test confirms this behavior. If this behavior is undesired, the logic or keywords need change.
        text = """
Figure 1. Fields in the FIELD_IS_KEYWORD_SECTION data file
Field Name Field Description
TEXT       This field is named TEXT.
FIELD_REGULAR Regular description.
"""
        # Expected: TEXT is not treated as a field. "This field is named TEXT." becomes an orphaned line.
        # Or, if a previous field was active, it would be appended to its description.
        # In this case, no previous field is active when "TEXT" is encountered.
        # So, "TEXT This field is named TEXT." is effectively ignored for field capture.
        expected = [
            {'Section': 'FIELD_IS_KEYWORD_SECTION', 'Field Name': 'FIELD_REGULAR', 'Field Description': 'Regular description.'}
        ]
        self.assertEqual(parse_fields_from_text(text), expected)

class TestWriteToCsv(unittest.TestCase):
    @patch('builtins.open', new_callable=mock_open)
    @patch('csv.DictWriter')
    def test_write_to_csv_success(self, MockDictWriter, mock_file_open):
        mock_writer_instance = MockDictWriter.return_value
        parsed_data = [
            {'Section': 'S1', 'Field Name': 'F1', 'Field Description': 'D1'},
            {'Section': 'S2', 'Field Name': 'F2', 'Field Description': 'D2'}
        ]
        csv_filepath = "dummy.csv"

        result = write_to_csv(parsed_data, csv_filepath)

        self.assertTrue(result)
        mock_file_open.assert_called_once_with(csv_filepath, 'w', newline='', encoding='utf-8')
        MockDictWriter.assert_called_once_with(mock_file_open.return_value, fieldnames=['Section', 'Field Name', 'Field Description'])
        mock_writer_instance.writeheader.assert_called_once()
        mock_writer_instance.writerows.assert_called_once_with(parsed_data)

    @patch('builtins.open', new_callable=mock_open) # Should not be called
    @patch('builtins.print') # To check the print message
    def test_write_to_csv_empty_data(self, mock_print, mock_file_open):
        parsed_data = []
        csv_filepath = "empty.csv"

        result = write_to_csv(parsed_data, csv_filepath)

        self.assertTrue(result) # Current logic returns True for empty data
        mock_print.assert_called_once_with("No data to write to CSV.")
        mock_file_open.assert_not_called()

    @patch('builtins.open', side_effect=IOError("Disk full"))
    @patch('builtins.print')
    def test_write_to_csv_io_error(self, mock_print, mock_file_open):
        parsed_data = [{'Section': 'S1', 'Field Name': 'F1', 'Field Description': 'D1'}]
        csv_filepath = "error.csv"

        result = write_to_csv(parsed_data, csv_filepath)

        self.assertFalse(result)
        mock_file_open.assert_called_once_with(csv_filepath, 'w', newline='', encoding='utf-8')
        mock_print.assert_called_once_with(f"Error: Could not write to CSV file '{csv_filepath}'. Details: Disk full")

    @patch('builtins.open', side_effect=Exception("Unexpected error during open"))
    @patch('builtins.print')
    def test_write_to_csv_unexpected_error_on_open(self, mock_print, mock_file_open):
        parsed_data = [{'Section': 'S1', 'Field Name': 'F1', 'Field Description': 'D1'}]
        csv_filepath = "error.csv"

        result = write_to_csv(parsed_data, csv_filepath)
        self.assertFalse(result)
        mock_file_open.assert_called_once_with(csv_filepath, 'w', newline='', encoding='utf-8') # Corrected encoding
        mock_print.assert_called_once_with(f"An unexpected error occurred while writing to CSV '{csv_filepath}': Unexpected error during open")


    @patch('builtins.open', new_callable=mock_open) # Open succeeds
    @patch('csv.DictWriter', side_effect=Exception("CSV processing error")) # DictWriter or its methods fail
    @patch('builtins.print')
    def test_write_to_csv_unexpected_error_during_write(self, mock_print, MockDictWriter, mock_file_open):
        parsed_data = [{'Section': 'S1', 'Field Name': 'F1', 'Field Description': 'D1'}]
        csv_filepath = "error.csv"

        result = write_to_csv(parsed_data, csv_filepath)
        self.assertFalse(result)
        mock_file_open.assert_called_once_with(csv_filepath, 'w', newline='', encoding='utf-8')
        MockDictWriter.assert_called_once() # It was called before the error
        mock_print.assert_called_once_with(f"An unexpected error occurred while writing to CSV '{csv_filepath}': CSV processing error")


if __name__ == '__main__':
    unittest.main()
