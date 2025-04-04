#!/bin/bash
# Start the FastAPI app using uvicorn
uvicorn asgi:application --host 0.0.0.0 --port 5000 --reload