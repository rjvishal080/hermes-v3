"""
agent/planner.py
─────────────────────────────────────────────────────────────────────────────
ReAct Planner — Reason + Act loop.

Standard chat:   User → RAG → LLM → Answer
Planner agent:   User → Plan → Tool calls → Synthesize → Answer → Reflect

The LLM decides:
  1. Do I need tools? (simple greetings → no)
  2. Which tools?     (exam question → get_attendance + get_goals + search_memory)
  3. What to do with results?
  4. Final answer

Format the LLM outputs as:
  THOUGHT: <reasoning about what to do>
  ACTION: {"tool": "name", "args": {...}}
  OBSERVATION: <tool result>
  ... (up to MAX_STEPS)
  ANSWER: <final response to user>

The planner streams the ANSWER part back to the user.
The THOUGHT/ACTION/OBSERVATION trace is stored for reflection.
"""

import json
import re
from typing import Generator

from agent.tools import execute_tool, TOOLS_SCHEMA

MAX_STEPS = 6   # max tool calls before forced answer

PLANNER_SYSTEM = """You are Hermes, a deeply personal AI assistant.
You have access to tools to look up information about the user.

Available tools:
{tools}

RULES:
1. For simple conversational messages (greetings, opinions), answer directly with ANSWER:
2. For questions about the user's life, ALWAYS use tools — never guess or recall from training
3. Use THOUGHT to reason about what you need
4. Use ACTION to call a tool (valid JSON)
5. Use OBSERVATION to receive the result (added by the system)
6. End with ANSWER — your response to the user
7. CRITICAL: Only state facts from OBSERVATION results. Never invent or hallucinate titles, names, or details not in tool output. If a tool returns exactly one movie, say exactly that one movie.
7. CRITICAL: Only state facts that appear in OBSERVATION results. Never invent titles, names, or details not in the tool output. If a tool returns one entry, report exactly that one entry.

Format EXACTLY like this:
THOUGHT: I need to check...
ACTION: {{"tool": "tool_name", "args": {{"key": "value"}}}}
OBSERVATION: <filled by system>
THOUGHT: Now I know...
ANSWER: <your response here>

PERSONAL CONTEXT:
{context}

Today: {today}
"""

NEEDS_TOOLS_SYSTEM = """You decide if a query needs tool lookups or can be answered conversationally.
Reply with ONLY "yes" or "no".
"yes" = needs personal data (memory, goals, grades, spending, events, attendance)
"no"  = general question, greeting, opinion, or coding help

Query: {query}"""


def _needs_tools(query: str) -> bool:
    """Fast check: does this query need tool calls?"""
    # Keywords that clearly need personal data lookup
    tool_keywords = [
        "movie", "anime", "watch", "read", "book", "game",
        "spend", "money", "cashiro", "finance", "transaction",
        "attendance", "cgpa", "grade", "course", "college",
        "goal", "milestone", "progress",
        "memory", "remember", "know about",
        "sleep", "health", "exercise",
        "screen time", "habit",
        "week", "month", "today", "recent", "so far",
        "tell me about", "what do you know", "what have i"
    ]
    q = query.lower()
    return any(kw in q for kw in tool_keywords)


def _parse_action(text: str) -> dict | None:
    """Extract tool call JSON from ACTION: line. Uses raw_decode to correctly
    handle nested braces in args (e.g. {"tool": "x", "args": {"type": "y"}}),
    which a naive non-greedy regex would truncate at the first inner '}'."""
    marker = "ACTION:"
    idx = text.find(marker)
    if idx == -1:
        return None
    start = text.find("{", idx)
    if start == -1:
        return None
    try:
        data, _ = json.JSONDecoder().raw_decode(text[start:])
        return data if "tool" in data else None
    except Exception:
        return None


def _extract_answer(text: str) -> str:
    """Extract the ANSWER: section."""
    match = re.search(r'ANSWER:\s*(.*)', text, re.DOTALL)
    if match:
        return match.group(1).strip()
    # Fallback: if no ANSWER: marker, return everything after last OBSERVATION
    parts = text.split("OBSERVATION:")
    return parts[-1].strip() if parts else text.strip()


def run_planner(
    user_message: str,
    session_id:   str,
    context:      str,
    history:      list[dict],
) -> Generator[str, None, dict]:
    """
    Run the ReAct planning loop.
    Yields tokens of the final answer.
    Returns trace dict when done.
    """
    import datetime
    from engine.llm import stream_generate, generate

    today   = datetime.date.today().isoformat()
    trace   = {"steps": [], "tools_used": [], "answer": ""}

    # Fast path: simple conversational messages skip the planner
    use_tools = _needs_tools(user_message)

    if not use_tools:
        # Direct answer — no tool calls
        system   = f"You are Hermes, a deeply personal AI.\n\nCONTEXT:\n{context}\n\nToday: {today}"
        messages = history + [{"role": "user", "content": user_message}]
        full = []
        for token in stream_generate(system, messages):
            full.append(token)
            yield token
        trace["answer"] = "".join(full)
        return trace

    # ReAct loop
    system   = PLANNER_SYSTEM.format(
        tools=TOOLS_SCHEMA, context=context, today=today
    )
    base_messages = history + [{"role": "user", "content": user_message}]

    # Build the ReAct conversation as a proper alternating message list.
    # IMPORTANT: OBSERVATION results go in their own "user" turn, never
    # appended inside the assistant's own turn. Burying a system-injected
    # OBSERVATION inside the assistant's turn causes this model to treat it
    # as a signal to emit an immediate stop token on the next generation
    # (confirmed via isolated testing — same prompt content, different only
    # in turn structure, went from 0 real tokens to a correct answer).
    react_messages = list(base_messages)
    final_answer = ""
    steps_taken = 0

    for step in range(MAX_STEPS):
        step_output = generate(system, react_messages, max_new_tokens=300, temperature=0.3)
        trace["steps"].append(step_output)
        steps_taken += 1

        action = _parse_action(step_output)

        if "ANSWER:" in step_output:
            final_answer = _extract_answer(step_output)
            break

        if action:
            tool_name = action.get("tool", "")
            tool_args = action.get("args", {})
            trace["tools_used"].append(tool_name)

            observation = execute_tool(tool_name, tool_args)
            if len(observation) > 1500:
                observation = observation[:1500] + "\n... (truncated)"

            # Assistant's THOUGHT/ACTION becomes its own turn; the result
            # comes back as a fresh user turn, mirroring normal chat structure.
            react_messages.append({"role": "assistant", "content": step_output})
            react_messages.append({
                "role": "user",
                "content": f"OBSERVATION: {observation}\n\nContinue with THOUGHT and then ANSWER."
            })
        else:
            # No tool call and no ANSWER — force a final answer on the next step.
            react_messages.append({"role": "assistant", "content": step_output})
            react_messages.append({
                "role": "user",
                "content": "Please give your final ANSWER now."
            })

    react_trace = "\n".join(trace["steps"])

    # Extract answer from trace and stream it directly
    answer = _extract_answer(react_trace)
    trace["answer"]      = answer
    trace["steps_taken"] = steps_taken

    # Stream the extracted answer character by character
    for char in answer:
        yield char

    return trace


def run_proactive_check(trigger: str) -> str:
    """
    Proactive agent run — triggered by scheduler, not user.
    Examples: "daily attendance check", "spending spike detected"
    Returns a notification message to surface to the user.
    """
    from engine.llm import generate
    from memory.manager import build_full_context

    context = build_full_context(trigger)
    system  = f"""You are Hermes running a proactive background check.
Trigger: {trigger}

Based on the user's data, generate a SHORT, actionable notification (1-2 sentences).
Only notify if there's something genuinely worth the user's attention.
If nothing notable, reply with SKIP.

USER CONTEXT:
{context}"""

    messages = [{"role": "user", "content": f"Run proactive check: {trigger}"}]
    try:
        result = generate(system, messages, max_new_tokens=100, temperature=0.4)
        if "SKIP" in result.upper():
            return ""
        return result.strip()
    except Exception as e:
        return f"Check failed: {e}"
