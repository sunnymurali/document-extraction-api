"""
OpenAI Service for Data Extraction
This module provides functions to extract structured data from text using OpenAI.
"""

import os
import json
import logging
from typing import Dict, Any, Optional, List

import openai
from openai import OpenAI

# Initialize OpenAI client with API key
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

def extract_structured_data(text: str, schema: Optional[str] = None) -> Dict[str, Any]:
    """
    Extract structured data from text using OpenAI.
    
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
        system_message = """You are a data extraction assistant that extracts structured information from text.
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
                system_message += f"\n\n{schema_desc}"
            except:
                # If schema parsing fails, just use a generic extraction instruction
                system_message += "\n\nExtract all relevant information from the document."
        else:
            # Default extraction without schema
            system_message += """
Extract the following common fields (if present):
- name: The full name of a person or entity
- date: Any relevant dates (e.g., invoice date, birth date)
- address: Complete address information
- phone: Phone number
- email: Email address
- total_amount: Any monetary total
- items: List of items with descriptions and prices
- any other key information present in the document"""
        
        # Make the API call to OpenAI
        # the newest OpenAI model is "gpt-4o" which was released May 13, 2024.
        # do not change this unless explicitly requested by the user
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": text}
            ],
            response_format={"type": "json_object"},
            temperature=0.1,  # Lower temperature for more deterministic outputs
            max_tokens=1000
        )
        
        # Extract the response content
        response_content = response.choices[0].message.content
        
        # Parse and return the JSON response
        return json.loads(response_content)
    
    except Exception as e:
        logging.error(f"Error in OpenAI extraction: {str(e)}")
        raise Exception(f"Failed to extract data: {str(e)}")