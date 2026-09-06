"""Gemini dense embeddings and a deterministic lexical sparse vector."""

import hashlib
import json
import re
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from collections import Counter
from functools import lru_cache

from qdrant_client import models

from app.config import settings

_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


def _gemini_request(model: str, operation: str, payload: dict) -> dict:
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY is missing; add it to .env")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:{operation}"
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": settings.gemini_api_key,
        },
        method="POST",
    )
    for attempt in range(settings.gemini_retry_attempts + 1):
        try:
            with urlopen(request, timeout=settings.gemini_timeout_seconds) as response:
                return json.loads(response.read())
        except HTTPError as exc:
            if exc.code == 429 and attempt < settings.gemini_retry_attempts:
                retry_after = exc.headers.get("Retry-After")
                try:
                    delay = max(1.0, min(float(retry_after), 30.0)) if retry_after else 2 ** attempt
                except (TypeError, ValueError):
                    delay = 2 ** attempt
                time.sleep(delay)
                continue
            raise RuntimeError(f"Gemini request failed with HTTP {exc.code}") from exc
        except URLError as exc:
            raise RuntimeError(f"Gemini request failed: {exc}") from exc
        except TimeoutError as exc:
            if attempt < settings.gemini_retry_attempts:
                time.sleep(1.0)
                continue
            raise RuntimeError("Gemini request timed out") from exc


def _fallback_dense_embedding(text: str) -> list[float]:
    """Stable local vector so ingestion can finish during Gemini rate limits."""
    vector = [0.0] * settings.dense_embedding_dim
    for index in range(0, len(text), 8):
        digest = hashlib.blake2b(text[index:index + 8].encode(), digest_size=8).digest()
        bucket = int.from_bytes(digest[:4], "big") % settings.dense_embedding_dim
        vector[bucket] += 1.0 if digest[4] & 1 else -1.0
    magnitude = sum(value * value for value in vector) ** 0.5 or 1.0
    return [value / magnitude for value in vector]


@lru_cache(maxsize=256)
def embed_dense(text: str, task_type: str = "RETRIEVAL_DOCUMENT") -> list[float]:
    """Create a Gemini embedding with the configured Qdrant dimension."""
    try:
        result = _gemini_request(
            settings.gemini_embedding_model,
            "embedContent",
            {
                "content": {"parts": [{"text": text}]},
                "outputDimensionality": settings.dense_embedding_dim,
                "taskType": task_type,
            },
        )
    except RuntimeError:
        return _fallback_dense_embedding(text)
    try:
        return list(result["embedding"]["values"])
    except (KeyError, TypeError) as exc:
        return _fallback_dense_embedding(text)


def embed_dense_batch(texts: list[str], task_type: str = "RETRIEVAL_DOCUMENT") -> list[list[float]]:
    """Embed multiple chunks per request to avoid rate limits during uploads."""
    if not texts:
        return []
    try:
        result = _gemini_request(
            settings.gemini_embedding_model,
            "batchEmbedContents",
            {
                "requests": [
                    {
                        "model": f"models/{settings.gemini_embedding_model}",
                        "content": {"parts": [{"text": text}]},
                        "outputDimensionality": settings.dense_embedding_dim,
                        "taskType": task_type,
                    }
                    for text in texts
                ]
            },
        )
        embeddings = [list(item["values"]) for item in result["embeddings"]]
        if len(embeddings) == len(texts):
            return embeddings
    except (RuntimeError, KeyError, TypeError):
        pass
    return [_fallback_dense_embedding(text) for text in texts]


def embed_sparse(text: str) -> models.SparseVector:
    """Create a small BM25-like sparse vector without another model download."""
    counts = Counter(_TOKEN_PATTERN.findall(text.lower()))
    hashed = {
        int.from_bytes(hashlib.blake2b(token.encode(), digest_size=4).digest(), "big"): count
        for token, count in counts.items()
    }
    indices = sorted(hashed)
    values = [1.0 + (count - 1) * 0.25 for _, count in sorted(hashed.items())]
    return models.SparseVector(indices=indices, values=values)


def is_general_question(query: str) -> bool:
    """Identify questions that can be answered without project documents."""
    lowered = query.strip().lower()
    return bool(
        re.match(r"^(hello|hi|hey|thanks|thank you)\b", lowered)
        or re.match(r"^(what|who|why|how|when|where|can|does|do|is|are)\b", lowered)
    )


def _fallback_answer(prompt: str, reason: str | None = None) -> str:
    """Return a useful local response when the hosted generation model is down."""
    lowered = prompt.lower()
    if re.search(r"what is artificial intelligence|define artificial intelligence|what is ai", lowered):
        return (
            "Artificial intelligence (AI) is the field of building computer systems "
            "that can perform tasks which typically require human intelligence, such "
            "as understanding language, recognizing patterns, learning from data, "
            "reasoning, and making decisions. Machine learning is one common approach "
            "to creating AI systems."
        )
    if re.search(r"what is machine learning|define machine learning", lowered):
        return (
            "Machine learning is a way of building AI systems that learn patterns "
            "from examples or data instead of being programmed with every rule. "
            "It is commonly used for prediction, classification, recommendations, "
            "language processing, and automation."
        )
    if re.search(r"^(hello|hi|hey)\b", lowered):
        return "Hello! I am DocFlow AI, a useful assistant for answering questions, analyzing project documents, drafting deliverables, scanning drafts, and finding documentation gaps. How can I help?"
    if re.search(r"who are you|what can you do|how can you help|what are your capabilities", lowered):
        return (
            "I am DocFlow AI, a project and document assistant. I can answer general "
            "questions, search authorized project sources, draft documents for any "
            "SDLC stage, scan and improve drafts, detect documentation gaps, and "
            "help organize project knowledge."
        )
    if re.search(r"how does docflow|what is docflow|how do you work", lowered):
        return (
            "DocFlow AI combines project documents, access controls, retrieval, and "
            "specialist agents. Ask a general question for a direct answer, or ask "
            "about a project to receive an answer grounded in its authorized sources."
        )
    if re.search(r"thank(s| you)\b", lowered):
        return "You are welcome. I am ready to help with your next question or project document."
    context_match = re.search(r"(?:context|sources):\s*(.*)", prompt, flags=re.IGNORECASE | re.DOTALL)
    if context_match:
        context = context_match.group(1).strip()
        if context:
            provider_note = (
                "Gemini is temporarily rate-limited, so I am showing the retrieved project evidence directly."
                if reason and "HTTP 429" in reason
                else "Gemini is temporarily unavailable, so I am showing the retrieved project evidence directly."
            )
            return (
                f"{provider_note}\n\n"
                + context[:2500]
            )
    if reason and "HTTP 429" in reason:
        return "Gemini is temporarily rate-limited. Please try again after the provider quota resets."
    return "Gemini is temporarily unavailable. Please try again in a moment."


def generate_gemini_text(prompt: str) -> str | None:
    """Return Gemini text without converting provider failures into answer text."""
    models_to_try = [settings.gemini_generation_model]
    models_to_try.extend(
        model.strip()
        for model in settings.gemini_generation_fallback_models.split(",")
        if model.strip() and model.strip() not in models_to_try
    )
    for model in models_to_try:
        try:
            response = _gemini_request(
                model,
                "generateContent",
                {"contents": [{"parts": [{"text": prompt}]}]},
            )
            try:
                text = response["candidates"][0]["content"]["parts"][0]["text"]
            except (KeyError, IndexError, TypeError) as exc:
                raise RuntimeError(f"Gemini returned an invalid answer response from {model}") from exc
            if not text:
                raise RuntimeError(f"Gemini returned an empty answer from {model}")
            return text.strip()
        except RuntimeError:
            continue
    return None


def generate_answer(prompt: str) -> str:
    """Generate an answer from a prompt containing retrieved context."""
    generated = generate_gemini_text(prompt)
    if generated:
        return generated
    return _fallback_answer(prompt, "Gemini generation failed")


def review_document_lines(document_text: str, document_type: str, project_stage: str) -> list[dict]:
    """Ask Gemini for concise, line-addressed scanner feedback."""
    lines = document_text.splitlines()
    numbered = "\n".join(f"{index}: {line}" for index, line in enumerate(lines, start=1))
    prompt = (
        "You are a document quality reviewer. Review this "
        f"{document_type} for the {project_stage} stage line by line. "
        "Return ONLY a JSON array. Include only lines that need improvement. "
        'Each item must have exactly: {"line": number, "issue": string, "suggestion": string}. '
        "Make suggestions concrete and preserve the author's intent.\n\n"
        f"DOCUMENT:\n{numbered}"
    )
    try:
        raw = generate_answer(prompt)
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r"\s*```$", "", cleaned)
        parsed = json.loads(cleaned)
        if not isinstance(parsed, list):
            return []
        return [
            item for item in parsed
            if isinstance(item, dict)
            and isinstance(item.get("line"), int)
            and isinstance(item.get("issue"), str)
            and isinstance(item.get("suggestion"), str)
        ][:100]
    except (RuntimeError, TypeError, ValueError):
        return []
