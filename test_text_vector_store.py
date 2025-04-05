"""
Test script for text file loading in vector store
"""

import os
import sys
import logging
import json
from utils.vector_store import add_document_to_vector_store, extract_data_from_vector_store

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_text_vector_store():
    """Test text file loading in vector store"""
    logger.info("Starting text vector store test")
    
    # Use sample_finance.txt as the test file
    test_file_path = "sample_finance.txt"
    
    if not os.path.exists(test_file_path):
        logger.error(f"Test file not found: {test_file_path}")
        return False
    
    logger.info(f"Testing with document: {test_file_path}")
    
    # Read the file
    with open(test_file_path, "rb") as f:
        file_content = f.read()
    
    # Generate a document ID
    document_id = "test_text_123"
    
    # Add the document to the vector store
    add_result = add_document_to_vector_store(document_id, file_content)
    logger.info(f"Add result: {json.dumps(add_result, indent=2)}")
    
    if not add_result.get("success", False):
        logger.error("Failed to add document to vector store")
        return False
    
    # Define fields to extract
    fields = [
        {"name": "company_name", "description": "The name of the company"},
        {"name": "total_revenue", "description": "The total revenue of the company"},
        {"name": "fiscal_year_end", "description": "The end date of the fiscal year"}
    ]
    
    # Extract data from the vector store
    extract_result = extract_data_from_vector_store(document_id, fields)
    logger.info(f"Extract result: {json.dumps(extract_result, indent=2)}")
    
    if not extract_result.get("success", False):
        logger.error("Failed to extract data from vector store")
        return False
    
    logger.info("✅ Text vector store test completed successfully")
    return True

if __name__ == "__main__":
    test_text_vector_store()