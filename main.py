import uvicorn
from app import app

# For direct execution with python main.py
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=5000, reload=True)
