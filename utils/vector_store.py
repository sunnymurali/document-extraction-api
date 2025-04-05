"""
Vector Storage and Retrieval 

This module provides utilities for storing and retrieving document content using 
ChromaDB as a vector database. It handles document ingestion, chunking, and semantic search.
"""

import os
import time
import json
import logging
import tempfile
from typing import Dict, List, Optional, Any, Tuple
import uuid

from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import OpenAIEmbeddings
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter

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

# Document storage with metadata
document_metadata = {}


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


def add_document_to_vector_store(document_id: str, file_content: bytes) -> Dict[str, Any]:
    """
    Add a document to the vector store
    
    Args:
        document_id: Unique ID for the document
        file_content: Binary content of the document
        
    Returns:
        Dictionary with ingestion results
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
                logger.info("Detected text file based on content")
        except Exception:
            # If we can't decode as text, it's likely binary (PDF or other)
            pass

        # Create a temporary file with the appropriate extension
        suffix = ".txt" if is_text_file else ".pdf"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(file_content)
            tmp_path = tmp.name
        
        try:
            start_time = time.time()
            collection_name = f"doc_{document_id}"
            
            # Load document with the appropriate loader
            if is_text_file:
                logger.info(f"Loading text file {tmp_path}")
                loader = TextLoader(tmp_path, encoding='utf-8')
                pages = loader.load()
            else:
                logger.info(f"Loading PDF file {tmp_path}")
                loader = PyPDFLoader(tmp_path)
                pages = loader.load()
            
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
        finally:
            # Clean up the temporary file
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
                
    except Exception as e:
        logger.error(f"Error adding document to vector store: {str(e)}")
        return {"success": False, "error": str(e), "document_id": document_id}


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
        vector_store = get_vector_store(collection_name)
        
        # Dictionary to store extraction results
        extracted_data = {}
        field_progress = {}
        
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
        vector_store = get_vector_store(collection_name)
        
        # Clear all documents in the collection
        vector_store.delete_collection()
        
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