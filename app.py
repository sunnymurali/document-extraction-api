"""
Flask Application for Document Data Extraction
This application provides a simple web interface for demonstration purposes.
"""

import os
from flask import Flask, render_template, request, jsonify, send_from_directory
import uuid

# Create Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key")

# Storage for demo data
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

@app.route('/documents/upload', methods=['POST'])
def upload_document():
    """Handle document upload"""
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
        "status": "pending"
    }
    
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
    # Simulate document processing
    if document_id in documents:
        # Update status to indexed if it was pending
        if documents[document_id]["status"] == "pending":
            documents[document_id]["status"] = "indexed"
        
        return jsonify({
            "success": True,
            "document_id": document_id,
            "status": {
                "status": documents[document_id]["status"],
                "message": f"Document {documents[document_id]['status']}",
                "file_name": documents[document_id]["file_name"]
            }
        })
    else:
        return jsonify({
            "success": False,
            "error": f"Document {document_id} not found"
        }), 404

@app.route('/documents/extract', methods=['POST'])
def extract_data():
    """Start data extraction"""
    data = request.json
    document_id = data.get("document_id")
    fields = data.get("fields", [])
    
    # Check if document exists
    if document_id not in documents:
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
        "status": "processing"
    }
    
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
    
    # Simulate extraction completion
    if task["status"] == "processing":
        # Complete all pending fields
        for field in task["fields"]:
            if field["status"] == "pending":
                field["status"] = "completed"
                
                # Simulate extraction results based on field name
                if field["field_name"].lower() == "revenue":
                    field["result"] = "$12.3 billion"
                elif field["field_name"].lower() == "net_income":
                    field["result"] = "$2.1 billion"
                elif field["field_name"].lower() == "total_assets":
                    field["result"] = "$45.7 billion"
                elif field["field_name"].lower() == "earnings_per_share":
                    field["result"] = "$3.45"
                else:
                    field["result"] = f"Value for {field['field_name']}"
        
        # Update task status
        task["status"] = "completed"
    
    # Check if all fields are completed
    completed = all(field["status"] == "completed" for field in task["fields"])
    
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
        if field["status"] == "completed"
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