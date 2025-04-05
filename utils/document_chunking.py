"""
Document Chunking and Merging Utilities

This module provides utilities for splitting large documents into manageable chunks
and merging extraction results from multiple chunks into a unified result.
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
import json

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Constants for chunking
DEFAULT_CHUNK_SIZE = 4000
DEFAULT_CHUNK_OVERLAP = 500
MAX_CHUNKS_TO_PROCESS = 20  # Safety limit to prevent excessive API calls

def split_text_into_chunks(text: str, chunk_size: int = DEFAULT_CHUNK_SIZE, 
                          chunk_overlap: int = DEFAULT_CHUNK_OVERLAP) -> List[str]:
    """
    Split a large text document into overlapping chunks of approximately equal size.
    
    Args:
        text: The text to split
        chunk_size: Target size of each chunk in characters
        chunk_overlap: Number of characters to overlap between chunks
        
    Returns:
        List of text chunks
    """
    if not text:
        return []
    
    # If text is small enough, return it as a single chunk
    if len(text) <= chunk_size:
        return [text]
    
    chunks = []
    start = 0
    
    while start < len(text):
        # Get a chunk of size chunk_size or the rest of the text
        end = min(start + chunk_size, len(text))
        
        # If this isn't the last chunk, try to end at a paragraph or sentence boundary
        if end < len(text):
            # Look for paragraph breaks first
            paragraph_end = text.rfind("\n\n", start, end)
            if paragraph_end > start + chunk_size // 2:  # If a paragraph break is in the second half of the chunk
                end = paragraph_end + 2  # Include the double newline
            else:
                # Otherwise look for sentence breaks (periods followed by space)
                sentence_end = text.rfind(". ", start, end)
                if sentence_end > start + chunk_size // 2:  # If a sentence break is in the second half of the chunk
                    end = sentence_end + 2  # Include the period and space
        
        # Add the chunk
        chunks.append(text[start:end])
        
        # Move to the next chunk, with overlap
        start = max(start, end - chunk_overlap)
        
        # Stop if we've reached the end of the text
        if start >= len(text):
            break
    
    logger.info(f"Split document into {len(chunks)} chunks")
    
    # Apply safety limit
    if len(chunks) > MAX_CHUNKS_TO_PROCESS:
        logger.warning(f"Document produced {len(chunks)} chunks, limiting to {MAX_CHUNKS_TO_PROCESS}")
        chunks = chunks[:MAX_CHUNKS_TO_PROCESS]
    
    return chunks

def calculate_field_confidence(value: Any, chunk_index: int, total_chunks: int) -> float:
    """
    Calculate a confidence score for an extracted field based on its value and position in the document.
    
    Args:
        value: The extracted value
        chunk_index: Index of the current chunk
        total_chunks: Total number of chunks
        
    Returns:
        Confidence score between 0 and 1
    """
    # Base confidence is higher for early chunks (typically contain headers and important info)
    position_factor = 1.0 - (chunk_index / (total_chunks * 2))  # Higher confidence for earlier chunks
    
    # Null values have minimum confidence
    if value is None:
        return 0.1
    
    # Empty strings or empty lists have low confidence
    if (isinstance(value, str) and not value.strip()) or (isinstance(value, list) and not value):
        return 0.2
    
    # Give higher confidence to non-empty values
    base_confidence = 0.7
    
    # Adjust based on position
    confidence = base_confidence + (position_factor * 0.3)
    
    # Ensure confidence is between 0 and 1
    return max(0.1, min(0.99, confidence))

def merge_extraction_results(results: List[Dict[str, Any]], schema: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Merge extraction results from multiple chunks into a unified result.
    
    Args:
        results: List of extraction results from individual chunks
        schema: Optional schema defining the fields to extract
        
    Returns:
        Merged extraction result
    """
    if not results:
        return {}
    
    merged_result = {}
    field_confidences = {}  # Track confidence for each field
    
    # Extract field names from schema if available
    schema_fields = []
    if schema and "fields" in schema:
        schema_fields = [field["name"] for field in schema["fields"]]
    
    # Process each result
    for i, result in enumerate(results):
        if not result or not isinstance(result, dict):
            continue
        
        # Calculate position-based confidence
        for field, value in result.items():
            # Skip the "success" and "error" fields which might be in the top-level result
            if field in ["success", "error"]:
                continue
                
            # Calculate confidence for this field
            confidence = calculate_field_confidence(value, i, len(results))
            
            # If field is not in merged_result or has higher confidence than previous value
            if field not in field_confidences or confidence > field_confidences[field]:
                merged_result[field] = value
                field_confidences[field] = confidence
            elif isinstance(value, list) and isinstance(merged_result.get(field), list):
                # Special handling for arrays - merge them
                merged_result[field].extend(value)
                # Remove duplicates if items are dictionaries
                if merged_result[field] and isinstance(merged_result[field][0], dict):
                    # Try to deduplicate based on a first field that might be an identifier
                    if merged_result[field][0]:
                        id_field = next(iter(merged_result[field][0].keys()))
                        seen = set()
                        unique_items = []
                        for item in merged_result[field]:
                            item_id = item.get(id_field, "")
                            if item_id and item_id not in seen:
                                seen.add(item_id)
                                unique_items.append(item)
                        merged_result[field] = unique_items
    
    logger.info(f"Merged {len(results)} extraction results into a unified result")
    return merged_result

def process_chunks_with_progress(chunks: List[str], extractor_func, schema: Optional[Dict[str, Any]] = None):
    """
    Process text chunks with a progress callback.
    
    Args:
        chunks: List of text chunks to process
        extractor_func: Function that extracts data from a single chunk
        schema: Optional schema defining the fields to extract
        
    Returns:
        Tuple of (merged_result, progress_info)
    """
    results = []
    progress_info = []
    
    total_chunks = len(chunks)
    logger.info(f"Processing {total_chunks} chunks")
    
    for i, chunk in enumerate(chunks):
        logger.info(f"Processing chunk {i+1}/{total_chunks} ({len(chunk)} characters)")
        logger.info(f"Chunk {i+1} preview: {chunk[:100]}...")
        
        # Extract data from this chunk
        try:
            logger.info(f"Calling extraction function for chunk {i+1}")
            chunk_result = extractor_func(chunk, schema)
            
            # Log fields extracted
            field_count = len(chunk_result) if chunk_result else 0
            field_names = list(chunk_result.keys()) if chunk_result else []
            logger.info(f"Chunk {i+1} processed successfully with {field_count} fields: {field_names}")
            
            # Add to results
            if chunk_result:
                results.append(chunk_result)
            else:
                logger.warning(f"Chunk {i+1} returned empty result")
                results.append({})  # Add empty dict to keep index alignment
            
            # Update progress
            progress_info.append({
                "chunk": i+1,
                "total_chunks": total_chunks,
                "chunk_size": len(chunk),
                "percent_complete": (i+1) / total_chunks * 100,
                "fields_extracted": field_count,
                "status": "success"
            })
            
        except Exception as e:
            logger.error(f"Error processing chunk {i+1}/{total_chunks}: {e}")
            
            # Add empty result for this chunk to keep index alignment
            results.append({})
            
            # Update progress with error
            progress_info.append({
                "chunk": i+1,
                "total_chunks": total_chunks,
                "chunk_size": len(chunk),
                "percent_complete": (i+1) / total_chunks * 100,
                "fields_extracted": 0,
                "status": "error",
                "error": str(e)
            })
    
    # Merge results
    logger.info(f"Merging results from {len(results)} chunks (successful: {sum(1 for p in progress_info if p.get('status') == 'success')})")
    merged_result = merge_extraction_results(results, schema)
    logger.info(f"Merge complete, final result has {len(merged_result)} fields: {list(merged_result.keys())}")
    
    return merged_result, progress_info