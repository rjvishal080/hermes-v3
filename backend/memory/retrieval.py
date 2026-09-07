"""
memory/retrieval.py
─────────────────────────────────────────────────────────────────────────────
Hybrid Retrieval — BM25 + Dense + Reranker.

Stage 1a: BM25 keyword search  → top K by exact/partial keyword match
Stage 1b: Dense vector search  → top K by semantic similarity (bge-m3)
Stage 2:  Fusion               → combine and deduplicate results
Stage 3:  Reranker             → bge-reranker-v2-m3 picks true top N

Why hybrid beats pure vector:
  - Course names:    "Operating Systems" → BM25 finds exact match fast
  - Transaction:     "₹500 Zomato"      → BM25 >> embeddings
  - Semantic query:  "how am I doing"   → Dense >> BM25
  - Combined:        best of both worlds

BM25 index is rebuilt in-memory from ChromaDB documents on each query.
(At <100k memories this is fast enough. Above that, persist the index.)
"""

import os
from pathlib import Path
from typing import Optional

import chromadb
from rank_bm25 import BM25Okapi

from engine.embeddings import BGEEmbeddingFunction, rerank_memories

DATA_DIR   = Path(os.getenv("HERMES_DATA_DIR", "./data"))
CHROMA_DIR = DATA_DIR / "chroma"

_chroma_client = chromadb.PersistentClient(path=str(CHROMA_DIR))
_embed_fn      = BGEEmbeddingFunction()

COLLECTIONS = {
    "memories":   "General memories (auto-extracted + manual)",
    "finances":   "Financial transactions and patterns",
    "academic":   "Academic records and notes",
    "episodes":   "Episodic events",
    "documents":  "Ingested PDFs and notes",
}


def _get_col(name: str):
    return _chroma_client.get_or_create_collection(
        name=name,
        embedding_function=_embed_fn,
        metadata={"hnsw:space": "cosine"},
    )


def add_to_collection(
    text:       str,
    metadata:   dict,
    collection: str = "memories",
    doc_id:     Optional[str] = None,
) -> str:
    import uuid
    col    = _get_col(collection)
    doc_id = doc_id or str(uuid.uuid4())
    import datetime
    meta   = {
        "timestamp": datetime.datetime.utcnow().isoformat(),
        **metadata,
    }
    col.add(documents=[text], metadatas=[meta], ids=[doc_id])
    return doc_id


def hybrid_search(
    query:       str,
    n_results:   int = 6,
    collection:  str = "memories",
    fetch_k:     int = 30,
    bm25_weight: float = 0.3,   # weight for BM25 score in fusion
    dense_weight: float = 0.7,  # weight for dense score in fusion
) -> list[dict]:
    """
    Full hybrid retrieval pipeline.
    Returns top n_results memories ranked by fused + reranked score.
    """
    col   = _get_col(collection)
    count = col.count()
    if count == 0:
        return []

    k = min(fetch_k, count)

    # ── Stage 1b: Dense retrieval ─────────────────────────────────────────────
    dense_raw = col.query(query_texts=[query], n_results=k)
    dense_docs = {}
    for i, doc in enumerate(dense_raw["documents"][0]):
        doc_id = dense_raw["ids"][0][i]
        dist   = dense_raw["distances"][0][i]
        dense_docs[doc_id] = {
            "id":       doc_id,
            "text":     doc,
            "metadata": dense_raw["metadatas"][0][i],
            "dense_score": 1.0 - dist,  # cosine distance → similarity
        }

    # ── Stage 1a: BM25 over the dense candidates ─────────────────────────────
    # We run BM25 over the retrieved dense set (not the full collection)
    # to keep it fast. For large collections, persist the BM25 index.
    texts     = [v["text"] for v in dense_docs.values()]
    doc_ids   = list(dense_docs.keys())
    tokenized = [t.lower().split() for t in texts]

    bm25_scores = {}
    if tokenized:
        bm25  = BM25Okapi(tokenized)
        raw_scores = bm25.get_scores(query.lower().split())
        max_score  = max(raw_scores) if max(raw_scores) > 0 else 1.0
        for i, doc_id in enumerate(doc_ids):
            bm25_scores[doc_id] = raw_scores[i] / max_score  # normalize 0–1

    # ── Stage 2: Reciprocal Rank Fusion ──────────────────────────────────────
    fused = {}
    for doc_id, info in dense_docs.items():
        dense_s = info["dense_score"]
        bm25_s  = bm25_scores.get(doc_id, 0.0)
        fused[doc_id] = {
            **info,
            "bm25_score":   bm25_s,
            "fused_score":  dense_weight * dense_s + bm25_weight * bm25_s,
        }

    # Sort by fused score, take top fetch_k//2 for reranking
    candidates = sorted(fused.values(), key=lambda x: x["fused_score"], reverse=True)
    candidates = candidates[:max(n_results * 3, 10)]

    # ── Stage 3: Reranker ────────────────────────────────────────────────────
    if len(candidates) <= n_results:
        return candidates

    reranked = rerank_memories(query, candidates, top_n=n_results)
    return reranked


def multi_collection_search(
    query:      str,
    n_results:  int = 8,
    collections: list[str] = None,
) -> list[dict]:
    """
    Search across multiple collections, merge and rerank.
    Used when query is ambiguous (not obviously finance vs academic etc).
    """
    if collections is None:
        collections = ["memories", "finances", "academic", "documents"]

    all_candidates = []
    per_col = max(n_results, 5)

    for col_name in collections:
        try:
            results = hybrid_search(query, n_results=per_col,
                                    collection=col_name, fetch_k=20)
            for r in results:
                r["collection"] = col_name
            all_candidates.extend(results)
        except Exception:
            continue

    if not all_candidates:
        return []

    # Deduplicate by text similarity (simple: by id)
    seen = set()
    unique = []
    for c in all_candidates:
        if c["id"] not in seen:
            seen.add(c["id"])
            unique.append(c)

    # Rerank the merged set
    from engine.embeddings import rerank_memories
    return rerank_memories(query, unique, top_n=n_results)


def delete_from_collection(doc_id: str, collection: str = "memories"):
    _get_col(collection).delete(ids=[doc_id])


def list_collection(collection: str = "memories", limit: int = 100) -> list[dict]:
    col     = _get_col(collection)
    results = col.get(limit=limit, include=["documents", "metadatas"])
    out = []
    for i, doc in enumerate(results["documents"]):
        out.append({
            "id":       results["ids"][i],
            "text":     doc,
            "metadata": results["metadatas"][i],
            "collection": collection,
        })
    return sorted(out, key=lambda x: x["metadata"].get("timestamp", ""), reverse=True)


def get_collection_stats() -> dict:
    stats = {}
    for col_name in COLLECTIONS:
        try:
            stats[col_name] = _get_col(col_name).count()
        except:
            stats[col_name] = 0
    return stats
