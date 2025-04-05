"""
Very simple test for vector store with text files
"""

import os
import sys
import logging
import json
import uuid
import time
from utils.vector_store import add_document_to_vector_store, extract_data_from_vector_store, delete_document_from_vector_store

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_simple_vector():
    """Test vector store with text file"""
    logger.info("Starting simple vector test")
    
    # Use sample_finance.txt as the test file
    test_file_path = "sample_finance.txt"
    
    if not os.path.exists(test_file_path):
        logger.error(f"Test file not found: {test_file_path}")
        return False
    
    logger.info(f"Testing with document: {test_file_path}")
    
    # Read the file
    with open(test_file_path, "rb") as f:
        file_content = f.read()
    
    # Generate a unique document ID
    document_id = f"test_{str(uuid.uuid4())[:8]}"
    
    try:
        # Add the document to the vector store
        add_result = add_document_to_vector_store(document_id, file_content)
        logger.info(f"Add result: {json.dumps(add_result, indent=2)}")
        
        if not add_result.get("success", False):
            logger.error("Failed to add document to vector store")
            return False
        
        # Give the system a moment to process
        time.sleep(1)
        
        # Define fields to extract
        fields = [
            {"name": "company_name", "description": "The name of the company"},
            {"name": "total_revenue", "description": "The total revenue of the company"},
            {"name": "fiscal_year_end", "description": "The end date of the fiscal year"}
        ]
        
        # Extract data from the vector store
        extract_result = extract_data_from_vector_store(document_id, fields)
        logger.info(f"Extract result: {json.dumps(extract_result, indent=2)}")
        
        success = extract_result.get("success", False)
        
        if success:
            logger.info("✅ Text vector store test completed successfully")
        else:
            logger.error("❌ Text vector store test failed")
        
        # Clean up
        delete_result = delete_document_from_vector_store(document_id)
        logger.info(f"Delete result: {json.dumps(delete_result, indent=2)}")
        
        return success
    except Exception as e:
        logger.error(f"Error during vector store test: {str(e)}")
        return False

if __name__ == "__main__":
    success = test_simple_vector()
    sys.exit(0 if success else 1)