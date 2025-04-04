"""
OpenAI Service for Data Extraction
This module provides functions to extract structured data from text using LangChain with Azure OpenAI.
"""

import os
import json
import logging
from typing import Dict, Any, Optional, List

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.output_parsers.json import parse_json

# Import Azure OpenAI configuration
from utils.azure_openai_config import get_azure_chat_openai

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def extract_structured_data(text: str, schema: Optional[str] = None) -> Dict[str, Any]:
    """
    Extract structured data from text using Azure OpenAI via LangChain.
    
    Args:
        text: The text to extract data from
        schema: Optional JSON schema describing the data to extract
    
    Returns:
        A dictionary containing the extracted structured data
    
    Raises:
        Exception: If there was an error during extraction
    """
    try:
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
        
        # Get Azure OpenAI client with appropriate settings
        client = get_azure_chat_openai(temperature=0.1, max_tokens=1000)
        
        # Make the API call to Azure OpenAI via LangChain
        response = client.invoke([system_message, human_message])
        
        # Extract the response content
        response_content = response.content
        
        # Parse and return the JSON response
        return json.loads(response_content)
    
    except Exception as e:
        logger.error(f"Error in Azure OpenAI extraction: {str(e)}")
        raise Exception(f"Failed to extract data: {str(e)}")