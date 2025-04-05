"""
Test script for ChromaDB vector store implementation
"""

import os
import time
import logging
import sys
from utils.vector_store import (
    add_document_to_vector_store,
    extract_data_from_vector_store,
    get_document_status,
    delete_document_from_vector_store,
    list_documents_in_vector_store
)

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_vector_store_workflow():
    """Test the complete vector store workflow"""
    
    # Check if documents exist in the assets directory
    sample_docs = [
        "attached_assets/MorganStanley10K.pdf",
        "attached_assets/capitalOne10K.pdf"
    ]
    
    existing_docs = [doc for doc in sample_docs if os.path.exists(doc)]
    
    if not existing_docs:
        logger.error("No sample documents found in attached_assets directory")
        return False
    
    # Use the first available document
    document_path = existing_docs[0]
    logger.info(f"Testing with document: {document_path}")
    
    try:
        # Generate a unique document ID for testing
        document_id = f"test_{int(time.time())}"
        
        # 1. Read the document
        with open(document_path, "rb") as f:
            file_content = f.read()
        
        logger.info(f"Document loaded: {document_path} ({len(file_content)} bytes)")
        
        # 2. Add document to vector store
        logger.info("Adding document to vector store...")
        result = add_document_to_vector_store(document_id, file_content)
        
        if not result.get("success", False):
            logger.error(f"Failed to add document to vector store: {result.get('error')}")
            return False
        
        logger.info(f"Document added to vector store with {result.get('chunks')} chunks")
        
        # 3. Check document status
        logger.info("Checking document status...")
        status = get_document_status(document_id)
        
        if not status.get("success", False):
            logger.error(f"Failed to get document status: {status.get('error')}")
            return False
        
        logger.info(f"Document status: {status}")
        
        # 4. Extract data from the document
        logger.info("Extracting data from document...")
        
        # Define sample fields for extraction
        fields = [
            {
                "name": "company_name",
                "description": "The name of the company that issued this financial document"
            },
            {
                "name": "fiscal_year_end",
                "description": "The date of the fiscal year end for this financial report"
            },
            {
                "name": "total_revenue",
                "description": "The total revenue reported by the company for the fiscal year"
            }
        ]
        
        extraction_result = extract_data_from_vector_store(document_id, fields)
        
        if not extraction_result.get("success", False):
            logger.error(f"Failed to extract data: {extraction_result.get('error')}")
            return False
        
        logger.info(f"Extracted data: {extraction_result.get('data')}")
        
        # 5. List all documents in store
        logger.info("Listing all documents in vector store...")
        docs = list_documents_in_vector_store()
        
        if not docs.get("success", False):
            logger.error(f"Failed to list documents: {docs.get('error')}")
            return False
        
        logger.info(f"Documents in store: {docs.get('documents')}")
        
        # 6. Clean up - delete the test document
        logger.info("Deleting test document...")
        delete_result = delete_document_from_vector_store(document_id)
        
        if not delete_result.get("success", False):
            logger.error(f"Failed to delete document: {delete_result.get('error')}")
            return False
        
        logger.info("Document successfully deleted from vector store")
        
        return True
    
    except Exception as e:
        logger.error(f"Error in vector store test: {str(e)}")
        return False


if __name__ == "__main__":
    logger.info("Starting vector store test")
    success = test_vector_store_workflow()
    
    if success:
        logger.info("✅ Vector store test completed successfully")
        sys.exit(0)
    else:
        logger.error("❌ Vector store test failed")
        sys.exit(1)