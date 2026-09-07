"""
memory/episodic.py
─────────────────────────────────────────────────────────────────────────────
Episodic Memory — events with timestamps.

Unlike semantic (facts) or procedural (preferences), episodic memory is
TEMPORAL. It answers: what happened, when?

Each episode has:
  - id:          UUID
  - date:        when it happened (ISO date)
  - summary:     one-sentence description
  - detail:      full text (optional)
  - category:    academic | finance | health | social | achievement | issue | general
  - emotion:     positive | negative | neutral (for mood tracking)
  - importance:  1–5 (higher = surface more often)
  - tags:        list of strings for filtering
  - source:      conversation | manual | portal | ingest

Also stored in ChromaDB for semantic search over events.
SQLite for exact date-range queries.
"""

import json
import uuid
import sqlite3
import datetime
from pathlib import Path
from typing import Optional

DATA_DIR = Path(__file__).parent.parent / "data"
DB_PATH  = DATA_DIR / "episodic.db"


def _conn() -> sqlite3.Connection:
    DATA_DIR.mkdir(exist_ok=True)
    c = sqlite3.connect(str(DB_PATH))
    c.row_factory = sqlite3.Row
    return c


def _init():
    with _conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS episodes (
                id          TEXT PRIMARY KEY,
                date        TEXT NOT NULL,
                summary     TEXT NOT NULL,
                detail      TEXT,
                category    TEXT NOT NULL DEFAULT 'general',
                emotion     TEXT NOT NULL DEFAULT 'neutral',
                importance  INTEGER NOT NULL DEFAULT 3,
                tags        TEXT NOT NULL DEFAULT '[]',
                source      TEXT NOT NULL DEFAULT 'manual',
                created_at  TEXT NOT NULL
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_date     ON episodes(date)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_category ON episodes(category)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_importance ON episodes(importance)")

_init()


def add_episode(
    summary:    str,
    date:       Optional[str] = None,
    detail:     str = "",
    category:   str = "general",
    emotion:    str = "neutral",
    importance: int = 3,
    tags:       list[str] = None,
    source:     str = "manual",
) -> str:
    ep_id = str(uuid.uuid4())
    now   = datetime.datetime.utcnow().isoformat()
    date  = date or datetime.date.today().isoformat()
    with _conn() as c:
        c.execute("""
            INSERT INTO episodes
              (id, date, summary, detail, category, emotion, importance, tags, source, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (ep_id, date, summary, detail, category, emotion,
              importance, json.dumps(tags or []), source, now))
    return ep_id


def get_recent(days: int = 30, limit: int = 50) -> list[dict]:
    cutoff = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
    with _conn() as c:
        rows = c.execute("""
            SELECT * FROM episodes
            WHERE date >= ?
            ORDER BY date DESC, importance DESC
            LIMIT ?
        """, (cutoff, limit)).fetchall()
    return [_parse(r) for r in rows]


def get_by_date_range(start: str, end: str) -> list[dict]:
    with _conn() as c:
        rows = c.execute("""
            SELECT * FROM episodes WHERE date BETWEEN ? AND ?
            ORDER BY date DESC
        """, (start, end)).fetchall()
    return [_parse(r) for r in rows]


def get_by_category(category: str, limit: int = 30) -> list[dict]:
    with _conn() as c:
        rows = c.execute("""
            SELECT * FROM episodes WHERE category=?
            ORDER BY date DESC LIMIT ?
        """, (category, limit)).fetchall()
    return [_parse(r) for r in rows]


def get_important(min_importance: int = 4, limit: int = 20) -> list[dict]:
    with _conn() as c:
        rows = c.execute("""
            SELECT * FROM episodes WHERE importance >= ?
            ORDER BY date DESC LIMIT ?
        """, (min_importance, limit)).fetchall()
    return [_parse(r) for r in rows]


def get_all(limit: int = 500) -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM episodes ORDER BY date DESC LIMIT ?", (limit,)
        ).fetchall()
    return [_parse(r) for r in rows]


def delete_episode(ep_id: str):
    with _conn() as c:
        c.execute("DELETE FROM episodes WHERE id=?", (ep_id,))


def _parse(row) -> dict:
    d = dict(row)
    d["tags"] = json.loads(d.get("tags", "[]"))
    return d


def to_timeline_string(days: int = 30) -> str:
    """Render recent episodes as a timeline string for LLM context."""
    episodes = get_recent(days=days, limit=20)
    if not episodes:
        return "No recent episodes."
    lines = []
    for ep in episodes:
        emotion_marker = {"positive": "✓", "negative": "✗", "neutral": "·"}.get(ep["emotion"], "·")
        lines.append(f"  {ep['date']} {emotion_marker} [{ep['category']}] {ep['summary']}")
    return "\n".join(lines)


def get_stats() -> dict:
    with _conn() as c:
        total    = c.execute("SELECT COUNT(*) FROM episodes").fetchone()[0]
        by_cat   = c.execute(
            "SELECT category, COUNT(*) as n FROM episodes GROUP BY category"
        ).fetchall()
        by_emo   = c.execute(
            "SELECT emotion, COUNT(*) as n FROM episodes GROUP BY emotion"
        ).fetchall()
    return {
        "total": total,
        "by_category": {r[0]: r[1] for r in by_cat},
        "by_emotion":  {r[0]: r[1] for r in by_emo},
    }
