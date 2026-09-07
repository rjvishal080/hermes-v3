"""
engine/scheduler.py — v3
Adds consolidation pipeline to agentic tasks.
"""

import os
import datetime
import subprocess
from pathlib import Path

try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger
    HAS_SCHEDULER = True
except ImportError:
    HAS_SCHEDULER = False

DATA_DIR   = Path(os.getenv("HERMES_DATA_DIR", "./data"))
_scheduler = None


def notify(title: str, body: str, urgency: str = "normal"):
    try:
        subprocess.run(
            ["notify-send", f"Hermes: {title}", body,
             f"--urgency={urgency}", "--app-name=Hermes"],
            check=False, timeout=5,
        )
    except Exception:
        print(f"[Scheduler] {title}: {body}")


def task_attendance_check():
    try:
        from memory.manager import load_profile
        attendance = load_profile().get("academic", {}).get("attendance", {})
        low = [(s, float(v)) for s, v in attendance.items() if float(v) < 75]
        if low:
            low_str = ", ".join([f"{s}({v:.0f}%)" for s, v in low])
            notify("Low Attendance", f"Below 75%: {low_str}", urgency="critical")
    except Exception as e:
        print(f"[Scheduler] attendance_check error: {e}")


def task_goal_deadline_check():
    try:
        from memory.goals import get_deadline_alerts
        alerts = get_deadline_alerts()
        for alert in alerts:
            days = alert["days_left"]
            if days < 0:
                notify("Overdue Goal", f"{alert['title']} is overdue by {-days} days!", "critical")
            elif days <= 3:
                notify("Goal Deadline", f"{alert['title']} due in {days} days", "critical")
            elif days <= 7:
                notify("Goal Deadline", f"{alert['title']} due in {days} days", "normal")
    except Exception as e:
        print(f"[Scheduler] goal_deadline_check error: {e}")


def task_daily_consolidation():
    """Run at 2am — summarize yesterday."""
    try:
        from memory.consolidation import run_daily_consolidation
        yesterday = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
        result    = run_daily_consolidation(yesterday)
        if result:
            print(f"[Scheduler] Daily consolidation done for {yesterday}")
    except Exception as e:
        print(f"[Scheduler] daily_consolidation error: {e}")


def task_weekly_consolidation():
    """Run Sunday 1am — summarize last week."""
    try:
        from memory.consolidation import run_weekly_consolidation, run_life_extraction
        run_weekly_consolidation()
        facts = run_life_extraction()
        if facts:
            notify("Memory Updated", f"Weekly consolidation complete. {len(facts)} new facts learned.")
    except Exception as e:
        print(f"[Scheduler] weekly_consolidation error: {e}")


def task_reset_working_memory():
    """Reset working memory at midnight."""
    try:
        from memory.working import reset
        reset()
        print("[Scheduler] Working memory reset for new day")
    except Exception as e:
        print(f"[Scheduler] reset_working_memory error: {e}")


def task_portal_sync():
    try:
        creds_path = DATA_DIR / "portal_creds.json"
        if not creds_path.exists():
            return
        import json
        with open(creds_path) as f:
            creds = json.load(f)
        if not creds.get("portal_url"):
            return
        from connectors.portal_scraper import scrape_portal
        result = scrape_portal(
            creds["portal_url"], creds["username"],
            creds.get("password", ""), creds.get("college", "")
        )
        if result.get("success"):
            notify("Portal Synced", f"Updated {len(result.get('attendance', {}))} subjects.")
    except Exception as e:
        print(f"[Scheduler] portal_sync error: {e}")


def task_proactive_check():
    """Run planner proactively — surface insights without being asked."""
    try:
        from agent.planner import run_proactive_check
        triggers = [
            "daily attendance status and any alerts",
            "upcoming goal deadlines",
            "spending patterns this week",
        ]
        for trigger in triggers:
            msg = run_proactive_check(trigger)
            if msg:
                notify("Hermes Insight", msg[:100])
    except Exception as e:
        print(f"[Scheduler] proactive_check error: {e}")


def start_scheduler():
    global _scheduler
    if not HAS_SCHEDULER:
        print("[Scheduler] APScheduler not installed — pip install apscheduler")
        return

    _scheduler = BackgroundScheduler(timezone="Asia/Kolkata")

    _scheduler.add_job(task_attendance_check,    CronTrigger(hour=8,  minute=0),  id="attendance")
    _scheduler.add_job(task_goal_deadline_check, CronTrigger(hour=8,  minute=5),  id="goal_deadlines")
    _scheduler.add_job(task_proactive_check,     CronTrigger(hour=9,  minute=0),  id="proactive")
    _scheduler.add_job(task_portal_sync,         CronTrigger(hour=6,  minute=0),  id="portal_sync")
    _scheduler.add_job(task_daily_consolidation, CronTrigger(hour=2,  minute=0),  id="daily_consolidation")
    _scheduler.add_job(task_reset_working_memory,CronTrigger(hour=0,  minute=1),  id="reset_wm")
    _scheduler.add_job(task_weekly_consolidation,
                       CronTrigger(day_of_week="sun", hour=1, minute=0),          id="weekly_consolidation")

    _scheduler.start()
    print("[Scheduler] v3 started — 7 autonomous tasks registered")


def stop_scheduler():
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown()


def run_task_now(task_name: str) -> str:
    tasks = {
        "attendance_check":      task_attendance_check,
        "goal_deadline_check":   task_goal_deadline_check,
        "daily_consolidation":   task_daily_consolidation,
        "weekly_consolidation":  task_weekly_consolidation,
        "portal_sync":           task_portal_sync,
        "proactive_check":       task_proactive_check,
        "reset_working_memory":  task_reset_working_memory,
    }
    fn = tasks.get(task_name)
    if not fn:
        return f"Unknown task. Available: {list(tasks.keys())}"
    try:
        fn()
        return f"Task '{task_name}' completed"
    except Exception as e:
        return f"Task '{task_name}' failed: {e}"
