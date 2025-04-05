"""
Document Extraction API

This module provides a FastAPI application with endpoints for document upload, 
indexing, and extraction using LangGraph RAG approach.

Main APIs:
- Upload/Index API: Handles document upload and vectorization
- Extract API: Extracts specific fields using LangGraph RAG
"""

import os
import time
import uuid
import tempfile
import logging
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor

import uvicorn
from fastapi import FastAPI, File, UploadFile, BackgroundTasks, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from langgraph.graph import StateGraph
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.vectorstores import Chroma

from api.models import (
    DocumentStatus, 
    FieldStatus, 
    ExtractionField, 
    DocumentUploadResponse,
    ExtractionStatusResponse,
    FieldExtractionStatus
)
import api.vector_service as vector_service

# Create FastAPI app
app = FastAPI(
    title="Document Extraction API",
    description="API for document upload, indexing, and extraction",
    version="0.1.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Directory for uploads
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Thread pool for background tasks
thread_pool = ThreadPoolExecutor(max_workers=4)

# Storage for tasks
extraction_tasks = {}

# Set up templates
templates = Jinja2Templates(directory="templates")


# Response models for API
class ExtractionRequest(BaseModel):
    document_id: str = Field(..., description="ID of the document to extract data from")
    fields: List[ExtractionField] = Field(..., description="Fields to extract from the document")


class ExtractionResponse(BaseModel):
    success: bool = Field(..., description="Whether the extraction was successful")
    document_id: str = Field(..., description="ID of the document")
    task_id: str = Field(..., description="ID of the extraction task")
    message: str = Field(..., description="Status message")


def get_embeddings():
    """Get embeddings model with proper fallback"""
    try:
        # Try using Azure OpenAI if configured
        if os.environ.get("AZURE_OPENAI_API_KEY") and os.environ.get("AZURE_OPENAI_ENDPOINT"):
            from langchain_openai import AzureOpenAIEmbeddings
            return AzureOpenAIEmbeddings(
                azure_deployment=os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME"),
                openai_api_version=os.environ.get("AZURE_OPENAI_API_VERSION"),
                azure_endpoint=os.environ.get("AZURE_OPENAI_ENDPOINT"),
                api_key=os.environ.get("AZURE_OPENAI_API_KEY"),
            )
        else:
            # Fall back to standard OpenAI
            return OpenAIEmbeddings()
    except Exception as e:
        logger.error(f"Error initializing embeddings: {str(e)}")
        raise


def get_vector_store(collection_name):
    """Get vector store for a specific collection"""
    try:
        embeddings = get_embeddings()
        vector_store_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vector_db")
        
        # Ensure vector store directory exists
        os.makedirs(vector_store_dir, exist_ok=True)
        
        # Create and return vector store
        return Chroma(
            collection_name=collection_name,
            embedding_function=embeddings,
            persist_directory=vector_store_dir
        )
    except Exception as e:
        logger.error(f"Error getting vector store: {str(e)}")
        raise


def get_llm():
    """Get language model with proper fallback"""
    try:
        # Try using Azure OpenAI if configured
        if os.environ.get("AZURE_OPENAI_API_KEY") and os.environ.get("AZURE_OPENAI_ENDPOINT"):
            from langchain_openai import AzureChatOpenAI
            return AzureChatOpenAI(
                azure_deployment=os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME"),
                openai_api_version=os.environ.get("AZURE_OPENAI_API_VERSION"),
                azure_endpoint=os.environ.get("AZURE_OPENAI_ENDPOINT"),
                api_key=os.environ.get("AZURE_OPENAI_API_KEY"),
                temperature=0
            )
        else:
            # Fall back to standard OpenAI
            # the newest OpenAI model is "gpt-4o" which was released May 13, 2024.
            # do not change this unless explicitly requested by the user
            return ChatOpenAI(temperature=0, model="gpt-4o")
    except Exception as e:
        logger.error(f"Error initializing LLM: {str(e)}")
        raise


async def process_document(document_id: str, file_path: str, file_name: str):
    """Process a document by adding it to the vector store"""
    try:
        # Read the file content
        with open(file_path, "rb") as file:
            file_content = file.read()
        
        # Index the document
        result = await vector_service.index_document(document_id)
        
        if not result["success"]:
            logger.error(f"Error indexing document: {result.get('error')}")
        
        return result
    except Exception as e:
        logger.error(f"Error processing document: {str(e)}")
        return {
            "success": False,
            "document_id": document_id,
            "error": f"Error processing document: {str(e)}"
        }


async def extract_field(document_id: str, task_id: str, field: ExtractionField):
    """Extract a single field from a document using LangGraph RAG"""
    try:
        # Create a StateGraph for RAG
        workflow = StateGraph(name=f"extract_{field.name}")
        
        # Initial state
        workflow.add_node("retrieve", lambda x: x)
        workflow.add_node("generate", lambda x: x)
        
        # Connect nodes
        workflow.add_edge("retrieve", "generate")
        
        # Define retrieval function
        async def retrieve(state):
            """Retrieve relevant chunks from vector store"""
            try:
                # Create collection name from document ID
                collection_name = f"doc_{document_id}"
                
                # Get vector store
                vector_store = get_vector_store(collection_name)
                
                # Create query from field
                field_desc = field.description or f"information about {field.name}"
                query = f"Find {field.name}: {field_desc}"
                
                # Search for relevant chunks
                relevant_chunks = vector_store.similarity_search(query, k=3)
                
                # Update task status
                if task_id in extraction_tasks:
                    task = extraction_tasks[task_id]
                    for i, f in enumerate(task["fields"]):
                        if f["field_name"] == field.name:
                            task["fields"][i]["status"] = FieldStatus.PROCESSING
                
                # Combine chunks into context
                context = "\n\n".join([chunk.page_content for chunk in relevant_chunks])
                
                # Return state with context
                return {"context": context, "field": field.model_dump()}
            except Exception as e:
                logger.error(f"Error in retrieve node: {str(e)}")
                raise
        
        # Define generation function
        async def generate(state):
            """Extract field information from retrieved context"""
            try:
                # Get LLM
                llm = get_llm()
                
                # Create prompt
                from langchain_core.prompts import ChatPromptTemplate
                prompt = ChatPromptTemplate.from_template("""
                You are an expert at extracting structured information from documents.
                Extract the value for the field {field_name} from the following context.
                
                Field description: {field_description}
                
                Context:
                {context}
                
                Return ONLY the extracted value for {field_name}. If you cannot find the value, return null.
                If you find a value, include the units if applicable.
                """)
                
                # Extract value
                field_name = state["field"]["name"]
                field_description = state["field"].get("description", f"Information about {field_name}")
                
                # Create chain
                chain = prompt | llm
                
                # Run chain
                result = await chain.ainvoke({
                    "field_name": field_name,
                    "field_description": field_description,
                    "context": state["context"]
                })
                
                # Parse result
                extracted_value = result.content.strip()
                
                # Handle "null" responses
                if extracted_value.lower() in ["null", "none", "not found", "not available", "n/a"]:
                    extracted_value = None
                
                # Update task status and result
                if task_id in extraction_tasks:
                    task = extraction_tasks[task_id]
                    for i, f in enumerate(task["fields"]):
                        if f["field_name"] == field_name:
                            task["fields"][i]["status"] = FieldStatus.COMPLETED
                            task["fields"][i]["result"] = extracted_value
                
                # Return state with extracted value
                return {**state, "result": extracted_value}
            except Exception as e:
                logger.error(f"Error in generate node: {str(e)}")
                
                # Update task status as failed
                if task_id in extraction_tasks:
                    task = extraction_tasks[task_id]
                    for i, f in enumerate(task["fields"]):
                        if f["field_name"] == field.name:
                            task["fields"][i]["status"] = FieldStatus.FAILED
                            task["fields"][i]["error"] = str(e)
                
                raise
        
        # Set up node functions
        workflow.set_node_function("retrieve", retrieve)
        workflow.set_node_function("generate", generate)
        
        # Compile the graph
        app = workflow.compile()
        
        # Run the graph
        result = await app.ainvoke({})
        
        return result
    except Exception as e:
        logger.error(f"Error extracting field {field.name}: {str(e)}")
        
        # Update task status as failed
        if task_id in extraction_tasks:
            task = extraction_tasks[task_id]
            for i, f in enumerate(task["fields"]):
                if f["field_name"] == field.name:
                    task["fields"][i]["status"] = FieldStatus.FAILED
                    task["fields"][i]["error"] = str(e)
        
        return {
            "error": f"Error extracting field: {str(e)}",
            "field": field.model_dump()
        }


@app.post("/documents/upload", response_model=DocumentUploadResponse)
async def upload_document(
    background_tasks: BackgroundTasks, 
    file: UploadFile = File(...),
):
    """
    Upload and index a document
    
    This endpoint handles document upload and initiates background indexing.
    
    Returns:
        DocumentUploadResponse: Upload response with document ID
    """
    try:
        # Generate document ID
        document_id = str(uuid.uuid4())
        
        # Create temp file
        temp_file = tempfile.NamedTemporaryFile(delete=False)
        file_path = temp_file.name
        
        # Write file content to temp file
        file_content = await file.read()
        with open(file_path, "wb") as f:
            f.write(file_content)
        
        # Upload document to vector store service
        upload_result = await vector_service.upload_document(file_content, file.filename, document_id)
        
        if not upload_result["success"]:
            return JSONResponse(
                status_code=500,
                content={
                    "success": False,
                    "error": upload_result.get("error", "Error uploading document")
                }
            )
        
        # Start background indexing task
        background_tasks.add_task(process_document, document_id, file_path, file.filename)
        
        return {
            "success": True,
            "document_id": document_id,
            "error": None
        }
    except Exception as e:
        logger.error(f"Error uploading document: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": f"Error uploading document: {str(e)}"
            }
        )


@app.get("/documents/{document_id}/status")
async def get_document_status(document_id: str):
    """
    Get document indexing status
    
    This endpoint returns the current status of document indexing.
    
    Args:
        document_id: ID of the document
        
    Returns:
        JSON with document status information
    """
    try:
        # Get document status
        status = vector_service.get_document_status(document_id)
        
        if not status:
            return JSONResponse(
                status_code=404,
                content={
                    "success": False,
                    "error": f"Document {document_id} not found"
                }
            )
        
        return {
            "success": True,
            "document_id": document_id,
            "status": status
        }
    except Exception as e:
        logger.error(f"Error getting document status: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": f"Error getting document status: {str(e)}"
            }
        )


@app.post("/documents/extract", response_model=ExtractionResponse)
async def extract_data(
    background_tasks: BackgroundTasks,
    request: ExtractionRequest,
):
    """
    Extract data from a document
    
    This endpoint initiates asynchronous field extraction using LangGraph RAG.
    
    Args:
        request: Extraction request with document ID and fields
        
    Returns:
        ExtractionResponse: Response with task ID for status tracking
    """
    try:
        # Get document ID and fields
        document_id = request.document_id
        fields = request.fields
        
        # Check if document exists
        status = vector_service.get_document_status(document_id)
        if not status:
            return JSONResponse(
                status_code=404,
                content={
                    "success": False,
                    "error": f"Document {document_id} not found"
                }
            )
        
        # Check if document is indexed
        if status["status"] != DocumentStatus.INDEXED and status["status"] != DocumentStatus.COMPLETED:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "error": f"Document {document_id} is not indexed (status: {status['status']})"
                }
            )
        
        # Generate task ID
        task_id = str(uuid.uuid4())
        
        # Create extraction task
        extraction_tasks[task_id] = {
            "document_id": document_id,
            "task_id": task_id,
            "created_at": time.time(),
            "status": "pending",
            "fields": [
                {
                    "field_name": field.name,
                    "status": FieldStatus.PENDING,
                    "result": None,
                    "error": None
                }
                for field in fields
            ],
            "completed": False
        }
        
        # Start background extraction task for each field
        for field in fields:
            background_tasks.add_task(extract_field, document_id, task_id, field)
        
        # Update task status
        extraction_tasks[task_id]["status"] = "processing"
        
        return {
            "success": True,
            "document_id": document_id,
            "task_id": task_id,
            "message": f"Started extraction of {len(fields)} fields"
        }
    except Exception as e:
        logger.error(f"Error starting extraction: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": f"Error starting extraction: {str(e)}"
            }
        )


@app.get("/tasks/{task_id}/status", response_model=ExtractionStatusResponse)
async def get_extraction_status(task_id: str):
    """
    Get extraction task status
    
    This endpoint returns the current status of an extraction task.
    
    Args:
        task_id: ID of the extraction task
        
    Returns:
        ExtractionStatusResponse: Current status of the extraction task
    """
    try:
        # Check if task exists
        if task_id not in extraction_tasks:
            return JSONResponse(
                status_code=404,
                content={
                    "success": False,
                    "error": f"Task {task_id} not found"
                }
            )
        
        # Get task
        task = extraction_tasks[task_id]
        
        # Check if all fields are completed or failed
        all_completed = all(
            f["status"] in [FieldStatus.COMPLETED, FieldStatus.FAILED]
            for f in task["fields"]
        )
        
        # Update task status
        if all_completed and task["status"] != "completed":
            task["status"] = "completed"
            task["completed"] = True
            task["completed_at"] = time.time()
        
        # Create field status list
        fields = [
            FieldExtractionStatus(
                field_name=f["field_name"],
                status=f["status"],
                result=f.get("result"),
                error=f.get("error")
            )
            for f in task["fields"]
        ]
        
        return {
            "success": True,
            "document_id": task["document_id"],
            "task_id": task_id,
            "status": task["status"],
            "fields": fields,
            "completed": task["completed"]
        }
    except Exception as e:
        logger.error(f"Error getting extraction status: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": f"Error getting extraction status: {str(e)}"
            }
        )


@app.get("/tasks/{task_id}/result")
async def get_extraction_result(task_id: str):
    """
    Get extraction task result
    
    This endpoint returns the results of a completed extraction task.
    
    Args:
        task_id: ID of the extraction task
        
    Returns:
        JSON with extraction results
    """
    try:
        # Check if task exists
        if task_id not in extraction_tasks:
            return JSONResponse(
                status_code=404,
                content={
                    "success": False,
                    "error": f"Task {task_id} not found"
                }
            )
        
        # Get task
        task = extraction_tasks[task_id]
        
        # Check if task is completed
        if not task.get("completed", False):
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "error": f"Task {task_id} is not completed (status: {task['status']})"
                }
            )
        
        # Create result dictionary
        result = {
            f["field_name"]: f.get("result")
            for f in task["fields"]
            if f["status"] == FieldStatus.COMPLETED
        }
        
        return {
            "success": True,
            "document_id": task["document_id"],
            "task_id": task_id,
            "data": result,
            "completed_time": task.get("completed_at"),
            "error": None
        }
    except Exception as e:
        logger.error(f"Error getting extraction result: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": f"Error getting extraction result: {str(e)}"
            }
        )


@app.get("/documents")
async def list_documents():
    """
    List all documents
    
    This endpoint returns a list of all documents in the system.
    
    Returns:
        JSON with list of documents
    """
    try:
        # Get all document statuses
        documents = []
        for doc_id, status in vector_service.document_statuses.items():
            # Add metadata
            doc_info = {
                "document_id": doc_id,
                "status": status["status"],
                "filename": vector_service.document_metadata.get(doc_id, {}).get("filename", "Unknown"),
                "upload_time": vector_service.document_metadata.get(doc_id, {}).get("upload_time"),
                "field_count": len(status.get("field_statuses", {}))
            }
            documents.append(doc_info)
        
        return {
            "success": True,
            "documents": documents,
            "count": len(documents)
        }
    except Exception as e:
        logger.error(f"Error listing documents: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": f"Error listing documents: {str(e)}"
            }
        )


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """
    Render the main application page
    
    This endpoint renders the HTML template for the application UI.
    
    Args:
        request: The incoming request
        
    Returns:
        HTMLResponse with the rendered index.html template
    """
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/health")
async def health_check():
    """
    Health check endpoint
    
    Returns:
        JSON with service status
    """
    return {
        "status": "online",
        "timestamp": time.time()
    }


# Serve static files
app.mount("/static", StaticFiles(directory="static"), name="static")


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=5000, reload=True)