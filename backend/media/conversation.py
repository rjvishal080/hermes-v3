"""
media/conversation.py
─────────────────────────────────────────────────────────────────────────────
Handles the @trigger chat flow for logging media experiences.

Triggers:
  @movie      → movie / film
  @anime      → anime
  @series     → TV series / show
  @manga      → manga / manhwa / manhua
  @book       → book / novel / light novel
  @game       → video game
  @comic      → comic / graphic novel
  @doc        → documentary
  @podcast    → podcast

Flow:
  1. User types "@movie I just finished Capernaum. It was fantastic."
  2. detect_trigger() identifies the type and extracts the title
  3. A media conversation session starts — special mode in the chat
  4. Hermes asks follow-up questions naturally (reaction → interpretation
     → what worked → what didn't → themes → rewatch → recommendation)
  5. After enough is gathered, extract_from_conversation() builds the entry
  6. Entry stored + personality signals pushed to procedural memory

The conversation is guided but feels natural — Hermes asks ONE question
at a time, reads the answer, and decides what to ask next based on
what's still missing rather than following a rigid script.
"""

import re
import json
from typing import Optional

# ── Trigger detection ─────────────────────────────────────────────────────────

TRIGGERS = {
    "@movie":      "movie",
    "@film":       "movie",
    "@anime":      "anime",
    "@series":     "series",
    "@show":       "series",
    "@manga":      "manga",
    "@manhwa":     "manhwa",
    "@manhua":     "manhua",
    "@book":       "book",
    "@novel":      "novel",
    "@ln":         "light_novel",
    "@lightnovel": "light_novel",
    "@game":       "game",
    "@comic":      "comic",
    "@doc":        "documentary",
    "@documentary":"documentary",
    "@podcast":    "podcast",
}

TYPE_LABELS = {
    "movie":       "film",
    "anime":       "anime",
    "series":      "series",
    "manga":       "manga",
    "manhwa":      "manhwa",
    "manhua":      "manhua",
    "book":        "book",
    "novel":       "novel",
    "light_novel": "light novel",
    "game":        "game",
    "comic":       "comic",
    "documentary": "documentary",
    "podcast":     "podcast",
}


def detect_trigger(message: str) -> Optional[dict]:
    """
    Check if a message starts a media logging session.
    Returns {type, title_hint, raw_message} or None.
    """
    lower = message.lower().strip()
    for trigger, media_type in TRIGGERS.items():
        if lower.startswith(trigger):
            # Everything after the trigger is the initial description
            rest = message[len(trigger):].strip()
            return {
                "type":        media_type,
                "raw_message": message,
                "initial_text": rest,
            }
    return None


def extract_title_from_text(text: str, media_type: str) -> str:
    """
    Best-effort title extraction from initial message.
    e.g. "I just finished Capernaum. It was fantastic." → "Capernaum"
    e.g. "Vinland Saga — absolutely destroyed me" → "Vinland Saga"
    """
    # Remove common filler phrases
    fillers = [
        r"^i just (finished|completed|watched|read|played)\s+",
        r"^just (finished|completed|watched|read|played)\s+",
        r"^finally (finished|completed|watched|read|played)\s+",
        r"^finished\s+",
        r"^watched\s+",
        r"^completed\s+",
        r"^read\s+",
        r"^played\s+",
    ]
    cleaned = text.strip()
    for pattern in fillers:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE).strip()

    # Take everything up to first sentence-ending punctuation or dash
    match = re.match(r'^([^.!?,\-—]+)', cleaned)
    if match:
        return match.group(1).strip()
    return cleaned[:60].strip()


# ── Conversation state ─────────────────────────────────────────────────────────

# Stored in working memory per session as a JSON blob
# Key: f"media_session_{session_id}"

QUESTIONS = [
    "reaction",
    "interpretation",
    "what_worked",
    "what_didnt",
    "themes",
    "memorable_moments",
    "rewatch",
    "recommend",
]

def get_next_question(gathered: dict, media_type: str, title: str) -> Optional[str]:
    """
    Decide what to ask next based on what's still missing.
    Returns the question key to ask, or None if enough is gathered.
    """
    # Must-haves before we can store
    if not gathered.get("reaction"):
        return "reaction"
    if not gathered.get("interpretation") and len(gathered.get("reaction", "")) > 20:
        return "interpretation"
    if not gathered.get("what_worked"):
        return "what_worked"
    if not gathered.get("what_didnt"):
        return "what_didnt"
    if not gathered.get("rewatch"):
        return "rewatch"
    if not gathered.get("recommend"):
        return "recommend"
    # Optional enrichment
    if not gathered.get("themes") and len(gathered.get("reaction", "")) > 50:
        return "themes"
    return None  # enough gathered, store it


# ── LLM-driven conversation ───────────────────────────────────────────────────

MEDIA_CONVERSATION_SYSTEM = """You are Hermes, a deeply personal AI having a conversation about a {type} the user just experienced.

Title: {title}
Media type: {type_label}
What they said initially: "{initial_text}"

Your job: have a NATURAL conversation to draw out their full experience. 
Ask ONE question at a time. Be conversational, not clinical.
React to what they say before asking the next question — show you're actually listening.
Match their energy. If they're emotional about it, be present with that.
If they say it was devastating, don't immediately pivot to "what worked?"

Current information gathered:
{gathered_summary}

Next thing to explore: {next_question}

Guidelines for each question:
- reaction: "What hit you most about it?" or react to their initial statement and ask what specifically
- interpretation: "What do you think it's actually about?" or "What's your read on [specific element they mentioned]?"
- what_worked: "What worked for you?" or follow naturally from what they praised
- what_didnt: "Anything that didn't land?" or "Was there anything that pulled you out?"
- themes: "What themes were you picking up on?" — only ask if they seem analytically inclined
- memorable_moments: "Any specific scene or moment that stays with you?" — follows naturally from reaction
- rewatch: "Would you go back to it?" or "Is this a rewatch or a carry-forever?"
- recommend: "Who would you put this in front of?"

When enough is gathered (reaction + interpretation + what_worked + what_didnt + rewatch + recommend are all present):
End with a brief, genuine summary of what you're storing, mention the personality signals you noticed, and confirm the entry is saved.
Say something like "Stored. [Title] logged — [brief characterization]" and mention what you noticed about their taste.

NEVER use bullet points or numbered lists in this conversation.
Keep responses short — 2-4 sentences max before your question.
Be direct. Don't say "Great!" or "That's fascinating!" before responding."""


EXTRACT_ENTRY_SYSTEM = """Extract a structured media entry from this conversation.

Return ONLY valid JSON, no markdown:
{
  "title": "exact title",
  "creator": "director/author/studio if mentioned, else empty string",
  "year": "year if mentioned, else empty string",
  "rating": 8.5,
  "rating_raw": "fantastic / 9/10 / etc — whatever they said",
  "reaction": "their raw emotional reaction in their own words (1-2 sentences)",
  "interpretation": "their reading of what it means or is about",
  "what_worked": ["specific element", "another element"],
  "what_didnt": ["specific thing that didn't land"],
  "themes_noticed": ["theme they identified"],
  "memorable_moments": ["specific scene or moment they mentioned"],
  "quotes": ["any quotes from the work they mentioned"],
  "rewatch": "yes_definitely|maybe|no_once_is_enough|carry_forever_no_rewatch|already_rewatched",
  "recommendation": "who they'd recommend it to and how strongly",
  "recommend_to": "brief description of who should watch this",
  "mood_when_consumed": "their mood/life context if mentioned",
  "personality_signals": [
    "prefers morally complex characters over clear heroes",
    "emotionally invests in specific characters not ensembles",
    "values slow burn with earned payoff",
    ... up to 5 signals inferred from their reactions
  ]
}

Rating inference from language:
  "masterpiece" / "all time" / "perfect" → 10
  "fantastic" / "loved it" / "essential" → 9-9.5
  "really good" / "great" → 8-8.5
  "good" / "enjoyed" → 7-7.5
  "decent" / "okay" → 6-6.5
  "disappointing" / "meh" → 5
  "bad" / "dropped" → 3-4

Personality signals should be specific and insightful — what does their reaction reveal about how they experience stories?
Focus on: what they value (pacing, character depth, themes, aesthetics), 
how they emotionally engage (which characters, what events affect them),
what they reject (what breaks immersion for them),
their analytical style (do they read themes explicitly? care about craft?).
No markdown, just raw JSON."""


def build_gathered_summary(gathered: dict) -> str:
    if not gathered:
        return "Nothing yet."
    lines = []
    if gathered.get("reaction"):        lines.append(f"Reaction: {gathered['reaction'][:100]}")
    if gathered.get("interpretation"):  lines.append(f"Interpretation: {gathered['interpretation'][:100]}")
    if gathered.get("what_worked"):     lines.append(f"What worked: {', '.join(gathered['what_worked'][:3])}")
    if gathered.get("what_didnt"):      lines.append(f"What didn't: {', '.join(gathered['what_didnt'][:2])}")
    if gathered.get("themes"):          lines.append(f"Themes: {', '.join(gathered['themes'][:3])}")
    if gathered.get("rewatch"):         lines.append(f"Rewatch: {gathered['rewatch']}")
    if gathered.get("recommend"):       lines.append(f"Recommend: {gathered['recommend'][:80]}")
    return "\n".join(lines) if lines else "Nothing substantive yet."


async def run_media_conversation_turn(
    session_id:   str,
    user_message: str,
    media_state:  dict,  # {type, title, initial_text, gathered, turn_count}
    history:      list[dict],
) -> tuple[str, dict, bool]:
    """
    Run one turn of the media conversation.
    Returns: (response_text, updated_media_state, is_complete)
    """
    from engine.llm import generate

    gathered    = media_state.get("gathered", {})
    title       = media_state.get("title", "")
    media_type  = media_state.get("type", "movie")
    initial     = media_state.get("initial_text", "")
    turn_count  = media_state.get("turn_count", 0)

    # Update gathered from this message
    next_q = get_next_question(gathered, media_type, title)
    if next_q and user_message.strip():
        if next_q == "reaction":
            gathered["reaction"] = user_message
        elif next_q == "interpretation":
            gathered["interpretation"] = user_message
        elif next_q == "what_worked":
            gathered["what_worked"] = [user_message]
        elif next_q == "what_didnt":
            gathered["what_didnt"] = [user_message]
        elif next_q == "themes":
            gathered["themes"] = [user_message]
        elif next_q == "memorable_moments":
            gathered["memorable_moments"] = [user_message]
        elif next_q == "rewatch":
            gathered["rewatch"] = user_message
        elif next_q == "recommend":
            gathered["recommend"] = user_message

    media_state["gathered"]   = gathered
    media_state["turn_count"] = turn_count + 1

    # Check if complete
    next_question = get_next_question(gathered, media_type, title)
    is_complete   = next_question is None or turn_count >= 7

    system = MEDIA_CONVERSATION_SYSTEM.format(
        type=media_type,
        type_label=TYPE_LABELS.get(media_type, media_type),
        title=title,
        initial_text=initial,
        gathered_summary=build_gathered_summary(gathered),
        next_question=next_question or "wrap up — enough gathered, confirm storage",
    )

    messages = history + [{"role": "user", "content": user_message}]
    response = generate(system, messages, max_new_tokens=200, temperature=0.7)

    return response, media_state, is_complete


def extract_entry_from_conversation(
    title:        str,
    media_type:   str,
    conversation: list[dict],
    gathered:     dict,
) -> dict:
    """
    Use LLM to extract structured entry from the full conversation.
    Falls back to gathered dict if LLM fails.
    """
    from engine.llm import generate

    conv_text = "\n".join([
        f"{m['role'].upper()}: {m['content']}"
        for m in conversation[-20:]
    ])

    messages = [{"role": "user", "content": f"""
Title: {title}
Type: {media_type}

Conversation:
{conv_text}

Extract the media entry."""}]

    try:
        raw   = generate(EXTRACT_ENTRY_SYSTEM, messages, max_new_tokens=600, temperature=0.1)
        clean = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
        data  = json.loads(clean)
        data["title"]      = data.get("title") or title
        data["media_type"] = media_type
        return data
    except Exception as e:
        print(f"[Media] Entry extraction failed: {e}")
        # Fallback to gathered dict
        return {
            "title":          title,
            "media_type":     media_type,
            "reaction":       gathered.get("reaction", ""),
            "interpretation": gathered.get("interpretation", ""),
            "what_worked":    gathered.get("what_worked", []),
            "what_didnt":     gathered.get("what_didnt", []),
            "themes_noticed": gathered.get("themes", []),
            "rewatch":        gathered.get("rewatch", "maybe"),
            "recommendation": gathered.get("recommend", ""),
            "rating":         None,
            "personality_signals": [],
        }
