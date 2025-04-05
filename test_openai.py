import os
import openai
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_openai_api():
    """Test OpenAI API connection"""
    try:
        # Get API key from environment
        api_key = os.environ.get('OPENAI_API_KEY')
        logger.info(f"Using API key: {api_key[:5]}...{api_key[-5:] if api_key else None}")
        
        # Create client
        client = openai.OpenAI(api_key=api_key)
        
        # Test completion
        logger.info("Sending test request to OpenAI API...")
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",  # Uses less tokens than gpt-4
            messages=[{"role": "user", "content": "Hello, this is a test."}],
            max_tokens=10
        )
        
        logger.info(f"Response received: {response.choices[0].message.content}")
        return True
    except Exception as e:
        logger.error(f"API test failed: {str(e)}")
        return False

def test_azure_openai_api():
    """Test Azure OpenAI API connection"""
    try:
        # Get Azure OpenAI credentials from environment
        api_key = os.environ.get('AZURE_OPENAI_API_KEY')
        endpoint = os.environ.get('AZURE_OPENAI_ENDPOINT')
        deployment = os.environ.get('AZURE_OPENAI_DEPLOYMENT_NAME')
        api_version = os.environ.get('AZURE_OPENAI_API_VERSION')
        
        logger.info(f"Azure OpenAI Endpoint: {endpoint}")
        logger.info(f"Azure OpenAI Deployment: {deployment}")
        logger.info(f"Azure OpenAI API Version: {api_version}")
        logger.info(f"Using Azure API key: {api_key[:5]}...{api_key[-5:] if api_key else None}")
        
        # Create Azure OpenAI client
        client = openai.AzureOpenAI(
            api_key=api_key,
            azure_endpoint=endpoint,
            api_version=api_version
        )
        
        # Test completion
        logger.info("Sending test request to Azure OpenAI API...")
        response = client.chat.completions.create(
            model=deployment,
            messages=[{"role": "user", "content": "Hello, this is a test."}],
            max_tokens=10
        )
        
        logger.info(f"Azure response received: {response.choices[0].message.content}")
        return True
    except Exception as e:
        logger.error(f"Azure API test failed: {str(e)}")
        return False

if __name__ == "__main__":
    print("Testing OpenAI API...")
    standard_api_working = test_openai_api()
    
    print("\nTesting Azure OpenAI API...")
    azure_api_working = test_azure_openai_api()
    
    print("\nResults:")
    print(f"Standard OpenAI API: {'✓ Working' if standard_api_working else '✗ Failed'}")
    print(f"Azure OpenAI API: {'✓ Working' if azure_api_working else '✗ Failed'}")