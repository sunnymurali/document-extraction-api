import logging
import PyPDF2
from typing import Optional

logger = logging.getLogger(__name__)

def extract_text_from_pdf(pdf_path: str) -> str:
    """
    Extract text from a PDF file.
    
    Args:
        pdf_path: Path to the PDF file
        
    Returns:
        Extracted text as a string
        
    Raises:
        Exception: If there was an error extracting text from the PDF
    """
    try:
        logger.debug(f"Opening PDF file: {pdf_path}")
        text = ""
        
        # Open the PDF file with PyPDF2
        with open(pdf_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            
            # Check if the PDF is encrypted
            if pdf_reader.is_encrypted:
                logger.warning("PDF is encrypted. Attempting to decrypt with empty password.")
                try:
                    pdf_reader.decrypt('')  # Try with empty password
                except:
                    raise Exception("The PDF file is encrypted and could not be decrypted.")
            
            # Get total number of pages
            num_pages = len(pdf_reader.pages)
            logger.debug(f"PDF has {num_pages} pages")
            
            if num_pages == 0:
                return ""
            
            # Extract text from each page
            for page_num in range(num_pages):
                page = pdf_reader.pages[page_num]
                page_text = page.extract_text()
                text += page_text + "\n"
        
        logger.debug(f"Extracted {len(text)} characters of text")
        return text
    
    except Exception as e:
        logger.error(f"Error extracting text from PDF: {str(e)}")
        raise Exception(f"Failed to extract text from PDF: {str(e)}")


def extract_text_from_pdf_with_fallback(pdf_path: str) -> str:
    """
    Extract text from a PDF file with fallback methods if PyPDF2 fails.
    
    Args:
        pdf_path: Path to the PDF file
        
    Returns:
        Extracted text as a string
        
    Raises:
        Exception: If all extraction methods fail
    """
    try:
        # First try with PyPDF2
        return extract_text_from_pdf(pdf_path)
    except Exception as e:
        logger.warning(f"PyPDF2 extraction failed: {str(e)}")
        
        try:
            # Try with pdfplumber as fallback (if available)
            import pdfplumber
            text = ""
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    text += page.extract_text() or ""
                    text += "\n"
            return text
        except ImportError:
            logger.error("pdfplumber not installed for fallback")
            raise Exception("Primary PDF extraction failed and pdfplumber is not installed as fallback")
        except Exception as e2:
            logger.error(f"All PDF extraction methods failed: {str(e2)}")
            raise Exception(f"Failed to extract text from PDF using multiple methods. Last error: {str(e2)}")
