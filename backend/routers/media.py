"""
routers/media.py
Full CRUD + search for media entries.
"""

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from media.entry import (
    create_entry, get_entry, get_all, get_by_type,
    update_entry, delete_entry, get_stats, find_by_title,
    MEDIA_TYPES, STATUSES,
)
from media.patterns import run_pattern_analysis, get_taste_summary

router = APIRouter()


class EntryCreate(BaseModel):
    title:               str
    media_type:          str = "movie"
    creator:             str = ""
    year:                str = ""
    status:              str = "completed"
    rating:              Optional[float] = None
    rating_raw:          str = ""
    mood_when_consumed:  str = ""
    reaction:            str = ""
    interpretation:      str = ""
    what_worked:         list[str] = []
    what_didnt:          list[str] = []
    themes_noticed:      list[str] = []
    memorable_moments:   list[str] = []
    quotes:              list[str] = []
    rewatch:             str = "maybe"
    recommendation:      str = ""
    recommend_to:        str = ""


class EntryUpdate(BaseModel):
    rating:              Optional[float] = None
    status:              Optional[str] = None
    reaction:            Optional[str] = None
    interpretation:      Optional[str] = None
    what_worked:         Optional[list[str]] = None
    what_didnt:          Optional[list[str]] = None
    themes_noticed:      Optional[list[str]] = None
    memorable_moments:   Optional[list[str]] = None
    quotes:              Optional[list[str]] = None
    rewatch:             Optional[str] = None
    recommendation:      Optional[str] = None


@router.get("")
def list_all(
    type:       Optional[str]   = None,
    status:     Optional[str]   = None,
    min_rating: Optional[float] = None,
    limit:      int             = 100,
):
    entries = get_all(media_type=type, status=status, min_rating=min_rating, limit=limit)
    return {"entries": entries, "total": len(entries)}


@router.get("/stats")
def stats():
    return get_stats()


@router.get("/types")
def media_types():
    return {"types": MEDIA_TYPES, "statuses": STATUSES}


@router.get("/taste")
def taste_profile():
    return {"taste_summary": get_taste_summary()}


@router.get("/search")
def search(q: str):
    # Title search
    by_title = find_by_title(q)
    results  = [by_title] if by_title else []

    # Semantic search in memory collection
    try:
        from memory.retrieval import hybrid_search
        semantic = hybrid_search(
            f"media reaction interpretation {q}",
            n_results=5,
            collection="memories",
        )
        # Filter to media entries only
        media_semantic = [r for r in semantic if r.get("metadata", {}).get("source") == "media"]
        results.extend(media_semantic)
    except Exception:
        pass

    return {"results": results}


@router.get("/by-type/{media_type}")
def by_type(media_type: str):
    entries = get_by_type(media_type)
    return {"entries": entries, "type": media_type}


@router.get("/patterns")
def patterns():
    result = run_pattern_analysis()
    return result


@router.get("/{entry_id}")
def get_one(entry_id: str):
    entry = get_entry(entry_id)
    if not entry:
        return {"error": "Not found"}
    return entry


@router.post("")
def create(req: EntryCreate):
    eid = create_entry(
        title              = req.title,
        media_type         = req.media_type,
        creator            = req.creator,
        year               = req.year,
        status             = req.status,
        rating             = req.rating,
        rating_raw         = req.rating_raw,
        mood_when_consumed = req.mood_when_consumed,
        reaction           = req.reaction,
        interpretation     = req.interpretation,
        what_worked        = req.what_worked,
        what_didnt         = req.what_didnt,
        themes_noticed     = req.themes_noticed,
        memorable_moments  = req.memorable_moments,
        quotes             = req.quotes,
        rewatch            = req.rewatch,
        recommendation     = req.recommendation,
        recommend_to       = req.recommend_to,
    )
    return {"id": eid, "message": f'"{req.title}" logged'}


@router.patch("/{entry_id}")
def update(entry_id: str, req: EntryUpdate):
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    update_entry(entry_id, **updates)
    return {"message": "Updated"}


@router.delete("/{entry_id}")
def delete(entry_id: str):
    delete_entry(entry_id)
    return {"message": "Deleted"}
