import json
import math
from functools import lru_cache

import boto3
from botocore.config import Config

from app.core.config import settings


_HTTP_POOL_SIZE = 64


@lru_cache(maxsize=1)
def get_bedrock_runtime_client():
    # Reuse a single client with connection pooling and adaptive retries.
    # Uses IAM role-based authentication by default or credentials from settings if provided
    kwargs = {
        "service_name": "bedrock-runtime",
        "region_name": settings.AWS_REGION,
        "config": Config(
            retries={"max_attempts": 5, "mode": "adaptive"},
            max_pool_connections=_HTTP_POOL_SIZE,
            connect_timeout=3,
            read_timeout=60,
        ),
    }
    
    # Only add credentials if they are provided in settings
    if settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
        kwargs["aws_access_key_id"] = settings.AWS_ACCESS_KEY_ID
        kwargs["aws_secret_access_key"] = settings.AWS_SECRET_ACCESS_KEY
    
    return boto3.client(**kwargs)


def _strip_fence(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    if cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    return cleaned.strip()


def _json_from_text(text: str) -> dict:
    cleaned = _strip_fence(text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(cleaned[start : end + 1])
        raise


def invoke_claude_text(
    system_prompt: str,
    user_prompt: str,
    *,
    model_id: str | None = None,
    max_tokens: int = 1000,
    temperature: float = 0.0,
) -> str:
    client = get_bedrock_runtime_client()
    resolved_model = model_id or settings.AWS_BEDROCK_TEXT_MODEL

    payload = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_prompt}],
        "temperature": temperature,
    }

    response = client.invoke_model(
        modelId=resolved_model,
        contentType="application/json",
        accept="application/json",
        body=json.dumps(payload),
    )
    body = json.loads(response["body"].read())
    content = body.get("content", [])
    if not content:
        return ""
    return content[0].get("text", "").strip()


def invoke_claude_json(
    system_prompt: str,
    user_prompt: str,
    *,
    model_id: str | None = None,
    max_tokens: int = 1000,
    temperature: float = 0.0,
) -> dict:
    text = invoke_claude_text(
        system_prompt,
        user_prompt,
        model_id=model_id,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    if not text:
        return {}
    return _json_from_text(text)


def _l2_normalize(values: list[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in values))
    if norm == 0.0:
        return values
    return [v / norm for v in values]


def _resize_vector(values: list[float], dim: int) -> list[float]:
    if len(values) == dim:
        return values
    if len(values) > dim:
        return values[:dim]
    return values + ([0.0] * (dim - len(values)))


def generate_embedding(text: str, *, input_type: str = "search_document") -> list[float]:
    if not text or not text.strip():
        return [0.0] * settings.AWS_EMBEDDING_DIM

    client = get_bedrock_runtime_client()
    model_id = settings.AWS_BEDROCK_EMBED_MODEL
    body: dict

    if model_id.startswith("cohere.embed"):
        body = {
            "texts": [text],
            "input_type": input_type,
            "truncate": "END",
        }
    else:
        body = {"inputText": text}

    response = client.invoke_model(
        modelId=model_id,
        contentType="application/json",
        accept="application/json",
        body=json.dumps(body),
    )

    payload = json.loads(response["body"].read())

    vector = payload.get("embedding")
    if vector is None:
        embeddings = payload.get("embeddings")
        if isinstance(embeddings, list) and embeddings:
            vector = embeddings[0]

    if vector is None:
        by_type = payload.get("embeddingsByType")
        if isinstance(by_type, dict):
            float_vec = by_type.get("float")
            if isinstance(float_vec, list):
                vector = float_vec

    if not isinstance(vector, list):
        raise ValueError("Bedrock embedding response did not contain a usable vector")

    vector = [float(x) for x in vector]
    vector = _resize_vector(vector, settings.AWS_EMBEDDING_DIM)
    if settings.AWS_EMBEDDING_NORMALIZE:
        vector = _l2_normalize(vector)
    return vector
