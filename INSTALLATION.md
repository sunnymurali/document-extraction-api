# Installation Guide

This document provides step-by-step instructions for setting up and running the Document Extraction API on your local machine.

## Prerequisites

- Python 3.9 or higher
- pip (Python package manager)
- Git

## Step 1: Clone the Repository

```bash
git clone https://github.com/sunnymurali/document-extraction-api.git
cd document-extraction-api
```

## Step 2: Set Up a Python Virtual Environment

```bash
# Create a virtual environment
python -m venv venv

# Activate the virtual environment
# On Windows
venv\Scripts\activate
# On macOS/Linux
source venv/bin/activate
```

## Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

If the requirements.txt file is not available, install the required packages manually:

```bash
pip install fastapi flask flask-sqlalchemy gunicorn langchain langchain-chroma langchain-community langchain-core langchain-openai langgraph openai pydantic pymupdf pypdf requests requests-toolbelt trafilatura uvicorn werkzeug
```

## Step 4: Set Up Environment Variables

Create a `.env` file in the root directory with the following variables:

```
# Azure OpenAI Configuration (Primary)
AZURE_OPENAI_API_KEY=your_azure_openai_api_key
AZURE_OPENAI_ENDPOINT=your_azure_endpoint
AZURE_OPENAI_DEPLOYMENT_NAME=your_deployment_name
AZURE_OPENAI_API_VERSION=2023-05-15

# Standard OpenAI Configuration (Fallback)
OPENAI_API_KEY=your_openai_api_key

# Flask Secret Key
SESSION_SECRET=your_secret_key
```

## Step 5: Create Required Directories

```bash
mkdir -p uploads vector_db
```

## Step 6: Run the Application

### For Flask Version:

```bash
# Using Flask development server
python main.py

# Or using Gunicorn (recommended for production)
gunicorn --bind 0.0.0.0:5000 --reuse-port --reload main:app
```

### For FastAPI Version:

```bash
# Using Uvicorn
uvicorn api:app --host 0.0.0.0 --port 8000 --reload
```

## Step 7: Access the Application

- Flask Web Interface: Open your browser and navigate to `http://localhost:5000`
- FastAPI API Documentation: Open your browser and navigate to `http://localhost:8000/docs`

## Testing OpenAI Connection

To test if the Azure OpenAI prioritization with fallback is working correctly:

```bash
curl -s http://localhost:5000/api/test-openai-connection | python -m json.tool
```

You should see a response indicating which provider is being used.

## Troubleshooting

### Connection Issues with OpenAI

If you're experiencing connection issues with OpenAI:

1. Verify that your API keys are correct in the `.env` file
2. Check that the Azure endpoint URL is accessible from your network
3. Ensure that the deployment name matches your Azure OpenAI deployment

### File Upload Issues

If you're having issues with file uploads:

1. Make sure the `uploads` directory exists and is writable
2. Check that the file size doesn't exceed any limits set in your web server configuration

### Vector Store Issues

If you're experiencing issues with the vector store:

1. Make sure the `vector_db` directory exists and is writable
2. Check the logs for any errors related to embeddings generation