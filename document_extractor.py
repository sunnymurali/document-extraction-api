"""
Document Data Extractor

A utility that extracts structured data from PDF documents using PyPDF and OpenAI models.
Returns extracted information as structured JSON data.
"""

import os
import json
import logging
import tempfile
from typing import Any, Dict, List, Optional

import pypdf
from openai import OpenAI

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize OpenAI client
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))


def extract_text_from_pdf(file_path: str) -> str:
    """
    Extract text content from a PDF file
    
    Args:
        file_path: Path to the PDF file
        
    Returns:
        Extracted text content as a string
    """
    try:
        logger.info(f"Extracting text from PDF: {file_path}")
        reader = pypdf.PdfReader(file_path)
        text = ""
        
        for page in reader.pages:
            page_text = page.extract_text() or ""
            text += page_text + "\n\n"
            
        return text.strip()
    except Exception as e:
        error_msg = f"Error extracting text from PDF: {str(e)}"
        logger.error(error_msg)
        raise Exception(error_msg)


def extract_structured_data(text: str, schema: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Extract structured data from text using OpenAI
    
    Args:
        text: The text to extract data from
        schema: Optional schema defining the fields to extract
        
    Returns:
        Extracted structured data as a dictionary
    """
    try:
        # If text is too long, truncate it to avoid exceeding token limits
        if len(text) > 15000:
            text = text[:15000] + "...(truncated)"
        
        # Prepare system message for the extraction
        system_prompt = (
            "You are a document data extraction assistant that extracts structured information from text. "
            "Extract the information as a valid JSON object based on the provided schema or general document data. "
            "If a field cannot be found in the text, use null as the value. Do not make up information."
        )
        
        # Add schema information to the prompt if provided
        if schema and "fields" in schema:
            field_info = "\n".join([f"- {field['name']}: {field.get('description', '')}" 
                                   for field in schema["fields"]])
            system_prompt += f"\n\nExtract the following fields:\n{field_info}"
        else:
            # Default extraction without specific schema
            system_prompt += """
Extract the following common fields (if present):
- name: The full name of a person or entity
- date: Any relevant dates (e.g., invoice date, birth date)
- address: Complete address information
- phone: Phone number
- email: Email address
- total_amount: Any monetary total
- items: List of items with descriptions and prices
- any other key information present in the document

Return the data as a clean JSON object.
"""
        
        # Make the API call to OpenAI
        # the newest OpenAI model is "gpt-4o" which was released May 13, 2024.
        # do not change this unless explicitly requested by the user
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Extract structured data from this document text:\n\n{text}"}
            ],
            response_format={"type": "json_object"},
            temperature=0.1,  # Lower temperature for more deterministic outputs
            max_tokens=1000
        )
        
        # Extract the response content
        response_content = response.choices[0].message.content
        
        # Parse and return the JSON response
        return json.loads(response_content)
    
    except Exception as e:
        logger.error(f"Error in OpenAI extraction: {str(e)}")
        raise Exception(f"Failed to extract data: {str(e)}")


def extract_document_data(file_path: str, schema: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Extract structured data from a PDF document
    
    Args:
        file_path: Path to the PDF document
        schema: Optional schema defining the fields to extract
        
    Returns:
        Dictionary with extraction results including either extracted data or error
    """
    try:
        # Extract text from PDF
        text = extract_text_from_pdf(file_path)
        
        if not text or text.isspace():
            return {"success": False, "error": "Could not extract any text from the PDF document"}
        
        # Extract structured data from text
        data = extract_structured_data(text, schema)
        
        return {"success": True, "data": data}
    
    except Exception as e:
        logger.error(f"Error extracting data from document: {str(e)}")
        return {"success": False, "error": str(e)}


def extract_from_binary_data(file_content: bytes, schema: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Extract structured data from binary document content
    
    Args:
        file_content: Binary content of the document
        schema: Optional schema defining the fields to extract
        
    Returns:
        Dictionary with extraction results including either extracted data or error
    """
    try:
        # Save the binary content to a temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(file_content)
            tmp_path = tmp.name
        
        try:
            # Extract data from the temporary file
            result = extract_document_data(tmp_path, schema)
            
            return result
        finally:
            # Clean up the temporary file
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
    
    except Exception as e:
        logger.error(f"Error processing binary data: {str(e)}")
        return {"success": False, "error": f"Error processing document: {str(e)}"}


if __name__ == "__main__":
    # Example usage
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python document_extractor.py <pdf_file_path>")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    
    # Example schema (optional)
    example_schema = {
        "fields": [
            {"name": "invoice_number", "description": "The invoice identification number"},
            {"name": "date", "description": "The invoice date"},
            {"name": "total_amount", "description": "The total amount due"},
            {"name": "customer", "description": "Customer name and details"},
            {"name": "items", "description": "List of items, quantities and prices"}
        ]
    }
    
    # Extract data
    result = extract_document_data(pdf_path, example_schema)
    
    # Print the result
    print(json.dumps(result, indent=2))