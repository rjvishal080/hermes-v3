"""
routers/chat.py — v3
Handles both regular chat (ReAct planner) and media logging (@trigger flow).
"""

import json
import uuid
import datetime
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional

from memory.manager import (
    save_message, load_history, list_sessions,
    build_full_context, extract_and_store_all,
    load_profile, generate_weekly_reflection,
)
from agent.planner import run_planner
from media.conversation import (
    detect_trigger, extract_title_from_text,
    run_media_conversation_turn, extract_entry_from_conversation,
    get_next_question,
)

router = APIRouter()

# In-memory media session state
# {session_id: {type, title, initial_text, gathered, turn_count}}
_media_sessions: dict[str, dict] = {}


class ChatRequest(BaseModel):
    message:    str
    session_id: Optional[str] = None


@router.post("")
def chat(req: ChatRequest):
    session_id = req.session_id or str(uuid.uuid4())
    profile    = load_profile()
    user_name  = profile.get("name", "User")

    history    = load_history(session_id, last_n=20)
    save_message(session_id, "user", req.message)

    # ── Check if this is a media trigger ─────────────────────────────────────
    trigger = detect_trigger(req.message)
    if trigger:
        # Start new media session
        title = extract_title_from_text(trigger["initial_text"], trigger["type"])
        _media_sessions[session_id] = {
            "type":         trigger["type"],
            "title":        title,
            "initial_text": trigger["initial_text"],
            "gathered":     {},
            "turn_count":   0,
        }

    # ── Check if we're mid media conversation ─────────────────────────────────
    if session_id in _media_sessions:
        media_state = _media_sessions[session_id]

        def generate_media():
            import asyncio
            loop = asyncio.new_event_loop()
            try:
                response, updated_state, is_complete = loop.run_until_complete(
                    run_media_conversation_turn(
                        session_id, req.message, media_state, history
                    )
                )
            finally:
                loop.close()

            _media_sessions[session_id] = updated_state

            # Stream response token by token (simulate)
            for token in response:
                yield f"data: {json.dumps({'token': token, 'session_id': session_id})}\n\n"

            save_message(session_id, "assistant", response)

            if is_complete:
                # Extract and store the full entry
                full_history = load_history(session_id, last_n=30)
                entry_data   = extract_entry_from_conversation(
                    updated_state["title"],
                    updated_state["type"],
                    full_history,
                    updated_state["gathered"],
                )

                # Store the entry
                from media.entry import create_entry
                eid = create_entry(
                    title              = entry_data.get("title", updated_state["title"]),
                    media_type         = updated_state["type"],
                    creator            = entry_data.get("creator", ""),
                    year               = entry_data.get("year", ""),
                    status             = "completed",
                    rating             = entry_data.get("rating"),
                    rating_raw         = entry_data.get("rating_raw", ""),
                    mood_when_consumed = entry_data.get("mood_when_consumed", ""),
                    reaction           = entry_data.get("reaction", ""),
                    interpretation     = entry_data.get("interpretation", ""),
                    what_worked        = entry_data.get("what_worked", []),
                    what_didnt         = entry_data.get("what_didnt", []),
                    themes_noticed     = entry_data.get("themes_noticed", []),
                    memorable_moments  = entry_data.get("memorable_moments", []),
                    quotes             = entry_data.get("quotes", []),
                    rewatch            = entry_data.get("rewatch", "maybe"),
                    recommendation     = entry_data.get("recommendation", ""),
                    recommend_to       = entry_data.get("recommend_to", ""),
                    personality_signals= entry_data.get("personality_signals", []),
                    session_id         = session_id,
                )

                # Push personality signals to procedural memory
                from memory.procedural import set_preference
                for signal in entry_data.get("personality_signals", []):
                    set_preference(
                        f"Media insight: {signal}",
                        category="personality",
                        strength=0.8,
                        source="media_conversation",
                    )

                # Push to vector store for semantic search
                from memory.retrieval import add_to_collection
                mem_text = (
                    f"[{updated_state['type'].upper()}] {entry_data.get('title', updated_state['title'])}"
                    f" — {entry_data.get('reaction', '')} "
                    f"Interpretation: {entry_data.get('interpretation', '')}"
                )
                add_to_collection(
                    mem_text,
                    metadata={"source": "media", "type": updated_state["type"],
                              "entry_id": eid, "rating": entry_data.get("rating")},
                    collection="memories",
                )

                # Check if pattern analysis should run
                from media.entry import get_stats
                stats = get_stats()
                if stats["total"] % 10 == 0 and stats["total"] > 0:
                    try:
                        from media.patterns import run_pattern_analysis
                        run_pattern_analysis()
                    except Exception as e:
                        print(f"[Media] Pattern analysis failed: {e}")

                # Clean up session
                del _media_sessions[session_id]

                sig_count = len(entry_data.get("personality_signals", []))
                yield f"data: {json.dumps({'done': True, 'session_id': session_id, 'media_logged': True, 'entry_id': eid, 'signals': sig_count})}\n\n"
            else:
                yield f"data: {json.dumps({'done': True, 'session_id': session_id, 'media_in_progress': True})}\n\n"

        return StreamingResponse(
            generate_media(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Session-Id": session_id},
        )

    # ── Regular chat — ReAct planner ──────────────────────────────────────────
    context = build_full_context(req.message)

    def generate():
        full_answer = []
        try:
            for token in run_planner(req.message, session_id, context, history):
                full_answer.append(token)
                yield f"data: {json.dumps({'token': token, 'session_id': session_id})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e), 'session_id': session_id})}\n\n"
            return

        final = "".join(full_answer)
        save_message(session_id, "assistant", final)

        counts = extract_and_store_all(session_id, user_name)
        yield f"data: {json.dumps({'done': True, 'session_id': session_id, 'extracted': counts})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Session-Id": session_id},
    )


@router.get("/sessions")
def get_sessions():
    return list_sessions()


@router.get("/history/{session_id}")
def get_history(session_id: str):
    return load_history(session_id, last_n=100)


@router.post("/reflect")
def weekly_reflect():
    reflection = generate_weekly_reflection()
    return {"reflection": reflection}


@router.get("/model")
def model_info():
    from engine.llm import get_model_info
    return get_model_info()
