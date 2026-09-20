"""
database.py
SQLite storage for the full two-role system: users, job postings, applications.
"""

import sqlite3
import json
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "resume_iq.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('hr', 'candidate')),
            company TEXT,
            resume_text TEXT,
            resume_filename TEXT,
            created_at TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS job_postings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hr_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'open',
            created_at TEXT NOT NULL,
            FOREIGN KEY (hr_id) REFERENCES users(id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER NOT NULL,
            candidate_id INTEGER NOT NULL,
            score REAL NOT NULL,
            matched_skills TEXT NOT NULL,
            missing_skills TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'review',
            notes TEXT DEFAULT '',
            applied_at TEXT NOT NULL,
            FOREIGN KEY (job_id) REFERENCES job_postings(id),
            FOREIGN KEY (candidate_id) REFERENCES users(id),
            UNIQUE(job_id, candidate_id)
        )
    """)

    # Migration safety net: if an older DB already has the applications table
    # without a notes column, add it. Harmless no-op on a fresh DB.
    cur.execute("PRAGMA table_info(applications)")
    existing_cols = [row[1] for row in cur.fetchall()]
    if "notes" not in existing_cols:
        cur.execute("ALTER TABLE applications ADD COLUMN notes TEXT DEFAULT ''")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            candidate_id INTEGER NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('user', 'model')),
            content TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (candidate_id) REFERENCES users(id)
        )
    """)

    conn.commit()
    conn.close()


# ---------- Users ----------

def create_user(name, email, password_hash, role, company=None) -> int:
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO users (name, email, password_hash, role, company, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (name, email, password_hash, role, company, datetime.utcnow().isoformat()),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_user_by_email(email: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE email = ?", (email,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_by_id(user_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def update_candidate_resume(user_id: int, resume_text: str, resume_filename: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "UPDATE users SET resume_text = ?, resume_filename = ? WHERE id = ?",
        (resume_text, resume_filename, user_id),
    )
    conn.commit()
    conn.close()


# ---------- Job postings ----------

def create_job(hr_id: int, title: str, description: str) -> int:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO job_postings (hr_id, title, description, status, created_at) VALUES (?, ?, ?, 'open', ?)",
        (hr_id, title, description, datetime.utcnow().isoformat()),
    )
    conn.commit()
    job_id = cur.lastrowid
    conn.close()
    return job_id


def get_jobs_by_hr(hr_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT j.*, (SELECT COUNT(*) FROM applications a WHERE a.job_id = j.id) AS applicant_count
        FROM job_postings j WHERE j.hr_id = ? ORDER BY j.created_at DESC
    """, (hr_id,))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_open_jobs():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT j.*, u.company, u.name AS hr_name
        FROM job_postings j JOIN users u ON j.hr_id = u.id
        WHERE j.status = 'open' ORDER BY j.created_at DESC
    """)
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_job_by_id(job_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM job_postings WHERE id = ?", (job_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


# ---------- Applications ----------

def create_application(job_id, candidate_id, score, matched_skills, missing_skills) -> int:
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO applications (job_id, candidate_id, score, matched_skills, missing_skills, status, applied_at)
            VALUES (?, ?, ?, ?, ?, 'review', ?)
        """, (job_id, candidate_id, score, json.dumps(matched_skills), json.dumps(missing_skills),
              datetime.utcnow().isoformat()))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_applications_for_job(job_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT a.*, u.name AS candidate_name, u.email AS candidate_email
        FROM applications a JOIN users u ON a.candidate_id = u.id
        WHERE a.job_id = ? ORDER BY a.score DESC
    """, (job_id,))
    rows = cur.fetchall()
    conn.close()
    results = []
    for r in rows:
        d = dict(r)
        d["matched_skills"] = json.loads(d["matched_skills"])
        d["missing_skills"] = json.loads(d["missing_skills"])
        results.append(d)
    return results


def get_applications_for_candidate(candidate_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT a.*, j.title AS job_title, u.company
        FROM applications a
        JOIN job_postings j ON a.job_id = j.id
        JOIN users u ON j.hr_id = u.id
        WHERE a.candidate_id = ? ORDER BY a.applied_at DESC
    """, (candidate_id,))
    rows = cur.fetchall()
    conn.close()
    results = []
    for r in rows:
        d = dict(r)
        d["matched_skills"] = json.loads(d["matched_skills"])
        d["missing_skills"] = json.loads(d["missing_skills"])
        results.append(d)
    return results


def get_application_by_job_and_candidate(job_id: int, candidate_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM applications WHERE job_id = ? AND candidate_id = ?", (job_id, candidate_id))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def update_application_status(application_id: int, status: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE applications SET status = ? WHERE id = ?", (status, application_id))
    conn.commit()
    conn.close()


def update_application_notes(application_id: int, notes: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE applications SET notes = ? WHERE id = ?", (notes, application_id))
    conn.commit()
    conn.close()


def update_job_status(job_id: int, status: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE job_postings SET status = ? WHERE id = ?", (status, job_id))
    conn.commit()
    conn.close()


def get_application_owner_job(application_id: int):
    """Returns the hr_id who owns the job this application belongs to (for permission checks)."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT j.hr_id FROM applications a JOIN job_postings j ON a.job_id = j.id WHERE a.id = ?
    """, (application_id,))
    row = cur.fetchone()
    conn.close()
    return row["hr_id"] if row else None


# ---------- Analytics ----------

def get_hr_analytics(hr_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT a.score, a.missing_skills FROM applications a
        JOIN job_postings j ON a.job_id = j.id WHERE j.hr_id = ?
    """, (hr_id,))
    rows = cur.fetchall()
    conn.close()

    scores = [r["score"] for r in rows]
    skill_counts = {}
    for r in rows:
        for skill in json.loads(r["missing_skills"]):
            skill_counts[skill] = skill_counts.get(skill, 0) + 1

    buckets = {"0-20": 0, "21-40": 0, "41-60": 0, "61-80": 0, "81-100": 0}
    for s in scores:
        if s <= 20: buckets["0-20"] += 1
        elif s <= 40: buckets["21-40"] += 1
        elif s <= 60: buckets["41-60"] += 1
        elif s <= 80: buckets["61-80"] += 1
        else: buckets["81-100"] += 1

    top_missing = sorted(skill_counts.items(), key=lambda x: x[1], reverse=True)[:5]

    return {
        "total_applicants": len(scores),
        "avg_score": round(sum(scores) / len(scores), 2) if scores else 0,
        "score_distribution": buckets,
        "top_missing_skills": [{"skill": k, "count": v} for k, v in top_missing],
    }


def get_candidate_feedback(candidate_id: int):
    """Aggregate missing skills across all of a candidate's applications."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT missing_skills, matched_skills FROM applications WHERE candidate_id = ?", (candidate_id,))
    rows = cur.fetchall()
    conn.close()

    missing_counts = {}
    matched_set = set()
    for r in rows:
        for skill in json.loads(r["missing_skills"]):
            missing_counts[skill] = missing_counts.get(skill, 0) + 1
        for skill in json.loads(r["matched_skills"]):
            matched_set.add(skill)

    top_missing = sorted(missing_counts.items(), key=lambda x: x[1], reverse=True)
    return {
        "strong_skills": sorted(matched_set),
        "suggested_skills": [{"skill": k, "appears_in_n_jobs": v} for k, v in top_missing],
    }


# ---------- Chat (candidate chatbot) ----------

def save_chat_message(candidate_id: int, role: str, content: str):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO chat_messages (candidate_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (candidate_id, role, content, datetime.utcnow().isoformat()),
        )
        conn.commit()
    finally:
        conn.close()


def get_chat_history(candidate_id: int, limit: int = 20):
    """Returns the most recent `limit` messages, oldest first (ready for the API)."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT role, content, created_at FROM chat_messages WHERE candidate_id = ? ORDER BY id DESC LIMIT ?",
        (candidate_id, limit),
    )
    rows = cur.fetchall()
    conn.close()
    return [{"role": r["role"], "content": r["content"], "created_at": r["created_at"]} for r in reversed(rows)]


def clear_chat_history(candidate_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM chat_messages WHERE candidate_id = ?", (candidate_id,))
    conn.commit()
    conn.close()
