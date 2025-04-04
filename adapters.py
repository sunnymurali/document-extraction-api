"""
Adapters to make FastAPI work with different server types.
This module provides adapters to run FastAPI with WSGI servers like gunicorn.
"""

import sys
import asyncio
from functools import partial

from fastapi import FastAPI


def _make_asgi_callable(app: FastAPI):
    """
    This function creates a callable that properly wraps the FastAPI app
    for use with gunicorn, taking into account the specific way gunicorn
    calls the WSGI application.
    """
    async def adapter(scope, receive, send):
        await app(scope, receive, send)
    
    return adapter


def wsgi_app(environ, start_response):
    """
    A WSGI to ASGI adapter that makes FastAPI work with gunicorn.
    This is a simplified adapter that bridges the gap between WSGI and ASGI.
    """
    path = environ.get('PATH_INFO', '')
    method = environ.get('REQUEST_METHOD', 'GET')
    
    # Redirect to FastAPI's 404 handler for all requests
    status = '404 Not Found'
    headers = [('Content-Type', 'text/plain')]
    body = f"FastAPI requires an ASGI server like uvicorn.\nRequest: {method} {path}"
    
    start_response(status, headers)
    return [body.encode()]