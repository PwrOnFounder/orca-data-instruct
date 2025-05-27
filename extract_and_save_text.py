from io import StringIO
from pdfminer.converter import TextConverter
from pdfminer.layout import LAParams
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.pdfpage import PDFPage
from pdfminer.pdfparser import PDFParser

def extract_text_from_pdf(pdf_path, num_pages=5):
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
    output_txt_path = 'extracted_text_sample.txt'
    extracted_text = extract_text_from_pdf(pdf_path)
    
    with open(output_txt_path, 'w', encoding='utf-8') as out_file:
        out_file.write(extracted_text)
    
    print(f"Text extracted from '{pdf_path}' and saved to '{output_txt_path}'")
