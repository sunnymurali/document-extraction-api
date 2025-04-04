# Document Data Extractor

A powerful, AI-powered document data extraction tool that converts unstructured document content into structured data in JSON format.

## Features

- **General Document Extraction**: Extract structured data from PDF, TXT, DOC, and DOCX files
- **Table Extraction**: Identify and extract tables from PDF documents
- **User-Friendly Field Builder**: Define extraction fields without writing JSON
- **AI-Powered Analysis**: Powered by OpenAI models for accurate data extraction
- **JSON Output**: Results provided in clean, structured JSON format

## Technical Details

- Built with Flask and FastAPI
- Uses OpenAI API for document analysis and extraction
- PyPDF and PyMuPDF for PDF processing
- Bootstrap CSS for responsive design

## Usage

1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Configure OpenAI API key in environment variables
4. Run the application: `python main.py`
5. Access the web interface at http://localhost:5000

## Screenshots

![Document Extractor Interface](screenshots/document-extractor.png)

## License

MIT