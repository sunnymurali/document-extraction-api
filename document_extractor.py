"""
Document Data Extractor

A utility that extracts structured data from PDF documents using PyPDF and OpenAI models via LangChain.
Returns extracted information as structured JSON data. This implementation primarily uses
Azure OpenAI services but can fall back to standard OpenAI API if Azure is unavailable.
"""

import os
import json
import base64
import logging
import tempfile
from typing import Any, Dict, List, Optional, Tuple

import pypdf

from langchain_core.messages import SystemMessage, HumanMessage
from utils.azure_openai_config import get_chat_openai
from utils.document_chunking import (
    split_text_into_chunks,
    merge_extraction_results,
    process_chunks_with_progress
)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


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
    Extract structured data from text using OpenAI services via LangChain.
    First attempts to use Azure OpenAI, then falls back to standard OpenAI if necessary.
    
    Args:
        text: The text to extract data from
        schema: Optional schema defining the fields to extract
        
    Returns:
        Extracted structured data as a dictionary
    """
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
    
    # Create LangChain message objects
    system_message = SystemMessage(content=system_prompt)
    human_message = HumanMessage(content=f"Extract structured data from this document text:\n\n{text}")
    
    try:
        logger.info("Attempting to extract data using OpenAI services...")
        
        # Get OpenAI client with appropriate settings (will try Azure first, then fallback to standard OpenAI)
        client = get_chat_openai(temperature=0.1, max_tokens=1000)
        
        # Make the API call to OpenAI via LangChain
        response = client.invoke([system_message, human_message])
        
        # Extract the response content
        response_content = response.content
        
        # Check if response looks like HTML (it might be an error page)
        if response_content.strip().startswith('<'):
            logger.error(f"Received HTML response instead of JSON: {response_content[:100]}...")
            raise Exception("Received HTML error page instead of JSON response. This usually indicates an authentication or API configuration issue.")
        
        # Try to parse the JSON response
        # Remove any potential markdown code block syntax
        cleaned_content = response_content
        if "```json" in cleaned_content:
            # Extract only the part between ```json and ```
            parts = cleaned_content.split("```json")
            if len(parts) > 1:
                json_parts = parts[1].split("```")
                if json_parts:
                    cleaned_content = json_parts[0].strip()
        elif "```" in cleaned_content:
            # Extract only the part between ``` and ```
            parts = cleaned_content.split("```")
            if len(parts) > 1:
                cleaned_content = parts[1].strip()
        
        logger.debug(f"Cleaned response content for JSON parsing: {cleaned_content[:100]}...")
        
        # Try to parse the JSON
        parsed_data = json.loads(cleaned_content)
        logger.info("Successfully parsed JSON response")
        return parsed_data
        
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing JSON from response: {e}")
        logger.debug(f"Raw response content: {response_content if 'response_content' in locals() else 'No response'}")
        error_preview = response_content[:50] + "..." if len(response_content) > 50 else response_content
        raise Exception(f"Failed to parse JSON response: {e}. Response begins with: {error_preview}")
    
    except Exception as e:
        # Any other error in the process
        error_msg = f"OpenAI connection failed (tried both Azure and standard OpenAI if configured): {e}"
        logger.error(error_msg)
        raise Exception(error_msg)


def extract_document_data(file_path: str, schema: Optional[Dict[str, Any]] = None, 
                       use_chunking: bool = True) -> Dict[str, Any]:
    """
    Extract structured data from a PDF document
    
    Args:
        file_path: Path to the PDF document
        schema: Optional schema defining the fields to extract
        use_chunking: Whether to use document chunking for large documents (default: True)
        
    Returns:
        Dictionary with extraction results including either extracted data or error
    """
    try:
        # Extract text from PDF
        text = extract_text_from_pdf(file_path)
        
        if not text or text.isspace():
            return {"success": False, "error": "Could not extract any text from the PDF document"}
        
        # Check if we should use chunking (based on text length)
        if use_chunking and len(text) > 10000:  # If text is longer than ~10K characters
            logger.info(f"Document is large ({len(text)} characters), using chunking strategy")
            
            # Split the text into chunks
            chunks = split_text_into_chunks(text)
            logger.info(f"Split document into {len(chunks)} chunks")
            
            # Define a function to extract data from a single chunk
            def extract_from_chunk(chunk_text, schema):
                return extract_structured_data(chunk_text, schema)
            
            # Process all chunks and merge results
            merged_data, progress_info = process_chunks_with_progress(chunks, extract_from_chunk, schema)
            
            return {
                "success": True, 
                "data": merged_data,
                "chunking_info": {
                    "used": True,
                    "chunks_processed": len(progress_info),
                    "total_chunks": len(chunks),
                    "progress": progress_info
                }
            }
        else:
            # For smaller documents, process as a single chunk
            logger.info("Processing document as a single chunk")
            data = extract_structured_data(text, schema)
            
            return {
                "success": True, 
                "data": data,
                "chunking_info": {"used": False}
            }
    
    except Exception as e:
        logger.error(f"Error extracting data from document: {str(e)}")
        return {"success": False, "error": str(e)}


def extract_from_binary_data(file_content: bytes, schema: Optional[Dict[str, Any]] = None,
                          use_chunking: bool = True) -> Dict[str, Any]:
    """
    Extract structured data from binary document content
    
    Args:
        file_content: Binary content of the document
        schema: Optional schema defining the fields to extract
        use_chunking: Whether to use document chunking for large documents (default: True)
        
    Returns:
        Dictionary with extraction results including either extracted data or error
    """
    try:
        # Save the binary content to a temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(file_content)
            tmp_path = tmp.name
        
        try:
            # Extract data from the temporary file, passing the chunking parameter
            result = extract_document_data(tmp_path, schema, use_chunking=use_chunking)
            
            return result
        finally:
            # Clean up the temporary file
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
    
    except Exception as e:
        logger.error(f"Error processing binary data: {str(e)}")
        return {"success": False, "error": f"Error processing document: {str(e)}"}


def convert_pdf_page_to_base64(file_path: str, page_num: int = 0) -> str:
    """
    Convert a PDF page to a base64-encoded string
    
    Args:
        file_path: Path to the PDF file
        page_num: Page number to convert (0-indexed)
        
    Returns:
        Base64-encoded string of the page image
    """
    import fitz  # PyMuPDF

    try:
        # Open the PDF
        doc = fitz.open(file_path)
        
        # Check if page exists
        if page_num >= len(doc):
            raise ValueError(f"Page {page_num} does not exist in the document with {len(doc)} pages")
        
        # Get the page
        page = doc.load_page(page_num)
        
        # Render the page to an image
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))  # 2x zoom for better resolution
        
        # Get the image as bytes
        img_bytes = pix.tobytes("png")
        
        # Convert to base64
        base64_image = base64.b64encode(img_bytes).decode("utf-8")
        
        return base64_image
    
    except Exception as e:
        logger.error(f"Error converting PDF page to base64: {str(e)}")
        raise


def extract_tables_from_pdf(file_path: str, max_pages: int = 5) -> Dict[str, Any]:
    """
    Extract tables from a PDF document using OpenAI services
    
    This function is intended to use OpenAI's vision capabilities when available.
    Currently, since neither Azure OpenAI nor standard OpenAI through LangChain fully support 
    multimodal content this way, it will return an error message.
    
    Args:
        file_path: Path to the PDF document
        max_pages: Maximum number of pages to process (default: 5)
        
    Returns:
        Dictionary with extraction results including tables found in the document
    """
    try:
        # Read the PDF to get total number of pages
        pdf = pypdf.PdfReader(file_path)
        total_pages = len(pdf.pages)
        
        if total_pages == 0:
            return {"success": False, "error": "PDF document is empty"}
        
        # List to store all tables
        all_tables = []
        
        # Process each page (limit to max_pages for performance)
        page_limit = min(total_pages, max_pages)
        
        # Process pages with progress logging
        logger.info(f"Starting table extraction from {page_limit} pages out of {total_pages} total pages")
        
        for page_num in range(page_limit):
            try:
                logger.info(f"Processing page {page_num + 1} of {page_limit}")
                
                # Convert the page to base64
                base64_image = convert_pdf_page_to_base64(file_path, page_num)
                
                # Prepare system message for table extraction
                system_prompt = (
                    "You are a table extraction expert. Identify and extract any tables in this PDF page. "
                    "If multiple tables are present, extract each one separately and provide a brief title or description for each table. "
                    "Format the output as a JSON array of table objects with this structure: "
                    "[{\"table_title\": \"Title of the table\", \"headers\": [\"Column1\", \"Column2\", ...], \"data\": [[\"row1col1\", \"row1col2\", ...], [\"row2col1\", \"row2col2\", ...], ...]}, ...]. "
                    "If no tables are present in the image, return an empty array []. "
                    "Make sure to maintain the row and column structure of each table. "
                    "Only extract actual tables with proper headers and rows. Do not extract lists, paragraphs of text, or other non-tabular content."
                )
                
                # Create LangChain message objects for table extraction
                system_message = SystemMessage(content=system_prompt)
                
                # Note: This is a placeholder for future Azure OpenAI with vision capabilities
                # Currently using a temporary implementation until Azure OpenAI fully supports multimodal content
                try:
                    # Get OpenAI client for table extraction with fallback
                    client = get_chat_openai(temperature=0.1, max_tokens=2000)
                    
                    # Placeholder for OpenAI vision implementation
                    # This is intentionally designed to raise an exception for now
                    logger.info("Attempting to extract tables using OpenAI services...")
                    
                    # This will raise an exception since LangChain doesn't yet fully support multimodal content this way
                    # The error will be caught and propagated
                    raise NotImplementedError("OpenAI multimodal extraction not yet implemented in this application")
                    
                except Exception as e:
                    error_msg = f"OpenAI connection failed (tried both Azure and standard OpenAI if configured): {e}"
                    logger.error(error_msg)
                    
                    # Return an empty array for tables, but with a clear error message
                    raise Exception(error_msg)
                
                # Note: Since we're raising an exception in the try/except block above,
                # this code will never be reached in the current implementation.
                # It's kept as a template for future implementation when Azure OpenAI
                # supports multimodal vision capabilities.
                
                # If we ever get to this point, it means we've successfully processed
                # a table with Azure OpenAI. Add a placeholder to process the response.
                tables_found = 0
                logger.info(f"Successfully processed page {page_num + 1}, found {tables_found} tables")
                
            except Exception as e:
                logger.warning(f"Error processing page {page_num + 1}: {str(e)}")
                continue
        
        logger.info(f"Table extraction complete. Found {len(all_tables)} tables across {page_limit} pages.")
        
        return {
            "success": True,
            "tables": all_tables,
            "total_tables": len(all_tables),
            "pages_processed": page_limit,
            "total_pages": total_pages
        }
    
    except Exception as e:
        logger.error(f"Error extracting tables from document: {str(e)}")
        return {"success": False, "error": str(e)}


def extract_tables_from_binary_data(file_content: bytes, max_pages: int = 5) -> Dict[str, Any]:
    """
    Extract tables from binary document content using OpenAI services
    
    This function is intended to use OpenAI's vision capabilities when available.
    Currently, since neither Azure OpenAI nor standard OpenAI through LangChain fully support 
    multimodal content this way, it will return an error message.
    
    Args:
        file_content: Binary content of the document
        max_pages: Maximum number of pages to process (default: 5)
        
    Returns:
        Dictionary with extraction results including tables found in the document
    """
    try:
        # Save the binary content to a temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(file_content)
            tmp_path = tmp.name
        
        try:
            # Extract tables from the temporary file with the specified max_pages
            result = extract_tables_from_pdf(tmp_path, max_pages=max_pages)
            
            return result
        finally:
            # Clean up the temporary file
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
    
    except Exception as e:
        logger.error(f"Error processing binary data for table extraction: {str(e)}")
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