"""
Document Chunking and Merging Utilities

This module provides utilities for splitting large documents into manageable chunks
and merging extraction results from multiple chunks into a unified result.
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
import json

# Configure logging - use WARNING level to reduce overhead
logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Constants for chunking - balance between coverage and performance
DEFAULT_CHUNK_SIZE = 6000   # Even larger chunks to better capture complex financial tables
DEFAULT_CHUNK_OVERLAP = 400  # Increased overlap to ensure complete financial tables between chunks
MAX_CHUNKS_TO_PROCESS = 8   # Process more chunks for Morgan Stanley and other complex financial documents

def split_text_into_chunks(text: str, chunk_size: int = DEFAULT_CHUNK_SIZE, 
                          chunk_overlap: int = DEFAULT_CHUNK_OVERLAP) -> List[str]:
    """
    Split a large text document into chunks with minimal processing overhead.
    
    Args:
        text: The text to split
        chunk_size: Target size of each chunk in characters
        chunk_overlap: Number of characters to overlap between chunks
        
    Returns:
        List of text chunks (limited to MAX_CHUNKS_TO_PROCESS)
    """
    if not text:
        return []
    
    # If text is small enough, return it as a single chunk
    if len(text) <= chunk_size:
        return [text]
    
    # Quick estimate of total chunks needed
    total_length = len(text)
    estimated_chunks = (total_length / (chunk_size - chunk_overlap)) + 1
    
    # If estimated chunks exceed our limit, adjust chunk size to process only important parts
    if estimated_chunks > MAX_CHUNKS_TO_PROCESS:
        # Strategy: Focus on beginning of document (usually contains more important info)
        # First half of max chunks from beginning, second half spread throughout the rest
        first_part_size = MAX_CHUNKS_TO_PROCESS // 2 * (chunk_size - chunk_overlap)
        if first_part_size >= total_length:
            # Document is small enough to process in MAX_CHUNKS_TO_PROCESS chunks
            pass
        else:
            # Process beginning and selected parts
            text = text[:first_part_size] + "\n\n[Content truncated for processing]\n\n" + text[-first_part_size:]
    
    chunks = []
    start = 0
    
    # Simple and efficient chunking - don't spend too much time looking for ideal boundaries
    while start < len(text) and len(chunks) < MAX_CHUNKS_TO_PROCESS:
        # Get a chunk of size chunk_size or the rest of the text
        end = min(start + chunk_size, len(text))
        
        # Only look for paragraph breaks, which is less CPU intensive
        if end < len(text):
            # Simple paragraph break search with a limit
            paragraph_end = text.rfind("\n\n", max(start, end - 200), end)
            if paragraph_end > 0:
                end = paragraph_end + 2
        
        # Add the chunk
        chunks.append(text[start:end])
        
        # Move to the next chunk, with overlap
        start = end - chunk_overlap
        
        # Break early if we've reached our limit
        if len(chunks) >= MAX_CHUNKS_TO_PROCESS:
            break
    
    logger.info(f"Split document into {len(chunks)} chunks")
    return chunks

def calculate_field_confidence(value: Any, chunk_index: int, total_chunks: int) -> float:
    """
    Simple and fast confidence calculation based primarily on chunk position.
    
    Args:
        value: The extracted value
        chunk_index: Index of the current chunk
        total_chunks: Total number of chunks
        
    Returns:
        Confidence score between 0 and 1
    """
    # Simplified confidence calculation
    # First chunk has highest confidence, decreasing for later chunks
    if chunk_index == 0:
        return 0.9  # First chunk has highest confidence
    elif value is None or (isinstance(value, str) and not value.strip()):
        return 0.1  # Empty values have low confidence
    else:
        # Simple position-based confidence calculation
        return max(0.1, min(0.8, 0.8 - (chunk_index / (total_chunks + 1)) * 0.5))

def merge_extraction_results(results: List[Dict[str, Any]], schema: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Optimized merging algorithm with less CPU-intensive operations.
    
    Args:
        results: List of extraction results from individual chunks
        schema: Optional schema defining the fields to extract
        
    Returns:
        Merged extraction result
    """
    if not results:
        return {}
    
    # Fast path for single result
    if len(results) == 1:
        # Filter out success/error keys if they exist
        result = {k: v for k, v in results[0].items() if k not in ["success", "error"]}
        return result
    
    merged_result = {}
    field_confidences = {}  # Track confidence for each field
    
    # Process each result with minimized operations
    for i, result in enumerate(results):
        if not result or not isinstance(result, dict):
            continue
        
        # Process only keys that might be valid fields (exclude metadata keys)
        for field, value in result.items():
            if field in ["success", "error"]:
                continue
                
            # Quick confidence calculation
            confidence = calculate_field_confidence(value, i, len(results))
            
            # Debug data to identify empty result issue
            logger.debug(f"Field: {field}, Value: {value}, Confidence: {confidence}")
            
            # Field doesn't exist or new value has higher confidence
            if field not in field_confidences or confidence > field_confidences[field]:
                # Skip empty values
                if value is not None and value != "":
                    merged_result[field] = value
                    field_confidences[field] = confidence
                elif field not in merged_result:
                    # Only add null if nothing exists for this field
                    merged_result[field] = value
                    field_confidences[field] = confidence
            
            # Only merge arrays if really necessary
            elif isinstance(value, list) and isinstance(merged_result.get(field), list):
                # Just extend for primitive lists (fast operation)
                if not value or not isinstance(value[0], dict):
                    merged_result[field].extend(value)
                else:
                    # Simplified deduplication for dictionary-based lists
                    # Only merge if confidence is close enough to be worth the effort
                    if confidence > field_confidences[field] * 0.8:
                        # Use a set for faster lookups
                        seen = set()
                        unique_items = []
                        
                        # Use the first key as identifier (faster than trying multiple keys)
                        if value[0]:
                            id_field = next(iter(value[0].keys()))
                            
                            # Process existing items
                            for item in merged_result[field]:
                                item_id = str(item.get(id_field, object()))  # Unique objects for missing ids
                                if item_id not in seen:
                                    seen.add(item_id)
                                    unique_items.append(item)
                            
                            # Add new items
                            for item in value:
                                item_id = str(item.get(id_field, object()))  # Unique objects for missing ids
                                if item_id not in seen:
                                    seen.add(item_id)
                                    unique_items.append(item)
                                    
                            merged_result[field] = unique_items
    
    logger.debug(f"Merged {len(results)} extraction results into a unified result")
    return merged_result

def process_chunks_with_progress(chunks: List[str], extractor_func, schema: Optional[Dict[str, Any]] = None):
    """
    Memory-optimized chunk processing with minimal logging.
    
    Args:
        chunks: List of text chunks to process
        extractor_func: Function that extracts data from a single chunk
        schema: Optional schema defining the fields to extract
        
    Returns:
        Tuple of (merged_result, progress_info)
    """
    # Preallocate result arrays to avoid dynamic resizing
    results = [{} for _ in range(len(chunks))]
    progress_info = []
    
    # Fast path for single chunk
    if len(chunks) == 1:
        try:
            logger.info("Processing single chunk document")
            single_result = extractor_func(chunks[0], schema)
            
            # Create simplified progress info
            progress_info = [{
                "chunk": 1,
                "total_chunks": 1,
                "chunk_size": len(chunks[0]),
                "percent_complete": 100.0,
                "fields_extracted": len(single_result) if single_result else 0,
                "status": "success"
            }]
            
            return single_result, progress_info
        except Exception as e:
            logger.error(f"Error processing single chunk: {e}")
            progress_info = [{
                "chunk": 1,
                "total_chunks": 1,
                "percent_complete": 100.0,
                "fields_extracted": 0,
                "status": "error",
                "error": str(e)
            }]
            return {}, progress_info
    
    # Process multiple chunks with minimal logging
    total_chunks = len(chunks)
    logger.info(f"Processing {total_chunks} chunks")
    
    # Track only essential metrics
    successful_chunks = 0
    
    for i, chunk in enumerate(chunks):
        # Only log at start and end of each chunk
        logger.info(f"Processing chunk {i+1}/{total_chunks}")
        
        # Extract data from this chunk
        try:
            chunk_result = extractor_func(chunk, schema)
            
            # Calculate basic metrics
            field_count = len(chunk_result) if chunk_result else 0
            field_names = list(chunk_result.keys())[:5] if chunk_result else []  # Only log first 5 fields
            
            # Only log success at warning level to reduce output
            if field_count > 0:
                logger.info(f"Chunk {i+1}: extracted {field_count} fields")
                successful_chunks += 1
            else:
                logger.warning(f"Chunk {i+1}: no fields extracted")
            
            # Store result directly in preallocated array
            results[i] = chunk_result if chunk_result else {}
            
            # Build progress info (minimal set of fields)
            progress_info.append({
                "chunk": i+1,
                "total_chunks": total_chunks,
                "percent_complete": (i+1) / total_chunks * 100,
                "fields_extracted": field_count,
                "status": "success"
            })
            
        except Exception as e:
            logger.error(f"Error processing chunk {i+1}: {str(e)[:100]}")
            
            # Progress info with error (minimized)
            progress_info.append({
                "chunk": i+1,
                "total_chunks": total_chunks,
                "percent_complete": (i+1) / total_chunks * 100,
                "status": "error",
                "error": str(e)[:100]  # Truncate long error messages
            })
    
    # Efficiently merge results
    logger.info(f"Merging results from {successful_chunks} successful chunks")
    merged_result = merge_extraction_results(results, schema)
    
    return merged_result, progress_info