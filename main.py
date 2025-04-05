"""
Document Extraction API - Flask Version

This module provides a Flask application wrapper for the document extraction functionality.
"""

from app import app

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)