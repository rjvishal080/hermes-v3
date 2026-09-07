"""
memory/goals.py
─────────────────────────────────────────────────────────────────────────────
Goal Tracker — the feature that changes the system's character.

Every goal has:
  - id, title, description
  - category: career | academic | health | financial | personal | skill
  - status:   active | paused | completed | abandoned
  - priority: 1 (low) – 5 (critical)
  - deadline: optional ISO date
  - milestones: list of sub-goals with completion flags
  - progress_notes: log of progress updates
  - created_at, updated_at

The key innovation: every new memory, episode, and conversation turn
gets scored against active goals. This lets Hermes reason:
  "This conversation is moving you toward your ML internship goal"
  "You've spent 3 days not studying for the OS exam deadline in 5 days"

Goal scoring uses the LLM — each memory gets a relevance tag:
  helps | hurts | neutral
relative to each active goal.
"""

import json
import uuid
import sqlite3
import datetime
from pathlib import Path
from typing import Optional

DATA_DIR = Path(__file__).parent.parent / "data"
DB_PATH  = DATA_DIR / "goals.db"

CATEGORIES = ["career", "academic", "health", "financial", "personal", "skill"]
STATUSES   = ["active", "paused", "completed", "abandoned"]


def _conn() -> sqlite3.Connection:
    DATA_DIR.mkdir(exist_ok=True)
    c = sqlite3.connect(str(DB_PATH))
    c.row_factory = sqlite3.Row
    return c


def _init():
    with _conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS goals (
                id              TEXT PRIMARY KEY,
                title           TEXT NOT NULL,
                description     TEXT NOT NULL DEFAULT '',
                category        TEXT NOT NULL DEFAULT 'personal',
                status          TEXT NOT NULL DEFAULT 'active',
                priority        INTEGER NOT NULL DEFAULT 3,
                deadline        TEXT,
                milestones      TEXT NOT NULL DEFAULT '[]',
                progress_notes  TEXT NOT NULL DEFAULT '[]',
                created_at      TEXT NOT NULL,
                updated_at      TEXT NOT NULL
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_status   ON goals(status)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_priority ON goals(priority)")
        c.execute("""
            CREATE TABLE IF NOT EXISTS memory_scores (
                id         TEXT PRIMARY KEY,
                memory_id  TEXT NOT NULL,
                goal_id    TEXT NOT NULL,
                score      TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_goal_id ON memory_scores(goal_id)")

_init()


def add_goal(
    title:       str,
    description: str = "",
    category:    str = "personal",
    priority:    int = 3,
    deadline:    Optional[str] = None,
    milestones:  list[str] = None,
) -> str:
    gid = str(uuid.uuid4())
    now = datetime.datetime.utcnow().isoformat()
    ms  = [{"text": m, "done": False} for m in (milestones or [])]
    with _conn() as c:
        c.execute("""
            INSERT INTO goals
              (id, title, description, category, status, priority,
               deadline, milestones, progress_notes, created_at, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """, (gid, title, description, category, "active", priority,
              deadline, json.dumps(ms), json.dumps([]), now, now))
    return gid


def get_goal(gid: str) -> Optional[dict]:
    with _conn() as c:
        row = c.execute("SELECT * FROM goals WHERE id=?", (gid,)).fetchone()
        return _parse(row) if row else None


def get_active() -> list[dict]:
    with _conn() as c:
        rows = c.execute("""
            SELECT * FROM goals WHERE status='active'
            ORDER BY priority DESC, deadline ASC NULLS LAST
        """).fetchall()
    return [_parse(r) for r in rows]


def get_all() -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM goals ORDER BY priority DESC, created_at DESC"
        ).fetchall()
    return [_parse(r) for r in rows]


def update_goal(gid: str, **kwargs):
    allowed = {"title", "description", "status", "priority", "deadline"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return
    updates["updated_at"] = datetime.datetime.utcnow().isoformat()
    cols   = ", ".join([f"{k}=?" for k in updates])
    values = list(updates.values()) + [gid]
    with _conn() as c:
        c.execute(f"UPDATE goals SET {cols} WHERE id=?", values)


def add_progress_note(gid: str, note: str):
    goal = get_goal(gid)
    if not goal:
        return
    notes = goal["progress_notes"]
    notes.append({
        "text": note,
        "date": datetime.date.today().isoformat(),
    })
    now = datetime.datetime.utcnow().isoformat()
    with _conn() as c:
        c.execute(
            "UPDATE goals SET progress_notes=?, updated_at=? WHERE id=?",
            (json.dumps(notes), now, gid)
        )


def complete_milestone(gid: str, milestone_text: str):
    goal = get_goal(gid)
    if not goal:
        return
    ms = goal["milestones"]
    for m in ms:
        if m["text"] == milestone_text:
            m["done"] = True
    now = datetime.datetime.utcnow().isoformat()
    with _conn() as c:
        c.execute(
            "UPDATE goals SET milestones=?, updated_at=? WHERE id=?",
            (json.dumps(ms), now, gid)
        )


def score_memory_against_goals(memory_id: str, memory_text: str) -> list[dict]:
    """
    Score a memory against all active goals.
    Returns list of {goal_id, goal_title, score: helps|hurts|neutral}
    This is called asynchronously after memory storage.
    """
    goals = get_active()
    if not goals:
        return []

    results = []
    now     = datetime.datetime.utcnow().isoformat()

    for goal in goals:
        # Simple keyword heuristic first (fast, no LLM needed)
        goal_words = set(goal["title"].lower().split() + goal["description"].lower().split())
        mem_words  = set(memory_text.lower().split())
        overlap    = goal_words & mem_words

        if len(overlap) >= 2:
            score = "helps"
        elif any(w in memory_text.lower() for w in ["miss", "fail", "skip", "procrastinat", "distract"]):
            score = "hurts"
        else:
            score = "neutral"

        if score != "neutral":
            sid = str(uuid.uuid4())
            with _conn() as c:
                c.execute(
                    "INSERT OR IGNORE INTO memory_scores (id, memory_id, goal_id, score, created_at) VALUES (?,?,?,?,?)",
                    (sid, memory_id, goal["id"], score, now)
                )
            results.append({"goal_id": goal["id"], "goal_title": goal["title"], "score": score})

    return results


def get_goal_progress_summary() -> str:
    """Compact summary of all active goals for LLM context."""
    goals = get_active()
    if not goals:
        return "No active goals set."

    lines = ["[ACTIVE GOALS]"]
    today = datetime.date.today()

    for g in goals:
        priority_star = "★" * g["priority"]
        deadline_str  = ""
        if g["deadline"]:
            try:
                dl   = datetime.date.fromisoformat(g["deadline"])
                days = (dl - today).days
                if days < 0:
                    deadline_str = f" ⚠ OVERDUE by {-days}d"
                elif days <= 7:
                    deadline_str = f" ⚡ {days}d left"
                else:
                    deadline_str = f" ({days}d)"
            except:
                deadline_str = f" (deadline: {g['deadline']})"

        ms_total = len(g["milestones"])
        ms_done  = sum(1 for m in g["milestones"] if m.get("done"))
        ms_str   = f" [{ms_done}/{ms_total} milestones]" if ms_total > 0 else ""

        lines.append(f"  {priority_star} {g['title']}{deadline_str}{ms_str}")
        if g["description"]:
            lines.append(f"    → {g['description'][:80]}")

    return "\n".join(lines)


def get_deadline_alerts() -> list[dict]:
    """Goals with deadlines within 7 days."""
    today  = datetime.date.today()
    week   = (today + datetime.timedelta(days=7)).isoformat()
    goals  = get_active()
    alerts = []
    for g in goals:
        if g["deadline"] and g["deadline"] <= week:
            dl   = datetime.date.fromisoformat(g["deadline"])
            days = (dl - today).days
            alerts.append({**g, "days_left": days})
    return sorted(alerts, key=lambda x: x["days_left"])


def _parse(row) -> dict:
    d = dict(row)
    d["milestones"]     = json.loads(d.get("milestones",     "[]"))
    d["progress_notes"] = json.loads(d.get("progress_notes", "[]"))
    return d


def delete_goal(gid: str):
    with _conn() as c:
        c.execute("DELETE FROM goals WHERE id=?", (gid,))
        c.execute("DELETE FROM memory_scores WHERE goal_id=?", (gid,))
