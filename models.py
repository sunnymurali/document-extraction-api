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
    from document_extractor import extract_from_binary_data, extract_structured_data
    
    # Field-specific extraction locks to prevent race conditions
    field_locks = {}
    
    # Create a dictionary to store individual field extraction results
    field_results = {}
    
    # Set up field extraction status tracking
    if document_id not in extraction_results:
        extraction_results[document_id] = {
            "document_id": document_id,
            "success": False,
            "data": {},
            "error": None,
            "completed_time": None
        }
    
    def extract_single_field(field_name, field_description, text_content):
        """Extract a single field from the document text"""
        try:
            logger.info(f"Starting extraction for field: {field_name}")
            
            # Update field status to processing
            with field_locks.get(field_name, threading.Lock()):
                document_store[document_id]["extraction_status"][field_name] = "processing"
            
            # Create a schema for just this one field
            field_schema = {
                "fields": [
                    {"name": field_name, "description": field_description}
                ]
            }
            
            # Extract just this one field
            field_result = extract_structured_data(text_content, field_schema)
            
            # Store the result for this field
            with field_locks.get(field_name, threading.Lock()):
                # Update the main extraction results for this field
                if field_name in field_result:
                    extraction_results[document_id]["data"][field_name] = field_result[field_name]
                    field_results[field_name] = field_result[field_name]
                else:
                    # Handle case where field wasn't found but no error occurred
                    extraction_results[document_id]["data"][field_name] = None
                    field_results[field_name] = None
                
                # Mark this field as completed
                document_store[document_id]["extraction_status"][field_name] = "completed"
            
            logger.info(f"Completed extraction for field: {field_name}")
            
        except Exception as e:
            logger.error(f"Error extracting field {field_name}: {str(e)}")
            
            with field_locks.get(field_name, threading.Lock()):
                # Mark this field as failed
                document_store[document_id]["extraction_status"][field_name] = "failed"
                # Still store null for this field since it failed
                extraction_results[document_id]["data"][field_name] = None
                field_results[field_name] = None
    
    def extraction_worker():
        try:
            # Update document status to processing
            document_store[document_id]["status"] = "processing"
            
            # Get the binary content
            file_content = document_binary_store[document_id]
            
            # First, extract the text content from the document
            # This avoids re-parsing the PDF for each field
            if use_chunking:
                # Process chunking once to get text content
                from utils.document_chunking import split_text_into_chunks
                text_content, chunking_info = extract_from_binary_data(file_content, None, False, return_text=True)
                text_content = text_content.get("text", "")
            else:
                # Get text content without chunking
                text_content = extract_from_binary_data(file_content, None, False, return_text=True)
                text_content = text_content.get("text", "")
            
            # If we don't have a schema with fields, fall back to standard extraction
            if not schema or "fields" not in schema:
                # Extract data from the document using the normal method
                result = extract_from_binary_data(file_content, schema, use_chunking)
                
                # Update document status
                document_store[document_id]["status"] = "completed" if result.get("success", False) else "failed"
                if not result.get("success", False) and "error" in result:
                    document_store[document_id]["error"] = result["error"]
                
                # Store the extraction result
                extraction_results[document_id] = {
                    "document_id": document_id,
                    "success": result.get("success", False),
                    "data": result.get("data", {}),
                    "error": result.get("error"),
                    "completed_time": time.time()
                }
                
                # Update progress for all fields
                if result.get("success", False) and "data" in result:
                    fields = result["data"].keys()
                    for field in fields:
                        document_store[document_id]["extraction_status"][field] = "completed"
            else:
                # Process each field in a separate thread for parallel extraction
                field_threads = []
                
                # Set up the status for each field
                for field in schema["fields"]:
                    field_name = field["name"]
                    field_description = field.get("description", "")
                    
                    # Initialize status for this field
                    document_store[document_id]["extraction_status"][field_name] = "pending"
                    field_locks[field_name] = threading.Lock()
                    
                    # Create a thread for this field
                    field_thread = threading.Thread(
                        target=extract_single_field,
                        args=(field_name, field_description, text_content)
                    )
                    field_thread.daemon = True
                    field_threads.append(field_thread)
                
                # Start all field extraction threads
                for thread in field_threads:
                    thread.start()
                
                # Wait for all field extractions to complete (with timeout)
                for thread in field_threads:
                    thread.join(timeout=300)  # 5-minute timeout per field
                
                # Check if all fields are completed or failed
                all_completed = True
                for field in schema["fields"]:
                    field_name = field["name"]
                    field_status = document_store[document_id]["extraction_status"].get(field_name, "pending")
                    if field_status not in ["completed", "failed"]:
                        all_completed = False
                        break
                
                # Update the final document status
                if all_completed:
                    document_store[document_id]["status"] = "completed"
                    extraction_results[document_id]["success"] = True
                    extraction_results[document_id]["completed_time"] = time.time()
                    
                    # Final cleanup of any invalid or empty values
                    final_data = {}
                    for field_name, field_value in field_results.items():
                        final_data[field_name] = field_value
                    
                    extraction_results[document_id]["data"] = final_data
                else:
                    document_store[document_id]["status"] = "failed"
                    document_store[document_id]["error"] = "Some fields failed to extract within the time limit"
                    extraction_results[document_id]["success"] = False
                    extraction_results[document_id]["error"] = "Some fields failed to extract within the time limit"
                    extraction_results[document_id]["completed_time"] = time.time()
            
            logger.info(f"Document {document_id} extraction completed with status: {document_store[document_id]['status']}")
            
            # Remove the document from active jobs
            if document_id in active_jobs:
                del active_jobs[document_id]
            
            # Call the callback if provided
            if callback:
                callback(document_id, extraction_results[document_id])
                
        except Exception as e:
            # Update document status to failed
            document_store[document_id]["status"] = "failed"
            document_store[document_id]["error"] = str(e)
            
            logger.error(f"Error extracting data from document {document_id}: {e}")
            
            # Update the extraction results
            extraction_results[document_id]["success"] = False
            extraction_results[document_id]["error"] = str(e)
            extraction_results[document_id]["completed_time"] = time.time()
            
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