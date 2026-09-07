"""
media/patterns.py
─────────────────────────────────────────────────────────────────────────────
Cross-media pattern analysis.

After 10+ entries, runs pattern extraction to surface:
  - What you consistently love across all media
  - What consistently breaks immersion for you
  - Themes you're drawn to
  - Character types you connect with
  - Your relationship with difficulty/darkness
  - Mood-consumption correlations
  - Taste profile summary

Results pushed to semantic memory as high-confidence personality facts.
"""

import json
from pathlib import Path

PATTERNS_SYSTEM = """You are analyzing someone's complete media consumption history to extract deep personality patterns.

This is NOT about their taste in movies — it's about what their reactions to fiction reveal about who they are.

Entries:
{entries_summary}

Analyze across all entries and return ONLY valid JSON:
{
  "what_they_love": [
    "morally ambiguous characters who act from genuine conviction, not clarity",
    "slow deliberate pacing that earns its emotional payoffs",
    ...up to 6 specific patterns
  ],
  "what_breaks_immersion": [
    "passive protagonists after strong openings",
    "redemption arcs that feel unearned",
    ...up to 4 patterns
  ],
  "recurring_themes": [
    "identity without purpose",
    "cycles of violence",
    "what it means to be human under pressure",
    ...up to 5 themes
  ],
  "character_types_connected_with": [
    "morally grey mentor/antagonist figures",
    "characters who carry enormous weight silently",
    ...up to 4 types
  ],
  "relationship_with_darkness": "one sentence — e.g. 'seeks out heavy content, doesn't avoid difficulty, processes it analytically rather than emotionally detaching'",
  "analytical_style": "one sentence — e.g. 'reads themes explicitly and before emotional response, interprets through character lens'",
  "emotional_engagement": "one sentence — how they emotionally connect",
  "taste_profile": "2-3 sentences that capture their entire aesthetic as a consumer — specific and personal, not generic",
  "semantic_facts": [
    {"key": "personality.media_taste_profile", "value": "...", "category": "personality"},
    {"key": "personality.favored_character_type", "value": "...", "category": "personality"},
    {"key": "personality.relationship_with_dark_content", "value": "...", "category": "personality"}
  ]
}

Be specific to THEIR actual entries, not generic observations.
No markdown. Raw JSON only."""


def run_pattern_analysis() -> dict:
    """
    Analyze all media entries and extract personality patterns.
    Pushes results to semantic memory.
    Runs after every 10 new entries (tracked via count in stats).
    """
    from media.entry import get_completed, get_all_signals
    from engine.llm import generate
    from memory.semantic import bulk_set

    entries = get_completed()
    if len(entries) < 5:
        return {"message": f"Need at least 5 entries, have {len(entries)}"}

    # Build compact summary for each entry
    summaries = []
    for e in entries:
        parts = [f"[{e['type'].upper()}] {e['title']}"]
        if e.get("rating"):          parts.append(f"Rating: {e['rating']}/10")
        if e.get("reaction"):        parts.append(f"Reaction: {e['reaction'][:120]}")
        if e.get("interpretation"):  parts.append(f"Interpretation: {e['interpretation'][:100]}")
        if e.get("what_worked"):     parts.append(f"Loved: {', '.join(e['what_worked'][:3])}")
        if e.get("what_didnt"):      parts.append(f"Didn't work: {', '.join(e['what_didnt'][:2])}")
        if e.get("themes_noticed"):  parts.append(f"Themes: {', '.join(e['themes_noticed'][:3])}")
        if e.get("rewatch"):         parts.append(f"Rewatch: {e['rewatch']}")
        summaries.append("\n  ".join(parts))

    entries_text = "\n\n".join(summaries)
    messages     = [{"role": "user", "content": f"Analyze these entries:\n\n{entries_text}"}]

    try:
        raw   = generate(PATTERNS_SYSTEM.format(entries_summary=entries_text),
                         messages, max_new_tokens=800, temperature=0.2)
        clean = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
        data  = json.loads(clean)
    except Exception as e:
        return {"error": f"Pattern analysis failed: {e}"}

    # Push semantic facts
    if data.get("semantic_facts"):
        valid_facts = [f for f in data["semantic_facts"]
                       if isinstance(f, dict) and "key" in f and "value" in f]
        if valid_facts:
            bulk_set(valid_facts)

    # Push all patterns to procedural memory
    from memory.procedural import set_preference
    for pattern in data.get("what_they_love", []):
        set_preference(f"Media: loves when — {pattern}", "personality", 0.85, "media_analysis")
    for pattern in data.get("what_breaks_immersion", []):
        set_preference(f"Media: dislikes when — {pattern}", "personality", 0.85, "media_analysis")

    return data


def get_taste_summary() -> str:
    """Quick taste profile for LLM context injection."""
    from media.entry import get_stats, get_all_signals
    from memory.semantic import get_fact

    profile = get_fact("personality.media_taste_profile")
    if profile:
        return profile["value"]

    # Build from signals if no profile yet
    signals = get_all_signals()
    stats   = get_stats()
    if not signals and stats["total"] == 0:
        return ""

    parts = []
    if stats["total"] > 0:
        parts.append(f"Has consumed {stats['total']} works across {len(stats['by_type'])} media types.")
    if signals:
        parts.append(f"Personality signals: {'; '.join(signals[:4])}")
    return " ".join(parts)
