# Document Data Extractor

A powerful, AI-powered document data extraction tool that converts unstructured document content into structured data in JSON format, with support for both OpenAI and Azure OpenAI services.

## Features

- **General Document Extraction**: Extract structured data from PDF, TXT, DOC, and DOCX files
- **Table Extraction**: Identify and extract tables from PDF documents
- **User-Friendly Field Builder**: Define extraction fields without writing JSON
- **Dual AI Integration**: Support for both OpenAI API and Azure OpenAI Service
- **Fallback Mechanism**: Automatic fallback from Azure to standard OpenAI if needed
- **JSON Output**: Results provided in clean, structured JSON format

## Technical Details

- Built with Flask and FastAPI
- Integration with OpenAI API and Azure OpenAI Service via LangChain
- PyPDF and PyMuPDF for PDF processing
- Bootstrap CSS for responsive design

## Usage

1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Configure API credentials in environment variables:
   
   **For Standard OpenAI:**
   ```
   OPENAI_API_KEY=your_openai_api_key
   ```
   
   **For Azure OpenAI:**
   ```
   AZURE_OPENAI_API_KEY=your_azure_openai_api_key
   AZURE_OPENAI_ENDPOINT=https://your-endpoint.openai.azure.com/
   AZURE_OPENAI_DEPLOYMENT_NAME=your_deployment_name
   AZURE_OPENAI_API_VERSION=2024-02-01  # Optional, defaults to a recent version
   ```

4. Run the application: `python main.py`
5. Access the web interface at http://localhost:5000

## Environment Configuration

The application will attempt to use Azure OpenAI first if configured, and then fall back to standard OpenAI if needed. You can configure either or both services:

- **Azure OpenAI Only**: Set only the Azure environment variables for an Azure-exclusive setup
- **Standard OpenAI Only**: Set only the OPENAI_API_KEY for a standard setup
- **Dual Configuration**: Set both for a setup that tries Azure first but falls back to standard OpenAI

## Screenshots

![Document Extractor Interface](screenshots/document-extractor.png)

## License

MIT