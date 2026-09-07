"""
memory/consolidation.py
─────────────────────────────────────────────────────────────────────────────
Memory Consolidation Pipeline.

Raw memories → Daily summary → Weekly summary → Life profile

Without this, after 6 months you have 10,000 memories saying
"user wants ML internship" — noise, not signal.

With consolidation:
  Day 1–7:   raw episodes stored in episodic + ChromaDB
  Day 7:     weekly consolidation runs → one 200-word summary
  Month 1:   monthly consolidation → key facts extracted to semantic memory
  Long-term: life profile updated with durable patterns

This runs via the scheduler (daily at 2am, weekly on Sunday at 1am).
It uses the LLM to summarize, so it needs the model to be loaded.

Consolidation levels:
  DAILY:   Summarize today's conversations + episodes → 1 paragraph
  WEEKLY:  Summarize 7 daily summaries → key facts + patterns
  LIFE:    Extract durable facts from weeklies → update semantic memory
"""

import json
import datetime
import sqlite3
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
DB_PATH  = DATA_DIR / "consolidation.db"


def _conn() -> sqlite3.Connection:
    DATA_DIR.mkdir(exist_ok=True)
    c = sqlite3.connect(str(DB_PATH))
    c.row_factory = sqlite3.Row
    return c


def _init():
    with _conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS summaries (
                id          TEXT PRIMARY KEY,
                level       TEXT NOT NULL,
                period      TEXT NOT NULL,
                content     TEXT NOT NULL,
                source_ids  TEXT NOT NULL DEFAULT '[]',
                created_at  TEXT NOT NULL
            )
        """)
        c.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_level_period ON summaries(level, period)")

_init()


DAILY_SYSTEM = """You are summarizing a person's day from their conversation history and events.
Write a concise 2-3 paragraph summary covering:
1. What they worked on / talked about
2. Any notable events, achievements, or problems
3. Emotional tone and energy level

Be specific — use actual subjects, amounts, people mentioned.
Write in third person. Max 200 words."""

WEEKLY_SYSTEM = """You are synthesizing a week of daily summaries into a weekly overview.
Identify:
1. Main themes and patterns this week
2. Progress toward goals
3. Recurring concerns or challenges
4. Key events worth remembering long-term
5. One insight about this person's week

Max 300 words. Third person. Specific and grounded."""

LIFE_EXTRACT_SYSTEM = """You are extracting durable facts from weekly summaries.
These facts will become part of the person's permanent profile.

Extract only facts that:
- Are likely to persist (not one-time events)
- Reveal personality, values, or consistent patterns
- Update or confirm known facts about the person

Return ONLY a JSON array of objects:
[{"key": "career.primary_goal", "value": "ML engineer at product company",
  "category": "career", "confidence": 0.9}]

Categories: academic, finance, health, career, personality, social, technical, general
Keys use dot notation. Only include high-confidence facts (>0.7).
If nothing durable found, return []."""


def run_daily_consolidation(date: str = None) -> str | None:
    """Summarize one day's activity. date = 'YYYY-MM-DD', defaults to yesterday."""
    from engine.llm import generate
    from memory.episodic import get_by_date_range

    target_date = date or (datetime.date.today() - datetime.timedelta(days=1)).isoformat()

    # Check if already done
    with _conn() as c:
        existing = c.execute(
            "SELECT id FROM summaries WHERE level='daily' AND period=?",
            (target_date,)
        ).fetchone()
        if existing:
            print(f"[Consolidation] Daily summary for {target_date} already exists")
            return None

    # Gather source material
    episodes = get_by_date_range(target_date, target_date)

    # Load conversation history for that date
    conv_dir   = DATA_DIR / "conversations"
    day_convos = []
    if conv_dir.exists():
        for p in conv_dir.glob("*.jsonl"):
            lines = p.read_text().strip().split("\n")
            msgs  = []
            for line in lines:
                if not line.strip():
                    continue
                try:
                    m = json.loads(line)
                    if m.get("ts", "").startswith(target_date):
                        msgs.append(m)
                except:
                    pass
            if msgs:
                day_convos.extend(msgs)

    if not episodes and not day_convos:
        print(f"[Consolidation] No data for {target_date}, skipping")
        return None

    # Build input text
    parts = []
    if episodes:
        parts.append("EVENTS:")
        for ep in episodes:
            parts.append(f"  - {ep['summary']} ({ep['category']})")
    if day_convos:
        parts.append("CONVERSATIONS (user messages):")
        user_msgs = [m for m in day_convos if m.get("role") == "user"][:20]
        for m in user_msgs:
            parts.append(f"  - {m['content'][:150]}")

    input_text = "\n".join(parts)
    messages   = [{"role": "user", "content": f"Summarize this day ({target_date}):\n\n{input_text}"}]

    try:
        summary = generate(DAILY_SYSTEM, messages, max_new_tokens=300, temperature=0.4)
        if not summary or len(summary) < 20:
            return None

        # Store summary
        import uuid
        sid = str(uuid.uuid4())
        now = datetime.datetime.utcnow().isoformat()
        with _conn() as c:
            c.execute(
                "INSERT OR REPLACE INTO summaries (id, level, period, content, source_ids, created_at) VALUES (?,?,?,?,?,?)",
                (sid, "daily", target_date, summary, json.dumps([]), now)
            )

        # Also store in episodic as high-importance event
        from memory.episodic import add_episode
        add_episode(
            summary=f"Day summary: {summary[:100]}...",
            detail=summary,
            date=target_date,
            category="general",
            importance=4,
            source="consolidation",
            tags=["daily_summary"],
        )

        print(f"[Consolidation] Daily summary stored for {target_date}")
        return summary
    except Exception as e:
        print(f"[Consolidation] Daily consolidation failed: {e}")
        return None


def run_weekly_consolidation(week_start: str = None) -> str | None:
    """Summarize 7 daily summaries into one weekly summary."""
    from engine.llm import generate

    if week_start is None:
        today      = datetime.date.today()
        days_since_monday = today.weekday()
        week_start = (today - datetime.timedelta(days=days_since_monday + 7)).isoformat()

    week_end = (datetime.date.fromisoformat(week_start) + datetime.timedelta(days=6)).isoformat()

    with _conn() as c:
        existing = c.execute(
            "SELECT id FROM summaries WHERE level='weekly' AND period=?",
            (week_start,)
        ).fetchone()
        if existing:
            return None

        dailies = c.execute("""
            SELECT period, content FROM summaries
            WHERE level='daily' AND period BETWEEN ? AND ?
            ORDER BY period
        """, (week_start, week_end)).fetchall()

    if not dailies:
        print(f"[Consolidation] No daily summaries for week {week_start}, skipping")
        return None

    input_text = "\n\n".join([f"=== {r['period']} ===\n{r['content']}" for r in dailies])
    messages   = [{"role": "user", "content": f"Create weekly summary:\n\n{input_text}"}]

    try:
        summary = generate(WEEKLY_SYSTEM, messages, max_new_tokens=400, temperature=0.4)
        if not summary or len(summary) < 30:
            return None

        import uuid
        sid = str(uuid.uuid4())
        now = datetime.datetime.utcnow().isoformat()
        with _conn() as c:
            c.execute(
                "INSERT OR REPLACE INTO summaries (id, level, period, content, source_ids, created_at) VALUES (?,?,?,?,?,?)",
                (sid, "weekly", week_start, summary, json.dumps([r["period"] for r in dailies]), now)
            )

        print(f"[Consolidation] Weekly summary stored for week of {week_start}")
        return summary
    except Exception as e:
        print(f"[Consolidation] Weekly consolidation failed: {e}")
        return None


def run_life_extraction() -> list[dict]:
    """Extract durable facts from recent weeklies → update semantic memory."""
    from engine.llm import generate
    from memory.semantic import bulk_set

    with _conn() as c:
        weeklies = c.execute("""
            SELECT content FROM summaries WHERE level='weekly'
            ORDER BY period DESC LIMIT 8
        """).fetchall()

    if not weeklies:
        return []

    combined = "\n\n---\n\n".join([r["content"] for r in weeklies])
    messages = [{"role": "user", "content": f"Extract durable facts:\n\n{combined}"}]

    try:
        raw   = generate(LIFE_EXTRACT_SYSTEM, messages, max_new_tokens=512, temperature=0.1)
        clean = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
        facts = json.loads(clean)
        if not isinstance(facts, list):
            return []

        valid = [f for f in facts if isinstance(f, dict) and "key" in f and "value" in f]
        if valid:
            bulk_set(valid)
            print(f"[Consolidation] Extracted {len(valid)} durable facts to semantic memory")
        return valid
    except Exception as e:
        print(f"[Consolidation] Life extraction failed: {e}")
        return []


def get_recent_summaries(level: str = "daily", limit: int = 7) -> list[dict]:
    with _conn() as c:
        rows = c.execute("""
            SELECT * FROM summaries WHERE level=?
            ORDER BY period DESC LIMIT ?
        """, (level, limit)).fetchall()
    return [dict(r) for r in rows]


def get_stats() -> dict:
    with _conn() as c:
        by_level = c.execute(
            "SELECT level, COUNT(*) FROM summaries GROUP BY level"
        ).fetchall()
    return {"by_level": {r[0]: r[1] for r in by_level}}
