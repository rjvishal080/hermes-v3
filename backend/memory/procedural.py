"""
memory/procedural.py
─────────────────────────────────────────────────────────────────────────────
Procedural Memory — how you like things done.

This is the memory type most personal AIs miss entirely.
It captures PREFERENCES and PATTERNS, not facts or events.

Examples:
  - "prefers studying with pomodoro technique"
  - "likes code explanations with examples first, theory after"
  - "responds better to direct feedback, not sugar-coated"
  - "prefers dark themes, minimal UI"
  - "coding style: no unnecessary comments, descriptive variable names"
  - "study method: active recall over re-reading"

These don't change often (unlike facts) but heavily shape how Hermes responds.

Categories:
  learning    — how you study, absorb information
  coding      — style, preferences, tools
  communication — tone, directness, format
  productivity — work style, focus patterns
  lifestyle   — routines, habits
  social      — how you interact with people
"""

import sqlite3
import datetime
from pathlib import Path
from typing import Optional

DATA_DIR = Path(__file__).parent.parent / "data"
DB_PATH  = DATA_DIR / "procedural.db"

CATEGORIES = [
    "learning", "coding", "communication",
    "productivity", "lifestyle", "social", "general",
]


def _conn() -> sqlite3.Connection:
    DATA_DIR.mkdir(exist_ok=True)
    c = sqlite3.connect(str(DB_PATH))
    c.row_factory = sqlite3.Row
    return c


def _init():
    with _conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS preferences (
                id          TEXT PRIMARY KEY,
                category    TEXT NOT NULL,
                description TEXT NOT NULL,
                strength    REAL NOT NULL DEFAULT 0.8,
                source      TEXT NOT NULL DEFAULT 'inferred',
                updated_at  TEXT NOT NULL
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_cat ON preferences(category)")

_init()


def set_preference(
    description: str,
    category:    str = "general",
    strength:    float = 0.8,   # 0.0 = weak hint, 1.0 = strong consistent preference
    source:      str = "inferred",
) -> str:
    """
    Add or update a preference. Deduplication by description similarity is
    handled at the LLM extraction layer — here we just store.
    """
    import hashlib
    # Use hash of description as stable ID (deduplicates exact re-extractions)
    pref_id = hashlib.md5(description.lower().strip().encode()).hexdigest()[:12]
    now     = datetime.datetime.utcnow().isoformat()
    with _conn() as c:
        c.execute("""
            INSERT INTO preferences (id, category, description, strength, source, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                strength=MAX(excluded.strength, strength),
                updated_at=excluded.updated_at
        """, (pref_id, category, description, strength, source, now))
    return pref_id


def get_category(category: str) -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM preferences WHERE category=? ORDER BY strength DESC",
            (category,)
        ).fetchall()
    return [dict(r) for r in rows]


def get_all() -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM preferences ORDER BY category, strength DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def delete_preference(pref_id: str):
    with _conn() as c:
        c.execute("DELETE FROM preferences WHERE id=?", (pref_id,))


def to_context_string() -> str:
    """Compact string of all preferences for system prompt injection."""
    prefs = get_all()
    if not prefs:
        return "No behavioral preferences learned yet."
    by_cat: dict[str, list] = {}
    for p in prefs:
        by_cat.setdefault(p["category"], []).append(p)
    lines = []
    for cat, items in by_cat.items():
        lines.append(f"[{cat.upper()} PREFERENCES]")
        for p in items:
            lines.append(f"  • {p['description']}")
    return "\n".join(lines)


def get_stats() -> dict:
    with _conn() as c:
        total  = c.execute("SELECT COUNT(*) FROM preferences").fetchone()[0]
        by_cat = c.execute(
            "SELECT category, COUNT(*) FROM preferences GROUP BY category"
        ).fetchall()
    return {"total": total, "by_category": {r[0]: r[1] for r in by_cat}}
