"""
Test FAISS Query

Simple script to test querying the FAISS vector store
"""

import os
import logging
import sys
from pathlib import Path

# Set up logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Import the vector store functions
try:
    from utils.vector_store import get_embeddings, get_vector_store
    logger.info("Successfully imported vector store functions")
except ImportError as e:
    logger.error(f"Error importing vector store functions: {str(e)}")
    sys.exit(1)

def test_faiss_query():
    """Test querying the FAISS vector store"""
    try:
        document_id = "test_1743908404"  # Use the ID from the previous test
        collection_name = f"doc_{document_id}"
        
        # Check if the vector store exists
        vector_db_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'vector_db')
        index_path = os.path.join(vector_db_dir, collection_name)
        
        if not os.path.exists(index_path):
            logger.error(f"Index path {index_path} does not exist")
            return False
        
        logger.info(f"Found FAISS index at {index_path}")
        
        # Load the vector store
        logger.info(f"Loading vector store for {collection_name}")
        vector_store = get_vector_store(collection_name)
        
        # Query the vector store
        query = "What is the revenue of Morgan Stanley?"
        logger.info(f"Querying vector store with: {query}")
        
        results = vector_store.similarity_search(query, k=1)
        
        if not results:
            logger.error("No results found")
            return False
        
        logger.info(f"Found {len(results)} results")
        logger.info(f"Top result content: {results[0].page_content[:200]}...")
        
        return True
        
    except Exception as e:
        logger.error(f"Error in FAISS query test: {str(e)}")
        return False

if __name__ == "__main__":
    success = test_faiss_query()
    if success:
        logger.info("Query test passed successfully")
        sys.exit(0)
    else:
        logger.error("Query test failed")
        sys.exit(1)