"""ASGI adapter for FastAPI"""

import uvicorn
from fastapi import FastAPI
from app import app
import contextlib
import typing as t

# Create an ASGI application from the FastAPI app
application = app

# This adapter makes the FastAPI app WSGI-compatible
def wsgi_adapter(application: FastAPI):
    """Adapt a FastAPI app to run with WSGI servers."""
    
    @contextlib.asynccontextmanager
    async def lifespan(scope, receive, send):
        """Handle lifespan for WSGI compatibility."""
        yield
    
    # Replace lifespan protocol with a noop
    application.router.lifespan_context = lifespan
    
    async def asgi_to_wsgi_adapter(environ, start_response):
        """Convert WSGI to ASGI."""
        # Simplified WSGI to ASGI adapter
        path_info = environ.get('PATH_INFO', '')
        query_string = environ.get('QUERY_STRING', '').encode()
        
        scope = {
            'type': 'http',
            'asgi': {'version': '3.0'},
            'http_version': environ.get('SERVER_PROTOCOL', 'HTTP/1.1').split('/')[-1],
            'method': environ.get('REQUEST_METHOD', 'GET'),
            'scheme': environ.get('wsgi.url_scheme', 'http'),
            'path': path_info,
            'raw_path': path_info.encode(),
            'query_string': query_string,
            'headers': [(k.encode(), v.encode()) for k, v in environ.items()
                       if k.startswith('HTTP_')],
        }
        
        async def receive():
            # Simple receive function
            return {'type': 'http.request', 'body': environ.get('wsgi.input', b'')}
        
        async def send(message):
            # Simple send function for response
            if message['type'] == 'http.response.start':
                status = message.get('status', 200)
                headers = [(k.decode(), v.decode()) for k, v in message.get('headers', [])]
                start_response(f'{status} OK', headers)
            elif message['type'] == 'http.response.body':
                return message.get('body', b'')
        
        # Call the ASGI application
        return await application(scope, receive, send)
    
    return asgi_to_wsgi_adapter

# Expose WSGI-compatible application
wsgi_app = wsgi_adapter(app)