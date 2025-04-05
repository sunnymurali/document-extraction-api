"""
Test script for ChromaDB vector store API endpoints
"""

import sys
import json
import requests
import logging
import time
import os
import uuid

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# API base URL
BASE_URL = "http://localhost:5000"


def test_document_upload():
    """Test the document upload API endpoint"""
    # Choose a sample document
    sample_docs = [
        "attached_assets/MorganStanley10K.pdf",
        "attached_assets/capitalOne10K.pdf"
    ]
    
    existing_docs = [doc for doc in sample_docs if os.path.exists(doc)]
    
    if not existing_docs:
        logger.error("No sample documents found in attached_assets directory")
        return None
    
    # Use the first available document
    document_path = existing_docs[0]
    logger.info(f"Testing with document: {document_path}")
    
    # Create a multipart form-data request
    files = {'file': open(document_path, 'rb')}
    response = requests.post(f"{BASE_URL}/api/upload", files=files)
    
    if response.status_code != 200:
        logger.error(f"Failed to upload document: {response.text}")
        return None
    
    result = response.json()
    
    logger.info(f"Document upload response: {json.dumps(result, indent=2)}")
    
    if not result.get("success", False):
        logger.error(f"Upload failed: {result.get('error')}")
        return None
    
    document_id = result.get("document_id")
    logger.info(f"Document uploaded with ID: {document_id}")
    
    # Give some time for vectorization to at least start
    logger.info("Waiting 5 seconds for document processing to begin...")
    time.sleep(5)
    
    return document_id


def test_extraction(document_id):
    """Test the extraction API endpoint"""
    if not document_id:
        logger.error("No document ID provided for extraction")
        return False
    
    # Define sample fields for extraction
    schema = {
        "fields": [
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
    }
    
    # Start the extraction
    response = requests.post(
        f"{BASE_URL}/api/extract",
        json={"document_id": document_id, "extraction_schema": schema}
    )
    
    if response.status_code != 200:
        logger.error(f"Failed to start extraction: {response.text}")
        return False
    
    result = response.json()
    logger.info(f"Extraction start response: {json.dumps(result, indent=2)}")
    
    if not result.get("success", False):
        logger.error(f"Extraction start failed: {result.get('error')}")
        return False
    
    # Poll for extraction status
    max_attempts = 30
    attempts = 0
    
    while attempts < max_attempts:
        logger.info(f"Checking extraction status (attempt {attempts+1}/{max_attempts})...")
        
        response = requests.get(f"{BASE_URL}/api/status/{document_id}")
        
        if response.status_code != 200:
            logger.error(f"Failed to check status: {response.text}")
            time.sleep(2)
            attempts += 1
            continue
        
        status = response.json()
        current_status = status.get("status")
        
        logger.info(f"Current status: {current_status}")
        
        if current_status == "completed":
            logger.info("Extraction completed successfully")
            break
        elif current_status == "failed":
            logger.error(f"Extraction failed: {status.get('error')}")
            return False
        
        # Wait before checking again
        time.sleep(2)
        attempts += 1
    
    if attempts >= max_attempts:
        logger.error("Extraction timed out")
        return False
    
    # Get the extraction results
    response = requests.get(f"{BASE_URL}/api/result/{document_id}")
    
    if response.status_code != 200:
        logger.error(f"Failed to get extraction results: {response.text}")
        return False
    
    result = response.json()
    logger.info(f"Extraction results: {json.dumps(result, indent=2)}")
    
    return True


def cleanup_document(document_id):
    """Clean up the document after testing"""
    if not document_id:
        return
    
    logger.info(f"Note: No cleanup endpoint available for document {document_id}")
    # In a production environment, we would need a cleanup endpoint
    # Currently, documents stay in the system until manually removed
    return


if __name__ == "__main__":
    logger.info("Starting API test")
    
    try:
        document_id = test_document_upload()
        
        if document_id:
            success = test_extraction(document_id)
            cleanup_document(document_id)
            
            if success:
                logger.info("✅ API test completed successfully")
                sys.exit(0)
            else:
                logger.error("❌ API test failed in extraction phase")
                sys.exit(1)
        else:
            logger.error("❌ API test failed in upload phase")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Unexpected error in API test: {str(e)}")
        sys.exit(1)