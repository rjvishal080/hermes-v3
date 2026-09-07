"""
memory/graph.py
─────────────────────────────────────────────────────────────────────────────
Knowledge Graph — relationships between facts.

Stored in SQLite as a simple (subject, relation, object, weight) table.
This is not a full graph DB — it's a lightweight triple store that lets
the planner reason across connected facts.

Example triples:
  ("Vishal", "studies_at",      "SJIT")
  ("Vishal", "taking_course",   "Operating Systems")
  ("OS",     "exam_in_days",    "5")
  ("OS",     "attendance",      "68%")
  ("Vishal", "goal",            "ML internship at Zoho")
  ("Zoho",   "placement_round", "next_month")

With this, the planner can reason:
  OS exam in 5 days + low attendance → priority alert
  Zoho round next month + ML goal → prep checklist

Without a graph, these three facts are isolated embeddings.

Schema:
  entities:    (id, name, type, properties_json)
  relations:   (id, subject_id, relation, object_id, weight, source, created_at)
"""

import json
import uuid
import sqlite3
import datetime
from pathlib import Path
from typing import Optional

DATA_DIR = Path(__file__).parent.parent / "data"
DB_PATH  = DATA_DIR / "graph.db"

ENTITY_TYPES = [
    "person", "place", "course", "goal", "project",
    "event", "skill", "company", "tool", "concept",
]

RELATION_TYPES = [
    "studies_at", "taking_course", "has_goal", "works_on",
    "knows", "attended", "exam_date", "deadline",
    "attendance_pct", "grade", "interested_in",
    "applied_to", "friend_with", "lives_in",
    "uses_tool", "has_skill", "wants_to_learn",
]


def _conn() -> sqlite3.Connection:
    DATA_DIR.mkdir(exist_ok=True)
    c = sqlite3.connect(str(DB_PATH))
    c.row_factory = sqlite3.Row
    return c


def _init():
    with _conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS entities (
                id         TEXT PRIMARY KEY,
                name       TEXT NOT NULL,
                type       TEXT NOT NULL DEFAULT 'concept',
                properties TEXT NOT NULL DEFAULT '{}',
                updated_at TEXT NOT NULL
            )
        """)
        c.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_name_type ON entities(name, type)")
        c.execute("""
            CREATE TABLE IF NOT EXISTS relations (
                id         TEXT PRIMARY KEY,
                subject    TEXT NOT NULL,
                relation   TEXT NOT NULL,
                object     TEXT NOT NULL,
                weight     REAL NOT NULL DEFAULT 1.0,
                source     TEXT NOT NULL DEFAULT 'auto',
                created_at TEXT NOT NULL,
                FOREIGN KEY(subject) REFERENCES entities(id),
                FOREIGN KEY(object)  REFERENCES entities(id)
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_subject  ON relations(subject)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_object   ON relations(object)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_relation ON relations(relation)")

_init()


def _get_or_create_entity(name: str, etype: str = "concept", props: dict = None) -> str:
    now = datetime.datetime.utcnow().isoformat()
    with _conn() as c:
        row = c.execute(
            "SELECT id FROM entities WHERE name=? AND type=?", (name, etype)
        ).fetchone()
        if row:
            return row["id"]
        eid = str(uuid.uuid4())
        c.execute(
            "INSERT INTO entities (id, name, type, properties, updated_at) VALUES (?,?,?,?,?)",
            (eid, name, etype, json.dumps(props or {}), now)
        )
        return eid


def add_triple(
    subject:  str,
    relation: str,
    obj:      str,
    subject_type: str = "concept",
    object_type:  str = "concept",
    weight:   float = 1.0,
    source:   str = "auto",
) -> str:
    """Add a (subject, relation, object) triple."""
    sid = _get_or_create_entity(subject, subject_type)
    oid = _get_or_create_entity(obj, object_type)
    rid = str(uuid.uuid4())
    now = datetime.datetime.utcnow().isoformat()
    with _conn() as c:
        # Avoid exact duplicates
        existing = c.execute(
            "SELECT id FROM relations WHERE subject=? AND relation=? AND object=?",
            (sid, relation, oid)
        ).fetchone()
        if existing:
            c.execute(
                "UPDATE relations SET weight=?, created_at=? WHERE id=?",
                (weight, now, existing["id"])
            )
            return existing["id"]
        c.execute(
            "INSERT INTO relations (id, subject, relation, object, weight, source, created_at) VALUES (?,?,?,?,?,?,?)",
            (rid, sid, relation, oid, weight, source, now)
        )
    return rid


def get_neighbors(entity_name: str, relation: Optional[str] = None) -> list[dict]:
    """Get all entities connected to this one."""
    with _conn() as c:
        row = c.execute(
            "SELECT id FROM entities WHERE name=?", (entity_name,)
        ).fetchone()
        if not row:
            return []
        eid = row["id"]

        query = """
            SELECT e2.name as target, r.relation, r.weight, r.source,
                   'outgoing' as direction
            FROM relations r
            JOIN entities e2 ON e2.id = r.object
            WHERE r.subject = ?
        """
        params = [eid]
        if relation:
            query += " AND r.relation = ?"
            params.append(relation)

        query += """
            UNION ALL
            SELECT e2.name as target, r.relation, r.weight, r.source,
                   'incoming' as direction
            FROM relations r
            JOIN entities e2 ON e2.id = r.subject
            WHERE r.object = ?
        """
        params.append(eid)
        if relation:
            query += " AND r.relation = ?"
            params.append(relation)

        rows = c.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def get_entity_subgraph(entity_name: str, depth: int = 2) -> dict:
    """Get entity and its neighborhood up to `depth` hops."""
    visited = set()
    nodes   = []
    edges   = []

    def explore(name: str, current_depth: int):
        if name in visited or current_depth > depth:
            return
        visited.add(name)
        nodes.append(name)
        for neighbor in get_neighbors(name):
            edges.append({
                "from":     name,
                "relation": neighbor["relation"],
                "to":       neighbor["target"],
                "weight":   neighbor["weight"],
            })
            explore(neighbor["target"], current_depth + 1)

    explore(entity_name, 0)
    return {"nodes": nodes, "edges": edges}


def to_context_string(entity_name: str = None) -> str:
    """Render graph as readable text for LLM context."""
    with _conn() as c:
        if entity_name:
            neighbors = get_neighbors(entity_name)
            if not neighbors:
                return f"No graph connections for {entity_name}."
            lines = [f"Knowledge graph for {entity_name}:"]
            for n in neighbors:
                arrow = "→" if n["direction"] == "outgoing" else "←"
                lines.append(f"  {entity_name} {arrow}[{n['relation']}]→ {n['target']}")
            return "\n".join(lines)
        else:
            rows = c.execute("""
                SELECT e1.name as s, r.relation, e2.name as o
                FROM relations r
                JOIN entities e1 ON e1.id = r.subject
                JOIN entities e2 ON e2.id = r.object
                ORDER BY r.created_at DESC
                LIMIT 40
            """).fetchall()
            if not rows:
                return "Knowledge graph is empty."
            return "\n".join([f"  {r['s']} →[{r['relation']}]→ {r['o']}" for r in rows])


def get_stats() -> dict:
    with _conn() as c:
        entities  = c.execute("SELECT COUNT(*) FROM entities").fetchone()[0]
        relations = c.execute("SELECT COUNT(*) FROM relations").fetchone()[0]
        types     = c.execute(
            "SELECT type, COUNT(*) FROM entities GROUP BY type"
        ).fetchall()
    return {
        "entities":  entities,
        "relations": relations,
        "by_type":   {r[0]: r[1] for r in types},
    }


def clear():
    with _conn() as c:
        c.execute("DELETE FROM relations")
        c.execute("DELETE FROM entities")
