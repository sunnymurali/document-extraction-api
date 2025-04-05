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
    Store a document in the document store and add it to ChromaDB vector store
    
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
            "status": "indexing",  # Changed from 'pending' to indicate vectorization
            "extraction_status": {},
            "error": None
        }
        
        # Store the binary content
        document_binary_store[document_id] = file_content
        
        logger.info(f"Document {document_id} ({filename}) stored successfully, starting vectorization")
        
        # Import inside function to avoid circular imports
        from utils.vector_store import add_document_to_vector_store
        
        # Start a background thread to add the document to the vector store
        def vectorization_worker():
            try:
                # Add the document to the vector store
                result = add_document_to_vector_store(document_id, file_content)
                
                if result.get("success", False):
                    # Update document status to indicate successful vectorization
                    document_store[document_id]["status"] = "ready"
                    logger.info(f"Document {document_id} vectorized successfully with {result.get('chunks', 0)} chunks")
                else:
                    # Update document status to indicate failed vectorization
                    document_store[document_id]["status"] = "failed"
                    document_store[document_id]["error"] = result.get("error", "Unknown error during vectorization")
                    logger.error(f"Error vectorizing document {document_id}: {result.get('error')}")
            except Exception as e:
                # Update document status to indicate failed vectorization
                document_store[document_id]["status"] = "failed"
                document_store[document_id]["error"] = str(e)
                logger.error(f"Error in vectorization worker for document {document_id}: {str(e)}")
        
        # Start the vectorization in a background thread
        thread = threading.Thread(target=vectorization_worker)
        thread.daemon = True
        thread.start()
        
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
    Extract data from a document asynchronously using ChromaDB vector storage
    
    This function supports both PDF and text files. It first tries to use the vector store
    for extraction, but falls back to direct extraction if there are issues with the vector store.
    
    Args:
        document_id: ID of the document
        schema: Optional schema defining the fields to extract
        use_chunking: Whether to use document chunking for large documents (ignored when using vector store)
        callback: Optional callback function to call when extraction is complete
    """
    # Import here to avoid circular imports
    from document_extractor import extract_structured_data, extract_document_data
    from utils.vector_store import extract_data_from_vector_store
    
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
    
    def extraction_worker():
        try:
            # Update document status to processing
            document_store[document_id]["status"] = "processing"
            
            # If we don't have a schema with fields, we can't use the vector store effectively
            if not schema or "fields" not in schema:
                error_msg = "A schema with fields is required for extraction"
                document_store[document_id]["status"] = "failed"
                document_store[document_id]["error"] = error_msg
                extraction_results[document_id]["success"] = False
                extraction_results[document_id]["error"] = error_msg
                extraction_results[document_id]["completed_time"] = time.time()
                
                logger.error(f"Error extracting data from document {document_id}: {error_msg}")
                
                # Call the callback if provided
                if callback:
                    callback(document_id, {"success": False, "error": error_msg})
                return
            
            # Try using vector store first, with fallback to direct extraction
            logger.info(f"Attempting to extract data from document {document_id} using vector store")
            
            # Check if document binary content is available
            if document_id not in document_binary_store:
                error_msg = f"Document binary content not found for {document_id}"
                document_store[document_id]["status"] = "failed"
                document_store[document_id]["error"] = error_msg
                extraction_results[document_id]["success"] = False
                extraction_results[document_id]["error"] = error_msg
                extraction_results[document_id]["completed_time"] = time.time()
                
                logger.error(error_msg)
                
                # Call the callback if provided
                if callback:
                    callback(document_id, {"success": False, "error": error_msg})
                return
            
            # Try vector store extraction first
            try:
                # Check if status indicates we should use vector store
                if document_store[document_id].get("status") in ["ready", "processing"]:
                    logger.info(f"Using vector store extraction for document {document_id}")
                    result = extract_data_from_vector_store(document_id, schema["fields"])
                    
                    if result.get("success", False):
                        # Extraction succeeded with vector store
                        document_store[document_id]["status"] = "completed"
                        extraction_results[document_id]["success"] = True
                        extraction_results[document_id]["data"] = result.get("data", {})
                        extraction_results[document_id]["completed_time"] = time.time()
                        
                        # Update extraction status for each field
                        field_progress = result.get("field_progress", {})
                        for field_name, status in field_progress.items():
                            document_store[document_id]["extraction_status"][field_name] = status
                        
                        logger.info(f"Document {document_id} extraction completed successfully using vector store")
                        
                        # Remove the document from active jobs
                        if document_id in active_jobs:
                            del active_jobs[document_id]
                        
                        # Call the callback if provided
                        if callback:
                            callback(document_id, extraction_results[document_id])
                        return
                    else:
                        # Vector store extraction failed, continue to fallback
                        logger.warning(f"Vector store extraction failed for document {document_id}, falling back to direct extraction")
                else:
                    logger.warning(f"Document {document_id} not ready for vector extraction (status: {document_store[document_id].get('status')}), using fallback")
            except Exception as e:
                logger.warning(f"Vector store extraction error for document {document_id}: {str(e)}, using fallback")
            
            # Fallback to direct extraction if vector store failed or document is not ready
            logger.info(f"Using fallback direct extraction for document {document_id}")
            
            # Extract data directly from the document
            file_content = document_binary_store[document_id]
            
            # Write content to a temporary file
            import tempfile
            import os
            
            # Detect if this is a text file by checking the first few bytes
            is_text_file = False
            file_extension = ".pdf"
            try:
                # Check if content starts with common text file markers
                sample = file_content[:20].decode('utf-8', errors='ignore')
                # Common text file markers include letters, numbers, and basic punctuation
                if all(c.isprintable() or c.isspace() for c in sample):
                    is_text_file = True
                    file_extension = ".txt"
                    logger.info(f"Detected text file for document {document_id} based on content")
            except Exception:
                # If we can't decode as text, it's likely binary (PDF or other)
                pass
                
            with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as tmp:
                tmp.write(file_content)
                tmp_path = tmp.name
                
            # For text files, we should update the extraction approach to handle them correctly
            if is_text_file:
                logger.info(f"Processing text file for document {document_id}: {tmp_path}")
            
            try:
                # Extract data directly
                extract_result = extract_document_data(tmp_path, schema, use_chunking)
                
                if extract_result.get("success", False):
                    # Direct extraction succeeded
                    document_store[document_id]["status"] = "completed"
                    extraction_results[document_id]["success"] = True
                    extraction_results[document_id]["data"] = extract_result.get("data", {})
                    extraction_results[document_id]["completed_time"] = time.time()
                    
                    # Update extraction status for fields
                    for field_name in schema.get("fields", []):
                        name = field_name.get("name", "") if isinstance(field_name, dict) else field_name
                        document_store[document_id]["extraction_status"][name] = "completed"
                    
                    logger.info(f"Document {document_id} extraction completed successfully using direct extraction")
                else:
                    # Direct extraction failed
                    error_msg = extract_result.get("error", "Unknown error during direct extraction")
                    document_store[document_id]["status"] = "failed"
                    document_store[document_id]["error"] = error_msg
                    extraction_results[document_id]["success"] = False
                    extraction_results[document_id]["error"] = error_msg
                    extraction_results[document_id]["completed_time"] = time.time()
                    
                    logger.error(f"Error in direct extraction for document {document_id}: {error_msg}")
            finally:
                # Clean up the temporary file
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
            
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
    
    logger.info(f"Started async extraction for document {document_id} using vector store")
    return document_id


def cleanup_document(document_id: str) -> bool:
    """
    Clean up a document from the document store and vector store
    
    Args:
        document_id: ID of the document
        
    Returns:
        True if document was cleaned up, False otherwise
    """
    try:
        # Check if the document exists
        if document_id not in document_store:
            return False
        
        # Clean up vector store
        try:
            from utils.vector_store import delete_document_from_vector_store
            vector_result = delete_document_from_vector_store(document_id)
            if not vector_result.get("success", False):
                logger.warning(f"Error cleaning up vector store for document {document_id}: {vector_result.get('error')}")
        except Exception as ve:
            logger.warning(f"Error cleaning up vector store for document {document_id}: {str(ve)}")
        
        # Remove the document from the stores
        if document_id in document_store:
            del document_store[document_id]
        
        if document_id in extraction_results:
            del extraction_results[document_id]
        
        if document_id in document_binary_store:
            del document_binary_store[document_id]
        
        # Remove from active jobs if present
        if document_id in active_jobs:
            del active_jobs[document_id]
        
        logger.info(f"Document {document_id} cleaned up successfully")
        return True
    
    except Exception as e:
        logger.error(f"Error cleaning up document {document_id}: {e}")
        return False