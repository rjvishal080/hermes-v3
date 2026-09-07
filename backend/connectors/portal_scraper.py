"""
connectors/portal_scraper.py
─────────────────────────────────────────────────────────────────────────────
College portal scraper.
Handles most Indian college ERP systems (PSG, VTU, Anna University affiliates).
Uses requests.Session() for cookie-based auth — no Selenium needed for most portals.

Supported patterns:
  - Generic table scraper (works on most portals)
  - SJIT / similar ERP format
  - Manual data entry fallback (always works)

Usage:
  python connectors/portal_scraper.py --url https://erp.college.edu --user ID --pass PASS
  or call scrape_portal() from ingest.py
"""

import os
import re
import sys
import argparse
import json
from pathlib import Path
from typing import Optional

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("Install: pip install requests beautifulsoup4")
    sys.exit(1)

sys.path.insert(0, str(Path(__file__).parent.parent))
from memory.manager import add_memory, update_profile_field, load_profile, save_profile


# ── Generic scraper ───────────────────────────────────────────────────────────

def make_session(portal_url: str, username: str, password: str) -> Optional[requests.Session]:
    """
    Attempt login to a portal. Tries common ERP login patterns.
    Returns authenticated session or None if failed.
    """
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    })

    # Pattern 1: Form POST to /login or /index.php
    login_endpoints = [
        portal_url.rstrip("/") + "/login",
        portal_url.rstrip("/") + "/index.php",
        portal_url.rstrip("/") + "/student/login",
        portal_url,
    ]

    common_field_names = [
        # (username_field, password_field)
        ("username", "password"),
        ("user", "pass"),
        ("loginid", "password"),
        ("regno", "dob"),
        ("rollno", "password"),
        ("email", "password"),
        ("userid", "passwd"),
    ]

    for endpoint in login_endpoints:
        try:
            resp = s.get(endpoint, timeout=10)
            if resp.status_code != 200:
                continue

            soup = BeautifulSoup(resp.text, "html.parser")
            form = soup.find("form")
            if not form:
                continue

            # Try to find login fields in the actual form
            inputs = {inp.get("name", ""): inp.get("value", "")
                      for inp in form.find_all("input") if inp.get("name")}

            # Find username and password fields by type/name hints
            user_field = None
            pass_field  = None
            for inp in form.find_all("input"):
                name = (inp.get("name") or "").lower()
                typ  = (inp.get("type") or "text").lower()
                if typ == "password":
                    pass_field = inp.get("name")
                elif any(h in name for h in ["user", "login", "regno", "roll", "id", "email"]):
                    user_field = inp.get("name")

            if user_field and pass_field:
                payload = dict(inputs)
                payload[user_field] = username
                payload[pass_field]  = password

                action = form.get("action") or endpoint
                if not action.startswith("http"):
                    from urllib.parse import urljoin
                    action = urljoin(endpoint, action)

                login_resp = s.post(action, data=payload, timeout=10)

                # Check if logged in (look for logout link or student name)
                if any(kw in login_resp.text.lower() for kw in
                       ["logout", "sign out", "welcome", "dashboard", "profile"]):
                    print(f"[Portal] Login successful at {action}")
                    return s

        except Exception as e:
            print(f"[Portal] Login attempt failed at {endpoint}: {e}")
            continue

    print("[Portal] Could not auto-login. Try manual data entry in the Data tab.")
    return None


def scrape_attendance(session: requests.Session, portal_url: str) -> dict:
    """Scrape attendance table. Returns {subject: percentage}"""
    attendance = {}
    search_paths = [
        "/student/attendance",
        "/attendance",
        "/student/view_attendance",
        "/academics/attendance",
    ]

    for path in search_paths:
        try:
            url  = portal_url.rstrip("/") + path
            resp = session.get(url, timeout=10)
            if resp.status_code != 200:
                continue

            soup = BeautifulSoup(resp.text, "html.parser")

            # Find tables with attendance-like headers
            for table in soup.find_all("table"):
                headers = [th.get_text(strip=True).lower() for th in table.find_all("th")]
                has_subject  = any("subject" in h or "course" in h for h in headers)
                has_percent  = any("%" in h or "percent" in h or "attend" in h for h in headers)

                if has_subject or has_percent:
                    rows = table.find_all("tr")[1:]  # skip header
                    for row in rows:
                        cells = [td.get_text(strip=True) for td in row.find_all("td")]
                        if len(cells) >= 2:
                            # Heuristic: subject name usually in first 2 cols, percentage in last few
                            subject = cells[0] if len(cells[0]) > 2 else cells[1]
                            # Find a percentage-like value
                            for cell in reversed(cells):
                                val = cell.replace("%", "").strip()
                                try:
                                    pct = float(val)
                                    if 0 <= pct <= 100:
                                        attendance[subject] = pct
                                        break
                                except ValueError:
                                    continue

                if attendance:
                    print(f"[Portal] Found {len(attendance)} subjects' attendance at {path}")
                    return attendance

        except Exception as e:
            print(f"[Portal] Attendance scrape failed at {path}: {e}")
            continue

    return attendance


def scrape_grades(session: requests.Session, portal_url: str) -> dict:
    """Scrape grades/marks. Returns {subject: grade_or_marks}"""
    grades = {}
    search_paths = [
        "/student/grades",
        "/student/marks",
        "/academics/grades",
        "/results",
    ]

    for path in search_paths:
        try:
            url  = portal_url.rstrip("/") + path
            resp = session.get(url, timeout=10)
            if resp.status_code != 200:
                continue

            soup = BeautifulSoup(resp.text, "html.parser")
            for table in soup.find_all("table"):
                headers = [th.get_text(strip=True).lower() for th in table.find_all("th")]
                if any("grade" in h or "mark" in h or "score" in h for h in headers):
                    rows = table.find_all("tr")[1:]
                    for row in rows:
                        cells = [td.get_text(strip=True) for td in row.find_all("td")]
                        if len(cells) >= 2:
                            subject = cells[0] if len(cells[0]) > 2 else cells[1]
                            grade   = cells[-1]
                            if grade and subject:
                                grades[subject] = grade

                if grades:
                    return grades

        except Exception as e:
            continue

    return grades


def scrape_cgpa(session: requests.Session, portal_url: str) -> Optional[str]:
    """Scrape CGPA from profile/academic page."""
    search_paths = ["/student/profile", "/student/academic", "/profile", "/dashboard"]
    for path in search_paths:
        try:
            resp = session.get(portal_url.rstrip("/") + path, timeout=10)
            text = resp.text
            # Look for CGPA pattern: number between 0 and 10 near the word CGPA
            match = re.search(r"cgpa[:\s]*([0-9]\.[0-9]{1,2})", text, re.IGNORECASE)
            if match:
                return match.group(1)
        except:
            continue
    return None


# ── Main scrape function ──────────────────────────────────────────────────────

def scrape_portal(
    portal_url: str,
    username: str,
    password: str,
    college_name: str = "",
) -> dict:
    """
    Full portal scrape: login → attendance → grades → cgpa → store all.
    Returns summary dict.
    """
    session = make_session(portal_url, username, password)
    result  = {"success": False, "attendance": {}, "grades": {}, "cgpa": None}

    if session is None:
        return result

    print("[Portal] Scraping attendance...")
    attendance = scrape_attendance(session, portal_url)
    result["attendance"] = attendance

    print("[Portal] Scraping grades...")
    grades = scrape_grades(session, portal_url)
    result["grades"] = grades

    print("[Portal] Scraping CGPA...")
    cgpa = scrape_cgpa(session, portal_url)
    result["cgpa"] = cgpa

    # Store in profile + ChromaDB
    profile = load_profile()
    if college_name:
        profile["academic"]["college"] = college_name
    if attendance:
        profile["academic"]["attendance"] = {k: str(v) for k, v in attendance.items()}
    if grades:
        profile["academic"]["grades"] = grades
    if cgpa:
        profile["academic"]["cgpa"] = cgpa
    save_profile(profile)

    # Store as memories
    if attendance:
        low = [(s, v) for s, v in attendance.items() if float(v) < 75]
        att_str = ", ".join([f"{s}: {v}%" for s, v in list(attendance.items())[:8]])
        add_memory(f"Attendance from portal: {att_str}", metadata={"source": "portal"})
        if low:
            low_str = ", ".join([f"{s} ({v}%)" for s, v in low])
            add_memory(f"Low attendance warning: {low_str} — below 75%",
                       metadata={"source": "portal", "type": "alert"})

    if grades:
        grade_str = ", ".join([f"{s}: {g}" for s, g in list(grades.items())[:8]])
        add_memory(f"Grades from portal: {grade_str}", metadata={"source": "portal"})

    if cgpa:
        add_memory(f"CGPA from portal: {cgpa}", metadata={"source": "portal"})

    result["success"] = True
    print(f"[Portal] Done — {len(attendance)} subjects, {len(grades)} grades, CGPA: {cgpa}")
    return result


# ── CLI ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape college portal data into Hermes")
    parser.add_argument("--url",     required=True,  help="Portal base URL")
    parser.add_argument("--user",    required=True,  help="Username / Register number")
    parser.add_argument("--pass",    dest="password", required=True, help="Password")
    parser.add_argument("--college", default="",     help="College name")
    args = parser.parse_args()

    result = scrape_portal(args.url, args.user, args.password, args.college)
    print(json.dumps(result, indent=2))
