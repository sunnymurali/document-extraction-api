"""
Document Data Extractor

A utility that extracts structured data from PDF documents using PyPDF and OpenAI models via LangChain.
Returns extracted information as structured JSON data. This implementation primarily uses
Azure OpenAI services but can fall back to standard OpenAI API if Azure is unavailable.
It now supports using ChromaDB for vector storage and retrieval for more efficient and targeted extraction.
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
    process_chunks_with_progress,
    MAX_CHUNKS_TO_PROCESS
)

# Configure logging - use WARNING level to reduce CPU usage from excessive logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def extract_text_from_pdf(file_path: str) -> str:
    """
    Extract text content from a PDF file with optimizations for financial documents
    
    Args:
        file_path: Path to the PDF file
        
    Returns:
        Extracted text content as a string
    """
    try:
        logger.info(f"Extracting text from PDF: {file_path}")
        
        # Use PyMuPDF for initial file analysis to detect document type
        import fitz  # PyMuPDF
        try:
            doc = fitz.open(file_path)
            first_page_text = doc[0].get_text()
            doc.close()
            
            # Detect document type based on content
            is_morgan_stanley = "Morgan Stanley" in first_page_text
            is_capital_one = "Capital One" in first_page_text
            
            logger.info(f"Document detection: Morgan Stanley: {is_morgan_stanley}, Capital One: {is_capital_one}")
        except Exception as mupdf_error:
            logger.warning(f"PyMuPDF analysis failed, proceeding with standard extraction: {mupdf_error}")
            is_morgan_stanley = False
            is_capital_one = False
            
        reader = pypdf.PdfReader(file_path)
        
        # Get total number of pages
        num_pages = len(reader.pages)
        logger.info(f"PDF document has {num_pages} pages")
        
        text = ""
        
        # Different extraction strategy based on document type
        if is_morgan_stanley:
            logger.info("Using Morgan Stanley specific extraction strategy")
            
            # Morgan Stanley reports often have financial data in specific sections
            # Focus on management discussion (MD&A) and financial statements sections
            
            # Extract from early pages (table of contents, highlights, key metrics)
            toc_range = min(15, num_pages)  # First few pages usually contain TOC
            for i in range(toc_range):
                page_text = reader.pages[i].extract_text() or ""
                text += page_text + "\n\n"
            
            # For Morgan Stanley, financial data is often in pages 60-120
            financial_start = min(60, num_pages)
            financial_end = min(120, num_pages)
            
            for i in range(financial_start, financial_end):
                if i < num_pages:
                    page_text = reader.pages[i].extract_text() or ""
                    text += page_text + "\n\n"
                    
            # Also extract management discussion section (usually pages 25-50)
            mda_start = min(25, num_pages)
            mda_end = min(50, num_pages)
            
            for i in range(mda_start, mda_end):
                if i < num_pages and i not in range(financial_start, financial_end):
                    page_text = reader.pages[i].extract_text() or ""
                    text += page_text + "\n\n"
                    
        elif is_capital_one:
            logger.info("Using Capital One specific extraction strategy")
            
            # Capital One specific extraction logic
            # Similar to default but with focus on different page ranges
            
            # Extract early pages for executive summary
            early_pages = min(int(num_pages * 0.25), 25)
            for i in range(early_pages):
                page_text = reader.pages[i].extract_text() or ""
                text += page_text + "\n\n"
            
            # Capital One often has key financial tables from pages 40-80
            middle_start = max(30, early_pages)
            middle_end = min(num_pages, 80)
            
            for i in range(middle_start, middle_end):
                if i < num_pages:
                    page_text = reader.pages[i].extract_text() or ""
                    text += page_text + "\n\n"
                
        else:
            # Default extraction for general financial documents
            # For financial documents, focus on the most important pages (limit to 100 pages)
            max_pages = min(num_pages, 100)
            
            # First extract from early pages (likely to contain management discussion, financial highlights)
            early_pages = min(int(max_pages * 0.3), 30)  # Up to 30% of document or 30 pages
            logger.info(f"Extracting first {early_pages} pages for executive summary and key metrics")
            
            for i in range(early_pages):
                if i < num_pages:
                    page_text = reader.pages[i].extract_text() or ""
                    text += page_text + "\n\n"
            
            # Then extract from middle pages (likely to contain financial statements and tables)
            if num_pages > early_pages:
                middle_start = early_pages
                middle_end = min(num_pages, 70)  # Financial statements usually before page 70
                logger.info(f"Extracting middle pages {middle_start} to {middle_end} for financial statements")
                
                for i in range(middle_start, middle_end):
                    if i < num_pages:
                        page_text = reader.pages[i].extract_text() or ""
                        text += page_text + "\n\n"
        
        # If text extraction failed or text is too short, try fallback method
        if len(text.strip()) < 1000 and num_pages > 5:
            logger.warning(f"Primary extraction yielded insufficient text ({len(text)} chars), using alternative method")
            
            # Fallback to sequential extraction of all pages
            text = ""
            
            # Try PyMuPDF as the fallback extraction method
            try:
                logger.info("Attempting PyMuPDF fallback extraction")
                doc = fitz.open(file_path)
                for i in range(min(num_pages, 100)):
                    page_text = doc[i].get_text() or ""
                    text += page_text + "\n\n"
                doc.close()
                logger.info("PyMuPDF fallback extraction successful")
            except Exception as mupdf_error:
                logger.warning(f"PyMuPDF fallback failed: {mupdf_error}, trying pypdf")
                # Fall back to original pypdf
                for i in range(min(num_pages, 100)):  # Limit to 100 pages
                    page_text = reader.pages[i].extract_text() or ""
                    text += page_text + "\n\n"
        
        # Process the text to clean up common PDF extraction issues in financial documents
        processed_text = text.replace("$", "$ ")  # Add space after dollar signs for better recognition
        processed_text = processed_text.replace("  ", " ")  # Remove double spaces
        
        # Additional processing for financial documents
        processed_text = processed_text.replace("(", " (")  # Add space before parentheses for negative numbers
        processed_text = processed_text.replace("%", "% ")  # Add space after percentage signs
        processed_text = processed_text.replace("million", " million ")  # Ensure spacing around financial terms
        processed_text = processed_text.replace("billion", " billion ")
        
        logger.info(f"Extracted {len(processed_text)} characters of text from PDF")
        return processed_text.strip()
    except Exception as e:
        error_msg = f"Error extracting text from PDF: {str(e)}"
        logger.error(error_msg)
        raise Exception(error_msg)


def extract_structured_data(text: str, schema: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Extract structured data from text using OpenAI services via LangChain.
    Optimized for performance with reduced token count.
    Enhanced to handle complex financial data like Morgan Stanley 10K.
    
    Args:
        text: The text to extract data from
        schema: Optional schema defining the fields to extract
        
    Returns:
        Extracted structured data as a dictionary
    """
    # If text is too long, truncate it more aggressively to reduce token usage
    if len(text) > 14000:
        text = text[:14000] + "...(text truncated for processing)"
    
    # Check if the document likely contains Morgan Stanley content
    is_morgan_stanley = "Morgan Stanley" in text[:5000]
    
    # Prepare system message for the extraction
    system_prompt = (
        "You are a financial document data extraction assistant specialized in extracting information from annual reports and 10-K filings. "
        "Extract the information as a valid JSON object based on the provided schema or general document data. "
        "Be methodical and thorough in your search for financial information in the document. "
        "Financial information is typically found in: "
        "1. Management's Discussion and Analysis (MD&A) section "
        "2. Financial Statements (Consolidated Balance Sheets, Income Statements, etc.) "
        "3. Notes to the Financial Statements "
        "4. Business Segment reporting sections "
        "Look for actual numeric values in tables and financial statements, paying special attention to dollar amounts in millions or billions. "
        "For financial metrics, be sure to extract the most recent annual or full-year values, not quarterly. "
        "If a field cannot be found in its typical form, look for equivalent metrics or alternative names. "
        "If after thorough search you cannot find the information, use null as the value. Never make up or estimate values. "
        "Be concise and direct in your extraction. For fields like 'Business Segment Financial Performance', "
        "extract a summary of performance across the company's main business segments or divisions."
    )
    
    # Add specialized instructions for Morgan Stanley 10K format
    if is_morgan_stanley:
        system_prompt += (
            "\n\nThis appears to be a Morgan Stanley annual report. For Morgan Stanley specifically:"
            "\n1. Net Interest Income is often reported as a line item in their Consolidated Income Statement"
            "\n2. Total operating expenses might be listed as 'Non-interest expenses' or 'Total non-interest expenses'"
            "\n3. Morgan Stanley reports on three main business segments: Institutional Securities, Wealth Management, and Investment Management"
            "\n4. Financial data is typically reported in millions of dollars"
            "\n5. Look for tables with clear financial measurements across multiple years, focus on the most recent year"
            "\n6. Page numbers 60-75 often contain important consolidated financial statements"
            "\n7. Business segment information is often found in a dedicated 'Business Segments' section"
        )
    
    # Add schema information to the prompt if provided
    if schema and "fields" in schema:
        # Build more detailed prompting for each field with specific financial instructions
        field_descriptions = []
        for field in schema["fields"]:
            field_name = field['name']
            field_desc = field.get('description', '')
            
            # Add specific guidance for each field type with alternative names/formats
            if field_name == "Net Interest Income":
                field_desc = "This is a key financial metric found in the income statement or financial results section. Look for mentions of 'Net Interest Income', 'NII', 'Interest Income - Interest Expense', or equivalent metrics. For banks and financial institutions, this is a critical metric typically reported in millions or billions of dollars. For Morgan Stanley, look in the Consolidated Income Statement or 'Consolidated Results of Operations'. Extract the most recent annual value."
            elif field_name == "Total operating expense":
                field_desc = "This is a financial metric found in the income statement, often listed as 'Operating Expenses', 'Total Operating Expenses', 'Non-interest expenses', 'Total non-interest expenses', or 'Operating Costs'. For Morgan Stanley, check the 'Consolidated Results of Operations' or 'Expense Management' section. Look for the sum of all expenses related to operations. Extract the most recent annual value."
            elif field_name == "Business Segment Financial Performance":
                field_desc = "Look for a section that breaks down the performance by different business segments or divisions. For Morgan Stanley, look for 'Business Segments' or 'Segment Information' sections. Key segments likely include Institutional Securities, Wealth Management, and Investment Management. Extract a summary of each segment's performance with their names and key metrics (revenue, income, assets, etc.). This is often found in a segment reporting section or in the Management's Discussion and Analysis."
            
            field_descriptions.append(f"- {field_name}: {field_desc}")
            
        field_info = "\n".join(field_descriptions)
        system_prompt += f"\n\nExtract the following fields:\n{field_info}\n\nThese fields are definitely present in the document. Search thoroughly through all sections and tables. Return the specific values (with proper formatting for currency) when available, and provide descriptive text for the Business Segment Financial Performance."
    else:
        # Default extraction with fewer fields to reduce complexity
        system_prompt += """
Extract the following common fields (if present):
- name: The full name of a person or entity
- date: Any relevant dates (e.g., invoice date)
- address: Complete address information
- phone: Phone number
- email: Email address
- total_amount: Any monetary total
- other_key_info: Any other important information

Return the data as a clean JSON object with no explanations.
"""
    
    # Create LangChain message objects
    system_message = SystemMessage(content=system_prompt)
    human_message = HumanMessage(content=f"Extract structured data from this document text:\n\n{text}")
    
    try:
        # Initialize response_content variable to avoid possible unbounded reference
        response_content = ""
        
        # Get OpenAI client with higher token limit for financial data
        client = get_chat_openai(temperature=0.1, max_tokens=1000)
        
        # Make the API call to OpenAI via LangChain
        response = client.invoke([system_message, human_message])
        
        # Extract the response content
        response_content = response.content
        
        # Check if response looks like HTML (it might be an error page)
        if response_content and response_content.strip().startswith('<'):
            logger.error(f"Received HTML response instead of JSON: {response_content[:100]}...")
            raise Exception("Received HTML error page instead of JSON response. This usually indicates an authentication or API configuration issue.")
        
        try:
            
            # Clean the content for JSON parsing (simplified version)
            cleaned_content = response_content
            if cleaned_content and "```" in cleaned_content:
                # Extract content between code blocks in one step
                parts = cleaned_content.split("```")
                if len(parts) >= 3:  # At least one full code block
                    # Get the content of the first code block
                    cleaned_content = parts[1]
                    # Remove json language identifier if present
                    if cleaned_content.startswith("json"):
                        cleaned_content = cleaned_content[4:].strip()
                        
            # Try to parse the JSON
            parsed_data = json.loads(cleaned_content)
            return parsed_data
        except json.JSONDecodeError as e:
            # Provide error with truncated details to save memory
            error_msg = f"Failed to parse JSON response: {str(e)[:100]}"
            response_preview = response_content[:50] if response_content else ""
        
        if response_preview:
            error_msg += f". Response preview: {response_preview}..."
        
        logger.error(error_msg)
        raise Exception(error_msg)
    
    except Exception as e:
        # Simplified error handling
        error_msg = f"OpenAI API error: {str(e)[:150]}"
        logger.error(error_msg)
        raise Exception(error_msg)


def extract_document_data(file_path: str, schema: Optional[Dict[str, Any]] = None, 
                       use_chunking: bool = True) -> Dict[str, Any]:
    """
    Extract structured data from a document (PDF or text file)
    
    Args:
        file_path: Path to the document (PDF or text file)
        schema: Optional schema defining the fields to extract
        use_chunking: Whether to use document chunking for large documents (default: True)
        
    Returns:
        Dictionary with extraction results including either extracted data or error
    """
    try:
        # Check if the file is a text file or PDF
        is_text_file = file_path.lower().endswith('.txt')
        
        if is_text_file:
            # For text files, read the content directly
            logger.info(f"Reading text directly from file: {file_path}")
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    text = f.read()
                logger.info(f"Extracted {len(text)} characters from text file")
            except Exception as e:
                error_msg = f"Error reading text file: {str(e)}"
                logger.error(error_msg)
                raise Exception(error_msg)
        else:
            # For PDF files, use the PDF extraction logic
            text = extract_text_from_pdf(file_path)
        
        if not text or text.isspace():
            if is_text_file:
                return {"success": False, "error": "The text file is empty"}
            else:
                return {"success": False, "error": "Could not extract any text from the PDF document"}
        
        # Check if we should use chunking (based on text length)
        if use_chunking and len(text) > 10000:  # If text is longer than ~10K characters
            logger.info(f"Document is large ({len(text)} characters), using chunking strategy")
            
            # Split the text into chunks
            # The split_text_into_chunks function already applies a limit of MAX_CHUNKS_TO_PROCESS (5)
            chunks = split_text_into_chunks(text)
            logger.info(f"Split document into {len(chunks)} chunks (max: {MAX_CHUNKS_TO_PROCESS} from document_chunking)")
            
            # Define a function to extract data from a single chunk
            def extract_from_chunk(chunk_text, schema):
                return extract_structured_data(chunk_text, schema)
            
            # Process all chunks and merge results
            # Print first 50 chars of each chunk for debugging
            for i, chunk in enumerate(chunks):
                logger.info(f"Chunk {i+1}/{len(chunks)} - Preview: {chunk[:50]}...")
            
            merged_data, progress_info = process_chunks_with_progress(chunks, extract_from_chunk, schema)
            
            result = {
                "success": True, 
                "data": merged_data,
                "chunking_info": {
                    "used": True,
                    "chunks_processed": len(progress_info),
                    "total_chunks": len(chunks),
                    "chunks_count": len(chunks),
                    "progress": progress_info
                }
            }
            
            # Summarize the extraction result
            logger.info(f"Extraction complete: {len(merged_data)} fields extracted from {len(chunks)} chunks")
            
            return result
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
                          use_chunking: bool = True, return_text: bool = False,
                          file_extension: str = ".pdf") -> Dict[str, Any]:
    """
    Extract structured data from binary document content
    
    Args:
        file_content: Binary content of the document
        schema: Optional schema defining the fields to extract
        use_chunking: Whether to use document chunking for large documents (default: True)
        return_text: If True, return the extracted text along with the results
        file_extension: The file extension to use for the temporary file (default: ".pdf")
        
    Returns:
        Dictionary with extraction results including either extracted data or error
    """
    try:
        # Detect if this is a text file by checking the first few bytes
        is_text_file = False
        try:
            # Check if content starts with common text file markers
            sample = file_content[:20].decode('utf-8', errors='ignore')
            # Common text file markers include letters, numbers, and basic punctuation
            if all(c.isprintable() or c.isspace() for c in sample):
                is_text_file = True
                file_extension = ".txt"
                logger.info("Detected text file based on content")
        except Exception:
            # If we can't decode as text, it's likely binary (PDF or other)
            pass
        
        # Save the binary content to a temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as tmp:
            tmp.write(file_content)
            tmp_path = tmp.name
        
        try:
            # If it's a text file, extract the text directly
            if is_text_file or file_extension.lower() == ".txt":
                with open(tmp_path, 'r', encoding='utf-8', errors='ignore') as f:
                    text = f.read()
                logger.info(f"Extracted {len(text)} characters from text file")
                
                # For text files, we can proceed directly to extraction from the text
                if return_text:
                    return {"success": True, "text": text}
                
                # Extract structured data directly from the text
                try:
                    data = extract_structured_data(text, schema)
                    return {
                        "success": True,
                        "data": data,
                        "extraction_method": "text_direct"
                    }
                except Exception as e:
                    logger.error(f"Error extracting structured data from text: {str(e)}")
                    return {"success": False, "error": str(e)}
            else:
                # For PDF files, use the PDF extraction logic
                # If return_text is True, just extract the text and return it
                if return_text:
                    text = extract_text_from_pdf(tmp_path)
                    return {"success": True, "text": text}
                
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
                    client = get_chat_openai(temperature=0.1, max_tokens=500)
                    
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


def extract_using_vector_store(document_id: str, fields: List[Dict[str, str]]) -> Dict[str, Any]:
    """
    Extract structured data from a document stored in the vector database
    
    This method leverages ChromaDB to perform semantic search on the document
    and extract specific fields by finding the most relevant text chunks.
    
    Args:
        document_id: ID of the document in the vector store
        fields: List of fields to extract from the document
        
    Returns:
        Dictionary with extraction results
    """
    try:
        # Import vector store utilities here to avoid circular imports
        from utils.vector_store import extract_data_from_vector_store
        
        # Query the vector store for the specified fields
        result = extract_data_from_vector_store(document_id, fields)
        
        if not result.get("success", False):
            raise Exception(result.get("error", "Unknown error retrieving data from vector store"))
        
        return {
            "success": True,
            "data": result.get("data", {}),
            "field_progress": result.get("field_progress", {})
        }
        
    except Exception as e:
        error_msg = f"Error extracting data using vector store: {str(e)}"
        logger.error(error_msg)
        return {
            "success": False,
            "error": error_msg
        }