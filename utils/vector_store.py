"""
Vector Storage and Retrieval 

This module provides utilities for storing and retrieving document content using 
FAISS as a vector database. It handles document ingestion, chunking, and semantic search.
It includes rate limiting to prevent 429 errors from OpenAI API.
"""

import os
import time
import json
import logging
import tempfile
from typing import Dict, List, Optional, Any, Tuple, Union
import uuid
import threading
from time import sleep

from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import OpenAIEmbeddings
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import AzureOpenAIEmbeddings
from langchain_core.embeddings import Embeddings

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
CHUNK_SIZE = 1500
CHUNK_OVERLAP = 200

# Rate limiting settings (requests per minute)
RPM_LIMIT = 60  # Default 60 RPM for standard OpenAI API
DELAY_BETWEEN_REQUESTS = 1.0  # Default delay of 1 second between requests
BATCH_SIZE = 10  # Process 10 chunks at a time

# Document storage with metadata
document_metadata = {}

# Lock for thread-safe rate limiting
rate_limit_lock = threading.Lock()
last_request_time = 0.0

class RateLimitedEmbeddings(Embeddings):
    """
    A wrapper for OpenAI embeddings that adds rate limiting
    to prevent 429 Too Many Requests errors
    """
    
    def __init__(self, wrapped_embeddings: Embeddings, rpm_limit: int = RPM_LIMIT):
        """
        Initialize with a wrapped embeddings provider and rate limit
        
        Args:
            wrapped_embeddings: The embeddings provider to wrap
            rpm_limit: Requests per minute limit (default: 60)
        """
        self.wrapped_embeddings = wrapped_embeddings
        self.rpm_limit = rpm_limit
        self.delay_seconds = 60.0 / rpm_limit
        self.last_request_time = 0
        self.lock = threading.Lock()
        
    def _wait_for_rate_limit(self):
        """Wait if necessary to comply with rate limits"""
        with self.lock:
            current_time = time.time()
            time_since_last_request = current_time - self.last_request_time
            
            if time_since_last_request < self.delay_seconds:
                sleep_time = self.delay_seconds - time_since_last_request
                logger.debug(f"Rate limiting: sleeping for {sleep_time:.2f} seconds")
                time.sleep(sleep_time)
            
            self.last_request_time = time.time()
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        Embed documents with rate limiting
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of embeddings vectors
        """
        self._wait_for_rate_limit()
        return self.wrapped_embeddings.embed_documents(texts)
    
    def embed_query(self, text: str) -> List[float]:
        """
        Embed a query with rate limiting
        
        Args:
            text: Query text to embed
            
        Returns:
            Embedding vector
        """
        self._wait_for_rate_limit()
        return self.wrapped_embeddings.embed_query(text)


def get_embeddings(use_rate_limiting: bool = True):
    """
    Get OpenAI embeddings model with error handling and optional rate limiting
    
    Args:
        use_rate_limiting: Whether to apply rate limiting to embeddings (default: True)
    
    Returns:
        Embeddings model (rate-limited if specified)
    """
    # First try Azure OpenAI embeddings
    if os.environ.get("AZURE_OPENAI_API_KEY") and os.environ.get("AZURE_OPENAI_ENDPOINT"):
        try:
            # Note: Azure OpenAI needs a specific deployment name for embeddings
            # By default, use the same deployment name as the chat model or a specific embeddings deployment
            embeddings_deployment = os.environ.get("AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT") or os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME")
            
            logger.info(f"Initializing Azure OpenAI embeddings with deployment: {embeddings_deployment}")
            from langchain_openai import AzureOpenAIEmbeddings
            
            embeddings = AzureOpenAIEmbeddings(
                azure_deployment=embeddings_deployment,
                openai_api_version=os.environ.get("AZURE_OPENAI_API_VERSION"),
                azure_endpoint=os.environ.get("AZURE_OPENAI_ENDPOINT"),
                api_key=os.environ.get("AZURE_OPENAI_API_KEY")
            )
            
            # Test the Azure embeddings
            logger.info("Testing Azure OpenAI embeddings connection")
            _ = embeddings.embed_query("test")
            logger.info("Successfully initialized Azure OpenAI embeddings")
            
            # Apply rate limiting if specified
            if use_rate_limiting:
                # Azure has higher limits than standard OpenAI, adjust accordingly
                azure_rpm = int(os.environ.get("AZURE_OPENAI_RPM", "240"))  # Default 240 RPM for Azure
                logger.info(f"Applying rate limiting to Azure OpenAI embeddings (RPM: {azure_rpm})")
                return RateLimitedEmbeddings(embeddings, rpm_limit=azure_rpm)
            return embeddings
            
        except Exception as e:
            logger.error(f"Error initializing Azure OpenAI embeddings, will fall back to standard OpenAI: {str(e)}")
    else:
        logger.info("Azure OpenAI credentials not fully configured, will try standard OpenAI")
    
    # Try standard OpenAI embeddings as fallback
    if os.environ.get("OPENAI_API_KEY"):
        try:
            logger.info("Falling back to standard OpenAI embeddings")
            model = "text-embedding-3-small"  # Latest embeddings model
            embeddings = OpenAIEmbeddings(
                model=model,
                openai_api_key=os.environ.get("OPENAI_API_KEY")
            )
            # Test the embeddings with a simple query
            logger.info("Testing OpenAI embeddings connection")
            _ = embeddings.embed_query("test")
            logger.info("Successfully initialized standard OpenAI embeddings")
            
            # Apply rate limiting if specified
            if use_rate_limiting:
                openai_rpm = int(os.environ.get("OPENAI_RPM", str(RPM_LIMIT)))
                logger.info(f"Applying rate limiting to standard OpenAI embeddings (RPM: {openai_rpm})")
                return RateLimitedEmbeddings(embeddings, rpm_limit=openai_rpm)
            return embeddings
            
        except Exception as e:
            logger.error(f"Error initializing standard OpenAI embeddings: {str(e)}")
    else:
        logger.error("No OPENAI_API_KEY set for fallback")
    
    # If we get here, we couldn't initialize any embeddings service
    logger.error("Failed to initialize any embeddings service")
    raise Exception("Failed to initialize Azure OpenAI or standard OpenAI embeddings. Check your API keys and configuration.")


def get_vector_store(collection_name):
    """Get vector store for the given collection name"""
    try:
        embeddings = get_embeddings()
        
        # Create a path for this specific collection's FAISS index
        index_path = os.path.join(VECTOR_STORE_DIR, collection_name)
        os.makedirs(index_path, exist_ok=True)
        
        # Check if a FAISS index already exists for this collection
        index_file = os.path.join(index_path, "index.faiss")
        if os.path.exists(index_file):
            logger.info(f"Loading existing FAISS index for {collection_name}")
            vector_store = FAISS.load_local(
                index_path, 
                embeddings, 
                allow_dangerous_deserialization=True  # This is safe as we control the creation of these files
            )
        else:
            logger.info(f"Creating new FAISS index for {collection_name}")
            # Create a new empty FAISS index
            vector_store = FAISS.from_texts(["placeholder"], embeddings, metadatas=[{"source": "placeholder"}])
            # Save the empty index
            vector_store.save_local(index_path)
        
        return vector_store
    except Exception as e:
        logger.error(f"Error getting vector store: {str(e)}")
        raise


def add_document_to_vector_store(document_id: str, file_content: bytes, file_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Add a document to the vector store
    
    Args:
        document_id: Unique ID for the document
        file_content: Binary content of the document
        file_name: Original filename (used for file type detection)
        
    Returns:
        Dictionary with ingestion results
    """
    tmp_path = None
    
    try:
        # Detect if this is a PDF file by checking the header or using filename
        is_pdf = False
        
        # Check if it's a PDF by file header
        if file_content.startswith(b'%PDF') or b'%PDF-' in file_content[:1024]:
            is_pdf = True
            logger.info("Detected as PDF file based on content")
        
        # Check if it's a PDF by filename
        if file_name and file_name.lower().endswith('.pdf'):
            is_pdf = True
            logger.info(f"Detected as PDF file based on filename: {file_name}")
            
        # Log file information for debugging
        logger.info(f"File type detection: is_pdf={is_pdf}, file_name={file_name}")
        if not is_pdf:
            # Try to see what the first few bytes look like for debugging
            logger.info(f"File header preview: {file_content[:50]!r}")
        
        start_time = time.time()
        collection_name = f"doc_{document_id}"
        
        # Process document based on file type
        if is_pdf:
            # Create a temporary file for the PDF
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
                tmp.write(file_content)
                tmp_path = tmp.name
            
            logger.info(f"Loading PDF file {tmp_path}")
            loader = PyPDFLoader(tmp_path)
            pages = loader.load()
            
        else:
            # Process as text content directly without using TextLoader
            try:
                # Try to decode as UTF-8 first
                text_content = file_content.decode('utf-8', errors='replace')
                logger.info(f"Processing text content of size {len(text_content)} characters")
                
                # Create a document with the text content
                from langchain_core.documents import Document
                pages = [Document(page_content=text_content, metadata={"source": f"text-{document_id}"})]
                
            except Exception as text_error:
                logger.error(f"Error processing text content: {str(text_error)}")
                return {"success": False, "error": f"Error processing text content: {str(text_error)}", "document_id": document_id}
        
        # Store metadata about the document
        document_metadata[document_id] = {
            "title": collection_name,
            "pages": len(pages),
            "added_at": time.time(),
            "chunks": 0
        }
        
        # Split the document into chunks
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
            separators=["\n\n", "\n", ".", " ", ""],
            length_function=len,
        )
        
        chunks = text_splitter.split_documents(pages)
        
        # Update metadata
        document_metadata[document_id]["chunks"] = len(chunks)
        logger.info(f"Split document into {len(chunks)} chunks")
        
        # Initialize vector store
        vector_store = get_vector_store(collection_name)
        
        # Remove placeholder document if it exists (from empty index initialization)
        # FAISS doesn't support delete by id, so we create a new one with the real content
        
        # Create path for this specific collection's FAISS index
        index_path = os.path.join(VECTOR_STORE_DIR, collection_name)
        
        # For FAISS, we need to create a new vector store from the chunks with rate limiting
        embeddings = get_embeddings(use_rate_limiting=True)
        
        # Process chunks in batches to avoid rate limits
        batch_size = int(os.environ.get("BATCH_SIZE", str(BATCH_SIZE)))
        total_chunks = len(chunks)
        
        logger.info(f"Processing {total_chunks} chunks in batches of {batch_size}")
        
        # Initialize an empty vector store with the first chunk
        if total_chunks > 0:
            # Start with the first chunk
            first_batch = chunks[:1]
            vector_store = FAISS.from_documents(first_batch, embeddings)
            logger.info(f"Created initial FAISS store with 1 chunk")
            
            # Process remaining chunks in batches
            remaining_chunks = chunks[1:]
            for i in range(0, len(remaining_chunks), batch_size):
                batch = remaining_chunks[i:i+batch_size]
                
                logger.info(f"Processing batch {i//batch_size + 1} with {len(batch)} chunks (total progress: {min(i+1+batch_size, total_chunks)}/{total_chunks})")
                
                # Add this batch to the vector store
                if batch:
                    time.sleep(DELAY_BETWEEN_REQUESTS)  # Add delay between batches
                    vector_store.add_documents(batch)
            
            logger.info(f"Finished processing all {total_chunks} chunks")
        else:
            # Empty document, create a placeholder index
            vector_store = FAISS.from_texts(["placeholder"], embeddings, metadatas=[{"source": "placeholder"}])
            logger.warning("Document produced no chunks, created placeholder index")
            
        # Save the completed index
        vector_store.save_local(index_path)
        logger.info(f"Added {total_chunks} chunks to FAISS vector store")
        
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
        logger.error(f"Error adding document to vector store: {str(e)}")
        return {"success": False, "error": str(e), "document_id": document_id}
        
    finally:
        # Clean up the temporary file
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except Exception as cleanup_error:
                logger.warning(f"Error cleaning up temporary file: {str(cleanup_error)}")


def extract_data_from_vector_store(document_id: str, fields: List[Dict[str, str]], 
                                  top_k_chunks: int = 3) -> Dict[str, Any]:
    """
    Extract data from a document in the vector store
    
    Args:
        document_id: ID of the document
        fields: List of fields to extract with their descriptions
        top_k_chunks: Number of top chunks to retrieve per field
        
    Returns:
        Dictionary with extracted data
    """
    try:
        if document_id not in document_metadata:
            return {"success": False, "error": f"Document {document_id} not found in vector store"}
        
        collection_name = f"doc_{document_id}"
        # Use rate-limited embeddings for field extraction too
        vector_store = get_vector_store(collection_name)
        
        # Dictionary to store extraction results
        extracted_data = {}
        field_progress = {}
        
        # Add delay between field processing
        delay_between_fields = float(os.environ.get("DELAY_BETWEEN_FIELDS", "0.5"))
        
        # Process each field with its own query
        for field in fields:
            field_name = field["name"]
            field_description = field.get("description", "")
            
            # Update progress
            field_progress[field_name] = "processing"
            
            # Create a targeted query for this field
            query = f"Extract information about {field_name}: {field_description}"
            
            try:
                # Retrieve relevant chunks from vector store for this field
                relevant_chunks = vector_store.similarity_search(query, k=top_k_chunks)
                
                if not relevant_chunks:
                    extracted_data[field_name] = None
                    field_progress[field_name] = "completed"
                    continue
                
                # Combine the text from all chunks
                combined_text = "\n\n".join([chunk.page_content for chunk in relevant_chunks])
                
                # Use OpenAI to extract the specific field from the combined text
                from document_extractor import extract_structured_data
                
                # Create a schema just for this field
                field_schema = {
                    "fields": [field]
                }
                
                # Extract the field
                extracted_field = extract_structured_data(combined_text, field_schema)
                
                # Store the extraction result
                if field_name in extracted_field:
                    extracted_data[field_name] = extracted_field[field_name]
                else:
                    extracted_data[field_name] = None
                
                # Update progress
                field_progress[field_name] = "completed"
                
                # Add delay between field processing to avoid rate limits
                time.sleep(delay_between_fields)
                
            except Exception as e:
                logger.error(f"Error extracting field {field_name}: {str(e)}")
                extracted_data[field_name] = None
                field_progress[field_name] = "failed"
        
        return {
            "success": True,
            "document_id": document_id,
            "data": extracted_data,
            "field_progress": field_progress
        }
    
    except Exception as e:
        logger.error(f"Error extracting data from vector store: {str(e)}")
        return {"success": False, "error": str(e), "document_id": document_id}


def get_document_status(document_id: str) -> Dict[str, Any]:
    """
    Get status information about a document in the vector store
    
    Args:
        document_id: ID of the document
        
    Returns:
        Dictionary with document status
    """
    if document_id not in document_metadata:
        return {"success": False, "error": f"Document {document_id} not found in vector store"}
    
    return {
        "success": True,
        "document_id": document_id,
        "metadata": document_metadata[document_id]
    }


def delete_document_from_vector_store(document_id: str) -> Dict[str, Any]:
    """
    Delete a document from the vector store
    
    Args:
        document_id: ID of the document
        
    Returns:
        Dictionary with deletion results
    """
    try:
        if document_id not in document_metadata:
            return {"success": False, "error": f"Document {document_id} not found in vector store"}
        
        collection_name = f"doc_{document_id}"
        index_path = os.path.join(VECTOR_STORE_DIR, collection_name)
        
        # For FAISS, we need to delete the index files 
        # FAISS doesn't have a delete_collection method, so we remove the directory
        if os.path.exists(index_path):
            import shutil
            shutil.rmtree(index_path)
            logger.info(f"Removed FAISS index directory for {collection_name}")
        
        # Remove metadata
        del document_metadata[document_id]
        
        return {
            "success": True,
            "document_id": document_id,
            "message": f"Document {document_id} deleted from vector store"
        }
    
    except Exception as e:
        logger.error(f"Error deleting document from vector store: {str(e)}")
        return {"success": False, "error": str(e), "document_id": document_id}


def list_documents_in_vector_store() -> Dict[str, Any]:
    """
    List all documents in the vector store
    
    Returns:
        Dictionary with list of documents
    """
    return {
        "success": True,
        "documents": list(document_metadata.keys()),
        "document_count": len(document_metadata),
        "metadata": document_metadata
    }