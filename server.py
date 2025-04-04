"""
FastAPI Server Setup
This file contains the server setup for running the FastAPI application.
"""

import uvicorn

if __name__ == "__main__":
    # Run the FastAPI app with uvicorn (ASGI server)
    uvicorn.run("app:app", host="0.0.0.0", port=5000, reload=True)