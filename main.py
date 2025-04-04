"""
Main entry point for the Document Data Extractor application
"""

import os
import sys
from app import app

# The application object for Gunicorn
application = app