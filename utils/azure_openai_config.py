"""
OpenAI Configuration

This module provides configuration and client setup for both Azure OpenAI and standard OpenAI API integration
via LangChain, with fallback from Azure to standard OpenAI if Azure configuration is unavailable or fails.
"""

import os
import logging
from typing import Optional, Union

from langchain_openai import AzureChatOpenAI, ChatOpenAI
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import SystemMessage, HumanMessage

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Azure OpenAI configuration
AZURE_OPENAI_ENDPOINT = os.environ.get("AZURE_OPENAI_ENDPOINT", "https://rdinternalapi.bbh.com/ai/test/")
AZURE_OPENAI_API_KEY = os.environ.get("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_DEPLOYMENT_NAME = os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o-mini-2")
AZURE_OPENAI_API_VERSION = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-08-01-preview")

# Standard OpenAI configuration
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
# the newest OpenAI model is "gpt-4o" which was released May 13, 2024.
# do not change this unless explicitly requested by the user
OPENAI_MODEL = "gpt-4o"

def get_chat_openai(temperature: float = 0.1, max_tokens: int = 1000) -> BaseChatModel:
    """
    Creates an instance of a chat model client with the specified parameters,
    preferring Azure OpenAI but falling back to standard OpenAI if Azure is unavailable.
    
    Args:
        temperature: Controls randomness. Lower values like 0.1 make output more focused and deterministic.
        max_tokens: Maximum number of tokens to generate in the completion.
        
    Returns:
        BaseChatModel: A configured chat model client instance (either Azure or standard OpenAI).
        
    Raises:
        Exception: If neither Azure OpenAI nor standard OpenAI can be configured.
    """
    # First try to use Azure OpenAI
    if AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_DEPLOYMENT_NAME:
        try:
            logger.info(f"Configuring Azure OpenAI client with endpoint: {AZURE_OPENAI_ENDPOINT}, deployment: {AZURE_OPENAI_DEPLOYMENT_NAME}, API version: {AZURE_OPENAI_API_VERSION}")
            azure_client = AzureChatOpenAI(
                openai_api_version=AZURE_OPENAI_API_VERSION,
                azure_deployment=AZURE_OPENAI_DEPLOYMENT_NAME,
                azure_endpoint=AZURE_OPENAI_ENDPOINT,
                api_key=AZURE_OPENAI_API_KEY,
                temperature=temperature,
                max_tokens=max_tokens
            )
            logger.info("Successfully created Azure OpenAI client")
            return azure_client
        except Exception as e:
            logger.warning(f"Failed to configure Azure OpenAI: {str(e)}")
            logger.info("Falling back to standard OpenAI")
    else:
        logger.info("Azure OpenAI credentials not fully configured")
        missing = []
        if not AZURE_OPENAI_API_KEY:
            missing.append("AZURE_OPENAI_API_KEY")
        if not AZURE_OPENAI_ENDPOINT:
            missing.append("AZURE_OPENAI_ENDPOINT")
        if not AZURE_OPENAI_DEPLOYMENT_NAME:
            missing.append("AZURE_OPENAI_DEPLOYMENT_NAME")
        logger.info(f"Missing Azure OpenAI credentials: {', '.join(missing)}")
        
    # Fallback to standard OpenAI
    if OPENAI_API_KEY:
        try:
            logger.info(f"Configuring standard OpenAI client with model: {OPENAI_MODEL}")
            openai_client = ChatOpenAI(
                model=OPENAI_MODEL,
                api_key=OPENAI_API_KEY,
                temperature=temperature,
                max_tokens=max_tokens
            )
            logger.info("Successfully created standard OpenAI client")
            return openai_client
        except Exception as e:
            logger.error(f"Failed to configure standard OpenAI: {str(e)}")
    else:
        logger.warning("OpenAI API key not provided for fallback")
    
    # If we get here, neither client could be configured
    raise Exception("Failed to configure either Azure OpenAI or standard OpenAI. Please check your API credentials.")

# For backward compatibility
def get_azure_chat_openai(temperature: float = 0.1, max_tokens: int = 1000) -> BaseChatModel:
    """
    Backward compatibility function that uses the new get_chat_openai function internally.
    This allows existing code to continue working without changes.
    
    Args:
        temperature: Controls randomness. Lower values like 0.1 make output more focused and deterministic.
        max_tokens: Maximum number of tokens to generate in the completion.
        
    Returns:
        BaseChatModel: A configured chat model client instance (either Azure or standard OpenAI).
    """
    logger.info("Using get_azure_chat_openai (with fallback to standard OpenAI)")
    return get_chat_openai(temperature, max_tokens)