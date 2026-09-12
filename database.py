import sqlite3
import json
from pathlib import Path
from datetime import datetime
from utils import normalize_linkedin_url

DB_PATH = Path("data/hunting.db")


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def get_conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with get_conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS searches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            location TEXT,
            seniority TEXT,
            min_years INTEGER DEFAULT 0,
            target_count INTEGER DEFAULT 20,
            status TEXT DEFAULT 'Activa',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS search_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            search_id INTEGER NOT NULL,
            version_number INTEGER NOT NULL,
            jd TEXT NOT NULL,
            must_have_json TEXT NOT NULL,
            nice_to_have_json TEXT NOT NULL,
            change_note TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(search_id) REFERENCES searches(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS batches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            search_id INTEGER NOT NULL,
            version_id INTEGER NOT NULL,
            batch_number INTEGER NOT NULL,
            criteria_summary TEXT,
            source_summary TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(search_id) REFERENCES searches(id) ON DELETE CASCADE,
            FOREIGN KEY(version_id) REFERENCES search_versions(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS candidates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            linkedin_url TEXT NOT NULL UNIQUE,
            location TEXT,
            current_role TEXT,
            current_company TEXT,
            first_seen_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS search_candidates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            search_id INTEGER NOT NULL,
            batch_id INTEGER NOT NULL,
            candidate_id INTEGER NOT NULL,
            match_score INTEGER DEFAULT 0,
            priority TEXT,
            evidence TEXT,
            validation TEXT,
            source TEXT,
            created_at TEXT NOT NULL,
            UNIQUE(search_id, candidate_id),
            FOREIGN KEY(search_id) REFERENCES searches(id) ON DELETE CASCADE,
            FOREIGN KEY(batch_id) REFERENCES batches(id) ON DELETE CASCADE,
            FOREIGN KEY(candidate_id) REFERENCES candidates(id)
        );
        """)


def create_search(title, location, seniority, min_years, target_count):
    ts = now()
    with get_conn() as conn:
        cur = conn.execute("""
            INSERT INTO searches(title, location, seniority, min_years, target_count, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, 'Activa', ?, ?)
        """, (title, location, seniority, min_years, target_count, ts, ts))
        return cur.lastrowid


def update_search_core(search_id, location, seniority, min_years):
    with get_conn() as conn:
        conn.execute("""
            UPDATE searches SET location=?, seniority=?, min_years=?, updated_at=? WHERE id=?
        """, (location, seniority, min_years, now(), search_id))


def add_search_version(search_id, jd, must_have, nice_to_have, change_note):
    with get_conn() as conn:
        current = conn.execute(
            "SELECT COALESCE(MAX(version_number), 0) AS n FROM search_versions WHERE search_id=?",
            (search_id,),
        ).fetchone()["n"]
        cur = conn.execute("""
            INSERT INTO search_versions(
                search_id, version_number, jd, must_have_json, nice_to_have_json, change_note, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            search_id,
            current + 1,
            jd,
            json.dumps(must_have, ensure_ascii=False),
            json.dumps(nice_to_have, ensure_ascii=False),
            change_note,
            now(),
        ))
        conn.execute("UPDATE searches SET updated_at=? WHERE id=?", (now(), search_id))
        return cur.lastrowid


def list_searches():
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT s.*,
                   COUNT(DISTINCT sc.candidate_id) AS candidate_count,
                   COUNT(DISTINCT b.id) AS batch_count
            FROM searches s
            LEFT JOIN search_candidates sc ON sc.search_id=s.id
            LEFT JOIN batches b ON b.search_id=s.id
            GROUP BY s.id
            ORDER BY s.updated_at DESC
        """).fetchall()
        return [dict(r) for r in rows]


def get_search(search_id):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM searches WHERE id=?", (search_id,)).fetchone()
        return dict(row) if row else None


def get_search_versions(search_id):
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT * FROM search_versions
            WHERE search_id=?
            ORDER BY version_number DESC
        """, (search_id,)).fetchall()

        result = []
        for r in rows:
            d = dict(r)
            d["must_have"] = json.loads(d.pop("must_have_json"))
            d["nice_to_have"] = json.loads(d.pop("nice_to_have_json"))
            result.append(d)
        return result


def add_batch(search_id, version_id, criteria_summary, source_summary=""):
    with get_conn() as conn:
        n = conn.execute(
            "SELECT COALESCE(MAX(batch_number), 0) AS n FROM batches WHERE search_id=?",
            (search_id,),
        ).fetchone()["n"]
        cur = conn.execute("""
            INSERT INTO batches(search_id, version_id, batch_number, criteria_summary, source_summary, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (search_id, version_id, n + 1, criteria_summary, source_summary, now()))
        conn.execute("UPDATE searches SET updated_at=? WHERE id=?", (now(), search_id))
        return cur.lastrowid


def get_batches(search_id):
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT b.*, COUNT(sc.id) AS candidate_count
            FROM batches b
            LEFT JOIN search_candidates sc ON sc.batch_id=b.id
            WHERE b.search_id=?
            GROUP BY b.id
            ORDER BY b.batch_number DESC
        """, (search_id,)).fetchall()
        return [dict(r) for r in rows]


def candidate_exists_global(linkedin_url):
    url = normalize_linkedin_url(linkedin_url)
    if not url:
        return False
    with get_conn() as conn:
        row = conn.execute("SELECT id FROM candidates WHERE linkedin_url=?", (url,)).fetchone()
        return row is not None


def add_candidate_to_batch(
    search_id, batch_id, name, linkedin_url, location,
    current_role, current_company, match_score, priority,
    evidence, validation, source
):
    url = normalize_linkedin_url(linkedin_url)
    if not url:
        raise ValueError("URL de LinkedIn inválida")

    ts = now()
    with get_conn() as conn:
        existing = conn.execute(
            "SELECT id FROM candidates WHERE linkedin_url=?", (url,)
        ).fetchone()

        if existing:
            candidate_id = existing["id"]
            conn.execute("""
                UPDATE candidates
                SET last_seen_at=?,
                    name=COALESCE(NULLIF(?, ''), name),
                    location=COALESCE(NULLIF(?, ''), location),
                    current_role=COALESCE(NULLIF(?, ''), current_role),
                    current_company=COALESCE(NULLIF(?, ''), current_company)
                WHERE id=?
            """, (ts, name, location, current_role, current_company, candidate_id))
        else:
            cur = conn.execute("""
                INSERT INTO candidates(
                    name, linkedin_url, location, current_role, current_company, first_seen_at, last_seen_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (name, url, location, current_role, current_company, ts, ts))
            candidate_id = cur.lastrowid

        conn.execute("""
            INSERT OR IGNORE INTO search_candidates(
                search_id, batch_id, candidate_id, match_score, priority,
                evidence, validation, source, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            search_id, batch_id, candidate_id, match_score, priority,
            evidence, validation, source, ts,
        ))


def get_candidates_for_search(search_id):
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT
                c.id AS candidate_id,
                c.name,
                c.linkedin_url,
                c.location,
                c.current_role,
                c.current_company,
                sc.match_score,
                sc.priority,
                sc.evidence,
                sc.validation,
                sc.source,
                sc.created_at,
                b.batch_number,
                b.criteria_summary,
                sv.version_number
            FROM search_candidates sc
            JOIN candidates c ON c.id=sc.candidate_id
            JOIN batches b ON b.id=sc.batch_id
            JOIN search_versions sv ON sv.id=b.version_id
            WHERE sc.search_id=?
            ORDER BY b.batch_number DESC, sc.match_score DESC, c.name
        """, (search_id,)).fetchall()
        return [dict(r) for r in rows]


def get_global_candidates():
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT c.*, COUNT(DISTINCT sc.search_id) AS searches_count
            FROM candidates c
            LEFT JOIN search_candidates sc ON sc.candidate_id=c.id
            GROUP BY c.id
            ORDER BY c.last_seen_at DESC
        """).fetchall()
        return [dict(r) for r in rows]


def update_search_status(search_id, status):
    with get_conn() as conn:
        conn.execute(
            "UPDATE searches SET status=?, updated_at=? WHERE id=?",
            (status, now(), search_id),
        )


def delete_search(search_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM search_candidates WHERE search_id=?", (search_id,))
        conn.execute("DELETE FROM batches WHERE search_id=?", (search_id,))
        conn.execute("DELETE FROM search_versions WHERE search_id=?", (search_id,))
        conn.execute("DELETE FROM searches WHERE id=?", (search_id,))
