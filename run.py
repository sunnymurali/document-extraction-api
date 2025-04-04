import uvicorn

if __name__ == "__main__":
    # Run the FastAPI app using uvicorn
    uvicorn.run("asgi:application", host="0.0.0.0", port=5000, reload=True)