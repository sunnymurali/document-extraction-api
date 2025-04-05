"""
Vector Storage Service

This module provides a service for storing and retrieving document content using 
ChromaDB as a vector database, with rate limiting considerations.
"""

import os
import time
import json
import logging
import tempfile
import asyncio
import uuid
from typing import Dict, List, Optional, Any, Tuple
from concurrent.futures import ThreadPoolExecutor

from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import OpenAIEmbeddings
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter

from api.models import DocumentStatus, FieldStatus

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Directory to store vector database
VECTOR_STORE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'vector_db')
os.makedirs(VECTOR_STORE_DIR, exist_ok=True)

# Get OpenAI API Key
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY") or os.environ.get("AZURE_OPENAI_API_KEY")
if not OPENAI_API_KEY:
    logger.warning("No OpenAI API key found. Vector search may not work.")

# Define chunk sizes and overlap for document splitting
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200

# Document storage with metadata
document_metadata = {}

# Document status tracking
document_statuses = {}

# Rate limiting configuration
RATE_LIMIT_TOKENS_PER_MIN = 90000  # OpenAI rate limit for tokens per minute
MAX_PARALLEL_REQUESTS = 5  # Maximum parallel requests to OpenAI API
RATE_LIMIT_DELAY = 0.5  # Delay between API requests in seconds

# Semaphore for rate limiting
api_semaphore = asyncio.Semaphore(MAX_PARALLEL_REQUESTS)

# Thread pool for CPU-bound tasks
thread_pool = ThreadPoolExecutor(max_workers=4)


def get_embeddings():
    """Get OpenAI embeddings model with error handling"""
    try:
        # Try to use Azure OpenAI if configured
        if os.environ.get("AZURE_OPENAI_API_KEY") and os.environ.get("AZURE_OPENAI_ENDPOINT"):
            from langchain_openai import AzureOpenAIEmbeddings
            return AzureOpenAIEmbeddings(
                azure_deployment=os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME"),
                openai_api_version=os.environ.get("AZURE_OPENAI_API_VERSION"),
                azure_endpoint=os.environ.get("AZURE_OPENAI_ENDPOINT"),
                api_key=os.environ.get("AZURE_OPENAI_API_KEY"),
            )
        else:
            # Fall back to standard OpenAI
            return OpenAIEmbeddings()
    except Exception as e:
        logger.error(f"Error initializing embeddings: {str(e)}")
        raise


def get_vector_store(collection_name):
    """Get vector store for the given collection name"""
    try:
        embeddings = get_embeddings()
        
        # Create a persistent ChromaDB instance
        vector_store = Chroma(
            collection_name=collection_name,
            embedding_function=embeddings,
            persist_directory=VECTOR_STORE_DIR
        )
        
        return vector_store
    except Exception as e:
        logger.error(f"Error getting vector store: {str(e)}")
        raise


def generate_document_id() -> str:
    """Generate a unique document ID"""
    return str(uuid.uuid4())


def update_document_status(document_id: str, status: DocumentStatus, error: Optional[str] = None):
    """Update document status"""
    if document_id not in document_statuses:
        document_statuses[document_id] = {
            "document_id": document_id,
            "status": status,
            "field_statuses": {},
            "error": error
        }
    else:
        document_statuses[document_id]["status"] = status
        if error:
            document_statuses[document_id]["error"] = error


def update_field_status(document_id: str, field_name: str, status: FieldStatus, error: Optional[str] = None):
    """Update field extraction status"""
    if document_id in document_statuses:
        document_statuses[document_id]["field_statuses"][field_name] = status


def get_document_status(document_id: str) -> Optional[Dict[str, Any]]:
    """Get document status"""
    return document_statuses.get(document_id)


async def upload_document(file_content: bytes, file_name: str, document_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Upload a document to the system
    
    Args:
        file_content: Binary content of the document
        file_name: Original filename
        document_id: Optional document ID for updates
        
    Returns:
        Dictionary with upload results
    """
    try:
        # Generate document ID if not provided
        if not document_id:
            document_id = generate_document_id()
        
        # Store document metadata
        document_metadata[document_id] = {
            "filename": file_name,
            "upload_time": time.time(),
            "status": DocumentStatus.PENDING
        }
        
        # Update document status
        update_document_status(document_id, DocumentStatus.PENDING)
        
        # Create document directory
        document_dir = os.path.join(VECTOR_STORE_DIR, document_id)
        os.makedirs(document_dir, exist_ok=True)
        
        # Save document content
        file_path = os.path.join(document_dir, file_name)
        with open(file_path, 'wb') as f:
            f.write(file_content)
        
        # Store file path in metadata
        document_metadata[document_id]["file_path"] = file_path
        
        # Detect file type
        is_text_file = file_name.lower().endswith('.txt')
        document_metadata[document_id]["is_text_file"] = is_text_file
        
        return {
            "success": True,
            "document_id": document_id,
            "message": "Document uploaded successfully"
        }
    
    except Exception as e:
        logger.error(f"Error uploading document: {str(e)}")
        return {
            "success": False,
            "error": f"Error uploading document: {str(e)}"
        }


async def index_document(document_id: str) -> Dict[str, Any]:
    """
    Index a document in the vector store with rate limiting
    
    Args:
        document_id: ID of the document to index
        
    Returns:
        Dictionary with indexing results
    """
    try:
        # Check if document exists
        if document_id not in document_metadata:
            return {
                "success": False,
                "document_id": document_id,
                "error": f"Document {document_id} not found",
                "status": DocumentStatus.FAILED
            }
        
        # Update document status
        update_document_status(document_id, DocumentStatus.INDEXING)
        
        # Get document metadata
        metadata = document_metadata[document_id]
        file_path = metadata["file_path"]
        is_text_file = metadata.get("is_text_file", file_path.lower().endswith('.txt'))
        
        # Start indexing in a separate thread to not block the event loop
        loop = asyncio.get_event_loop()
        
        try:
            # Index the document in a separate thread
            result = await loop.run_in_executor(
                thread_pool, 
                lambda: _index_document_worker(document_id, file_path, is_text_file)
            )
            
            # Update status based on result
            if result["success"]:
                update_document_status(document_id, DocumentStatus.INDEXED)
            else:
                update_document_status(document_id, DocumentStatus.FAILED, result["error"])
            
            # Add status to result
            result["status"] = document_statuses[document_id]["status"]
            
            return result
        
        except Exception as e:
            error_message = f"Error indexing document: {str(e)}"
            logger.error(error_message)
            update_document_status(document_id, DocumentStatus.FAILED, error_message)
            
            return {
                "success": False,
                "document_id": document_id,
                "error": error_message,
                "status": DocumentStatus.FAILED
            }
    
    except Exception as e:
        error_message = f"Error in index_document: {str(e)}"
        logger.error(error_message)
        update_document_status(document_id, DocumentStatus.FAILED, error_message)
        
        return {
            "success": False,
            "document_id": document_id,
            "error": error_message,
            "status": DocumentStatus.FAILED
        }


def _index_document_worker(document_id: str, file_path: str, is_text_file: bool) -> Dict[str, Any]:
    """Worker function for document indexing to be run in a separate thread"""
    try:
        start_time = time.time()
        collection_name = f"doc_{document_id}"
        
        # Load document with the appropriate loader
        if is_text_file:
            logger.info(f"Loading text file {file_path}")
            loader = TextLoader(file_path, encoding='utf-8')
            pages = loader.load()
        else:
            logger.info(f"Loading PDF file {file_path}")
            loader = PyPDFLoader(file_path)
            pages = loader.load()
        
        # Update metadata
        document_metadata[document_id].update({
            "pages": len(pages),
            "indexed_at": time.time()
        })
        
        # Split the document into chunks
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
            separators=["\n\n", "\n", ".", " ", ""],
        )
        
        chunks = text_splitter.split_documents(pages)
        
        # Update metadata
        document_metadata[document_id]["chunks"] = len(chunks)
        
        # Initialize vector store
        vector_store = get_vector_store(collection_name)
        
        # Add chunks to vector store
        vector_store.add_documents(chunks)
        
        # Persist the vector store
        if hasattr(vector_store, 'persist'):
            vector_store.persist()
        
        processing_time = time.time() - start_time
        
        logger.info(f"Document {document_id} added to vector store with {len(chunks)} chunks in {processing_time:.2f} seconds")
        
        return {
            "success": True,
            "document_id": document_id,
            "chunks": len(chunks),
            "pages": len(pages),
            "processing_time": processing_time
        }
    
    except Exception as e:
        logger.error(f"Error in indexing worker: {str(e)}")
        return {
            "success": False,
            "document_id": document_id,
            "error": f"Error indexing document: {str(e)}"
        }


async def extract_field(document_id: str, field_name: str, field_description: Optional[str] = None) -> Dict[str, Any]:
    """
    Extract a single field from a document with rate limiting
    
    Args:
        document_id: ID of the document
        field_name: Name of the field to extract
        field_description: Optional description of the field
        
    Returns:
        Dictionary with extraction results
    """
    try:
        # Check if document exists
        if document_id not in document_metadata:
            return {
                "success": False,
                "document_id": document_id,
                "field_name": field_name,
                "error": f"Document {document_id} not found",
                "status": FieldStatus.FAILED
            }
        
        # Check if document is indexed
        status = document_statuses.get(document_id, {}).get("status")
        if status != DocumentStatus.INDEXED and status != DocumentStatus.COMPLETED:
            return {
                "success": False,
                "document_id": document_id,
                "field_name": field_name,
                "error": f"Document {document_id} is not indexed (status: {status})",
                "status": FieldStatus.FAILED
            }
        
        # Update field status
        update_field_status(document_id, field_name, FieldStatus.PROCESSING)
        
        # Use a semaphore to limit concurrent requests to the OpenAI API
        async with api_semaphore:
            # Rate limiting: add a small delay
            await asyncio.sleep(RATE_LIMIT_DELAY)
            
            try:
                # Extract the field using a CPU-bound thread
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    thread_pool,
                    lambda: _extract_field_worker(document_id, field_name, field_description)
                )
                
                # Update field status based on result
                if result["success"]:
                    update_field_status(document_id, field_name, FieldStatus.COMPLETED)
                else:
                    update_field_status(document_id, field_name, FieldStatus.FAILED)
                
                # Add status to result
                result["status"] = document_statuses[document_id]["field_statuses"].get(field_name, FieldStatus.FAILED)
                
                return result
            
            except Exception as e:
                error_message = f"Error extracting field {field_name}: {str(e)}"
                logger.error(error_message)
                update_field_status(document_id, field_name, FieldStatus.FAILED)
                
                return {
                    "success": False,
                    "document_id": document_id,
                    "field_name": field_name,
                    "error": error_message,
                    "status": FieldStatus.FAILED
                }
    
    except Exception as e:
        error_message = f"Error in extract_field: {str(e)}"
        logger.error(error_message)
        
        return {
            "success": False,
            "document_id": document_id,
            "field_name": field_name,
            "error": error_message,
            "status": FieldStatus.FAILED
        }


def _extract_field_worker(document_id: str, field_name: str, field_description: Optional[str] = None) -> Dict[str, Any]:
    """Worker function for field extraction to be run in a separate thread"""
    try:
        collection_name = f"doc_{document_id}"
        vector_store = get_vector_store(collection_name)
        
        # Create a targeted query for this field
        description = field_description or f"Information about {field_name}"
        query = f"Extract information about {field_name}: {description}"
        
        # Retrieve relevant chunks from vector store for this field
        relevant_chunks = vector_store.similarity_search(query, k=3)
        
        if not relevant_chunks:
            return {
                "success": True,
                "document_id": document_id,
                "field_name": field_name,
                "value": None,
                "message": "No relevant content found for this field"
            }
        
        # Combine the text from all chunks
        combined_text = "\n\n".join([chunk.page_content for chunk in relevant_chunks])
        
        # Extract the specific field from the combined text using LangChain and OpenAI
        from langchain_openai import ChatOpenAI
        from langchain_core.prompts import ChatPromptTemplate
        
        # Create a prompt for extracting the field
        prompt = ChatPromptTemplate.from_template("""
        You are an expert data extractor. Extract the value for the field {field_name} from the provided text.
        
        Field description: {field_description}
        
        Text:
        {text}
        
        Return ONLY the extracted value for {field_name}. If you cannot find the value, return null.
        If you find a value, include the units if applicable.
        """)
        
        # Create a chat model
        llm = ChatOpenAI(temperature=0, model="gpt-4o")
        
        # Create a chain
        chain = prompt | llm
        
        # Extract the value
        result = chain.invoke({
            "field_name": field_name,
            "field_description": description,
            "text": combined_text
        })
        
        # Parse the result
        extracted_value = result.content.strip()
        
        # Handle "null" responses
        if extracted_value.lower() in ["null", "none", "not found", "not available", "n/a"]:
            extracted_value = None
        
        return {
            "success": True,
            "document_id": document_id,
            "field_name": field_name,
            "value": extracted_value
        }
    
    except Exception as e:
        logger.error(f"Error in extraction worker: {str(e)}")
        return {
            "success": False,
            "document_id": document_id,
            "field_name": field_name,
            "error": f"Error extracting field: {str(e)}"
        }


async def batch_extract_fields(document_id: str, fields: List[Dict[str, str]]) -> Dict[str, Any]:
    """
    Start batch extraction of multiple fields from a document
    
    Args:
        document_id: ID of the document
        fields: List of fields to extract
        
    Returns:
        Dictionary with extraction request results
    """
    try:
        # Check if document exists
        if document_id not in document_metadata:
            return {
                "success": False,
                "document_id": document_id,
                "error": f"Document {document_id} not found",
                "status": "failed"
            }
        
        # Check if document is indexed
        status = document_statuses.get(document_id, {}).get("status")
        if status != DocumentStatus.INDEXED and status != DocumentStatus.COMPLETED:
            return {
                "success": False,
                "document_id": document_id,
                "error": f"Document {document_id} is not indexed (status: {status})",
                "status": "failed"
            }
        
        # Update document status
        update_document_status(document_id, DocumentStatus.EXTRACTING)
        
        # Start extraction tasks for each field asynchronously
        tasks = []
        for field in fields:
            field_name = field["name"]
            field_description = field.get("description")
            
            # Create task for field extraction
            task = asyncio.create_task(
                extract_field(document_id, field_name, field_description)
            )
            tasks.append(task)
        
        # Return immediately, don't wait for tasks to complete
        return {
            "success": True,
            "document_id": document_id,
            "status": "extracting",
            "message": f"Started extraction of {len(fields)} fields"
        }
    
    except Exception as e:
        error_message = f"Error starting batch extraction: {str(e)}"
        logger.error(error_message)
        
        return {
            "success": False,
            "document_id": document_id,
            "error": error_message,
            "status": "failed"
        }


def delete_document(document_id: str) -> Dict[str, Any]:
    """
    Delete a document from the system
    
    Args:
        document_id: ID of the document
        
    Returns:
        Dictionary with deletion results
    """
    try:
        # Check if document exists
        if document_id not in document_metadata:
            return {
                "success": False,
                "document_id": document_id,
                "error": f"Document {document_id} not found"
            }
        
        # Delete document from vector store
        collection_name = f"doc_{document_id}"
        try:
            vector_store = get_vector_store(collection_name)
            vector_store.delete_collection()
        except Exception as e:
            logger.error(f"Error deleting vector store collection: {str(e)}")
        
        # Delete document files
        file_path = document_metadata[document_id].get("file_path")
        if file_path and os.path.exists(file_path):
            os.unlink(file_path)
        
        # Delete document directory
        document_dir = os.path.join(VECTOR_STORE_DIR, document_id)
        if os.path.exists(document_dir):
            import shutil
            shutil.rmtree(document_dir)
        
        # Remove from metadata and status tracking
        del document_metadata[document_id]
        if document_id in document_statuses:
            del document_statuses[document_id]
        
        return {
            "success": True,
            "document_id": document_id,
            "message": f"Document {document_id} deleted successfully"
        }
    
    except Exception as e:
        logger.error(f"Error deleting document: {str(e)}")
        return {
            "success": False,
            "document_id": document_id,
            "error": f"Error deleting document: {str(e)}"
        }