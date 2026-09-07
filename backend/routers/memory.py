from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from memory import semantic, episodic, procedural, working, graph, retrieval, consolidation

router = APIRouter()


# ── Semantic ──────────────────────────────────────────────────────────────────
@router.get("/semantic")
def get_semantic(category: Optional[str] = None):
    if category:
        return semantic.get_category(category)
    return semantic.get_all()


@router.post("/semantic")
def set_semantic(key: str, value: str, category: str = "general", confidence: float = 1.0):
    semantic.set_fact(key, value, category, confidence, "manual")
    return {"message": "Fact stored"}


@router.delete("/semantic/{key:path}")
def delete_semantic(key: str):
    semantic.delete_fact(key)
    return {"message": "Deleted"}


# ── Episodic ──────────────────────────────────────────────────────────────────
class EpisodeCreate(BaseModel):
    summary:    str
    date:       Optional[str] = None
    detail:     str = ""
    category:   str = "general"
    emotion:    str = "neutral"
    importance: int = 3
    tags:       list[str] = []


@router.get("/episodic")
def get_episodic(days: int = 30, category: Optional[str] = None):
    if category:
        return episodic.get_by_category(category)
    return episodic.get_recent(days=days)


@router.post("/episodic")
def add_episodic(req: EpisodeCreate):
    ep_id = episodic.add_episode(**req.model_dump(), source="manual")
    return {"id": ep_id}


@router.delete("/episodic/{ep_id}")
def delete_episodic(ep_id: str):
    episodic.delete_episode(ep_id)
    return {"message": "Deleted"}


# ── Procedural ────────────────────────────────────────────────────────────────
@router.get("/procedural")
def get_procedural(category: Optional[str] = None):
    if category:
        return procedural.get_category(category)
    return procedural.get_all()


@router.post("/procedural")
def add_procedural(description: str, category: str = "general", strength: float = 0.8):
    pid = procedural.set_preference(description, category, strength, "manual")
    return {"id": pid}


@router.delete("/procedural/{pref_id}")
def delete_procedural(pref_id: str):
    procedural.delete_preference(pref_id)
    return {"message": "Deleted"}


# ── Working memory ────────────────────────────────────────────────────────────
@router.get("/working")
def get_working():
    return working.get()


@router.post("/working/focus")
def set_focus(focus: str):
    working.set_focus(focus)
    return {"message": "Focus set"}


@router.post("/working/task")
def add_task(task: str):
    working.add_pending_task(task)
    return {"message": "Task added"}


@router.delete("/working/task")
def complete_task(task: str):
    working.complete_task(task)
    return {"message": "Task completed"}


# ── Graph ─────────────────────────────────────────────────────────────────────
@router.get("/graph")
def get_graph(entity: Optional[str] = None):
    if entity:
        return graph.get_entity_subgraph(entity, depth=2)
    return {"context": graph.to_context_string(), "stats": graph.get_stats()}


@router.post("/graph")
def add_triple(subject: str, relation: str, obj: str,
               subject_type: str = "concept", object_type: str = "concept"):
    rid = graph.add_triple(subject, relation, obj, subject_type, object_type, "manual")
    return {"id": rid}


# ── Vector search ─────────────────────────────────────────────────────────────
class SearchReq(BaseModel):
    query:      str
    n_results:  int = 6
    collection: Optional[str] = None


@router.post("/search")
def search(req: SearchReq):
    if req.collection:
        results = retrieval.hybrid_search(req.query, req.n_results, req.collection)
    else:
        results = retrieval.multi_collection_search(req.query, req.n_results)
    return {"results": results}


@router.get("/collections")
def collection_stats():
    return retrieval.get_collection_stats()


@router.get("/collection/{name}")
def list_collection(name: str, limit: int = 50):
    return retrieval.list_collection(name, limit)


@router.post("/collection/{name}/add")
def add_to_collection(name: str, text: str, source: str = "manual"):
    import datetime
    doc_id = retrieval.add_to_collection(
        text, {"source": source, "timestamp": datetime.datetime.utcnow().isoformat()}, name
    )
    return {"id": doc_id}


@router.delete("/collection/{name}/{doc_id}")
def delete_from_collection(name: str, doc_id: str):
    retrieval.delete_from_collection(doc_id, name)
    return {"message": "Deleted"}


# ── Consolidation ─────────────────────────────────────────────────────────────
@router.get("/consolidation")
def get_consolidation(level: str = "daily", limit: int = 7):
    return consolidation.get_recent_summaries(level, limit)


@router.post("/consolidation/daily")
def run_daily(date: Optional[str] = None):
    result = consolidation.run_daily_consolidation(date)
    return {"summary": result}


@router.post("/consolidation/weekly")
def run_weekly():
    result = consolidation.run_weekly_consolidation()
    return {"summary": result}


@router.post("/consolidation/life")
def run_life():
    facts = consolidation.run_life_extraction()
    return {"facts_extracted": facts}


# ── Stats ─────────────────────────────────────────────────────────────────────
@router.get("/stats")
def all_stats():
    return {
        "semantic":      len(semantic.get_all()),
        "episodic":      episodic.get_stats(),
        "procedural":    procedural.get_stats(),
        "graph":         graph.get_stats(),
        "collections":   retrieval.get_collection_stats(),
        "consolidation": consolidation.get_stats(),
    }
