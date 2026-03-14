"""
embedding.py
------------
Generates text embeddings using Google's Gemini embedding model.

Enhanced features:
- Exponential backoff retry for API rate limits
- Batch progress logging
- Embedding validation (zero-norm detection and re-request)
"""

import os
import time
import numpy as np
from dotenv import load_dotenv

from src.logger import get_logger

load_dotenv(override=True)

logger = get_logger("embedding")

# Retry configuration
MAX_RETRIES = 5
BASE_DELAY = 2.0   # seconds
MAX_DELAY = 60.0    # seconds


def _retry_with_backoff(func, *args, max_retries=MAX_RETRIES, **kwargs):
    """Execute a function with exponential backoff on rate-limit errors."""
    last_error = None
    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            last_error = e
            error_str = str(e).lower()
            if "429" in str(e) or "quota" in error_str or "rate" in error_str or "resource" in error_str:
                delay = min(BASE_DELAY * (2 ** attempt), MAX_DELAY)
                logger.warning(
                    "Rate limited (attempt %d/%d), retrying in %.1fs...",
                    attempt + 1, max_retries, delay
                )
                time.sleep(delay)
            else:
                raise
    raise RuntimeError(f"Max retries ({max_retries}) exceeded. Last error: {last_error}")


def get_gemini_embeddings(texts: list, api_key: str = None) -> np.ndarray:
    """
    Generate embeddings for a list of texts using Gemini embedding model.

    Enhanced with retry logic, progress logging, and embedding validation.

    Args:
        texts: List of text strings to embed
        api_key: Google API key (uses env var if not provided)

    Returns:
        numpy array of shape (len(texts), embedding_dim)
    """
    import google.generativeai as genai

    key = api_key or os.getenv("GOOGLE_API_KEY")
    if not key:
        raise ValueError("GOOGLE_API_KEY not found. Set it in .env file or pass as argument.")

    genai.configure(api_key=key)

    embeddings = []

    logger.info("Generating embeddings for %d texts sequentially", len(texts))

    for text_idx, text in enumerate(texts):
        if text_idx % 10 == 0:
            logger.info("  Embedding text %d/%d", text_idx + 1, len(texts))

        # Truncate very long texts for embedding
        truncated = text[:2048] if len(text) > 2048 else text

        def _embed():
            return genai.embed_content(
                model="models/gemini-embedding-001",
                content=truncated,
                task_type="retrieval_document",
            )

        result = _retry_with_backoff(_embed)
        emb = result["embedding"]

        # Validate: check for zero-norm vectors
        emb_arr = np.array(emb, dtype=np.float32)
        if np.linalg.norm(emb_arr) < 1e-8:
            logger.warning(
                "Zero-norm embedding detected for text %d, re-requesting...",
                text_idx,
            )
            result = _retry_with_backoff(_embed)
            emb = result["embedding"]

        embeddings.append(emb)

    logger.info("Embedding generation complete: %d vectors", len(embeddings))
    return np.array(embeddings, dtype=np.float32)


def get_query_embedding(query: str, api_key: str = None) -> np.ndarray:
    """
    Generate embedding for a search query using Gemini.
    Uses retrieval_query task type for better search performance.

    Args:
        query: The search query text
        api_key: Google API key

    Returns:
        1D numpy array (embedding vector)
    """
    import google.generativeai as genai

    key = api_key or os.getenv("GOOGLE_API_KEY")
    if not key:
        raise ValueError("GOOGLE_API_KEY not found.")

    genai.configure(api_key=key)

    def _embed():
        return genai.embed_content(
            model="models/gemini-embedding-001",
            content=query,
            task_type="retrieval_query",
        )

    result = _retry_with_backoff(_embed)
    return np.array(result["embedding"], dtype=np.float32)
