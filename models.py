"""
Data models for the PDF extraction API
"""

import os
import json
import time
import uuid
import threading
import logging
from typing import Dict, Any, List, Optional, Union
from pydantic import BaseModel, Field

# Set up logging
logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# In-memory document store (in a real app, this would be a database)
# Dictionary mapping document IDs to their metadata and status
document_store = {}

# Dictionary mapping document IDs to their extraction results
extraction_results = {}

# Dictionary to track active extraction jobs
active_jobs = {}

# Dictionary to store document binary data (would be file system or blob storage in production)
document_binary_store = {}


class ExtractionField(BaseModel):
    """Model for a single extraction field"""
    name: str = Field(..., description="The name of the field to extract")
    description: Optional[str] = Field(None, description="Description of the field to help with extraction")


class ExtractionSchema(BaseModel):
    """Model for defining the data extraction schema"""
    fields: List[Dict[str, str]] = Field(..., description="List of fields to extract with their descriptions")


class DocumentStatus(BaseModel):
    """Model for document status"""
    id: str = Field(..., description="Unique identifier for the document")
    filename: str = Field(..., description="Original filename")
    upload_time: float = Field(..., description="Unix timestamp of upload time")
    status: str = Field(..., description="Status of the document processing (pending, processing, completed, failed)")
    extraction_status: Dict[str, str] = Field(default_factory=dict, description="Status of each field extraction")
    error: Optional[str] = Field(None, description="Error message if processing failed")


class ExtractionTask(BaseModel):
    """Model for an extraction task"""
    document_id: str
    schema: Optional[Dict[str, Any]] = None
    use_chunking: bool = True


class ExtractionResult(BaseModel):
    """Model for extraction results"""
    document_id: str = Field(..., description="ID of the document")
    success: bool = Field(..., description="Whether the extraction was successful")
    data: Optional[Dict[str, Any]] = Field(None, description="The extracted data")
    error: Optional[str] = Field(None, description="Error message if extraction failed")
    completed_time: float = Field(..., description="Unix timestamp of completion time")


class DocumentUploadResponse(BaseModel):
    """Model for document upload response"""
    success: bool = Field(..., description="Whether the upload was successful")
    document_id: Optional[str] = Field(None, description="ID of the uploaded document")
    error: Optional[str] = Field(None, description="Error message if upload failed")


def generate_document_id() -> str:
    """Generate a unique ID for a document"""
    return str(uuid.uuid4())


def store_document(filename: str, file_content: bytes) -> DocumentUploadResponse:
    """
    Store a document in the document store
    
    Args:
        filename: Original filename
        file_content: Binary content of the document
        
    Returns:
        DocumentUploadResponse with success status and document ID
    """
    try:
        # Generate a unique ID for the document
        document_id = generate_document_id()
        
        # Create metadata for the document
        document_store[document_id] = {
            "id": document_id,
            "filename": filename,
            "upload_time": time.time(),
            "status": "pending", 
            "extraction_status": {}
        }
        
        # Store the binary content
        document_binary_store[document_id] = file_content
        
        logger.info(f"Document {document_id} ({filename}) stored successfully")
        
        return DocumentUploadResponse(
            success=True,
            document_id=document_id
        )
    
    except Exception as e:
        logger.error(f"Error storing document: {e}")
        return DocumentUploadResponse(
            success=False,
            error=str(e)
        )


def get_document_status(document_id: str) -> Optional[DocumentStatus]:
    """
    Get the status of a document
    
    Args:
        document_id: ID of the document
        
    Returns:
        DocumentStatus if document exists, None otherwise
    """
    if document_id not in document_store:
        return None
    
    doc_data = document_store[document_id]
    return DocumentStatus(**doc_data)


def get_extraction_result(document_id: str) -> Optional[Dict[str, Any]]:
    """
    Get the extraction result for a document
    
    Args:
        document_id: ID of the document
        
    Returns:
        Dictionary with extraction results if available, None otherwise
    """
    if document_id not in extraction_results:
        return None
    
    return extraction_results[document_id]


def async_extract_document(document_id: str, schema: Optional[Dict[str, Any]] = None, 
                          use_chunking: bool = True, callback=None):
    """
    Extract data from a document asynchronously
    
    Args:
        document_id: ID of the document
        schema: Optional schema defining the fields to extract
        use_chunking: Whether to use document chunking for large documents
        callback: Optional callback function to call when extraction is complete
    """
    # Import here to avoid circular imports
    from document_extractor import extract_from_binary_data
    
    def extraction_worker():
        try:
            # Update document status to processing
            document_store[document_id]["status"] = "processing"
            
            # Get the binary content
            file_content = document_binary_store[document_id]
            
            # Extract data from the document
            result = extract_from_binary_data(file_content, schema, use_chunking)
            
            # Update document status
            document_store[document_id]["status"] = "completed" if result.get("success", False) else "failed"
            if not result.get("success", False) and "error" in result:
                document_store[document_id]["error"] = result["error"]
            
            # Store the extraction result
            extraction_results[document_id] = {
                "document_id": document_id,
                "success": result.get("success", False),
                "data": result.get("data"),
                "error": result.get("error"),
                "completed_time": time.time()
            }
            
            # Update progress for all fields
            if result.get("success", False) and "data" in result:
                fields = result["data"].keys()
                for field in fields:
                    document_store[document_id]["extraction_status"][field] = "completed"
            
            logger.info(f"Document {document_id} extraction completed with status: {document_store[document_id]['status']}")
            
            # Remove the document from active jobs
            if document_id in active_jobs:
                del active_jobs[document_id]
            
            # Call the callback if provided
            if callback:
                callback(document_id, result)
                
        except Exception as e:
            # Update document status to failed
            document_store[document_id]["status"] = "failed"
            document_store[document_id]["error"] = str(e)
            
            logger.error(f"Error extracting data from document {document_id}: {e}")
            
            # Remove the document from active jobs
            if document_id in active_jobs:
                del active_jobs[document_id]
            
            # Call the callback if provided
            if callback:
                callback(document_id, {"success": False, "error": str(e)})
    
    # Create a thread for extraction
    thread = threading.Thread(target=extraction_worker)
    thread.daemon = True
    
    # Store the thread in active jobs
    active_jobs[document_id] = thread
    
    # Start the thread
    thread.start()
    
    logger.info(f"Started async extraction for document {document_id}")
    return document_id


def cleanup_document(document_id: str) -> bool:
    """
    Clean up a document from the document store
    
    Args:
        document_id: ID of the document
        
    Returns:
        True if document was cleaned up, False otherwise
    """
    try:
        # Check if the document exists
        if document_id not in document_store:
            return False
        
        # Remove the document from the stores
        if document_id in document_store:
            del document_store[document_id]
        
        if document_id in extraction_results:
            del extraction_results[document_id]
        
        if document_id in document_binary_store:
            del document_binary_store[document_id]
        
        logger.info(f"Document {document_id} cleaned up successfully")
        return True
    
    except Exception as e:
        logger.error(f"Error cleaning up document {document_id}: {e}")
        return False