"""
ASGI entry point for the FastAPI application
"""

from app import app

# Make the application importable for ASGI servers
application = app