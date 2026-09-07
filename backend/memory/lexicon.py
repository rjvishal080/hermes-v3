"""
memory/lexicon.py
─────────────────────────────────────────────────────────────────────────────
Personal Lexicon — your dialect, slang, references, and communication style.

Three tables:

1. terms
   Personal vocabulary and slang with meanings + usage examples.
   e.g. "tonyad" → "got beaten or outcompeted by someone"
        example: "I got tonyad in the hackathon" = I lost to a competitor

2. style_rules
   How you communicate — tone, directness, energy, format preferences.
   e.g. "respond at my energy level — casual messages get casual replies"
        "never say 'certainly' or 'absolutely'"
        "use 'bro' as a neutral term, I do too"

3. references
   Cultural / personal references the model should understand.
   e.g. "when I say 'sigma grindset' I'm being ironic, not serious"
        "Arch btw = I use Arch Linux, I say this as a meme"

Injection into system prompt:
  The full lexicon is injected as a compact block so the model:
  - Understands your terms when you use them
  - Uses them back naturally when contextually right
  - Matches your communication register
  - Never sounds generic or corporate
"""

import json
import sqlite3
import hashlib
import datetime
from pathlib import Path
from typing import Optional

DATA_DIR = Path(__file__).parent.parent / "data"
DB_PATH  = DATA_DIR / "lexicon.db"

TERM_CATEGORIES = [
    "slang",        # casual/street slang
    "personal",     # your own invented terms
    "technical",    # tech terms you use in your own way
    "cultural",     # memes, references, inside jokes
    "emotional",    # how you express feelings
    "irony",        # things you say sarcastically or ironically
]

STYLE_CATEGORIES = [
    "tone",         # formal/casual, serious/playful
    "format",       # how you want replies structured
    "address",      # how to address you, terms of address
    "energy",       # how to match your vibe
    "forbidden",    # words/phrases the model should NEVER say
    "preferred",    # words/phrases to use more
]


def _conn() -> sqlite3.Connection:
    DATA_DIR.mkdir(exist_ok=True)
    c = sqlite3.connect(str(DB_PATH))
    c.row_factory = sqlite3.Row
    return c


def _init():
    with _conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS terms (
                id          TEXT PRIMARY KEY,
                term        TEXT NOT NULL UNIQUE,
                meaning     TEXT NOT NULL,
                category    TEXT NOT NULL DEFAULT 'slang',
                examples    TEXT NOT NULL DEFAULT '[]',
                context     TEXT NOT NULL DEFAULT '',
                created_at  TEXT NOT NULL,
                updated_at  TEXT NOT NULL
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_term ON terms(term)")

        c.execute("""
            CREATE TABLE IF NOT EXISTS style_rules (
                id          TEXT PRIMARY KEY,
                rule        TEXT NOT NULL,
                category    TEXT NOT NULL DEFAULT 'tone',
                strength    REAL NOT NULL DEFAULT 1.0,
                created_at  TEXT NOT NULL
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS references_ (
                id          TEXT PRIMARY KEY,
                trigger     TEXT NOT NULL,
                meaning     TEXT NOT NULL,
                is_ironic   INTEGER NOT NULL DEFAULT 0,
                created_at  TEXT NOT NULL
            )
        """)

_init()


# ── Terms ─────────────────────────────────────────────────────────────────────

def add_term(
    term:     str,
    meaning:  str,
    category: str = "slang",
    examples: list[str] = None,
    context:  str = "",
) -> str:
    """
    Add or update a personal term.
    examples: list of full sentences showing the term in use.
    e.g. add_term(
        term="tonyad",
        meaning="got beaten or outcompeted by someone who wanted to win",
        examples=["I got tonyad in the hackathon", "bro completely tonyad me in DSA"],
        context="used when a competitor beats you, implies they wanted to specifically beat you"
    )
    """
    tid  = hashlib.md5(term.lower().strip().encode()).hexdigest()[:12]
    now  = datetime.datetime.utcnow().isoformat()
    exs  = json.dumps(examples or [])
    with _conn() as c:
        c.execute("""
            INSERT INTO terms (id, term, meaning, category, examples, context, created_at, updated_at)
            VALUES (?,?,?,?,?,?,?,?)
            ON CONFLICT(term) DO UPDATE SET
                meaning=excluded.meaning,
                category=excluded.category,
                examples=excluded.examples,
                context=excluded.context,
                updated_at=excluded.updated_at
        """, (tid, term.strip(), meaning, category, exs, context, now, now))
    return tid


def get_term(term: str) -> Optional[dict]:
    with _conn() as c:
        row = c.execute("SELECT * FROM terms WHERE term=?", (term.lower().strip(),)).fetchone()
        return _parse_term(row) if row else None


def get_all_terms() -> list[dict]:
    with _conn() as c:
        rows = c.execute("SELECT * FROM terms ORDER BY category, term").fetchall()
    return [_parse_term(r) for r in rows]


def delete_term(term_id: str):
    with _conn() as c:
        c.execute("DELETE FROM terms WHERE id=?", (term_id,))


def _parse_term(row) -> dict:
    d = dict(row)
    d["examples"] = json.loads(d.get("examples", "[]"))
    return d


# ── Style rules ───────────────────────────────────────────────────────────────

def add_style_rule(
    rule:     str,
    category: str = "tone",
    strength: float = 1.0,
) -> str:
    """
    Add a communication style rule.
    e.g. add_style_rule("Never say 'certainly' or 'absolutely' — sounds corporate", "forbidden")
         add_style_rule("Match my energy — if I'm hype, be hype back", "energy")
         add_style_rule("I say 'bro' as neutral, use it back sometimes", "address")
         add_style_rule("Don't over-explain things I already know", "format")
    """
    rid = hashlib.md5(rule.lower().strip().encode()).hexdigest()[:12]
    now = datetime.datetime.utcnow().isoformat()
    with _conn() as c:
        c.execute("""
            INSERT OR IGNORE INTO style_rules (id, rule, category, strength, created_at)
            VALUES (?,?,?,?,?)
        """, (rid, rule.strip(), category, strength, now))
    return rid


def get_all_style_rules() -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM style_rules ORDER BY strength DESC, category"
        ).fetchall()
    return [dict(r) for r in rows]


def delete_style_rule(rule_id: str):
    with _conn() as c:
        c.execute("DELETE FROM style_rules WHERE id=?", (rule_id,))


# ── References ────────────────────────────────────────────────────────────────

def add_reference(
    trigger:   str,
    meaning:   str,
    is_ironic: bool = False,
) -> str:
    """
    Add a cultural/personal reference.
    e.g. add_reference("sigma grindset", "ironic reference to hustle culture, I don't mean it seriously", True)
         add_reference("Arch btw", "I use Arch Linux, said as a meme/flex", False)
    """
    rid = hashlib.md5(trigger.lower().strip().encode()).hexdigest()[:12]
    now = datetime.datetime.utcnow().isoformat()
    with _conn() as c:
        c.execute("""
            INSERT OR IGNORE INTO references_ (id, trigger, meaning, is_ironic, created_at)
            VALUES (?,?,?,?,?)
        """, (rid, trigger.strip(), meaning, int(is_ironic), now))
    return rid


def get_all_references() -> list[dict]:
    with _conn() as c:
        rows = c.execute("SELECT * FROM references_ ORDER BY trigger").fetchall()
    return [dict(r) for r in rows]


def delete_reference(ref_id: str):
    with _conn() as c:
        c.execute("DELETE FROM references_ WHERE id=?", (ref_id,))


# ── System prompt injection ───────────────────────────────────────────────────

def to_system_prompt_block() -> str:
    """
    Build the full lexicon block for injection into the LLM system prompt.
    This is the core of the feature — the model reads this before every response.
    """
    terms  = get_all_terms()
    rules  = get_all_style_rules()
    refs   = get_all_references()

    if not terms and not rules and not refs:
        return ""

    parts = []

    # ── Vocabulary block ──────────────────────────────────────────────────────
    if terms:
        parts.append("MY PERSONAL VOCABULARY (understand and use naturally):")
        for t in terms:
            line = f'  "{t["term"]}" → {t["meaning"]}'
            if t["context"]:
                line += f' [{t["context"]}]'
            parts.append(line)
            for ex in t["examples"][:2]:  # max 2 examples per term
                parts.append(f'    e.g. "{ex}"')

    # ── Communication style ───────────────────────────────────────────────────
    if rules:
        parts.append("\nHOW I COMMUNICATE (adapt your style to match):")

        # Group by category for clarity
        by_cat: dict[str, list] = {}
        for r in rules:
            by_cat.setdefault(r["category"], []).append(r["rule"])

        for cat, cat_rules in by_cat.items():
            parts.append(f"  [{cat.upper()}]")
            for rule in cat_rules:
                parts.append(f"    • {rule}")

    # ── References ────────────────────────────────────────────────────────────
    if refs:
        parts.append("\nMY REFERENCES AND IN-JOKES:")
        for ref in refs:
            ironic = " (IRONIC — I don't mean it literally)" if ref["is_ironic"] else ""
            parts.append(f'  "{ref["trigger"]}" → {ref["meaning"]}{ironic}')

    # ── Closing instruction ───────────────────────────────────────────────────
    parts.append(
        "\nIMPORTANT: Use this vocabulary naturally — don't over-explain my slang back to me. "
        "When I use these terms, just understand them. Use them back when it fits naturally. "
        "Never sound like a corporate assistant."
    )

    return "\n".join(parts)


# ── Auto-extraction from conversation ────────────────────────────────────────

EXTRACT_LEXICON_SYSTEM = """Analyze this conversation and extract any personal vocabulary, slang, or style patterns.

Return ONLY valid JSON:
{
  "terms": [
    {
      "term": "the word/phrase",
      "meaning": "what it means in context",
      "category": "slang|personal|technical|cultural|emotional|irony",
      "examples": ["full sentence using it from the conversation"],
      "context": "additional context about when/how it's used"
    }
  ],
  "style_rules": [
    {
      "rule": "a clear rule about how this person communicates",
      "category": "tone|format|address|energy|forbidden|preferred"
    }
  ],
  "references": [
    {
      "trigger": "the phrase or reference",
      "meaning": "what it actually means",
      "is_ironic": false
    }
  ]
}

Only extract things that are clearly personal/non-standard vocabulary.
Don't extract common English words.
Don't extract things already obvious.
If nothing found, return {"terms": [], "style_rules": [], "references": []}
No markdown."""


def extract_from_conversation(conversation_text: str) -> dict:
    """
    Auto-extract vocabulary and style from a conversation.
    Called after each session to learn new terms organically.
    """
    from engine.llm import generate

    messages = [{"role": "user", "content": f"Extract personal vocabulary:\n\n{conversation_text}"}]

    try:
        raw   = generate(EXTRACT_LEXICON_SYSTEM, messages, max_new_tokens=600, temperature=0.1)
        clean = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
        data  = json.loads(clean)
    except Exception as e:
        print(f"[Lexicon] Extraction failed: {e}")
        return {"terms": 0, "style_rules": 0, "references": 0}

    counts = {"terms": 0, "style_rules": 0, "references": 0}

    for t in data.get("terms", []):
        if t.get("term") and t.get("meaning") and len(t["term"]) > 1:
            add_term(
                term=t["term"],
                meaning=t["meaning"],
                category=t.get("category", "slang"),
                examples=t.get("examples", []),
                context=t.get("context", ""),
            )
            counts["terms"] += 1

    for r in data.get("style_rules", []):
        if r.get("rule"):
            add_style_rule(r["rule"], r.get("category", "tone"))
            counts["style_rules"] += 1

    for ref in data.get("references", []):
        if ref.get("trigger") and ref.get("meaning"):
            add_reference(ref["trigger"], ref["meaning"], ref.get("is_ironic", False))
            counts["references"] += 1

    return counts


def get_stats() -> dict:
    with _conn() as c:
        terms  = c.execute("SELECT COUNT(*) FROM terms").fetchone()[0]
        rules  = c.execute("SELECT COUNT(*) FROM style_rules").fetchone()[0]
        refs   = c.execute("SELECT COUNT(*) FROM references_").fetchone()[0]
        by_cat = c.execute("SELECT category, COUNT(*) FROM terms GROUP BY category").fetchall()
    return {
        "terms":      terms,
        "style_rules": rules,
        "references": refs,
        "terms_by_category": {r[0]: r[1] for r in by_cat},
    }
