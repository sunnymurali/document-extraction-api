"""
Test FAISS Vector Store Integration

This script tests the FAISS vector store functions in our document extraction API.
"""

import os
import time
import sys
import logging
from pathlib import Path

# Set up logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Import the vector store functions from utils
try:
    from utils.vector_store import (
        get_embeddings, 
        get_vector_store, 
        add_document_to_vector_store, 
        extract_data_from_vector_store,
        list_documents_in_vector_store
    )
    logger.info("Successfully imported vector store functions")
except ImportError as e:
    logger.error(f"Error importing vector store functions: {str(e)}")
    sys.exit(1)

def test_faiss_vector_store():
    """Test the FAISS vector store implementation"""
    try:
        logger.info("Starting FAISS vector store test")
        
        # Generate a unique test document ID
        document_id = f"test_{int(time.time())}"
        collection_name = f"doc_{document_id}"
        
        # Get sample document
        sample_path = Path("sample_finance.txt")
        if not sample_path.exists():
            logger.error(f"Sample file {sample_path} not found")
            return False
        
        with open(sample_path, "rb") as f:
            file_content = f.read()
        
        # Test adding document to vector store
        logger.info(f"Adding document {document_id} to vector store")
        result = add_document_to_vector_store(document_id, file_content, "sample_finance.txt")
        
        if not result.get("success", False):
            logger.error(f"Failed to add document: {result.get('error')}")
            return False
        
        logger.info(f"Successfully added document with {result.get('chunks')} chunks")
        
        # Test listing documents
        logger.info("Listing documents in vector store")
        docs = list_documents_in_vector_store()
        logger.info(f"Found {docs.get('document_count')} documents")
        
        # Check if our test document is in the list
        if document_id not in docs.get("documents", []):
            logger.error(f"Test document {document_id} not found in document list")
            return False
        
        # Test extracting data
        logger.info("Extracting data from vector store")
        fields = [
            {"name": "revenue", "description": "Total revenue or sales figure of the company"},
            {"name": "net_income", "description": "Net income or profit after tax"}
        ]
        
        extraction_result = extract_data_from_vector_store(document_id, fields)
        
        if not extraction_result.get("success", False):
            logger.error(f"Failed to extract data: {extraction_result.get('error')}")
            return False
        
        logger.info("Successfully extracted data:")
        for field_name, value in extraction_result.get("data", {}).items():
            logger.info(f"  {field_name}: {value}")
        
        logger.info("FAISS vector store test completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"Error in FAISS vector store test: {str(e)}")
        return False

if __name__ == "__main__":
    success = test_faiss_vector_store()
    if success:
        logger.info("All tests passed successfully")
        sys.exit(0)
    else:
        logger.error("Test failed")
        sys.exit(1)