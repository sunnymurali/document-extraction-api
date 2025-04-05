"""
Data models for document extraction API
"""

from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


class DocumentStatus(str, Enum):
    """Document processing status"""
    PENDING = "pending"
    INDEXING = "indexing"
    INDEXED = "indexed"
    EXTRACTING = "extracting"
    COMPLETED = "completed"
    FAILED = "failed"


class FieldStatus(str, Enum):
    """Field extraction status"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ExtractionField(BaseModel):
    """Model for a single extraction field"""
    name: str = Field(..., description="The name of the field to extract")
    description: Optional[str] = Field(None, description="Description of the field to help with extraction")


class ExtractionSchema(BaseModel):
    """Model for defining the data extraction schema"""
    fields: List[ExtractionField] = Field(..., description="List of fields to extract with their descriptions")


class DocumentUploadRequest(BaseModel):
    """Request model for document upload"""
    document_id: Optional[str] = Field(None, description="Optional document ID for updates")


class DocumentUploadResponse(BaseModel):
    """Response model for document upload"""
    success: bool = Field(..., description="Whether the upload was successful")
    document_id: Optional[str] = Field(None, description="ID of the uploaded document")
    error: Optional[str] = Field(None, description="Error message if upload failed")


class IndexingRequest(BaseModel):
    """Request model for document indexing"""
    document_id: str = Field(..., description="ID of the document to index")


class IndexingResponse(BaseModel):
    """Response model for document indexing"""
    success: bool = Field(..., description="Whether the indexing was successful")
    document_id: str = Field(..., description="ID of the indexed document")
    error: Optional[str] = Field(None, description="Error message if indexing failed")
    status: DocumentStatus = Field(..., description="Status of the document")


class FieldExtractionRequest(BaseModel):
    """Request model for field extraction"""
    document_id: str = Field(..., description="ID of the document to extract from")
    field: ExtractionField = Field(..., description="Field to extract")


class FieldExtractionResponse(BaseModel):
    """Response model for field extraction"""
    success: bool = Field(..., description="Whether the extraction was successful")
    document_id: str = Field(..., description="ID of the document")
    field_name: str = Field(..., description="Name of the extracted field")
    value: Optional[Any] = Field(None, description="Extracted value")
    error: Optional[str] = Field(None, description="Error message if extraction failed")
    status: FieldStatus = Field(..., description="Status of the field extraction")


class DocumentStatusResponse(BaseModel):
    """Response model for document status"""
    document_id: str = Field(..., description="ID of the document")
    status: DocumentStatus = Field(..., description="Status of the document")
    field_statuses: Dict[str, FieldStatus] = Field(default_factory=dict, description="Status of each field extraction")
    error: Optional[str] = Field(None, description="Error message if processing failed")


class BatchExtractionRequest(BaseModel):
    """Request model for batch field extraction"""
    document_id: str = Field(..., description="ID of the document to extract from")
    fields: List[ExtractionField] = Field(..., description="Fields to extract")


class BatchExtractionResponse(BaseModel):
    """Response model for batch field extraction"""
    success: bool = Field(..., description="Whether the extraction request was successful")
    document_id: str = Field(..., description="ID of the document")
    status: str = Field(..., description="Status of the extraction request")
    message: str = Field(..., description="Information message")


class FieldExtractionStatus(BaseModel):
    """Status of a field extraction"""
    field_name: str = Field(..., description="Name of the field")
    status: str = Field(..., description="Status of the extraction (pending, processing, completed, failed)")
    result: Optional[Any] = Field(None, description="Extracted value if status is completed")
    error: Optional[str] = Field(None, description="Error message if status is failed")


class ExtractionStatusResponse(BaseModel):
    """Response model for extraction status"""
    success: bool = Field(..., description="Whether the status check was successful")
    document_id: str = Field(..., description="ID of the document")
    task_id: str = Field(..., description="ID of the extraction task")
    status: str = Field(..., description="Overall status of the extraction task")
    fields: List[FieldExtractionStatus] = Field(..., description="Status of each field extraction")
    completed: bool = Field(..., description="Whether all field extractions are complete")