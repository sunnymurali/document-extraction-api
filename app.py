"""
Flask Application for Document Data Extraction
This application provides a web interface and API endpoints for extracting structured data from documents.
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

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
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


@app.route('/api/extract', methods=['POST'])
def extract_data():
    """
    API endpoint to extract data from uploaded documents
    
    Request: multipart/form-data with:
    - file: The document file
    - extraction_schema: (optional) JSON string defining extraction schema
    
    Response: JSON with extraction results
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
        # Parse extraction schema if provided
        schema = None
        if 'extraction_schema' in request.form and request.form['extraction_schema']:
            try:
                schema = json.loads(request.form['extraction_schema'])
            except json.JSONDecodeError as e:
                return jsonify({'success': False, 'error': f'Invalid schema format: {str(e)}'}), 400
        
        # Save the file
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        
        try:
            # Handle text files directly (for testing purposes)
            if filename.endswith('.txt'):
                with open(file_path, 'r') as f:
                    text = f.read()
                
                # For text files, we'll create a mock extraction result
                # This is helpful for testing when PDF processing is not available
                result = {
                    'success': True,
                    'data': {
                        '_source': 'Text file direct extraction',
                        'text_content': text[:500] + ('...' if len(text) > 500 else '')
                    }
                }
                
                if schema:
                    # Use extract_structured_data for text files if we have a schema
                    from document_extractor import extract_structured_data
                    try:
                        structured_data = extract_structured_data(text, schema)
                        result['data'] = structured_data
                    except Exception as e:
                        logger.warning(f"Could not extract structured data from text: {e}")
                        # Keep the default text preview if extraction fails
            else:
                # Process the uploaded file with our extractor
                result = extract_document_data(file_path, schema)
            
            return jsonify(result)
        
        finally:
            # Clean up the uploaded file
            try:
                if os.path.exists(file_path):
                    os.unlink(file_path)
            except Exception as e:
                logger.error(f"Error removing temporary file: {e}")
    
    except Exception as e:
        logger.error(f"Error in extraction process: {e}")
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