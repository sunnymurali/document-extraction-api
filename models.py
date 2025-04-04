from pydantic import BaseModel
from typing import Dict, Any, Optional, List

class ExtractionSchema(BaseModel):
    """Model for defining the data extraction schema"""
    fields: List[Dict[str, str]]
    
class ExtractionRequest(BaseModel):
    """Model for the extraction request"""
    schema: Optional[ExtractionSchema] = None
    
class ExtractionResponse(BaseModel):
    """Model for the extraction response"""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
