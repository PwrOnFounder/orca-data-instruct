from io import StringIO
from pdfminer.converter import TextConverter
from pdfminer.layout import LAParams
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.pdfpage import PDFPage
from pdfminer.pdfparser import PDFParser

def extract_text_from_pdf(pdf_path, num_pages=3):
    """Extracts text from the first num_pages of a PDF file."""
    output_string = StringIO()
    with open(pdf_path, 'rb') as in_file:
        parser = PDFParser(in_file)
        doc = PDFDocument(parser)
        rsrcmgr = PDFResourceManager()
        device = TextConverter(rsrcmgr, output_string, laparams=LAParams())
        interpreter = PDFPageInterpreter(rsrcmgr, device)
        for i, page in enumerate(PDFPage.create_pages(doc)):
            if i < num_pages:
                interpreter.process_page(page)
            else:
                break
    return output_string.getvalue()

if __name__ == '__main__':
    pdf_path = 'Form_D.SEC.Data.Guide.pdf'
    extracted_text = extract_text_from_pdf(pdf_path)
    print(extracted_text)
