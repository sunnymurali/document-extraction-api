"""
Flask Application for Document Data Extraction
This application provides a web interface and API endpoints for extracting structured data from documents.
The application uses asynchronous processing to handle large documents without blocking.
"""

import os
import json
import logging
from flask import Flask, render_template, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename

# Import the document extractor
from document_extractor import (
    extract_from_binary_data, 
    extract_document_data,
    extract_tables_from_binary_data,
    extract_tables_from_pdf
)

# Import models and async document processing
from models import (
    store_document,
    get_document_status,
    get_extraction_result,
    async_extract_document,
    cleanup_document,
    DocumentStatus
)

# Set up logging
logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key-change-in-production")

# Configure file upload settings
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf', 'txt', 'doc', 'docx'}
MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10MB limit

# Ensure upload directory exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH


def allowed_file(filename):
    """Check if file has an allowed extension"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/')
def index():
    """Render the main page"""
    return render_template('index.html')


@app.route('/api/upload', methods=['POST'])
def upload_document():
    """
    API endpoint to upload a document
    
    Request: multipart/form-data with:
    - file: The document file
    
    Response: JSON with upload results including document ID
    """
    # Check if a file was uploaded
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    
    # Check if file was selected
    if file.filename == '':
        return jsonify({'success': False, 'error': 'No file selected'}), 400
    
    # Check file type
    if not allowed_file(file.filename):
        return jsonify({'success': False, 'error': f'Invalid file type. Allowed types: {", ".join(ALLOWED_EXTENSIONS)}'}), 400
    
    try:
        # Read file content
        file_content = file.read()
        
        # Store document
        result = store_document(file.filename, file_content)
        
        if not result.success:
            return jsonify({
                'success': False, 
                'error': result.error or 'Failed to store document'
            }), 500
        
        return jsonify({
            'success': True,
            'document_id': result.document_id,
            'message': 'Document uploaded successfully'
        })
    
    except Exception as e:
        logger.error(f"Error in document upload: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/extract', methods=['POST'])
def extract_data():
    """
    API endpoint to start document extraction (async)
    
    Request: JSON with:
    - document_id: ID of the document to extract data from
    - extraction_schema: (optional) JSON defining extraction schema
    - use_chunking: (optional) Boolean to enable/disable chunking (default: true)
    
    Response: JSON with the status of the extraction job
    """
    # Parse request data
    try:
        data = request.json
        
        # Check for required parameters
        if not data or 'document_id' not in data:
            return jsonify({'success': False, 'error': 'Missing document_id parameter'}), 400
        
        document_id = data['document_id']
        
        # Check if document exists
        doc_status = get_document_status(document_id)
        if not doc_status:
            return jsonify({'success': False, 'error': f'Document {document_id} not found'}), 404
        
        # Parse schema if provided
        schema = None
        if 'extraction_schema' in data and data['extraction_schema']:
            schema = data['extraction_schema']
        
        # Check if chunking should be used
        use_chunking = data.get('use_chunking', True)
        
        # Start async extraction
        async_extract_document(document_id, schema, use_chunking)
        
        return jsonify({
            'success': True,
            'document_id': document_id,
            'status': 'processing',
            'message': 'Extraction started'
        })
    
    except Exception as e:
        logger.error(f"Error starting extraction: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/status/<document_id>', methods=['GET'])
def document_status(document_id):
    """
    API endpoint to check the status of a document extraction
    
    Path parameter:
    - document_id: ID of the document to check
    
    Response: JSON with the current status
    """
    try:
        # Get document status
        status = get_document_status(document_id)
        
        if not status:
            return jsonify({'success': False, 'error': f'Document {document_id} not found'}), 404
        
        # Return the status
        return jsonify({
            'success': True,
            'document_id': document_id,
            'status': status.status,
            'extraction_status': status.extraction_status,
            'error': status.error,
            'filename': status.filename,
            'upload_time': status.upload_time
        })
    
    except Exception as e:
        logger.error(f"Error checking document status: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/result/<document_id>', methods=['GET'])
def extraction_result(document_id):
    """
    API endpoint to get the extraction result for a document
    
    Path parameter:
    - document_id: ID of the document to get results for
    
    Response: JSON with the extraction results
    """
    try:
        # Get document status
        status = get_document_status(document_id)
        
        if not status:
            return jsonify({'success': False, 'error': f'Document {document_id} not found'}), 404
        
        # Check if extraction is completed
        if status.status != 'completed':
            return jsonify({
                'success': False, 
                'error': f'Document extraction is not completed (current status: {status.status})',
                'status': status.status
            }), 400
        
        # Get the extraction result
        result = get_extraction_result(document_id)
        
        if not result:
            return jsonify({'success': False, 'error': f'No results found for document {document_id}'}), 404
        
        # Return the result
        return jsonify(result)
    
    except Exception as e:
        logger.error(f"Error retrieving extraction result: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/extract-tables', methods=['POST'])
def extract_tables():
    """
    API endpoint to extract tables from uploaded documents
    
    Request: multipart/form-data with:
    - file: The document file (PDF only)
    
    Response: JSON with extraction results including tables found in the document
    """
    # Check if a file was uploaded
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    
    # Check if file was selected
    if file.filename == '':
        return jsonify({'success': False, 'error': 'No file selected'}), 400
    
    # Check file type - tables extraction only works with PDFs
    if not file.filename.lower().endswith('.pdf'):
        return jsonify({'success': False, 'error': 'Table extraction only supports PDF files'}), 400
    
    try:
        # Save the file
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        
        try:
            # Process the uploaded file with our table extractor
            result = extract_tables_from_pdf(file_path)
            
            # Return the results as JSON
            return jsonify(result)
        
        finally:
            # Clean up the uploaded file
            try:
                if os.path.exists(file_path):
                    os.unlink(file_path)
            except Exception as e:
                logger.error(f"Error removing temporary file: {e}")
    
    except Exception as e:
        logger.error(f"Error in table extraction process: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/static/<path:path>')
def serve_static(path):
    """Serve static files"""
    return send_from_directory('static', path)


# Check if OpenAI API key is available
# Using before_request instead of before_first_request (which is deprecated)
@app.before_request
def check_api_key():
    # Use a flag to only log once
    if not getattr(app, '_api_key_checked', False):
        # Check for either OpenAI API key or Azure OpenAI configuration
        if not os.environ.get("OPENAI_API_KEY") and not os.environ.get("AZURE_OPENAI_API_KEY"):
            logger.warning("Neither OPENAI_API_KEY nor AZURE_OPENAI_API_KEY environment variable is set. Extraction functionality will not work correctly.")
        
        # Check Azure OpenAI required variables
        if os.environ.get("AZURE_OPENAI_API_KEY"):
            if not os.environ.get("AZURE_OPENAI_ENDPOINT"):
                logger.warning("AZURE_OPENAI_ENDPOINT environment variable not set. Azure OpenAI functionality will not work correctly.")
            
            if not os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME"):
                logger.warning("AZURE_OPENAI_DEPLOYMENT_NAME environment variable not set. Azure OpenAI functionality will not work correctly.")
        
        app._api_key_checked = True


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)