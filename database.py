"""
database.py
Lightweight SQLite data layer for the recruitment automation app.
No ORM needed at this scale - plain sqlite3 keeps it dependency-free.
"""
import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "app.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS candidates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            role TEXT,
            department TEXT,
            salary TEXT,
            joining_date TEXT,
            doc_type TEXT DEFAULT 'offer_letter',
            status TEXT DEFAULT 'pending',
            document_path TEXT,
            last_sent_at TEXT,
            error_message TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            kind TEXT NOT NULL,  -- 'document' or 'email'
            subject TEXT,        -- only for email templates
            body TEXT NOT NULL,  -- merge-field text, {{field}} syntax
            is_default INTEGER DEFAULT 0
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS send_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            candidate_id INTEGER NOT NULL,
            action TEXT NOT NULL,      -- 'generate' or 'send'
            status TEXT NOT NULL,      -- 'success' or 'failed'
            detail TEXT,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (candidate_id) REFERENCES candidates (id)
        )
    """)

    conn.commit()

    # Seed default templates if none exist yet
    cur.execute("SELECT COUNT(*) as c FROM templates")
    if cur.fetchone()["c"] == 0:
        cur.execute("""
            INSERT INTO templates (name, kind, subject, body, is_default)
            VALUES (?, ?, ?, ?, 1)
        """, (
            "Standard Offer Letter", "document", None,
            (
                "OFFER OF EMPLOYMENT\n\n"
                "Date: {{today}}\n\n"
                "Dear {{name}},\n\n"
                "We are pleased to offer you the position of {{role}} in the "
                "{{department}} department at our organization. Your annual "
                "compensation will be {{salary}}, and your expected joining "
                "date is {{joining_date}}.\n\n"
                "We are excited about the possibility of you joining our team "
                "and contributing your skills and experience. Please review "
                "the terms of this offer and confirm your acceptance by "
                "replying to this email.\n\n"
                "We look forward to welcoming you aboard.\n\n"
                "Sincerely,\n"
                "HR Team"
            )
        ))
        cur.execute("""
            INSERT INTO templates (name, kind, subject, body, is_default)
            VALUES (?, ?, ?, ?, 1)
        """, (
            "Standard Offer Email", "email",
            "Your Offer Letter - {{role}} Position",
            (
                "Hi {{name}},\n\n"
                "Congratulations! We are delighted to offer you the position "
                "of {{role}} in the {{department}} team.\n\n"
                "Please find your offer letter attached, with full details "
                "on compensation and your expected joining date of "
                "{{joining_date}}.\n\n"
                "Kindly review the attachment and reply to confirm your "
                "acceptance. Let us know if you have any questions.\n\n"
                "Welcome aboard,\n"
                "HR Team"
            )
        ))
        conn.commit()

    conn.close()


# ---------- Candidate operations ----------

def add_candidate(name, email, role, department, salary, joining_date, doc_type="offer_letter"):
    conn = get_conn()
    cur = conn.execute("""
        INSERT INTO candidates (name, email, role, department, salary, joining_date, doc_type)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (name, email, role, department, salary, joining_date, doc_type))
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return new_id


def bulk_add_candidates(rows):
    """rows: list of dicts with keys name,email,role,department,salary,joining_date"""
    conn = get_conn()
    for r in rows:
        conn.execute("""
            INSERT INTO candidates (name, email, role, department, salary, joining_date, doc_type)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            r.get("name", "").strip(),
            r.get("email", "").strip(),
            r.get("role", "").strip(),
            r.get("department", "").strip(),
            r.get("salary", "").strip(),
            r.get("joining_date", "").strip(),
            r.get("doc_type", "offer_letter").strip() or "offer_letter",
        ))
    conn.commit()
    conn.close()


def get_candidates(status=None):
    conn = get_conn()
    if status and status != "all":
        rows = conn.execute(
            "SELECT * FROM candidates WHERE status = ? ORDER BY id DESC", (status,)
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM candidates ORDER BY id DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_candidate(candidate_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def update_candidate_status(candidate_id, status, document_path=None, error_message=None):
    conn = get_conn()
    if status == "sent":
        conn.execute("""
            UPDATE candidates
            SET status = ?, document_path = COALESCE(?, document_path),
                last_sent_at = ?, error_message = NULL
            WHERE id = ?
        """, (status, document_path, datetime.now().isoformat(timespec="seconds"), candidate_id))
    elif status == "failed":
        conn.execute("""
            UPDATE candidates SET status = ?, error_message = ? WHERE id = ?
        """, (status, error_message, candidate_id))
    else:
        conn.execute("""
            UPDATE candidates
            SET status = ?, document_path = COALESCE(?, document_path)
            WHERE id = ?
        """, (status, document_path, candidate_id))
    conn.commit()
    conn.close()


def delete_candidate(candidate_id):
    conn = get_conn()
    conn.execute("DELETE FROM candidates WHERE id = ?", (candidate_id,))
    conn.execute("DELETE FROM send_log WHERE candidate_id = ?", (candidate_id,))
    conn.commit()
    conn.close()


# ---------- Template operations ----------

def get_templates(kind=None):
    conn = get_conn()
    if kind:
        rows = conn.execute("SELECT * FROM templates WHERE kind = ? ORDER BY id", (kind,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM templates ORDER BY kind, id").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_template(template_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM templates WHERE id = ?", (template_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def save_template(template_id, name, subject, body):
    conn = get_conn()
    conn.execute("""
        UPDATE templates SET name = ?, subject = ?, body = ? WHERE id = ?
    """, (name, subject, body, template_id))
    conn.commit()
    conn.close()


# ---------- Send log ----------

def log_event(candidate_id, action, status, detail=""):
    conn = get_conn()
    conn.execute("""
        INSERT INTO send_log (candidate_id, action, status, detail)
        VALUES (?, ?, ?, ?)
    """, (candidate_id, action, status, detail))
    conn.commit()
    conn.close()


def get_log(candidate_id=None, limit=200):
    conn = get_conn()
    if candidate_id:
        rows = conn.execute("""
            SELECT l.*, c.name, c.email FROM send_log l
            JOIN candidates c ON c.id = l.candidate_id
            WHERE l.candidate_id = ? ORDER BY l.id DESC
        """, (candidate_id,)).fetchall()
    else:
        rows = conn.execute("""
            SELECT l.*, c.name, c.email FROM send_log l
            JOIN candidates c ON c.id = l.candidate_id
            ORDER BY l.id DESC LIMIT ?
        """, (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def stats():
    conn = get_conn()
    row = conn.execute("""
        SELECT
          COUNT(*) as total,
          SUM(CASE WHEN status='sent' THEN 1 ELSE 0 END) as sent,
          SUM(CASE WHEN status='pending' THEN 1 ELSE 0 END) as pending,
          SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END) as failed
        FROM candidates
    """).fetchone()
    conn.close()
    return dict(row)
