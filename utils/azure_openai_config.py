"""
Azure OpenAI Configuration

This module provides configuration and client setup for Azure OpenAI API integration via LangChain.
"""

import os
from typing import Optional

from langchain_openai import AzureChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

# Azure OpenAI configuration
AZURE_OPENAI_ENDPOINT = os.environ.get("AZURE_OPENAI_ENDPOINT", "https://rdinternalapi.bbh.com/ai/test/")
AZURE_OPENAI_API_KEY = os.environ.get("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_DEPLOYMENT_NAME = os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o-mini-2")
AZURE_OPENAI_API_VERSION = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-08-01-preview")

def get_azure_chat_openai(temperature: float = 0.1, max_tokens: int = 1000) -> AzureChatOpenAI:
    """
    Creates an instance of AzureChatOpenAI client with the specified parameters.
    
    Args:
        temperature: Controls randomness. Lower values like 0.1 make output more focused and deterministic.
        max_tokens: Maximum number of tokens to generate in the completion.
        
    Returns:
        AzureChatOpenAI: A configured Azure OpenAI client instance.
    """
    # Create the Azure OpenAI client
    client = AzureChatOpenAI(
        openai_api_version=AZURE_OPENAI_API_VERSION,
        azure_deployment=AZURE_OPENAI_DEPLOYMENT_NAME,
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        api_key=AZURE_OPENAI_API_KEY,
        temperature=temperature,
        max_tokens=max_tokens
    )
    
    return client