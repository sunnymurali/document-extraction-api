"""
FastAPI Application for PDF Data Extraction
This API extracts structured data from PDF files using OpenAI models.
"""

import os
import json
import tempfile
import logging
from typing import Optional

from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn

from models import ExtractionResponse
from utils.pdf_extractor import extract_text_from_pdf_with_fallback
from utils.openai_service import extract_structured_data

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI application
app = FastAPI(
    title="PDF Data Extractor API",
    description="API for extracting structured data from PDF files using OpenAI",
    version="1.0.0",
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Set up templates
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Serve the index page"""
    return templates.TemplateResponse(
        "index.html", {"request": request, "title": "PDF Data Extractor"}
    )

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
    # Validate file is a PDF
    if not file.content_type or "pdf" not in file.content_type.lower():
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": "Uploaded file must be a PDF"}
        )
    
    try:
        # Process the file
        contents = await file.read()
        
        # Create a temporary file to process the PDF
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(contents)
            tmp_path = tmp.name
        
        try:
            # Extract text from PDF
            logger.info(f"Extracting text from PDF: {file.filename}")
            pdf_text = extract_text_from_pdf_with_fallback(tmp_path)
            
            if not pdf_text or pdf_text.isspace():
                return JSONResponse(
                    status_code=422,
                    content={"success": False, "error": "Could not extract any text from the PDF file"}
                )
            
            # Extract structured data
            logger.info("Extracting structured data with OpenAI")
            extracted_data = extract_structured_data(pdf_text, extraction_schema)
            
            # Return successful response
            return JSONResponse(
                content={"success": True, "data": extracted_data}
            )
        finally:
            # Clean up temporary file
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
    
    except Exception as e:
        logger.error(f"Error processing PDF: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": f"Error processing PDF: {str(e)}"}
        )

@app.get("/api/documentation")
async def get_documentation():
    """Return API documentation"""
    return {
        "api_version": "1.0.0",
        "endpoints": [
            {
                "path": "/",
                "method": "GET",
                "description": "Web interface for PDF data extraction"
            },
            {
                "path": "/api/extract",
                "method": "POST",
                "description": "Extract data from a PDF file",
                "parameters": [
                    {
                        "name": "file",
                        "type": "file",
                        "required": True,
                        "description": "PDF file to extract data from"
                    },
                    {
                        "name": "extraction_schema",
                        "type": "string (JSON)",
                        "required": False,
                        "description": "Schema defining the data fields to extract"
                    }
                ]
            },
            {
                "path": "/api/documentation",
                "method": "GET",
                "description": "API documentation"
            }
        ]
    }