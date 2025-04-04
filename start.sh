#!/bin/bash
# Start the FastAPI application using uvicorn (ASGI server)
exec uvicorn app:app --host 0.0.0.0 --port 5000 --reload