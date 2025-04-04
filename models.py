"""
Data models for the PDF extraction API
"""

from typing import Dict, List, Any, Optional

from pydantic import BaseModel, Field


class ExtractionField(BaseModel):
    """Model for a single extraction field"""
    name: str = Field(..., description="The name of the field to extract")
    description: Optional[str] = Field(None, description="Description of the field to help with extraction")


class ExtractionSchema(BaseModel):
    """Model for defining the data extraction schema"""
    fields: List[Dict[str, str]] = Field(..., description="List of fields to extract with their descriptions")


class ExtractionRequest(BaseModel):
    """Model for the extraction request"""
    extraction_schema: Optional[ExtractionSchema] = Field(None, description="Schema defining the fields to extract")


class ExtractionResponse(BaseModel):
    """Model for the extraction response"""
    success: bool = Field(..., description="Whether the extraction was successful")
    data: Optional[Dict[str, Any]] = Field(None, description="The extracted data")
    error: Optional[str] = Field(None, description="Error message if extraction failed")