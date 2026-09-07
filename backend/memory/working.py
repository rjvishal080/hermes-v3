"""
memory/working.py
─────────────────────────────────────────────────────────────────────────────
Working Memory — temporary context for the current session/day.

Think of this as the LLM's "RAM" — what's immediately relevant right now.
It gets refreshed daily and is never persisted long-term.

Holds:
  - current_focus:  what the user is working on right now
  - today_events:   things that happened today
  - active_goals:   goals currently in focus (from goal tracker)
  - pending_tasks:  things to do / follow up on
  - mood:           inferred emotional state
  - context_notes:  anything the agent decided to keep in mind

Working memory is stored in a single JSON file (not a DB).
It resets at midnight via the scheduler.
"""

import json
import datetime
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
WM_PATH  = DATA_DIR / "working_memory.json"

DEFAULT_WM = {
    "date":          "",
    "current_focus": "",
    "today_events":  [],
    "active_goals":  [],
    "pending_tasks": [],
    "mood":          "neutral",
    "context_notes": [],
    "updated_at":    "",
}


def _load() -> dict:
    DATA_DIR.mkdir(exist_ok=True)
    if WM_PATH.exists():
        with open(WM_PATH) as f:
            return json.load(f)
    return DEFAULT_WM.copy()


def _save(wm: dict):
    wm["updated_at"] = datetime.datetime.utcnow().isoformat()
    with open(WM_PATH, "w") as f:
        json.dump(wm, f, indent=2)


def get() -> dict:
    wm = _load()
    # Auto-reset if date changed
    today = datetime.date.today().isoformat()
    if wm.get("date") != today:
        wm = DEFAULT_WM.copy()
        wm["date"] = today
        _save(wm)
    return wm


def set_focus(focus: str):
    wm = get()
    wm["current_focus"] = focus
    _save(wm)


def add_today_event(event: str):
    wm = get()
    if event not in wm["today_events"]:
        wm["today_events"].append(event)
    _save(wm)


def set_active_goals(goals: list[str]):
    wm = get()
    wm["active_goals"] = goals
    _save(wm)


def add_pending_task(task: str):
    wm = get()
    if task not in wm["pending_tasks"]:
        wm["pending_tasks"].append(task)
    _save(wm)


def complete_task(task: str):
    wm = get()
    wm["pending_tasks"] = [t for t in wm["pending_tasks"] if t != task]
    _save(wm)


def set_mood(mood: str):
    """neutral | positive | negative | anxious | focused | tired"""
    wm = get()
    wm["mood"] = mood
    _save(wm)


def add_context_note(note: str):
    wm = get()
    if note not in wm["context_notes"]:
        wm["context_notes"].append(note)
        if len(wm["context_notes"]) > 10:
            wm["context_notes"] = wm["context_notes"][-10:]
    _save(wm)


def reset():
    """Force reset working memory (called by scheduler at midnight)."""
    wm = DEFAULT_WM.copy()
    wm["date"] = datetime.date.today().isoformat()
    _save(wm)


def to_context_string() -> str:
    """Compact string for LLM system prompt."""
    wm = get()
    lines = [f"[TODAY: {wm['date']}]"]
    if wm["current_focus"]:
        lines.append(f"  Current focus: {wm['current_focus']}")
    if wm["mood"] != "neutral":
        lines.append(f"  Mood: {wm['mood']}")
    if wm["today_events"]:
        lines.append(f"  Today so far: {'; '.join(wm['today_events'][:5])}")
    if wm["active_goals"]:
        lines.append(f"  Active goals: {', '.join(wm['active_goals'][:3])}")
    if wm["pending_tasks"]:
        lines.append(f"  Pending: {', '.join(wm['pending_tasks'][:4])}")
    if wm["context_notes"]:
        lines.append(f"  Context: {'; '.join(wm['context_notes'][:3])}")
    return "\n".join(lines)
