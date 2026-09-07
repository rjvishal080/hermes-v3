"""
memory/semantic.py
─────────────────────────────────────────────────────────────────────────────
Semantic Memory — facts about you.

Stores typed, structured facts extracted from conversations and ingested data.
Each fact has:
  - key:        unique identifier  e.g. "academic.cgpa"
  - value:      the fact itself    e.g. "8.5"
  - category:   semantic group     e.g. "academic" | "finance" | "health" | "personality" | "social"
  - confidence: 0.0–1.0            how certain we are
  - source:     where it came from e.g. "conversation" | "portal" | "manual"
  - updated_at: ISO timestamp

Backed by SQLite for exact lookup + ChromaDB for semantic search.
This is separate from episodic (events) and procedural (preferences).
"""

import json
import sqlite3
import datetime
from pathlib import Path
from typing import Optional

DATA_DIR = Path(__file__).parent.parent / "data"
DB_PATH  = DATA_DIR / "semantic.db"


def _conn() -> sqlite3.Connection:
    DATA_DIR.mkdir(exist_ok=True)
    c = sqlite3.connect(str(DB_PATH))
    c.row_factory = sqlite3.Row
    return c


def _init():
    with _conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS facts (
                key         TEXT PRIMARY KEY,
                value       TEXT NOT NULL,
                category    TEXT NOT NULL DEFAULT 'general',
                confidence  REAL NOT NULL DEFAULT 1.0,
                source      TEXT NOT NULL DEFAULT 'manual',
                updated_at  TEXT NOT NULL
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_category ON facts(category)")

_init()

CATEGORIES = [
    "academic",     # CGPA, courses, attendance, college
    "finance",      # budget, spending habits, income
    "health",       # sleep, exercise, weight, diet
    "career",       # goals, skills, target companies, internships
    "personality",  # traits, values, preferences
    "social",       # relationships, family, friends
    "technical",    # programming languages, tools, projects
    "general",      # anything else
]


def set_fact(key: str, value: str, category: str = "general",
             confidence: float = 1.0, source: str = "manual"):
    """Upsert a fact. key uses dot notation: 'academic.cgpa'"""
    now = datetime.datetime.utcnow().isoformat()
    with _conn() as c:
        c.execute("""
            INSERT INTO facts (key, value, category, confidence, source, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value=excluded.value,
                confidence=excluded.confidence,
                source=excluded.source,
                updated_at=excluded.updated_at
        """, (key, str(value), category, confidence, source, now))


def get_fact(key: str) -> Optional[dict]:
    with _conn() as c:
        row = c.execute("SELECT * FROM facts WHERE key=?", (key,)).fetchone()
        return dict(row) if row else None


def get_category(category: str) -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM facts WHERE category=? ORDER BY updated_at DESC",
            (category,)
        ).fetchall()
        return [dict(r) for r in rows]


def get_all() -> list[dict]:
    with _conn() as c:
        rows = c.execute("SELECT * FROM facts ORDER BY category, key").fetchall()
        return [dict(r) for r in rows]


def delete_fact(key: str):
    with _conn() as c:
        c.execute("DELETE FROM facts WHERE key=?", (key,))


def to_context_string() -> str:
    """Render all facts as a compact string for LLM system prompt."""
    facts = get_all()
    if not facts:
        return "No semantic facts yet."
    by_cat: dict[str, list] = {}
    for f in facts:
        by_cat.setdefault(f["category"], []).append(f)
    lines = []
    for cat, items in by_cat.items():
        lines.append(f"[{cat.upper()}]")
        for item in items:
            conf = f" (confidence: {item['confidence']:.0%})" if item["confidence"] < 0.8 else ""
            lines.append(f"  {item['key']}: {item['value']}{conf}")
    return "\n".join(lines)


def bulk_set(facts: list[dict]):
    """Set multiple facts at once. Each dict: {key, value, category, confidence, source}"""
    for f in facts:
        set_fact(
            key=f["key"],
            value=f["value"],
            category=f.get("category", "general"),
            confidence=f.get("confidence", 1.0),
            source=f.get("source", "auto"),
        )
