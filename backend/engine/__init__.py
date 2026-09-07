import threading
from engine.llm import load_model
from engine.embeddings import load_embed_model, load_rerank_model


def load_all_async():
    t1 = threading.Thread(target=load_embed_model,  daemon=True, name="bge-m3")
    t2 = threading.Thread(target=load_rerank_model, daemon=True, name="reranker")
    t3 = threading.Thread(target=load_model,        daemon=True, name="hermes-3")
    t1.start(); t2.start(); t3.start()
    print("[Hermes v3] Models loading: bge-m3 + reranker + qwen2.5-coder:7b")


def load_all_sync():
    load_embed_model()
    load_rerank_model()
    load_model()
