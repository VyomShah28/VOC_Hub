import json
import boto3
from typing import Dict, Any, List

from app.core.config import settings

# Initialize the Bedrock Runtime client
bedrock_client = boto3.client(
    service_name='bedrock-runtime',
    region_name=settings.AWS_REGION_NAME,
    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
)

def generate_text_with_bedrock(system_prompt: str, user_prompt: str, is_json: bool = False) -> str:
    """
    Generate text using AWS Bedrock models (Nova, Llama, Claude, etc.) using the Converse API.
    Includes fallbacks if a specific model version is unavailable.
    """
    
    # Prefix the user prompt to force JSON response if requested
    if is_json:
        user_prompt += "\n\nRespond ONLY with a valid JSON object. Do not include any markdown formatting or introductory text."

    # Fallback cascade of models
    models_to_try = [
        "amazon.nova-micro-v1:0", 
        "amazon.nova-lite-v1:0",
        "meta.llama3-3-70b-instruct-v1:0"
    ]
    
    last_error = None
    for model_id in models_to_try:
        try:
            response = bedrock_client.converse(
                modelId=model_id,
                messages=[
                    {
                        "role": "user",
                        "content": [{"text": user_prompt}]
                    }
                ],
                system=[{"text": system_prompt}],
                inferenceConfig={
                    "maxTokens": 4096
                }
            )
            return response["output"]["message"]["content"][0]["text"]
        except bedrock_client.exceptions.ResourceNotFoundException as e:
            print(f"[BEDROCK] Model {model_id} not available, trying next... ({e})")
            last_error = e
        except bedrock_client.exceptions.ValidationException as e:
            print(f"[BEDROCK] Validation failed for {model_id}, trying next... ({e})")
            last_error = e
        except Exception as e:
            print(f"[BEDROCK] Text generation failed with {model_id}: {e}")
            raise e
            
    print(f"[BEDROCK] All fallback models failed. Last error: {last_error}")
    raise last_error

def generate_embedding_with_bedrock(text: str) -> List[float]:
    """
    Generate text embedding using Amazon Titan Text Embeddings V2.
    Dimensions: 256
    """
    model_id = "amazon.titan-embed-text-v2:0"
    
    body = {
        "inputText": text,
        "dimensions": 256,
        "normalize": True
    }

    try:
        response = bedrock_client.invoke_model(
            modelId=model_id,
            body=json.dumps(body)
        )
        response_body = json.loads(response.get("body").read())
        return response_body.get("embedding")
    except Exception as e:
        print(f"[BEDROCK] Embedding generation failed: {e}")
        raise
