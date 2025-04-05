"""
Test script for PDF extraction API
"""

import sys
import json
import requests
import logging
import time
import os

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# API base URL
BASE_URL = "http://localhost:5000"


def test_document_upload():
    """Test document upload API"""
    # Choose a sample document
    sample_docs = [
        "attached_assets/MorganStanley10K.pdf",
        "attached_assets/capitalOne10K.pdf"
    ]
    
    existing_docs = [doc for doc in sample_docs if os.path.exists(doc)]
    
    if not existing_docs:
        logger.error("No sample documents found")
        return None
    
    # Use the first available document
    document_path = existing_docs[0]
    logger.info(f"Testing with document: {document_path}")
    
    # Upload document
    files = {'file': open(document_path, 'rb')}
    response = requests.post(f"{BASE_URL}/api/upload", files=files)
    
    if response.status_code != 200:
        logger.error(f"Failed to upload document: {response.status_code}")
        return None
    
    result = response.json()
    logger.info(f"Upload response: {json.dumps(result, indent=2)}")
    
    document_id = result.get("document_id")
    return document_id


def test_extraction():
    """Test extraction API without using vector store"""
    document_id = test_document_upload()
    
    if not document_id:
        logger.error("Failed to upload document for extraction test")
        return False
    
    # Define a simple schema for extraction
    schema = {
        "fields": [
            {
                "name": "company_name",
                "description": "The name of the company that issued this financial document"
            },
            {
                "name": "document_date",
                "description": "The date of the document"
            }
        ]
    }
    
    # Start extraction
    response = requests.post(
        f"{BASE_URL}/api/extract",
        json={"document_id": document_id, "extraction_schema": schema, "use_chunking": True}
    )
    
    if response.status_code != 200:
        logger.error(f"Failed to start extraction: {response.status_code}")
        return False
    
    result = response.json()
    logger.info(f"Extraction start response: {json.dumps(result, indent=2)}")
    
    # Poll for status
    max_attempts = 60
    attempts = 0
    
    while attempts < max_attempts:
        time.sleep(5)  # Wait 5 seconds between status checks
        attempts += 1
        
        response = requests.get(f"{BASE_URL}/api/status/{document_id}")
        
        if response.status_code != 200:
            logger.error(f"Failed to check status: {response.status_code}")
            continue
        
        status = response.json()
        current_status = status.get("status")
        logger.info(f"Status check {attempts}: {current_status}")
        
        if current_status == "completed":
            logger.info("Extraction completed successfully")
            break
        elif current_status == "failed":
            logger.error(f"Extraction failed: {status.get('error')}")
            return False
    
    # Get results
    response = requests.get(f"{BASE_URL}/api/result/{document_id}")
    
    if response.status_code != 200:
        logger.error(f"Failed to get results: {response.status_code}")
        return False
    
    result = response.json()
    logger.info(f"Extraction results: {json.dumps(result, indent=2)}")
    
    return True


if __name__ == "__main__":
    logger.info("Starting document API test")
    
    success = test_extraction()
    
    if success:
        logger.info("✅ API test completed successfully")
        sys.exit(0)
    else:
        logger.error("❌ API test failed")
        sys.exit(1)