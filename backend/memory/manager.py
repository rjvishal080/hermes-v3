"""
memory/manager.py
─────────────────────────────────────────────────────────────────────────────
Central Memory Manager v3.

Orchestrates all memory types:
  - Semantic   (facts)
  - Episodic   (events)
  - Procedural (preferences)
  - Working    (current context)
  - Graph      (relationships)
  - Goals      (objectives + scoring)
  - Retrieval  (hybrid BM25 + dense + rerank)
  - Consolidation (daily → weekly → life)

Single interface used by routers and the planner agent.
"""

import json
import datetime
import uuid
from pathlib import Path
from typing import Optional

from memory import semantic, episodic, procedural, working, graph, goals, retrieval, consolidation, lexicon

DATA_DIR = Path(__file__).parent.parent / "data"

# ── Conversation history (JSONL, unchanged from v2) ───────────────────────────

def save_message(session_id: str, role: str, content: str):
    (DATA_DIR / "conversations").mkdir(exist_ok=True)
    path = DATA_DIR / "conversations" / f"{session_id}.jsonl"
    with open(path, "a") as f:
        f.write(json.dumps({
            "role": role, "content": content,
            "ts":   datetime.datetime.utcnow().isoformat(),
        }) + "\n")


def load_history(session_id: str, last_n: int = 20) -> list[dict]:
    path = DATA_DIR / "conversations" / f"{session_id}.jsonl"
    if not path.exists():
        return []
    lines = path.read_text().strip().split("\n")
    msgs  = [json.loads(l) for l in lines if l.strip()]
    return [{"role": m["role"], "content": m["content"]} for m in msgs[-last_n:]]


def list_sessions() -> list[dict]:
    sessions = []
    conv_dir = DATA_DIR / "conversations"
    if not conv_dir.exists():
        return []
    for p in sorted(conv_dir.glob("*.jsonl"), reverse=True)[:30]:
        lines = p.read_text().strip().split("\n")
        msgs  = [json.loads(l) for l in lines if l.strip()]
        if msgs:
            sessions.append({
                "session_id":    p.stem,
                "message_count": len(msgs),
                "last_message":  msgs[-1]["ts"],
                "preview":       msgs[0]["content"][:80],
            })
    return sessions


# ── Profile (JSON, unchanged from v2) ────────────────────────────────────────

PROFILE_PATH = DATA_DIR / "profile.json"
DEFAULT_PROFILE = {
    "name": "", "bio": "",
    "academic": {"college": "", "semester": "", "cgpa": "", "courses": [],
                 "attendance": {}, "grades": {}, "portal_url": ""},
    "finances": {"cashiro_linked": False, "monthly_budget": 0,
                 "categories": {}, "monthly_totals": {}},
    "health":   {"sleep_avg_hrs": 0, "exercise_days_week": 0,
                 "weight_kg": None, "notes": ""},
    "screen_time": {"daily_avg_mins": 0, "top_apps": {}},
    "custom_fields": {},
    "last_updated": "",
}

def load_profile() -> dict:
    if PROFILE_PATH.exists():
        with open(PROFILE_PATH) as f:
            return json.load(f)
    return DEFAULT_PROFILE.copy()

def save_profile(data: dict):
    DATA_DIR.mkdir(exist_ok=True)
    data["last_updated"] = datetime.datetime.utcnow().isoformat()
    with open(PROFILE_PATH, "w") as f:
        json.dump(data, f, indent=2)


# ── Full context builder for LLM system prompt ───────────────────────────────

def build_full_context(query: str = "") -> str:
    """
    Build the complete context string injected into every LLM system prompt.
    Draws from all memory types.
    """
    parts = []

    # 0. Lexicon — injected FIRST so it shapes how all other context is read
    lex_block = lexicon.to_system_prompt_block()
    if lex_block:
        parts.append(lex_block)

    # 1. Semantic facts (structured, always included)
    sem = semantic.to_context_string()
    if sem and sem != "No semantic facts yet.":
        parts.append(f"KNOWN FACTS ABOUT YOU:\n{sem}")

    # 2. Working memory (today's context)
    wm = working.to_context_string()
    if wm:
        parts.append(wm)

    # 3. Active goals
    goal_summary = goals.get_goal_progress_summary()
    if goal_summary and goal_summary != "No active goals set.":
        parts.append(goal_summary)

    # 4. Procedural preferences
    proc = procedural.to_context_string()
    if proc and proc != "No behavioral preferences learned yet.":
        parts.append(f"YOUR PREFERENCES:\n{proc}")

    # 5. Recent episodic timeline
    timeline = episodic.to_timeline_string(days=14)
    if timeline and timeline != "No recent episodes.":
        parts.append(f"RECENT EVENTS (last 14 days):\n{timeline}")

    # 6. Semantically retrieved memories (query-specific)
    if query:
        retrieved = retrieval.multi_collection_search(query, n_results=6)
        if retrieved:
            mem_lines = [f"  - {m['text']}" for m in retrieved]
            parts.append(f"RELEVANT MEMORIES:\n" + "\n".join(mem_lines))

    # 7. Media taste profile (from pattern analysis)
    try:
        from media.patterns import get_taste_summary
        taste = get_taste_summary()
        if taste:
            parts.append(f"MEDIA TASTE: {taste}")
    except Exception:
        pass

    return "\n\n".join(parts) if parts else "No personal context yet. Start chatting to build your memory."


# ── Self-evolution: extract all memory types from conversation ────────────────

EXTRACTION_SYSTEM = """Analyze this conversation and extract structured information.
Return ONLY valid JSON with these keys (omit any with no findings):

{
  "facts": [{"key": "academic.cgpa", "value": "8.5", "category": "academic", "confidence": 0.95}],
  "episodes": [{"summary": "...", "category": "academic", "emotion": "neutral", "importance": 3}],
  "preferences": [{"description": "prefers active recall over re-reading", "category": "learning", "strength": 0.8}],
  "graph_triples": [{"subject": "Vishal", "relation": "taking_course", "object": "OS", "subject_type": "person", "object_type": "course"}],
  "goal_updates": [{"goal_title": "...", "progress_note": "..."}],
  "working_updates": {"focus": "...", "mood": "neutral", "tasks": ["..."]}
}

Rules:
- facts: only objective, verifiable info (CGPA, college name, budget etc)
- episodes: specific events that happened TODAY or in this conversation
- preferences: how the user likes things done (patterns, not one-offs)
- graph_triples: relationships between named entities
- goal_updates: if user mentioned progress/setback on a known goal
- working_updates: what the user is currently focused on

Return empty arrays [] for sections with no findings. No markdown."""


def extract_and_store_all(session_id: str, user_name: str = "User") -> dict:
    """
    Full extraction pipeline — runs after each conversation.
    Returns counts of what was stored.
    """
    from engine.llm import generate

    history = load_history(session_id, last_n=30)
    if len(history) < 2:
        return {}

    user_msgs = [m for m in history if m["role"] == "user"]
    conv_text = "\n".join([f"USER: {m['content']}" for m in user_msgs[-15:]])

    messages  = [{"role": "user", "content": f"Extract from this conversation with {user_name}:\n\n{conv_text}"}]

    try:
        raw   = generate(EXTRACTION_SYSTEM, messages, max_new_tokens=800, temperature=0.1)
        clean = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
        data  = json.loads(clean)
    except Exception as e:
        print(f"[Manager] Extraction failed: {e}")
        return {}

    counts = {}

    # Facts → semantic memory
    if data.get("facts"):
        semantic.bulk_set(data["facts"])
        counts["facts"] = len(data["facts"])

    # Episodes → episodic memory + ChromaDB
    if data.get("episodes"):
        for ep in data["episodes"]:
            ep_id = episodic.add_episode(
                summary=ep["summary"],
                category=ep.get("category", "general"),
                emotion=ep.get("emotion", "neutral"),
                importance=ep.get("importance", 3),
                source="conversation",
                date=datetime.date.today().isoformat(),
            )
            retrieval.add_to_collection(
                ep["summary"],
                metadata={"source": "episodic", "session_id": session_id},
                collection="memories",
                doc_id=ep_id,
            )
        counts["episodes"] = len(data["episodes"])

    # Preferences → procedural memory
    if data.get("preferences"):
        for pref in data["preferences"]:
            procedural.set_preference(
                description=pref["description"],
                category=pref.get("category", "general"),
                strength=pref.get("strength", 0.7),
                source="conversation",
            )
        counts["preferences"] = len(data["preferences"])

    # Graph triples → knowledge graph
    if data.get("graph_triples"):
        for triple in data["graph_triples"]:
            graph.add_triple(
                subject=triple["subject"],
                relation=triple["relation"],
                obj=triple["object"],
                subject_type=triple.get("subject_type", "concept"),
                object_type=triple.get("object_type", "concept"),
                source="conversation",
            )
        counts["graph_triples"] = len(data["graph_triples"])

    # Working memory updates
    if data.get("working_updates"):
        wu = data["working_updates"]
        if wu.get("focus"):   working.set_focus(wu["focus"])
        if wu.get("mood"):    working.set_mood(wu["mood"])
        for task in wu.get("tasks", []):
            working.add_pending_task(task)

    # Goal progress notes
    if data.get("goal_updates"):
        active = goals.get_active()
        title_to_id = {g["title"].lower(): g["id"] for g in active}
        for upd in data["goal_updates"]:
            gid = title_to_id.get(upd.get("goal_title", "").lower())
            if gid and upd.get("progress_note"):
                goals.add_progress_note(gid, upd["progress_note"])

    # Lexicon — extract new slang, style patterns, references from conversation
    # Run every 3rd conversation to avoid redundancy (lightweight heuristic)
    try:
        full_conv = "\n".join([f"{m['role'].upper()}: {m['content']}" for m in history[-20:]])
        lex_counts = lexicon.extract_from_conversation(full_conv)
        if any(v > 0 for v in lex_counts.values()):
            counts["lexicon"] = lex_counts
    except Exception as e:
        print(f"[Manager] Lexicon extraction failed: {e}")

    return counts


# ── Generate weekly reflection ────────────────────────────────────────────────

REFLECT_SYSTEM = """You are Hermes, a deeply personal AI.
Synthesize everything you know about this person into a weekly reflection.
Cover:
1. Progress toward goals (be specific)
2. Patterns you notice (spending, sleep, screen time, mood)
3. Achievements this week
4. Concerns worth addressing
5. One concrete recommendation for next week

Reference actual numbers and events. Be honest, warm, direct. Max 250 words."""

def generate_weekly_reflection() -> str:
    from engine.llm import generate

    profile     = load_profile()
    all_facts   = semantic.to_context_string()
    goal_summ   = goals.get_goal_progress_summary()
    timeline    = episodic.to_timeline_string(days=7)
    weeklies    = consolidation.get_recent_summaries("daily", limit=7)
    daily_text  = "\n".join([f"{s['period']}: {s['content'][:150]}" for s in weeklies])

    context = f"""
SEMANTIC FACTS:
{all_facts}

GOALS:
{goal_summ}

THIS WEEK'S EVENTS:
{timeline}

DAILY SUMMARIES:
{daily_text}
""".strip()

    messages = [{"role": "user", "content": f"Generate my weekly reflection:\n\n{context}"}]

    try:
        return generate(REFLECT_SYSTEM, messages, max_new_tokens=400, temperature=0.6)
    except Exception as e:
        return f"Could not generate reflection: {e}"
