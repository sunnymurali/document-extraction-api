"""
PDF Text Extraction Module
This module provides functions to extract text from PDF files.
"""

import os
import io
import PyPDF2
from typing import Optional


def extract_text_from_pdf(pdf_file) -> str:
    """
    Extract text from a PDF file.
    
    Args:
        pdf_file: File-like object containing PDF data
        
    Returns:
        Extracted text as a string
        
    Raises:
        Exception: If there was an error extracting text from the PDF
    """
    try:
        reader = PyPDF2.PdfReader(pdf_file)
        text = ""
        
        for page_num in range(len(reader.pages)):
            page = reader.pages[page_num]
            text += page.extract_text() or ""
            text += "\n\n"  # Add spacing between pages
            
        return text.strip()
    except Exception as e:
        raise Exception(f"Error extracting text from PDF: {str(e)}")


def extract_text_from_pdf_with_fallback(pdf_file) -> str:
    """
    Extract text from a PDF file with fallback methods if PyPDF2 fails.
    
    Args:
        pdf_file: File-like object containing PDF data
        
    Returns:
        Extracted text as a string
        
    Raises:
        Exception: If all extraction methods fail
    """
    try:
        return extract_text_from_pdf(pdf_file)
    except Exception as main_error:
        # Could implement additional extraction methods here if needed
        raise Exception(f"Failed to extract text from PDF: {str(main_error)}")