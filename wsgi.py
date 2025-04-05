"""
WSGI entry point for the Flask application

This module provides a WSGI-compatible entry point for gunicorn to serve the Flask application.
"""

from app import app

# WSGI entry point
application = app