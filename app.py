"""
Flask Application for Document Data Extraction
This application provides a simple web interface for document extraction using ChromaDB and vector embeddings.
"""

import os
import logging
import threading
import time
from flask import Flask, render_template, request, jsonify, send_from_directory
import uuid

# Import ChromaDB vector store utilities
from utils.vector_store import (
    add_document_to_vector_store,
    extract_data_from_vector_store,
    get_document_status,
    list_documents_in_vector_store
)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key")

# Storage for document and task data
documents = {}
tasks = {}

# Set up routes
@app.route('/')
def index():
    """Render the main application page"""
    return render_template('index.html')

@app.route('/static/<path:path>')
def serve_static(path):
    """Serve static files"""
    return send_from_directory('static', path)

def process_document_in_background(document_id, file_path, file_name):
    """Process document in background thread"""
    try:
        # Update document status
        documents[document_id]["status"] = "indexing"
        documents[document_id]["message"] = "Document is being indexed..."
        
        # Read the file
        with open(file_path, "rb") as f:
            file_content = f.read()
        
        # Add document to vector store
        result = add_document_to_vector_store(document_id, file_content)
        
        if result.get("success", False):
            # Update document status to success
            documents[document_id]["status"] = "indexed"
            documents[document_id]["message"] = "Document indexed"
            documents[document_id]["chunks"] = result.get("chunks", 0)
            documents[document_id]["pages"] = result.get("pages", 0)
            documents[document_id]["processing_time"] = result.get("processing_time", 0)
            
            logger.info(f"Document {document_id} indexed successfully with {result.get('chunks', 0)} chunks")
        else:
            # Update document status to failed
            documents[document_id]["status"] = "failed"
            documents[document_id]["message"] = f"Indexing failed: {result.get('error', 'Unknown error')}"
            
            logger.error(f"Document {document_id} indexing failed: {result.get('error', 'Unknown error')}")
    
    except Exception as e:
        # Update document status to failed
        documents[document_id]["status"] = "failed"
        documents[document_id]["message"] = f"Indexing failed: {str(e)}"
        
        logger.error(f"Error processing document {document_id}: {str(e)}")

@app.route('/documents/upload', methods=['POST'])
def upload_document():
    """Handle document upload and initiate indexing with ChromaDB"""
    file = request.files.get('file')
    if not file:
        return jsonify({"success": False, "error": "No file provided"}), 400
    
    # Save file to uploads directory
    os.makedirs('uploads', exist_ok=True)
    file_path = os.path.join('uploads', file.filename)
    file.save(file_path)
    
    # Generate document ID
    document_id = str(uuid.uuid4())
    
    # Store document info
    documents[document_id] = {
        "file_name": file.filename,
        "file_path": file_path,
        "status": "pending",
        "message": "Document uploaded successfully. Indexing in progress..."
    }
    
    # Start background processing
    threading.Thread(
        target=process_document_in_background, 
        args=(document_id, file_path, file.filename)
    ).start()
    
    # Return response
    return jsonify({
        "success": True,
        "document_id": document_id,
        "error": None,
        "indexing_status": "pending"
    })

@app.route('/documents/<document_id>/status', methods=['GET'])
def document_status(document_id):
    """Check document indexing status"""
    if document_id in documents:
        return jsonify({
            "success": True,
            "document_id": document_id,
            "status": {
                "status": documents[document_id]["status"],
                "message": documents[document_id].get("message", f"Document {documents[document_id]['status']}"),
                "file_name": documents[document_id]["file_name"]
            }
        })
    else:
        # Try to get status from vector store
        status = get_document_status(document_id)
        if status.get("success", False):
            metadata = status.get("metadata", {})
            return jsonify({
                "success": True,
                "document_id": document_id,
                "status": {
                    "status": "indexed",
                    "message": "Document indexed",
                    "file_name": metadata.get("title", f"Document {document_id}")
                }
            })
        else:
            return jsonify({
                "success": False,
                "error": f"Document {document_id} not found"
            }), 404

def process_extraction_in_background(task_id, document_id, fields):
    """Process extraction in background thread"""
    try:
        # Update task status
        tasks[task_id]["status"] = "processing"
        
        # Extract data from vector store
        result = extract_data_from_vector_store(document_id, fields)
        
        if result.get("success", False):
            # Update task status
            tasks[task_id]["status"] = "completed"
            
            # Update fields status
            extracted_data = result.get("data", {})
            field_progress = result.get("field_progress", {})
            
            for field in tasks[task_id]["fields"]:
                field_name = field["field_name"]
                
                # Update field status based on extraction result
                if field_name in field_progress:
                    field["status"] = field_progress[field_name]
                else:
                    field["status"] = "completed"
                
                # Update field result
                if field_name in extracted_data:
                    field["result"] = extracted_data[field_name]
                
            logger.info(f"Extraction for task {task_id} completed successfully")
        else:
            # Update task status to failed
            tasks[task_id]["status"] = "failed"
            
            # Update all fields to failed
            for field in tasks[task_id]["fields"]:
                field["status"] = "failed"
                field["error"] = result.get("error", "Unknown error")
            
            logger.error(f"Extraction for task {task_id} failed: {result.get('error', 'Unknown error')}")
    
    except Exception as e:
        # Update task status to failed
        tasks[task_id]["status"] = "failed"
        
        # Update all fields to failed
        for field in tasks[task_id]["fields"]:
            field["status"] = "failed"
            field["error"] = str(e)
        
        logger.error(f"Error processing extraction for task {task_id}: {str(e)}")

@app.route('/documents/extract', methods=['POST'])
def extract_data():
    """Start data extraction using ChromaDB vector search"""
    data = request.json
    document_id = data.get("document_id")
    fields = data.get("fields", [])
    
    # Check if document exists in our local registry
    document_exists = document_id in documents
    
    # If not in local registry, check vector store
    if not document_exists:
        status = get_document_status(document_id)
        document_exists = status.get("success", False)
    
    if not document_exists:
        return jsonify({
            "success": False,
            "error": f"Document {document_id} not found"
        }), 404
    
    # Generate task ID
    task_id = str(uuid.uuid4())
    
    # Store task info
    tasks[task_id] = {
        "document_id": document_id,
        "fields": [
            {
                "field_name": field["name"],
                "status": "pending",
                "result": None,
                "error": None
            }
            for field in fields
        ],
        "status": "pending"
    }
    
    # Start background processing
    threading.Thread(
        target=process_extraction_in_background,
        args=(task_id, document_id, fields)
    ).start()
    
    # Return response
    return jsonify({
        "success": True,
        "document_id": document_id,
        "task_id": task_id,
        "message": "Extraction started"
    })

@app.route('/extraction/<task_id>/status', methods=['GET'])
def extraction_status(task_id):
    """Check extraction status"""
    # Check if task exists
    if task_id not in tasks:
        return jsonify({
            "success": False,
            "error": f"Task {task_id} not found"
        }), 404
    
    # Get task info
    task = tasks[task_id]
    
    # Check if all fields are completed
    completed = (
        task["status"] == "completed" or 
        task["status"] == "failed" or 
        all(field["status"] in ["completed", "failed"] for field in task["fields"])
    )
    
    if completed and task["status"] == "processing":
        task["status"] = "completed"
    
    # Return response
    return jsonify({
        "success": True,
        "document_id": task["document_id"],
        "task_id": task_id,
        "status": task["status"],
        "fields": task["fields"],
        "completed": completed
    })

@app.route('/extraction/<task_id>/result', methods=['GET'])
def extraction_result(task_id):
    """Get extraction results"""
    # Check if task exists
    if task_id not in tasks:
        return jsonify({
            "success": False,
            "error": f"Task {task_id} not found"
        }), 404
    
    # Get task info
    task = tasks[task_id]
    
    # Format results
    results = {
        field["field_name"]: field["result"]
        for field in task["fields"]
        if field["status"] == "completed" and field["result"] is not None
    }
    
    # Return response
    return jsonify({
        "success": True,
        "document_id": task["document_id"],
        "task_id": task_id,
        "results": results
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)