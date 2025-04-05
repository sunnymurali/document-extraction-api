"""
Adapters to make FastAPI work with different server types.
This module provides adapters to run FastAPI with WSGI servers like gunicorn.
"""

import logging
import sys
from io import BytesIO

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class WSGItoASGIAdapter:
    """
    WSGI to ASGI adapter for FastAPI to work with gunicorn.
    Based on uvicorn's WSGIMiddleware.
    """
    
    def __init__(self, app):
        self.app = app
    
    def __call__(self, environ, start_response):
        try:
            # Create a one-time event loop for this request
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
            # Extract relevant WSGI environment variables
            path = environ['PATH_INFO']
            query_string = environ.get('QUERY_STRING', '').encode()
            method = environ['REQUEST_METHOD']
            scheme = environ.get('wsgi.url_scheme', 'http')
            remote_addr = environ.get('REMOTE_ADDR', '')
            
            # Read the request body
            content_length = int(environ.get('CONTENT_LENGTH', '0'))
            body = environ['wsgi.input'].read(content_length) if content_length else b''
            
            # Process headers
            headers = []
            for key, value in environ.items():
                if key.startswith('HTTP_'):
                    name = key[5:].replace('_', '-').lower().encode()
                    headers.append((name, value.encode()))
                elif key in ('CONTENT_TYPE', 'CONTENT_LENGTH'):
                    name = key.replace('_', '-').lower().encode()
                    headers.append((name, value.encode()))
            
            # Create ASGI scope
            scope = {
                'type': 'http',
                'asgi': {
                    'version': '3.0',
                    'spec_version': '2.1',
                },
                'http_version': '1.1',
                'method': method,
                'scheme': scheme,
                'path': path,
                'query_string': query_string,
                'headers': headers,
                'client': (remote_addr, 0),
                'server': (environ.get('SERVER_NAME', ''), int(environ.get('SERVER_PORT', 0))),
                'extensions': {},
            }
            
            # Track response to return to WSGI
            status_code = None
            response_headers = None
            response_body = BytesIO()
            
            # ASGI receive function
            async def receive():
                return {
                    'type': 'http.request',
                    'body': body,
                    'more_body': False,
                }
            
            # ASGI send function
            async def send(message):
                nonlocal status_code, response_headers, response_body
                
                message_type = message['type']
                
                if message_type == 'http.response.start':
                    status_code = message['status']
                    response_headers = [
                        (key.decode('latin1'), value.decode('latin1'))
                        for key, value in message.get('headers', [])
                    ]
                elif message_type == 'http.response.body':
                    response_body.write(message.get('body', b''))
            
            # Run the ASGI app
            async def run_asgi():
                try:
                    await self.app(scope, receive, send)
                except Exception as e:
                    logger.exception(f"Error running ASGI app: {e}")
                    # Handle the error by setting a 500 status
                    if status_code is None:
                        status_code = 500
                        response_headers = [('Content-Type', 'text/plain')]
                        response_body.write(b'Internal Server Error')
            
            loop.run_until_complete(run_asgi())
            
            # Return the WSGI response
            if status_code is None:
                status_code = 500
                response_headers = [('Content-Type', 'text/plain')]
                response_body.write(b'Internal Server Error')
            
            start_response(f"{status_code} ", response_headers or [])
            response_body.seek(0)
            return [response_body.read()]
            
        except Exception as e:
            logger.exception(f"Unhandled exception in WSGI adapter: {e}")
            start_response('500 Internal Server Error', [('Content-Type', 'text/plain')])
            return [b'Internal Server Error']


def wsgi_app(environ, start_response):
    """
    WSGI entry point for FastAPI.
    """
    from main import app
    adapter = WSGItoASGIAdapter(app)
    return adapter(environ, start_response)