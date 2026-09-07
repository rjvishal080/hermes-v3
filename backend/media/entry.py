"""
media/entry.py
─────────────────────────────────────────────────────────────────────────────
Media consciousness layer — stores what you watched/read/played
and more importantly HOW you experienced it.

Not a watchlist. A record of interpretation, emotion, and meaning.

Each entry captures:
  - The work itself (title, type, creator, year)
  - Your experience (rating, status, mood when consumed)
  - Your reaction (raw emotional response in your own words)
  - Your interpretation (what you think it actually means)
  - What worked / what didn't (specific and honest)
  - Themes you noticed
  - Memorable moments / quotes
  - Rewatch intent + recommendation stance
  - Personality signals extracted (fed to procedural memory)

Media types: anime, manga, movie, series, book, novel, light_novel,
             game, comic, manhwa, manhua, podcast, documentary
"""

import json
import uuid
import sqlite3
import datetime
from pathlib import Path
from typing import Optional

DATA_DIR = Path(__file__).parent.parent / "data"
DB_PATH  = DATA_DIR / "media.db"

MEDIA_TYPES = [
    "anime", "manga", "movie", "series", "book",
    "light_novel", "novel", "game", "comic",
    "manhwa", "manhua", "documentary", "podcast", "other",
]

STATUSES = ["completed", "watching", "reading", "playing",
            "dropped", "on_hold", "want_to", "rewatching"]

REWATCH_OPTIONS = ["yes_definitely", "maybe", "no_once_is_enough",
                   "carry_forever_no_rewatch", "already_rewatched"]


def _conn() -> sqlite3.Connection:
    DATA_DIR.mkdir(exist_ok=True)
    c = sqlite3.connect(str(DB_PATH))
    c.row_factory = sqlite3.Row
    return c


def _init():
    with _conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS media_entries (
                id                  TEXT PRIMARY KEY,
                title               TEXT NOT NULL,
                type                TEXT NOT NULL DEFAULT 'movie',
                creator             TEXT NOT NULL DEFAULT '',
                year                TEXT NOT NULL DEFAULT '',
                status              TEXT NOT NULL DEFAULT 'completed',
                rating              REAL,
                rating_raw          TEXT NOT NULL DEFAULT '',
                started_date        TEXT NOT NULL DEFAULT '',
                finished_date       TEXT NOT NULL DEFAULT '',
                mood_when_consumed  TEXT NOT NULL DEFAULT '',

                reaction            TEXT NOT NULL DEFAULT '',
                interpretation      TEXT NOT NULL DEFAULT '',
                what_worked         TEXT NOT NULL DEFAULT '[]',
                what_didnt          TEXT NOT NULL DEFAULT '[]',
                themes_noticed      TEXT NOT NULL DEFAULT '[]',
                memorable_moments   TEXT NOT NULL DEFAULT '[]',
                quotes              TEXT NOT NULL DEFAULT '[]',

                rewatch             TEXT NOT NULL DEFAULT 'maybe',
                recommendation      TEXT NOT NULL DEFAULT '',
                recommend_to        TEXT NOT NULL DEFAULT '',

                personality_signals TEXT NOT NULL DEFAULT '[]',
                session_id          TEXT NOT NULL DEFAULT '',

                created_at          TEXT NOT NULL,
                updated_at          TEXT NOT NULL
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_type   ON media_entries(type)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_status ON media_entries(status)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_rating ON media_entries(rating)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_title  ON media_entries(title)")

_init()


def create_entry(
    title:              str,
    media_type:         str = "movie",
    creator:            str = "",
    year:               str = "",
    status:             str = "completed",
    rating:             Optional[float] = None,
    rating_raw:         str = "",
    mood_when_consumed: str = "",
    reaction:           str = "",
    interpretation:     str = "",
    what_worked:        list[str] = None,
    what_didnt:         list[str] = None,
    themes_noticed:     list[str] = None,
    memorable_moments:  list[str] = None,
    quotes:             list[str] = None,
    rewatch:            str = "maybe",
    recommendation:     str = "",
    recommend_to:       str = "",
    personality_signals: list[str] = None,
    session_id:         str = "",
    finished_date:      str = "",
) -> str:
    eid  = str(uuid.uuid4())
    now  = datetime.datetime.utcnow().isoformat()
    date = finished_date or (datetime.date.today().isoformat() if status == "completed" else "")

    with _conn() as c:
        c.execute("""
            INSERT INTO media_entries (
                id, title, type, creator, year, status, rating, rating_raw,
                finished_date, mood_when_consumed,
                reaction, interpretation, what_worked, what_didnt,
                themes_noticed, memorable_moments, quotes,
                rewatch, recommendation, recommend_to,
                personality_signals, session_id, created_at, updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            eid, title, media_type, creator, year, status,
            rating, rating_raw, date, mood_when_consumed,
            reaction, interpretation,
            json.dumps(what_worked or []),
            json.dumps(what_didnt or []),
            json.dumps(themes_noticed or []),
            json.dumps(memorable_moments or []),
            json.dumps(quotes or []),
            rewatch, recommendation, recommend_to,
            json.dumps(personality_signals or []),
            session_id, now, now,
        ))
    return eid


def update_entry(entry_id: str, **kwargs):
    """Update specific fields of a media entry."""
    list_fields = {"what_worked", "what_didnt", "themes_noticed",
                   "memorable_moments", "quotes", "personality_signals"}
    updates = {}
    for k, v in kwargs.items():
        if k in list_fields:
            updates[k] = json.dumps(v if isinstance(v, list) else [v])
        else:
            updates[k] = v
    if not updates:
        return
    updates["updated_at"] = datetime.datetime.utcnow().isoformat()
    cols   = ", ".join([f"{k}=?" for k in updates])
    values = list(updates.values()) + [entry_id]
    with _conn() as c:
        c.execute(f"UPDATE media_entries SET {cols} WHERE id=?", values)


def get_entry(entry_id: str) -> Optional[dict]:
    with _conn() as c:
        row = c.execute("SELECT * FROM media_entries WHERE id=?", (entry_id,)).fetchone()
    return _parse(row) if row else None


def find_by_title(title: str) -> Optional[dict]:
    with _conn() as c:
        row = c.execute(
            "SELECT * FROM media_entries WHERE LOWER(title) LIKE LOWER(?)",
            (f"%{title}%",)
        ).fetchone()
    return _parse(row) if row else None


def get_all(
    media_type: Optional[str] = None,
    status:     Optional[str] = None,
    min_rating: Optional[float] = None,
    limit:      int = 200,
) -> list[dict]:
    query  = "SELECT * FROM media_entries WHERE 1=1"
    params = []
    if media_type:
        query += " AND type=?"
        params.append(media_type)
    if status:
        query += " AND status=?"
        params.append(status)
    if min_rating is not None:
        query += " AND rating >= ?"
        params.append(min_rating)
    query += " ORDER BY updated_at DESC LIMIT ?"
    params.append(limit)
    with _conn() as c:
        rows = c.execute(query, params).fetchall()
    return [_parse(r) for r in rows]


def get_by_type(media_type: str) -> list[dict]:
    return get_all(media_type=media_type)


def get_completed() -> list[dict]:
    return get_all(status="completed")


def get_all_signals() -> list[str]:
    """Get all personality signals extracted from media consumption."""
    with _conn() as c:
        rows = c.execute(
            "SELECT personality_signals FROM media_entries WHERE personality_signals != '[]'"
        ).fetchall()
    signals = []
    for row in rows:
        signals.extend(json.loads(row[0]))
    return list(set(signals))


def delete_entry(entry_id: str):
    with _conn() as c:
        c.execute("DELETE FROM media_entries WHERE id=?", (entry_id,))


def get_stats() -> dict:
    with _conn() as c:
        total    = c.execute("SELECT COUNT(*) FROM media_entries").fetchone()[0]
        by_type  = c.execute("SELECT type, COUNT(*) FROM media_entries GROUP BY type").fetchall()
        by_status= c.execute("SELECT status, COUNT(*) FROM media_entries GROUP BY status").fetchall()
        avg_rat  = c.execute("SELECT AVG(rating) FROM media_entries WHERE rating IS NOT NULL").fetchone()[0]
        top_rated= c.execute(
            "SELECT title, type, rating FROM media_entries WHERE rating IS NOT NULL ORDER BY rating DESC LIMIT 5"
        ).fetchall()
    return {
        "total":      total,
        "by_type":    {r[0]: r[1] for r in by_type},
        "by_status":  {r[0]: r[1] for r in by_status},
        "avg_rating": round(avg_rat, 2) if avg_rat else None,
        "top_rated":  [{"title": r[0], "type": r[1], "rating": r[2]} for r in top_rated],
    }


def _parse(row) -> dict:
    d = dict(row)
    for field in ["what_worked", "what_didnt", "themes_noticed",
                  "memorable_moments", "quotes", "personality_signals"]:
        d[field] = json.loads(d.get(field, "[]"))
    return d
