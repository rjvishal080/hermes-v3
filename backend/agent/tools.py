"""
agent/tools.py
─────────────────────────────────────────────────────────────────────────────
Tool registry for the ReAct planner.

Each tool has:
  - name:        unique identifier
  - description: what it does (shown to LLM)
  - parameters:  what it takes
  - fn:          the actual Python function

The LLM outputs tool calls as JSON:
  {"tool": "search_memory", "args": {"query": "OS exam", "collection": "academic"}}

The planner executes the call and feeds results back to the LLM.
"""

import datetime
import json
from typing import Callable

# ── Tool definitions ──────────────────────────────────────────────────────────

TOOLS: list[dict] = [
    {
        "name": "search_memory",
        "description": "Search across all personal memories semantically + keyword hybrid.",
        "parameters": {
            "query":      "string — what to search for",
            "collection": "optional string — memories|finances|academic|documents (default: auto)",
        },
    },
    {
        "name": "get_semantic_facts",
        "description": "Get structured facts about the user by category.",
        "parameters": {
            "category": "optional string — academic|finance|health|career|personality|social|technical",
        },
    },
    {
        "name": "get_recent_events",
        "description": "Get recent episodes/events from the user's life.",
        "parameters": {
            "days":     "optional int — how many days back (default 7)",
            "category": "optional string — filter by category",
        },
    },
    {
        "name": "get_goals",
        "description": "Get active goals and their progress.",
        "parameters": {},
    },
    {
        "name": "get_goal_alerts",
        "description": "Get goals with deadlines coming up within 7 days.",
        "parameters": {},
    },
    {
        "name": "get_graph_connections",
        "description": "Get knowledge graph connections for an entity.",
        "parameters": {
            "entity": "string — entity name e.g. 'OS' or 'Zoho'",
        },
    },
    {
        "name": "get_profile",
        "description": "Get the user's structured profile (academic, finance, health).",
        "parameters": {},
    },
    {
        "name": "get_working_memory",
        "description": "Get what the user is currently focused on today.",
        "parameters": {},
    },
    {
        "name": "add_memory",
        "description": "Store a new memory for the user.",
        "parameters": {
            "text":       "string — the memory to store",
            "collection": "optional string — which collection",
        },
    },
    {
        "name": "add_episode",
        "description": "Record a specific event in episodic memory.",
        "parameters": {
            "summary":    "string",
            "category":   "string — academic|finance|health|social|achievement|issue|general",
            "importance": "int 1-5",
        },
    },
    {
        "name": "update_goal_progress",
        "description": "Add a progress note to a goal.",
        "parameters": {
            "goal_id": "string — goal ID",
            "note":    "string — progress note",
        },
    },
    {
        "name": "get_media",
        "description": "Get the user's media library — movies, anime, books, games they've watched/read/played and their reactions.",
        "parameters": {
            "type":       "optional string — movie|anime|series|manga|book|game|comic",
            "min_rating": "optional float — minimum rating filter",
        },
    },
    {
        "name": "get_lexicon",
        "description": "Get the user's personal vocabulary, slang, and communication style rules.",
        "parameters": {},
    },
    {
        "name": "get_today_date",
        "description": "Get the current date.",
        "parameters": {},
    },
    {
        "name": "get_spending_summary",
        "description": "Get a summary of spending patterns.",
        "parameters": {},
    },
    {
        "name": "get_attendance_status",
        "description": "Get current attendance status for all subjects.",
        "parameters": {},
    },
    {
        "name": "get_consolidation_summary",
        "description": "Get recent daily/weekly summaries.",
        "parameters": {
            "level": "string — daily|weekly",
            "limit": "optional int — how many (default 7)",
        },
    },
]

TOOLS_SCHEMA = json.dumps(
    [{"name": t["name"], "description": t["description"], "parameters": t["parameters"]}
     for t in TOOLS],
    indent=2
)


# ── Tool execution ────────────────────────────────────────────────────────────

def execute_tool(name: str, args: dict) -> str:
    """Execute a tool by name and return result as string."""
    fn = _REGISTRY.get(name)
    if not fn:
        return f"Unknown tool: {name}"
    try:
        result = fn(**args)
        if isinstance(result, (dict, list)):
            return json.dumps(result, indent=2, default=str)
        return str(result)
    except Exception as e:
        return f"Tool error ({name}): {e}"


def _search_memory(query: str, collection: str = None) -> list:
    if collection:
        from memory.retrieval import hybrid_search
        return hybrid_search(query, n_results=6, collection=collection)
    else:
        from memory.retrieval import multi_collection_search
        return multi_collection_search(query, n_results=8)


def _get_semantic_facts(category: str = None) -> list:
    from memory import semantic
    if category:
        return semantic.get_category(category)
    return semantic.get_all()


def _get_recent_events(days: int = 7, category: str = None) -> list:
    from memory import episodic
    if category:
        return episodic.get_by_category(category)
    return episodic.get_recent(days=days)


def _get_goals() -> list:
    from memory import goals
    return goals.get_active()


def _get_goal_alerts() -> list:
    from memory import goals
    return goals.get_deadline_alerts()


def _get_graph_connections(entity: str) -> dict:
    from memory import graph
    return graph.get_entity_subgraph(entity, depth=2)


def _get_profile() -> dict:
    from memory.manager import load_profile
    return load_profile()


def _get_working_memory() -> dict:
    from memory import working
    return working.get()


def _add_memory(text: str, collection: str = "memories") -> str:
    from memory.retrieval import add_to_collection
    doc_id = add_to_collection(text, {"source": "agent"}, collection)
    return f"Stored memory: {doc_id}"


def _add_episode(summary: str, category: str = "general", importance: int = 3) -> str:
    from memory import episodic
    ep_id = episodic.add_episode(summary=summary, category=category,
                                  importance=importance, source="agent")
    return f"Episode stored: {ep_id}"


def _update_goal_progress(goal_id: str, note: str) -> str:
    from memory import goals
    goals.add_progress_note(goal_id, note)
    return f"Progress note added to goal {goal_id}"


def _get_media(type: str = None, min_rating: float = None) -> list:
    from media.entry import get_all
    entries = get_all(media_type=type, min_rating=min_rating, limit=50)
    # Trimmed view for the planner — full entries (reaction, themes, quotes,
    # personality_signals, timestamps, etc.) are too verbose and were causing
    # the model to lose track of the ReAct format on the next step.
    return [
        {
            "title":  e.get("title"),
            "type":   e.get("type"),
            "status": e.get("status"),
            "rating": e.get("rating"),
            "year":   e.get("year") or None,
        }
        for e in entries
    ]


def _get_lexicon() -> dict:
    from memory.lexicon import get_all_terms, get_all_style_rules, get_all_references
    return {
        "terms":       get_all_terms(),
        "style_rules": get_all_style_rules(),
        "references":  get_all_references(),
    }


def _get_today_date() -> str:
    return datetime.date.today().isoformat()


def _get_spending_summary() -> dict:
    from memory.manager import load_profile
    p = load_profile()
    f = p.get("finances", {})
    return {
        "monthly_budget":  f.get("monthly_budget", 0),
        "top_categories":  f.get("categories", {}),
        "monthly_totals":  f.get("monthly_totals", {}),
        "cashiro_linked":  f.get("cashiro_linked", False),
    }


def _get_attendance_status() -> dict:
    from memory.manager import load_profile
    p = load_profile()
    attendance = p.get("academic", {}).get("attendance", {})
    low = {s: v for s, v in attendance.items() if float(v) < 75}
    return {
        "attendance":     attendance,
        "low_attendance": low,
        "at_risk_count":  len(low),
    }


def _get_consolidation_summary(level: str = "daily", limit: int = 7) -> list:
    from memory import consolidation
    return consolidation.get_recent_summaries(level, limit)


_REGISTRY: dict[str, Callable] = {
    "search_memory":          _search_memory,
    "get_semantic_facts":     _get_semantic_facts,
    "get_recent_events":      _get_recent_events,
    "get_goals":              _get_goals,
    "get_goal_alerts":        _get_goal_alerts,
    "get_graph_connections":  _get_graph_connections,
    "get_profile":            _get_profile,
    "get_working_memory":     _get_working_memory,
    "add_memory":             _add_memory,
    "add_episode":            _add_episode,
    "update_goal_progress":   _update_goal_progress,
    "get_media":              _get_media,
    "get_lexicon":            _get_lexicon,
    "get_today_date":         _get_today_date,
    "get_spending_summary":   _get_spending_summary,
    "get_attendance_status":  _get_attendance_status,
    "get_consolidation_summary": _get_consolidation_summary,
}
