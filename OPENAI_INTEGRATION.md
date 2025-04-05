# OpenAI Integration

This document explains the Azure OpenAI and standard OpenAI integration architecture used in this application.

## Integration Architecture

The application integrates with both Azure OpenAI and standard OpenAI services, using the following approach:

1. **Azure OpenAI First**: The system attempts to use Azure OpenAI as the primary service
2. **Fallback Mechanism**: Only if Azure OpenAI fails, the system automatically falls back to standard OpenAI
3. **Connection Testing**: Each connection is tested before use to ensure it is working properly

## Key Files

- `utils/azure_openai_config.py`: Contains the main integration logic with the prioritization approach
- `utils/vector_store.py`: Uses the integration for embeddings generation
- `api.py`: Uses the integration for LLM inference and embeddings generation
- `document_extractor.py`: Uses the integration for document extraction

## Connection Testing

You can test the OpenAI connection by accessing the `/api/test-openai-connection` endpoint, which will return:

```json
{
  "message": "Successfully connected to [Provider]",
  "provider": "[Azure OpenAI or Standard OpenAI]",
  "success": true
}
```

## Environment Variables

The following environment variables can be configured:

### Azure OpenAI Configuration
- `AZURE_OPENAI_API_KEY`: Your Azure OpenAI API key
- `AZURE_OPENAI_ENDPOINT`: Your Azure OpenAI endpoint URL
- `AZURE_OPENAI_DEPLOYMENT_NAME`: The deployment name for your Azure OpenAI model
- `AZURE_OPENAI_API_VERSION`: The API version to use (default: "2023-05-15")
- `AZURE_OPENAI_EMBEDDINGS_DEPLOYMENT`: Optional specific deployment for embeddings (if different from main deployment)

### Standard OpenAI Configuration
- `OPENAI_API_KEY`: Your standard OpenAI API key

## Model Information

- Standard OpenAI uses the `gpt-4o` model for chat functionality 
- Standard OpenAI uses the `text-embedding-3-small` model for embeddings generation
