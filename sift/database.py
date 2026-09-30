import sqlite3
import time
from pathlib import Path
from uuid import uuid4


def connect(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def migrate_database(source_path, destination_path):
    source = Path(source_path)
    destination = Path(destination_path)
    if not source.is_file() or destination.exists():
        return False

    temporary = destination.with_name(f"{destination.name}.{uuid4().hex}.migrating")
    source_conn = sqlite3.connect(source)
    destination_conn = sqlite3.connect(temporary)
    try:
        source_conn.backup(destination_conn)
        destination_conn.close()
        source_conn.close()
        temporary.replace(destination)
    except Exception:
        destination_conn.close()
        source_conn.close()
        temporary.unlink(missing_ok=True)
        raise
    return True


def init_db(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS roots (
            id INTEGER PRIMARY KEY,
            path TEXT NOT NULL UNIQUE,
            added_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY,
            root_id INTEGER NOT NULL REFERENCES roots(id),
            path TEXT NOT NULL,
            size INTEGER,
            modified REAL,
            status TEXT NOT NULL,
            error TEXT,
            last_seen REAL NOT NULL,
            UNIQUE (root_id, path)
        );
        CREATE TABLE IF NOT EXISTS scans (
            id INTEGER PRIMARY KEY,
            root_id INTEGER NOT NULL REFERENCES roots(id),
            started_at REAL NOT NULL,
            ended_at REAL,
            status TEXT NOT NULL
        );
    """)
    conn.commit()


def add_root(conn, path):
    conn.execute(
        "INSERT OR IGNORE INTO roots (path, added_at) VALUES (?, ?)",
        (path, time.time()),
    )
    conn.commit()
    return conn.execute("SELECT id FROM roots WHERE path = ?", (path,)).fetchone()["id"]


def save_file(conn, root_id, item, seen_at):
    conn.execute(
        """
        INSERT INTO files (root_id, path, size, modified, status, error, last_seen)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (root_id, path) DO UPDATE SET
            size = excluded.size,
            modified = excluded.modified,
            status = excluded.status,
            error = excluded.error,
            last_seen = excluded.last_seen
        """,
        (root_id, item.path, item.size, item.modified, item.status, item.error, seen_at),
    )


def get_files(conn, limit=1000):
    return conn.execute(
        "SELECT path, size, modified, status, error, last_seen FROM files ORDER BY path LIMIT ?",
        (limit,),
    ).fetchall()


def count_files(conn):
    return conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]


def start_scan(conn, root_id):
    cur = conn.execute(
        "INSERT INTO scans (root_id, started_at, status) VALUES (?, ?, 'running')",
        (root_id, time.time()),
    )
    conn.commit()
    return cur.lastrowid


def finish_scan(conn, scan_id, status):
    conn.execute(
        "UPDATE scans SET ended_at = ?, status = ? WHERE id = ?",
        (time.time(), status, scan_id),
    )
    conn.commit()


def mark_interrupted(conn):
    cur = conn.execute(
        "UPDATE scans SET status = 'interrupted', ended_at = ? WHERE status = 'running'",
        (time.time(),),
    )
    conn.commit()
    return cur.rowcount


def get_latest_root(conn):
    return conn.execute(
        """
        SELECT roots.path
        FROM roots
        LEFT JOIN scans ON scans.root_id = roots.id
        GROUP BY roots.id
        ORDER BY COALESCE(MAX(scans.started_at), roots.added_at) DESC, roots.id DESC
        LIMIT 1
        """
    ).fetchone()
