from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import chat, memory, ingest, profile, models, goals, lexicon, media
import uvicorn


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load models in background threads
    from engine import load_all_async
    load_all_async()
    # Start agentic scheduler
    try:
        from engine.scheduler import start_scheduler
        start_scheduler()
    except Exception as e:
        print(f"[Hermes] Scheduler not started: {e}")
    yield
    try:
        from engine.scheduler import stop_scheduler
        stop_scheduler()
    except:
        pass


app = FastAPI(title="Hermes v3 — Personal AI Brain", version="3.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router,    prefix="/api/chat",    tags=["chat"])
app.include_router(memory.router,  prefix="/api/memory",  tags=["memory"])
app.include_router(ingest.router,  prefix="/api/ingest",  tags=["ingest"])
app.include_router(profile.router, prefix="/api/profile", tags=["profile"])
app.include_router(models.router,  prefix="/api/models",  tags=["models"])
app.include_router(goals.router,   prefix="/api/goals",   tags=["goals"])
app.include_router(lexicon.router, prefix="/api/lexicon", tags=["lexicon"])
app.include_router(media.router,   prefix="/api/media",   tags=["media"])


@app.get("/api/health")
def health():
    from engine.llm import get_model_info
    from engine.embeddings import _embed_model, _rerank_model
    from memory import semantic, episodic, procedural, graph, retrieval
    return {
        "status":            "ok",
        "version":           "3.0.0",
        "llm":               get_model_info(),
        "embeddings_loaded": _embed_model  is not None,
        "reranker_loaded":   _rerank_model is not None,
        "memory_stats": {
            "semantic":    len(semantic.get_all()),
            "episodic":    episodic.get_stats()["total"],
            "procedural":  procedural.get_stats()["total"],
            "graph":       graph.get_stats(),
            "collections": retrieval.get_collection_stats(),
        },
    }


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False, workers=1)
