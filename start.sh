#!/bin/bash
# Start the Flask application using Gunicorn with extended timeout
exec gunicorn --bind 0.0.0.0:5000 --reuse-port --reload --timeout 120 main:app