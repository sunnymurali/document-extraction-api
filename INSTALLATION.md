# Installation Guide

## Required Python Packages

To run the Document Data Extractor, you'll need to install the following Python packages:

```
flask>=2.3.0
gunicorn>=21.2.0
openai>=1.0.0
pypdf>=3.15.1
flask-sqlalchemy>=3.0.0
pydantic>=2.11.2
fastapi>=0.115.12
uvicorn>=0.34.0
werkzeug>=3.1.3
pymupdf>=1.25.5
langchain>=0.3.23
langchain-openai>=0.3.12
langchain-core>=0.3.51
trafilatura>=2.0.0
```

## Development Dependencies

For development, you may also want to install these additional packages:

```
pytest>=7.0.0
black>=23.0.0
```

## Installation Using Poetry

If you have Poetry installed, you can simply run:

```bash
poetry install
```

## Installation Using pip

If you prefer to use pip, you can install all required packages with:

```bash
pip install flask>=2.3.0 gunicorn>=21.2.0 openai>=1.0.0 pypdf>=3.15.1 flask-sqlalchemy>=3.0.0 pydantic>=2.11.2 fastapi>=0.115.12 uvicorn>=0.34.0 werkzeug>=3.1.3 pymupdf>=1.25.5 langchain>=0.3.23 langchain-openai>=0.3.12 langchain-core>=0.3.51 trafilatura>=2.0.0
```

For development dependencies:

```bash
pip install pytest>=7.0.0 black>=23.0.0
```

## Configuration

After installing the required packages, don't forget to set up the environment variables:

```
AZURE_OPENAI_API_KEY=your_azure_openai_api_key
AZURE_OPENAI_ENDPOINT=https://your-endpoint.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT_NAME=your_deployment_name
AZURE_OPENAI_API_VERSION=2024-02-01
```