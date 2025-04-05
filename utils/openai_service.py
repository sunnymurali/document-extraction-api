"""
OpenAI Service for Data Extraction
This module provides functions to extract structured data from text using LangChain with
OpenAI services, supporting both Azure OpenAI and standard OpenAI with automatic fallback.
"""

import os
import json
import logging
from typing import Dict, Any, Optional, List

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.output_parsers.json import parse_json

# Import OpenAI configuration (supports both Azure and standard OpenAI)
from utils.azure_openai_config import get_chat_openai

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def extract_structured_data(text: str, schema: Optional[str] = None) -> Dict[str, Any]:
    """
    Extract structured data from text using OpenAI (Azure or standard) via LangChain.
    
    Args:
        text: The text to extract data from
        schema: Optional JSON schema describing the data to extract
    
    Returns:
        A dictionary containing the extracted structured data
    
    Raises:
        Exception: If there was an error during extraction with both Azure and standard OpenAI
    """
    # If text is too long, truncate it to avoid exceeding token limits
    if len(text) > 15000:
        text = text[:15000] + "...(truncated)"
    
    # Prepare system message with extraction instructions
    system_message_content = """You are a data extraction assistant that extracts structured information from text.
Extract the information as a valid JSON object according to the schema provided.
If a field cannot be found in the text, use null as the value. Do not make up information."""
    
    # Add schema instructions if provided
    if schema:
        try:
            schema_obj = json.loads(schema)
            # Convert schema to a readable format for the model
            schema_desc = "Extract the following fields:\n"
            for field in schema_obj.get("fields", []):
                field_name = field.get("name", "")
                field_desc = field.get("description", "")
                schema_desc += f"- {field_name}: {field_desc}\n"
            system_message_content += f"\n\n{schema_desc}"
        except:
            # If schema parsing fails, just use a generic extraction instruction
            system_message_content += "\n\nExtract all relevant information from the document."
    else:
        # Default extraction without schema
        system_message_content += """
Extract the following common fields (if present):
- name: The full name of a person or entity
- date: Any relevant dates (e.g., invoice date, birth date)
- address: Complete address information
- phone: Phone number
- email: Email address
- total_amount: Any monetary total
- items: List of items with descriptions and prices
- any other key information present in the document"""
    
    # Create LangChain message objects
    system_message = SystemMessage(content=system_message_content)
    human_message = HumanMessage(content=text)
    
    try:
        # Get OpenAI client with appropriate settings (will use standard OpenAI with fallback to Azure)
        # Reduced max_tokens to help with memory issues
        client = get_chat_openai(temperature=0.1, max_tokens=500)
        
        logger.info("Successfully created OpenAI client, attempting to invoke...")
        
        # Make the API call to OpenAI via LangChain
        try:
            response = client.invoke([system_message, human_message])
            # Extract the response content
            response_content = response.content
        except Exception as invoke_error:
            logger.error(f"Error invoking OpenAI: {str(invoke_error)}")
            raise Exception(f"Failed to get response from OpenAI: {str(invoke_error)}")
        
        logger.info(f"Received response from OpenAI, length: {len(response_content) if response_content else 0}")
        
        # Check if response looks like HTML (it might be an error page)
        if response_content and response_content.strip().startswith('<'):
            logger.error(f"Received HTML response instead of JSON: {response_content[:100]}...")
            raise Exception("Received HTML error page instead of JSON response. This usually indicates an authentication or API configuration issue.")
        
        # Remove any potential markdown code block syntax
        cleaned_content = response_content
        if "```json" in cleaned_content:
            # Extract only the part between ```json and ```
            parts = cleaned_content.split("```json")
            if len(parts) > 1:
                json_parts = parts[1].split("```")
                if json_parts:
                    cleaned_content = json_parts[0].strip()
        elif "```" in cleaned_content:
            # Extract only the part between ``` and ```
            parts = cleaned_content.split("```")
            if len(parts) > 1:
                cleaned_content = parts[1].strip()
        
        # Parse and return the JSON response
        return json.loads(cleaned_content)
    
    except json.JSONDecodeError as json_err:
        logger.error(f"Failed to parse JSON from response: {json_err}")
        logger.debug(f"Raw response content: {response_content if 'response_content' in locals() else 'No response'}")
        raise Exception(f"Failed to parse JSON from response: {json_err}. Response begins with: {response_content[:50] if 'response_content' in locals() else 'No response'}...")
    
    except Exception as e:
        error_msg = f"OpenAI connection failed (tried both Azure and standard OpenAI if configured): {str(e)}"
        logger.error(error_msg)
        raise Exception(error_msg)