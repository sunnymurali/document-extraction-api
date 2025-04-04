"""
Main entry point for the application.
This file imports the FastAPI app and provides a callable variable for gunicorn.
"""

import os
import sys
from app import app

# Add the appropriate sys.path additions if needed
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# The application object that should be passed to Gunicorn/ASGI server
application = app