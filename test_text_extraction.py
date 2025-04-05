"""
Test script for extracting data from text files
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
    """Test document upload with text file"""
    # Use the sample text file
    document_path = "sample_finance.txt"
    
    if not os.path.exists(document_path):
        logger.error(f"Sample document not found: {document_path}")
        return None
    
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
    """Test extraction API with small document"""
    document_id = test_document_upload()
    
    if not document_id:
        logger.error("Failed to upload document for extraction test")
        return False
    
    # Define a simple schema for extraction with well-known fields
    schema = {
        "fields": [
            {
                "name": "company_name",
                "description": "The legal name of the company that filed this financial document"
            },
            {
                "name": "fiscal_year_end",
                "description": "The date of the fiscal year end for this financial report (format: YYYY-MM-DD)"
            },
            {
                "name": "total_revenue",
                "description": "The total revenue reported by the company for the fiscal year"
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
    max_attempts = 30  # 1 minute max wait time with 2 second interval
    attempts = 0
    
    while attempts < max_attempts:
        time.sleep(2)  # Wait 2 seconds between status checks
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
    
    if attempts >= max_attempts:
        logger.error("Extraction timed out")
        return False
    
    # Get results
    response = requests.get(f"{BASE_URL}/api/result/{document_id}")
    
    if response.status_code != 200:
        logger.error(f"Failed to get results: {response.status_code}")
        return False
    
    result = response.json()
    logger.info(f"Extraction results: {json.dumps(result, indent=2)}")
    
    # Verify results contain the expected fields
    if not result.get("data"):
        logger.error("No data returned in extraction results")
        return False
    
    data = result.get("data")
    expected_fields = ["company_name", "fiscal_year_end", "total_revenue"]
    
    for field in expected_fields:
        if field not in data:
            logger.warning(f"Expected field {field} not found in results")
    
    return True


if __name__ == "__main__":
    logger.info("Starting text extraction test")
    
    success = test_extraction()
    
    if success:
        logger.info("✅ Extraction test completed successfully")
        sys.exit(0)
    else:
        logger.error("❌ Extraction test failed")
        sys.exit(1)