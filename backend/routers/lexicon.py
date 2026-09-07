"""
routers/lexicon.py
CRUD for personal vocabulary, style rules, and references.
"""

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from memory import lexicon

router = APIRouter()


# ── Terms ─────────────────────────────────────────────────────────────────────

class TermCreate(BaseModel):
    term:     str
    meaning:  str
    category: str = "slang"
    examples: list[str] = []
    context:  str = ""


@router.get("/terms")
def list_terms():
    return {"terms": lexicon.get_all_terms()}


@router.post("/terms")
def add_term(req: TermCreate):
    tid = lexicon.add_term(
        term=req.term, meaning=req.meaning,
        category=req.category, examples=req.examples, context=req.context,
    )
    return {"id": tid, "message": f'Term "{req.term}" saved'}


@router.delete("/terms/{term_id}")
def delete_term(term_id: str):
    lexicon.delete_term(term_id)
    return {"message": "Deleted"}


# ── Style rules ───────────────────────────────────────────────────────────────

class StyleRuleCreate(BaseModel):
    rule:     str
    category: str = "tone"
    strength: float = 1.0


@router.get("/style")
def list_style():
    return {"rules": lexicon.get_all_style_rules()}


@router.post("/style")
def add_style(req: StyleRuleCreate):
    rid = lexicon.add_style_rule(req.rule, req.category, req.strength)
    return {"id": rid, "message": "Style rule saved"}


@router.delete("/style/{rule_id}")
def delete_style(rule_id: str):
    lexicon.delete_style_rule(rule_id)
    return {"message": "Deleted"}


# ── References ────────────────────────────────────────────────────────────────

class RefCreate(BaseModel):
    trigger:   str
    meaning:   str
    is_ironic: bool = False


@router.get("/references")
def list_refs():
    return {"references": lexicon.get_all_references()}


@router.post("/references")
def add_ref(req: RefCreate):
    rid = lexicon.add_reference(req.trigger, req.meaning, req.is_ironic)
    return {"id": rid, "message": f'Reference "{req.trigger}" saved'}


@router.delete("/references/{ref_id}")
def delete_ref(ref_id: str):
    lexicon.delete_reference(ref_id)
    return {"message": "Deleted"}


# ── Extract from conversation ─────────────────────────────────────────────────

class ExtractReq(BaseModel):
    text: str


@router.post("/extract")
def extract(req: ExtractReq):
    counts = lexicon.extract_from_conversation(req.text)
    return {"extracted": counts}


# ── Stats + full block ────────────────────────────────────────────────────────

@router.get("/stats")
def stats():
    return lexicon.get_stats()


@router.get("/prompt-block")
def prompt_block():
    """Preview exactly what gets injected into the LLM system prompt."""
    return {"block": lexicon.to_system_prompt_block()}
