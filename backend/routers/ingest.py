"""
routers/ingest.py — v3
Data ingestion: Cashiro CSV, screen time, academic, health, PDF notes.
All ingested data flows into the appropriate memory types.
"""

import csv
import io
import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, UploadFile, File
from pydantic import BaseModel

from memory.manager import load_profile, save_profile
from memory import semantic, episodic, retrieval

router = APIRouter()


# ── Cashiro / Bank CSV ────────────────────────────────────────────────────────
@router.post("/cashiro")
async def ingest_cashiro(file: UploadFile = File(...)):
    content = await file.read()
    text    = content.decode("utf-8-sig")
    reader  = csv.DictReader(io.StringIO(text))

    stored     = 0
    monthly    = {}
    categories = {}
    high_spends = []

    for row in reader:
        date  = row.get("date") or row.get("Date") or row.get("DATE") or ""
        desc  = row.get("description") or row.get("Description") or row.get("narration") or row.get("Narration") or ""
        amt   = row.get("amount") or row.get("Amount") or row.get("debit") or row.get("Debit") or "0"
        cat   = row.get("category") or row.get("Category") or "Uncategorized"

        try:
            amount = abs(float(str(amt).replace(",", "").replace("₹", "")))
        except:
            amount = 0

        mem_text = f"Transaction on {date}: {desc} — ₹{amount:.0f} ({cat})"
        retrieval.add_to_collection(
            mem_text,
            metadata={"source": "cashiro", "date": date, "category": cat, "amount": amount},
            collection="finances",
        )
        stored += 1

        month = date[:7] if len(date) >= 7 else "unknown"
        monthly[month]    = monthly.get(month, 0) + amount
        categories[cat]   = categories.get(cat, 0) + amount
        if amount > 2000:
            high_spends.append({"desc": desc, "amount": amount, "date": date})

    # Update profile + semantic memory
    profile = load_profile()
    profile["finances"]["cashiro_linked"]  = True
    profile["finances"]["categories"]      = {k: round(v) for k, v in sorted(categories.items(), key=lambda x: -x[1])[:10]}
    profile["finances"]["monthly_totals"]  = {k: round(v) for k, v in sorted(monthly.items())[-6:]}
    save_profile(profile)

    # Semantic facts
    if categories:
        top_cat = max(categories, key=categories.get)
        semantic.set_fact("finance.top_category", top_cat, "finance", source="cashiro")
        semantic.set_fact("finance.cashiro_linked", "true", "finance", source="cashiro")
    if monthly:
        avg_monthly = sum(monthly.values()) / len(monthly)
        semantic.set_fact("finance.avg_monthly_spend", f"₹{avg_monthly:.0f}", "finance", source="cashiro")

    # Notable episode
    episodic.add_episode(
        summary=f"Cashiro data imported: {stored} transactions, top category: {max(categories, key=categories.get) if categories else 'N/A'}",
        category="finance", importance=3, source="cashiro",
    )

    return {"imported": stored, "months": len(monthly), "categories": len(categories), "high_spend_count": len(high_spends)}


# ── Screen time ───────────────────────────────────────────────────────────────
class ScreenTimeData(BaseModel):
    daily_avg_mins: int
    weekly_data:    Optional[dict] = {}
    top_apps:       Optional[dict] = {}
    date:           Optional[str] = ""


@router.post("/screentime")
def ingest_screentime(data: ScreenTimeData):
    profile = load_profile()
    profile["screen_time"]["daily_avg_mins"] = data.daily_avg_mins
    profile["screen_time"]["top_apps"]       = data.top_apps or {}
    save_profile(profile)

    date = data.date or datetime.date.today().isoformat()
    top_apps_str = ", ".join([f"{k}: {v}min" for k, v in (data.top_apps or {}).items()][:5])

    semantic.set_fact("health.screen_time_daily_avg", f"{data.daily_avg_mins} min", "health", source="screen_time")

    retrieval.add_to_collection(
        f"Screen time ({date}): {data.daily_avg_mins} min/day. Top: {top_apps_str}",
        metadata={"source": "screen_time", "date": date},
    )

    if data.daily_avg_mins > 360:
        episodic.add_episode(
            summary=f"High screen time: {data.daily_avg_mins} min/day",
            category="health", emotion="negative", importance=3,
            date=date, source="screen_time",
        )

    return {"daily_avg": data.daily_avg_mins}


# ── Academic ──────────────────────────────────────────────────────────────────
class AcademicData(BaseModel):
    college:        Optional[str] = ""
    semester:       Optional[str] = ""
    cgpa:           Optional[str] = ""
    courses:        Optional[list[str]] = []
    attendance:     Optional[dict] = {}
    grades:         Optional[dict] = {}
    portal_url:     Optional[str] = ""


@router.post("/academic")
def ingest_academic(data: AcademicData):
    profile = load_profile()
    acad    = profile["academic"]
    if data.college:    acad["college"]    = data.college
    if data.semester:   acad["semester"]   = data.semester
    if data.cgpa:       acad["cgpa"]       = data.cgpa
    if data.courses:    acad["courses"]    = data.courses
    if data.attendance: acad["attendance"] = data.attendance
    if data.grades:     acad["grades"]     = data.grades
    if data.portal_url: acad["portal_url"] = data.portal_url
    save_profile(profile)

    # Semantic facts
    if data.cgpa:
        semantic.set_fact("academic.cgpa", data.cgpa, "academic", source="manual")
    if data.college:
        semantic.set_fact("academic.college", data.college, "academic", source="manual")
    if data.semester:
        semantic.set_fact("academic.semester", data.semester, "academic", source="manual")
    if data.courses:
        semantic.set_fact("academic.current_courses", ", ".join(data.courses), "academic", source="manual")

    # Graph relationships
    from memory import graph
    if data.college:
        graph.add_triple("User", "studies_at", data.college, "person", "place", source="academic")
    for course in (data.courses or []):
        graph.add_triple("User", "taking_course", course, "person", "course", source="academic")

    # Attendance → semantic + episodes
    if data.attendance:
        low = [(s, float(v)) for s, v in data.attendance.items() if float(v) < 75]
        if low:
            low_str = ", ".join([f"{s}({v:.0f}%)" for s, v in low])
            semantic.set_fact("academic.low_attendance_subjects", low_str, "academic",
                              confidence=1.0, source="manual")
            episodic.add_episode(
                summary=f"Low attendance warning: {low_str}",
                category="academic", emotion="negative", importance=4,
                source="academic",
            )

    # Grades → retrieval collection
    if data.grades:
        grade_str = ", ".join([f"{s}: {g}" for s, g in data.grades.items()])
        retrieval.add_to_collection(
            f"Grades: {grade_str}",
            metadata={"source": "academic", "type": "grades"},
            collection="academic",
        )

    return {"message": "Academic data stored"}


# ── Health ────────────────────────────────────────────────────────────────────
class HealthData(BaseModel):
    sleep_avg_hrs:       Optional[float] = None
    exercise_days_week:  Optional[int] = None
    weight_kg:           Optional[float] = None
    notes:               Optional[str] = ""
    date:                Optional[str] = ""


@router.post("/health")
def ingest_health(data: HealthData):
    profile = load_profile()
    health  = profile["health"]
    if data.sleep_avg_hrs is not None:       health["sleep_avg_hrs"]      = data.sleep_avg_hrs
    if data.exercise_days_week is not None:  health["exercise_days_week"] = data.exercise_days_week
    if data.weight_kg is not None:           health["weight_kg"]          = data.weight_kg
    if data.notes:                           health["notes"]              = data.notes
    save_profile(profile)

    date = data.date or datetime.date.today().isoformat()

    if data.sleep_avg_hrs is not None:
        semantic.set_fact("health.sleep_avg_hrs", f"{data.sleep_avg_hrs}h", "health", source="manual")
    if data.exercise_days_week is not None:
        semantic.set_fact("health.exercise_days_week", str(data.exercise_days_week), "health", source="manual")
    if data.weight_kg is not None:
        semantic.set_fact("health.weight_kg", str(data.weight_kg), "health", source="manual")

    parts = []
    if data.sleep_avg_hrs:      parts.append(f"sleep {data.sleep_avg_hrs}h")
    if data.exercise_days_week: parts.append(f"exercise {data.exercise_days_week}d/week")
    if data.weight_kg:          parts.append(f"weight {data.weight_kg}kg")
    if data.notes:              parts.append(data.notes)
    if parts:
        retrieval.add_to_collection(
            f"Health log ({date}): {', '.join(parts)}",
            metadata={"source": "health", "date": date},
        )

    return {"message": "Health data stored"}


# ── Life log ──────────────────────────────────────────────────────────────────
class LogEntry(BaseModel):
    content:  str
    category: str = "general"
    date:     Optional[str] = ""
    emotion:  str = "neutral"
    importance: int = 3


@router.post("/log")
def manual_log(entry: LogEntry):
    date = entry.date or datetime.date.today().isoformat()

    ep_id = episodic.add_episode(
        summary=entry.content[:200],
        detail=entry.content,
        date=date,
        category=entry.category,
        emotion=entry.emotion,
        importance=entry.importance,
        source="manual",
    )
    retrieval.add_to_collection(
        f"[{entry.category.upper()} — {date}] {entry.content}",
        metadata={"source": "manual_log", "category": entry.category, "date": date},
        doc_id=ep_id,
    )
    return {"id": ep_id, "message": "Entry logged"}


# ── PDF ingestion ─────────────────────────────────────────────────────────────
@router.post("/pdf")
async def ingest_pdf(file: UploadFile = File(...), title: str = "", subject: str = "general"):
    try:
        import fitz  # pymupdf
    except ImportError:
        return {"error": "pymupdf not installed. Run: pip install pymupdf"}

    content = await file.read()
    doc     = fitz.open(stream=content, filetype="pdf")
    pages   = []

    for page_num in range(len(doc)):
        page_text = doc[page_num].get_text()
        if page_text.strip():
            pages.append(page_text.strip())

    doc.close()

    if not pages:
        return {"error": "No text extracted from PDF"}

    # Chunk by page and store in documents collection
    stored = 0
    file_title = title or file.filename or "PDF"

    for i, page_text in enumerate(pages):
        # Split long pages into chunks
        chunks = [page_text[j:j+800] for j in range(0, len(page_text), 600)]  # 200 overlap
        for chunk in chunks:
            if len(chunk.strip()) < 50:
                continue
            retrieval.add_to_collection(
                chunk,
                metadata={
                    "source":   "pdf",
                    "title":    file_title,
                    "subject":  subject,
                    "page":     i + 1,
                    "filename": file.filename or "",
                },
                collection="documents",
            )
            stored += 1

    # Semantic fact
    semantic.set_fact(
        f"documents.{file_title.lower().replace(' ', '_')}",
        f"PDF ingested: {len(pages)} pages, subject: {subject}",
        "technical", source="pdf",
    )

    episodic.add_episode(
        summary=f"Ingested PDF: {file_title} ({len(pages)} pages, {subject})",
        category="academic", importance=2, source="pdf",
    )

    return {"pages": len(pages), "chunks_stored": stored, "title": file_title}
