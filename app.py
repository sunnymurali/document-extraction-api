import os
from fastapi import FastAPI, File, UploadFile, HTTPException, Form, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import tempfile
import logging
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import traceback

from utils.pdf_extractor import extract_text_from_pdf
from utils.openai_service import extract_structured_data

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Initialize FastAPI
app = FastAPI(
    title="PDF Data Extraction API",
    description="API for extracting structured data from PDF files using OpenAI",
    version="1.0.0"
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Template directory
templates = Jinja2Templates(directory="templates")

class ExtractionResponse(BaseModel):
    """Model for the extraction response"""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

@app.get("/")
async def index(request: Request):
    """Serve the index page"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/api/extract", response_model=ExtractionResponse)
async def extract_data(
    file: UploadFile = File(...),
    extraction_schema: Optional[str] = Form(None)
):
    """
    Extract structured data from a PDF file
    
    - **file**: The PDF file to extract data from
    - **extraction_schema**: Optional JSON schema describing the data to extract
    
    Returns a JSON response with the extracted data
    """
    try:
        # Validate file type
        if not file.filename.endswith('.pdf'):
            raise HTTPException(status_code=400, detail="Only PDF files are accepted")
        
        # Save the uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
            contents = await file.read()
            temp_file.write(contents)
            temp_file_path = temp_file.name
        
        try:
            # Extract text from PDF
            logger.debug(f"Extracting text from {file.filename}")
            extracted_text = extract_text_from_pdf(temp_file_path)
            
            if not extracted_text or extracted_text.strip() == "":
                raise HTTPException(status_code=422, detail="Could not extract any text from the PDF file. The file might be encrypted, empty, or contain only images.")
            
            # Process the extracted text with OpenAI
            logger.debug("Sending text to OpenAI for structured extraction")
            structured_data = extract_structured_data(extracted_text, extraction_schema)
            
            return ExtractionResponse(success=True, data=structured_data)
            
        finally:
            # Clean up the temporary file
            os.unlink(temp_file_path)
            
    except HTTPException as e:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error during data extraction: {str(e)}")
        logger.error(traceback.format_exc())
        return ExtractionResponse(success=False, error=str(e))

# API documentation endpoints
@app.get("/api/docs")
async def get_documentation():
    """Return API documentation"""
    return {
        "endpoints": [
            {
                "path": "/api/extract",
                "method": "POST",
                "description": "Extract structured data from a PDF file",
                "parameters": [
                    {
                        "name": "file",
                        "type": "file",
                        "required": True,
                        "description": "The PDF file to extract data from"
                    },
                    {
                        "name": "extraction_schema",
                        "type": "string",
                        "required": False,
                        "description": "Optional JSON schema describing the data structure to extract"
                    }
                ],
                "response": {
                    "success": "boolean",
                    "data": "object (if success is true)",
                    "error": "string (if success is false)"
                }
            }
        ],
        "examples": {
            "basic_extraction": {
                "description": "Basic extraction without schema",
                "request": "POST /api/extract with PDF file upload",
                "response": {
                    "success": True,
                    "data": {
                        "extracted_fields": "Will depend on the PDF content"
                    }
                }
            },
            "schema_extraction": {
                "description": "Extraction with a specific schema",
                "request": "POST /api/extract with PDF file upload and schema",
                "schema_example": {
                    "fields": [
                        {"name": "invoice_number", "type": "string", "description": "The invoice number"},
                        {"name": "date", "type": "date", "description": "The invoice date"},
                        {"name": "total_amount", "type": "number", "description": "The total invoice amount"}
                    ]
                },
                "response": {
                    "success": True,
                    "data": {
                        "invoice_number": "INV-12345",
                        "date": "2023-04-15",
                        "total_amount": 1234.56
                    }
                }
            }
        }
    }
