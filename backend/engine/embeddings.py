"""
engine/embeddings.py
─────────────────────────────────────────────────────────────────────────────
Two-stage retrieval pipeline:

Stage 1 — Dense retrieval:
  BAAI/bge-m3 via FlagEmbedding
  - 8192 token context (vs nomic-embed-text's 2048)
  - Multilingual (handles Hindi/Tamil mixed text)
  - 1024-dim embeddings, very strong semantic understanding
  - Runs on CPU to leave full VRAM for LLM

Stage 2 — Reranking:
  BAAI/bge-reranker-v2-m3
  - Takes top-K from ChromaDB (e.g. 20)
  - Re-scores each (query, document) pair with cross-encoder
  - Returns true top-N (e.g. 5)
  - Dramatically improves which memories Hermes actually uses
  - Also CPU (small model, fast enough)

Why two stages:
  ChromaDB ANN search is approximate and optimized for speed.
  The reranker is exact but slow — fine for small candidate sets.
  Together: fast retrieval + accurate final selection.
"""

import os
import threading
from pathlib import Path
from typing import Optional

MODELS_DIR = Path(os.getenv("HERMES_MODELS_DIR", "./models"))
EMBED_MODEL  = os.getenv("HERMES_EMBED_MODEL",  "BAAI/bge-m3")
RERANK_MODEL = os.getenv("HERMES_RERANK_MODEL", "BAAI/bge-reranker-v2-m3")

# ── Singleton state ───────────────────────────────────────────────────────────
_embed_model  = None
_rerank_model = None
_embed_lock   = threading.Lock()
_rerank_lock  = threading.Lock()


def load_embed_model():
    global _embed_model
    with _embed_lock:
        if _embed_model is not None:
            return
        print(f"[Hermes Embeddings] Loading {EMBED_MODEL}...")
        from FlagEmbedding import BGEM3FlagModel
        _embed_model = BGEM3FlagModel(
            EMBED_MODEL,
            use_fp16=False,
            device="cpu",
        )
        print("[Hermes Embeddings] bge-m3 loaded on CPU")


def load_rerank_model():
    global _rerank_model
    with _rerank_lock:
        if _rerank_model is not None:
            return
        print(f"[Hermes Reranker] Loading {RERANK_MODEL}...")
        from FlagEmbedding import FlagReranker
        _rerank_model = FlagReranker(
            RERANK_MODEL,
            use_fp16=False,
            device="cpu",
        )
        print("[Hermes Reranker] bge-reranker-v2-m3 loaded on CPU")


def embed(texts: list[str]) -> list[list[float]]:
    """Embed a list of texts. Returns list of 1024-dim vectors."""
    if _embed_model is None:
        load_embed_model()
    output = _embed_model.encode(
        texts,
        batch_size=12,
        max_length=8192,
        return_dense=True,
        return_sparse=False,
        return_colbert_vecs=False,
    )
    return output["dense_vecs"].tolist()


def embed_single(text: str) -> list[float]:
    return embed([text])[0]


def rerank(query: str, documents: list[str], top_n: int = 5) -> list[tuple[int, float]]:
    """
    Rerank documents against a query.
    Returns list of (original_index, score) sorted by score descending.
    """
    if not documents:
        return []
    if _rerank_model is None:
        load_rerank_model()

    pairs = [[query, doc] for doc in documents]
    scores = _rerank_model.compute_score(pairs, normalize=True)

    if isinstance(scores, float):
        scores = [scores]

    ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
    return ranked[:top_n]


def rerank_memories(query: str, memories: list[dict], top_n: int = 5) -> list[dict]:
    """
    Takes raw ChromaDB results (list of dicts with 'text' key),
    reranks them, returns top_n in order of relevance.
    """
    if not memories:
        return []
    if len(memories) <= top_n:
        return memories  # no point reranking if already small set

    docs = [m["text"] for m in memories]
    ranked = rerank(query, docs, top_n=top_n)
    return [memories[i] for i, _ in ranked]


# ── ChromaDB embedding function wrapper ───────────────────────────────────────
class BGEEmbeddingFunction:
    """
    Drop-in replacement for ChromaDB's embedding_function.
    Uses bge-m3 instead of nomic-embed-text.
    """
    def __call__(self, input: list[str]) -> list[list[float]]:
        return embed(input)
