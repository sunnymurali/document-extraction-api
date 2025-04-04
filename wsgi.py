"""
WSGI adapter for FastAPI application.
This allows using gunicorn with a FastAPI application.
"""

import os
import sys
from app import app

# Properly get the application from the app module
application = app