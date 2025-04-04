import json
import os
import logging
from typing import Optional, Dict, Any

# the newest OpenAI model is "gpt-4o" which was released May 13, 2024.
# do not change this unless explicitly requested by the user
from openai import OpenAI

logger = logging.getLogger(__name__)

# Initialize OpenAI client
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
openai = OpenAI(api_key=OPENAI_API_KEY)

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
        # Truncate text if it's too long
        max_text_length = 16000  # A conservative limit
        if len(text) > max_text_length:
            logger.warning(f"Text is too long ({len(text)} chars), truncating to {max_text_length}")
            text = text[:max_text_length] + "...[text truncated due to length]"
        
        # Create the system message based on whether a schema was provided
        if schema:
            try:
                # Parse the schema to validate it's proper JSON
                schema_obj = json.loads(schema)
                schema_str = json.dumps(schema_obj, indent=2)
                system_content = (
                    "You are a data extraction expert. Extract structured data from the provided PDF text "
                    f"according to this schema: {schema_str}. "
                    "Return ONLY a valid JSON object with the extracted data. "
                    "If you cannot find certain fields, use null for those fields."
                )
            except json.JSONDecodeError:
                # If schema is not valid JSON, treat it as a text description
                system_content = (
                    "You are a data extraction expert. Extract structured data from the provided PDF text "
                    f"according to this description: {schema}. "
                    "Return ONLY a valid JSON object with the extracted data. "
                    "If you cannot find certain fields, use null for those fields."
                )
        else:
            # No schema provided, use a general extraction prompt
            system_content = (
                "You are a data extraction expert. Analyze the provided PDF text and extract all relevant "
                "data points into a structured format. Identify key fields like names, dates, addresses, "
                "numbers, and any domain-specific information. "
                "Return ONLY a valid JSON object with the extracted data, grouped by logical categories. "
                "Use clear, concise field names."
            )
        
        logger.debug("Sending request to OpenAI API")
        response = openai.chat.completions.create(
            model="gpt-4o",  # Using the latest model as per blueprint guidelines
            messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": text}
            ],
            response_format={"type": "json_object"},
            temperature=0.3,  # Lower temperature for more deterministic outputs
        )
        
        # Extract the JSON response
        json_response = json.loads(response.choices[0].message.content)
        logger.debug("Successfully received structured data from OpenAI")
        
        return json_response
    
    except Exception as e:
        logger.error(f"Error extracting structured data: {str(e)}")
        raise Exception(f"Failed to extract structured data: {str(e)}")
