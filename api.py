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
import json
import asyncio
import logging
import tempfile
from typing import List, Dict, Any, Optional
from pathlib import Path
import uuid
import shutil

from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks, Form, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from fastapi.responses import JSONResponse

# LangGraph and LangChain imports
from langgraph.graph import END, StateGraph
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI, AzureOpenAIEmbeddings, AzureChatOpenAI
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import OpenAIEmbeddings
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Create uploads directory if it doesn't exist
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

# Configure vector database directory
VECTOR_DB_DIR = Path("vector_db")
VECTOR_DB_DIR.mkdir(exist_ok=True)

# Document store (in-memory for now)
document_store = {}
extraction_tasks = {}
extraction_results = {}

# Configure OpenAI API key
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
AZURE_OPENAI_API_KEY = os.environ.get("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_ENDPOINT = os.environ.get("AZURE_OPENAI_ENDPOINT")

# Define models
class DocumentUploadResponse(BaseModel):
    success: bool = Field(..., description="Whether the upload was successful")
    document_id: Optional[str] = Field(None, description="ID of the uploaded document")
    error: Optional[str] = Field(None, description="Error message if upload failed")
    indexing_status: Optional[str] = Field(None, description="Status of the indexing process")

class ExtractionField(BaseModel):
    name: str = Field(..., description="Name of the field to extract")
    description: str = Field(..., description="Description of the field to help with extraction")

class ExtractionRequest(BaseModel):
    document_id: str = Field(..., description="ID of the document to extract data from")
    fields: List[ExtractionField] = Field(..., description="Fields to extract from the document")

class ExtractionResponse(BaseModel):
    success: bool = Field(..., description="Whether the extraction was successful")
    document_id: str = Field(..., description="ID of the document")
    task_id: str = Field(..., description="ID of the extraction task")
    message: str = Field(..., description="Status message")

class FieldExtractionStatus(BaseModel):
    field_name: str = Field(..., description="Name of the field")
    status: str = Field(..., description="Status of the extraction (pending, processing, completed, failed)")
    result: Optional[Any] = Field(None, description="Extracted value if status is completed")
    error: Optional[str] = Field(None, description="Error message if status is failed")

class ExtractionStatusResponse(BaseModel):
    success: bool = Field(..., description="Whether the status check was successful")
    document_id: str = Field(..., description="ID of the document")
    task_id: str = Field(..., description="ID of the extraction task")
    status: str = Field(..., description="Overall status of the extraction task")
    fields: List[FieldExtractionStatus] = Field(..., description="Status of each field extraction")
    completed: bool = Field(..., description="Whether all field extractions are complete")

# Create FastAPI app
app = FastAPI(title="Document Extraction API",
              description="API for document upload, indexing, and extraction using LangGraph RAG")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Utility functions
def get_embeddings():
    """Get embeddings model with proper fallback"""
    try:
        # Try to use Azure OpenAI if configured
        if AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT:
            return AzureOpenAIEmbeddings(
                azure_deployment=os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME", "text-embedding-ada-002"),
                openai_api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2023-05-15"),
                azure_endpoint=AZURE_OPENAI_ENDPOINT,
                api_key=AZURE_OPENAI_API_KEY,
            )
        # Fall back to standard OpenAI
        return OpenAIEmbeddings(api_key=OPENAI_API_KEY)
    except Exception as e:
        logger.error(f"Error initializing embeddings: {str(e)}")
        raise

def get_vector_store(collection_name):
    """Get vector store for a specific collection"""
    try:
        embeddings = get_embeddings()
        
        # Create a persistent Chroma instance
        vector_store = Chroma(
            collection_name=collection_name,
            embedding_function=embeddings,
            persist_directory=str(VECTOR_DB_DIR)
        )
        
        return vector_store
    except Exception as e:
        logger.error(f"Error getting vector store: {str(e)}")
        raise

def get_llm():
    """Get language model with proper fallback"""
    try:
        # Try to use Azure OpenAI if configured
        if AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT:
            return AzureChatOpenAI(
                azure_deployment=os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o"),
                openai_api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2023-05-15"),
                azure_endpoint=AZURE_OPENAI_ENDPOINT,
                api_key=AZURE_OPENAI_API_KEY,
                temperature=0,
            )
        # Fall back to standard OpenAI
        # the newest OpenAI model is "gpt-4o" which was released May 13, 2024.
        # do not change this unless explicitly requested by the user
        return ChatOpenAI(model="gpt-4o", api_key=OPENAI_API_KEY, temperature=0)
    except Exception as e:
        logger.error(f"Error initializing language model: {str(e)}")
        raise

async def process_document(document_id: str, file_path: str, file_name: str):
    """Process a document by adding it to the vector store"""
    try:
        # Update document status
        document_store[document_id]["status"] = "processing"
        
        # Determine if this is a text file based on extension
        is_text_file = file_name.lower().endswith(('.txt', '.csv', '.json'))
        
        # Load the document with the appropriate loader
        if is_text_file:
            logger.info(f"Loading text file: {file_path}")
            loader = TextLoader(file_path, encoding='utf-8')
            docs = loader.load()
        else:
            logger.info(f"Loading PDF file: {file_path}")
            loader = PyPDFLoader(file_path)
            docs = loader.load()
        
        # Split the document into chunks
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1500,
            chunk_overlap=200,
            separators=["\n\n", "\n", ".", " ", ""],
            length_function=len,
        )
        
        chunks = text_splitter.split_documents(docs)
        
        # Update document metadata with chunk count
        document_store[document_id]["chunks"] = len(chunks)
        document_store[document_id]["pages"] = len(docs)
        
        # Get the vector store for this document
        collection_name = f"doc_{document_id}"
        vector_store = get_vector_store(collection_name)
        
        # Add chunks to vector store
        vector_store.add_documents(chunks)
        
        # Persist the vector store
        if hasattr(vector_store, 'persist'):
            vector_store.persist()
        
        # Update document status
        document_store[document_id]["status"] = "indexed"
        document_store[document_id]["indexed_at"] = time.time()
        
        logger.info(f"Document {document_id} indexed successfully with {len(chunks)} chunks")
        
    except Exception as e:
        # Update document status
        document_store[document_id]["status"] = "failed"
        document_store[document_id]["error"] = str(e)
        logger.error(f"Error processing document {document_id}: {str(e)}")

async def extract_field(document_id: str, task_id: str, field: ExtractionField):
    """Extract a single field from a document using LangGraph RAG"""
    field_name = field.name
    field_description = field.description
    
    try:
        # Update field status
        extraction_tasks[task_id]["fields"][field_name] = {
            "status": "processing",
            "result": None,
            "error": None,
            "started_at": time.time()
        }
        
        # Define the RAG workflow using LangGraph
        async def retrieve(state):
            """Retrieve relevant chunks from vector store"""
            try:
                collection_name = f"doc_{document_id}"
                vector_store = get_vector_store(collection_name)
                
                # Construct a focused query for this field
                query = f"Find information about {field_name}: {field_description}"
                
                # Retrieve relevant chunks
                docs = vector_store.similarity_search(query, k=3)
                
                # Extract and combine text from chunks
                context = "\n\n".join([doc.page_content for doc in docs])
                
                return {
                    "context": context,
                    "query": query,
                    "field_name": field_name,
                    "field_description": field_description
                }
            except Exception as e:
                logger.error(f"Error in retrieve step for field {field_name}: {str(e)}")
                return {
                    "context": "",
                    "query": "",
                    "field_name": field_name,
                    "field_description": field_description,
                    "error": str(e)
                }
        
        async def generate(state):
            """Extract field information from retrieved context"""
            try:
                # If there was an error in the retrieve step
                if "error" in state:
                    return {
                        "field_name": state["field_name"],
                        "field_value": None,
                        "error": state["error"]
                    }
                
                context = state["context"]
                field_name = state["field_name"]
                field_description = state["field_description"]
                
                # If context is empty, we can't extract anything
                if not context:
                    return {
                        "field_name": field_name,
                        "field_value": None,
                        "error": "No relevant content found for this field"
                    }
                
                # Set up messages for the LLM
                system_msg = SystemMessage(content=f"""
                You are a financial document extraction expert. Extract specific data from document excerpts.
                If the information is not present in the provided text, return null.
                Always respond with valid JSON in this format:
                {{
                    "field_value": extracted_value_or_null,
                    "confidence": number_between_0_and_1
                }}
                """)
                
                human_msg = HumanMessage(content=f"""
                I need to extract the value for "{field_name}" from this document.
                Field description: {field_description}
                
                Here is the text to extract from:
                ---
                {context}
                ---
                
                Extract only the precise value for this field. If the information is not present, 
                return null for field_value. Provide a confidence score between 0 and 1.
                """)
                
                # Get LLM
                llm = get_llm()
                
                # Call LLM with retry for rate limiting
                max_retries = 3
                retry_count = 0
                
                while retry_count < max_retries:
                    try:
                        response = await llm.ainvoke([system_msg, human_msg])
                        break
                    except Exception as e:
                        retry_count += 1
                        if "rate limit" in str(e).lower() and retry_count < max_retries:
                            # Exponential backoff for rate limiting
                            wait_time = 2 ** retry_count
                            logger.warning(f"Rate limit hit, retrying in {wait_time} seconds...")
                            await asyncio.sleep(wait_time)
                        else:
                            if retry_count >= max_retries:
                                logger.error(f"Max retries reached for field {field_name}")
                            return {
                                "field_name": field_name,
                                "field_value": None,
                                "error": str(e)
                            }
                
                # Parse response
                try:
                    result = json.loads(response.content)
                    return {
                        "field_name": field_name,
                        "field_value": result["field_value"],
                        "confidence": result.get("confidence", 0.0)
                    }
                except Exception as e:
                    logger.error(f"Error parsing LLM response for field {field_name}: {str(e)}")
                    return {
                        "field_name": field_name,
                        "field_value": None,
                        "error": f"Error parsing response: {str(e)}"
                    }
            
            except Exception as e:
                logger.error(f"Error in generate step for field {field_name}: {str(e)}")
                return {
                    "field_name": field_name,
                    "field_value": None,
                    "error": str(e)
                }
        
        # Construct the LangGraph workflow
        workflow = StateGraph(steps={"retrieve": retrieve, "generate": generate})
        
        # Define the workflow
        workflow.add_node("retrieve")
        workflow.add_node("generate")
        
        # Add edges
        workflow.add_edge("retrieve", "generate")
        workflow.add_edge("generate", END)
        
        # Set entry point
        workflow.set_entry_point("retrieve")
        
        # Compile the workflow
        app = workflow.compile()
        
        # Run the workflow
        result = await app.ainvoke({})
        
        # Process the result
        if "error" in result and result["error"]:
            extraction_tasks[task_id]["fields"][field_name] = {
                "status": "failed",
                "result": None,
                "error": result["error"],
                "completed_at": time.time()
            }
        else:
            extraction_tasks[task_id]["fields"][field_name] = {
                "status": "completed",
                "result": result["field_value"],
                "confidence": result.get("confidence", 0.0),
                "completed_at": time.time()
            }
        
        # Check if all fields are completed
        all_completed = all(
            task["status"] in ["completed", "failed"] 
            for task in extraction_tasks[task_id]["fields"].values()
        )
        
        if all_completed:
            extraction_tasks[task_id]["status"] = "completed"
            extraction_tasks[task_id]["completed_at"] = time.time()
            
            # Store extraction results
            extraction_results[task_id] = {
                "document_id": document_id,
                "task_id": task_id,
                "fields": {
                    field: task["result"] 
                    for field, task in extraction_tasks[task_id]["fields"].items()
                },
                "completed_at": time.time()
            }
            
        logger.info(f"Field {field_name} extraction completed for task {task_id}")
        
    except Exception as e:
        logger.error(f"Error extracting field {field_name} for task {task_id}: {str(e)}")
        extraction_tasks[task_id]["fields"][field_name] = {
            "status": "failed",
            "result": None,
            "error": str(e),
            "completed_at": time.time()
        }

# API endpoints
@app.post("/api/upload", response_model=DocumentUploadResponse)
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
        
        # Save file
        file_path = UPLOAD_DIR / f"{document_id}_{file.filename}"
        
        # Ensure the file is closed after saving
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Store document metadata
        document_store[document_id] = {
            "id": document_id,
            "filename": file.filename,
            "uploaded_at": time.time(),
            "status": "pending",
            "file_path": str(file_path),
            "size": os.path.getsize(file_path)
        }
        
        # Start background processing
        background_tasks.add_task(
            process_document, document_id, str(file_path), file.filename
        )
        
        return DocumentUploadResponse(
            success=True,
            document_id=document_id,
            indexing_status="pending"
        )
    
    except Exception as e:
        logger.error(f"Error uploading document: {str(e)}")
        return DocumentUploadResponse(
            success=False,
            error=str(e)
        )

@app.get("/api/document/{document_id}/status")
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
        if document_id not in document_store:
            raise HTTPException(status_code=404, detail=f"Document {document_id} not found")
        
        return JSONResponse(content={
            "success": True,
            "document_id": document_id,
            "status": document_store[document_id]["status"],
            "filename": document_store[document_id]["filename"],
            "uploaded_at": document_store[document_id]["uploaded_at"],
            "indexed_at": document_store[document_id].get("indexed_at"),
            "chunks": document_store[document_id].get("chunks"),
            "pages": document_store[document_id].get("pages"),
            "error": document_store[document_id].get("error")
        })
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting document status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/extract", response_model=ExtractionResponse)
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
        document_id = request.document_id
        
        # Check if document exists and is indexed
        if document_id not in document_store:
            raise HTTPException(status_code=404, detail=f"Document {document_id} not found")
        
        if document_store[document_id]["status"] != "indexed":
            raise HTTPException(
                status_code=400, 
                detail=f"Document {document_id} is not ready for extraction (status: {document_store[document_id]['status']})"
            )
        
        # Generate task ID
        task_id = str(uuid.uuid4())
        
        # Initialize extraction task
        extraction_tasks[task_id] = {
            "document_id": document_id,
            "task_id": task_id,
            "status": "pending",
            "created_at": time.time(),
            "fields": {
                field.name: {
                    "status": "pending",
                    "result": None,
                    "error": None
                } for field in request.fields
            }
        }
        
        # Start background extraction tasks for each field
        for field in request.fields:
            background_tasks.add_task(
                extract_field, document_id, task_id, field
            )
        
        # Update task status
        extraction_tasks[task_id]["status"] = "processing"
        
        return ExtractionResponse(
            success=True,
            document_id=document_id,
            task_id=task_id,
            message="Extraction started"
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting extraction: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/extract/{task_id}/status", response_model=ExtractionStatusResponse)
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
        if task_id not in extraction_tasks:
            raise HTTPException(status_code=404, detail=f"Extraction task {task_id} not found")
        
        task = extraction_tasks[task_id]
        
        # Prepare field status list
        fields = [
            FieldExtractionStatus(
                field_name=field_name,
                status=info["status"],
                result=info.get("result"),
                error=info.get("error")
            )
            for field_name, info in task["fields"].items()
        ]
        
        # Check if all fields are completed
        all_completed = all(
            field.status in ["completed", "failed"] for field in fields
        )
        
        return ExtractionStatusResponse(
            success=True,
            document_id=task["document_id"],
            task_id=task_id,
            status=task["status"],
            fields=fields,
            completed=all_completed
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting extraction status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/extract/{task_id}/result")
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
            raise HTTPException(status_code=404, detail=f"Extraction task {task_id} not found")
        
        task = extraction_tasks[task_id]
        
        # Check if task is completed
        if task["status"] != "completed":
            raise HTTPException(
                status_code=400, 
                detail=f"Extraction task {task_id} is not completed (status: {task['status']})"
            )
        
        # Return results
        return JSONResponse(content={
            "success": True,
            "document_id": task["document_id"],
            "task_id": task_id,
            "created_at": task["created_at"],
            "completed_at": task.get("completed_at"),
            "fields": {
                field_name: info.get("result")
                for field_name, info in task["fields"].items()
                if info["status"] == "completed"
            }
        })
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting extraction result: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/documents")
async def list_documents():
    """
    List all documents
    
    This endpoint returns a list of all documents in the system.
    
    Returns:
        JSON with list of documents
    """
    try:
        documents = []
        
        for doc_id, doc in document_store.items():
            documents.append({
                "id": doc_id,
                "filename": doc["filename"],
                "status": doc["status"],
                "uploaded_at": doc["uploaded_at"],
                "indexed_at": doc.get("indexed_at"),
                "chunks": doc.get("chunks"),
                "pages": doc.get("pages")
            })
        
        return JSONResponse(content={
            "success": True,
            "documents": documents,
            "count": len(documents)
        })
    
    except Exception as e:
        logger.error(f"Error listing documents: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Health check endpoint
@app.get("/api/health")
async def health_check():
    """
    Health check endpoint
    
    Returns:
        JSON with service status
    """
    return JSONResponse(content={
        "status": "ok",
        "timestamp": time.time(),
        "version": "1.0.0"
    })

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)