# Document Data Extractor for Large Documents

A powerful, AI-powered document data extraction tool that converts unstructured document content into structured data in JSON format, optimized for large documents and exclusively using Azure OpenAI services.

## Features

- **General Document Extraction**: Extract structured data from PDF, TXT, DOC, and DOCX files
- **Table Extraction**: Identify and extract tables from PDF documents
- **User-Friendly Field Builder**: Define extraction fields without writing JSON
- **Azure OpenAI Integration**: Exclusive integration with Azure OpenAI Service
- **Large Document Processing**: Advanced document chunking capability for processing large documents
- **Intelligent Result Merging**: Smart merging of extraction results from document chunks
- **JSON Output**: Results provided in clean, structured JSON format

## Technical Details

- Built with Flask and FastAPI
- Integration with Azure OpenAI Service via LangChain
- PyPDF and PyMuPDF for PDF processing
- Bootstrap CSS for responsive design
- Intelligent chunking and result merging for large documents

## Usage

1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Configure Azure OpenAI API credentials in environment variables:
   
   ```
   AZURE_OPENAI_API_KEY=your_azure_openai_api_key
   AZURE_OPENAI_ENDPOINT=https://your-endpoint.openai.azure.com/
   AZURE_OPENAI_DEPLOYMENT_NAME=your_deployment_name
   AZURE_OPENAI_API_VERSION=2024-02-01
   ```

4. Run the application: `python main.py`
5. Access the web interface at http://localhost:5000

## Environment Configuration

The application uses Azure OpenAI services as primary, with fallback to standard OpenAI. 
For Azure OpenAI, all of the following environment variables are required:

- `AZURE_OPENAI_API_KEY`: Your Azure OpenAI API key
- `AZURE_OPENAI_ENDPOINT`: Your Azure OpenAI endpoint URL
- `AZURE_OPENAI_DEPLOYMENT_NAME`: The deployment name for your Azure OpenAI model
- `AZURE_OPENAI_API_VERSION`: The API version to use (e.g., "2024-02-01")

For standard OpenAI fallback:

- `OPENAI_API_KEY`: Your standard OpenAI API key

## Rate Limiting Configuration

The application includes rate limiting for OpenAI API requests to prevent 429 "Too Many Requests" errors. 
You can configure the rate limiting behavior using these optional environment variables:

- `OPENAI_RPM`: Requests per minute for standard OpenAI API (default: 60)
- `AZURE_OPENAI_RPM`: Requests per minute for Azure OpenAI API (default: 240)
- `BATCH_SIZE`: Number of document chunks to process in a single batch (default: 10)
- `DELAY_BETWEEN_REQUESTS`: Delay in seconds between batch processing requests (default: 1.0)
- `DELAY_BETWEEN_FIELDS`: Delay in seconds between field extraction requests (default: 0.5)

## Screenshots

![Document Extractor Interface](screenshots/document-extractor.png)

## License

MIT