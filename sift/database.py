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
        CREATE TABLE IF NOT EXISTS media_metadata (
            id INTEGER PRIMARY KEY,
            file_id INTEGER NOT NULL REFERENCES files(id),
            extractor TEXT NOT NULL,
            extractor_version TEXT NOT NULL,
            media_kind TEXT,
            detected_format TEXT,
            width INTEGER,
            height INTEGER,
            duration_seconds REAL,
            video_codec TEXT,
            capture_date TEXT,
            capture_date_source TEXT,
            camera_make TEXT,
            camera_model TEXT,
            orientation INTEGER,
            input_size INTEGER,
            input_modified REAL,
            extracted_at REAL NOT NULL,
            status TEXT NOT NULL,
            error TEXT,
            UNIQUE (file_id, extractor, extractor_version)
        );
        CREATE TABLE IF NOT EXISTS fingerprints (
            file_id INTEGER PRIMARY KEY REFERENCES files(id),
            sha256 TEXT NOT NULL,
            input_size INTEGER,
            input_modified REAL,
            computed_at REAL NOT NULL
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

def save_metadata(conn, file_id, extractor, version, r, input_size, input_modified):
    conn.execute(
        """
        INSERT INTO media_metadata (file_id, extractor, extractor_version,
            media_kind, detected_format, width, height, duration_seconds,
            video_codec, capture_date, capture_date_source, camera_make,
            camera_model, orientation, input_size, input_modified,
            extracted_at, status, error)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (file_id, extractor, extractor_version) DO UPDATE SET
            media_kind = excluded.media_kind,
            detected_format = excluded.detected_format,
            width = excluded.width, height = excluded.height,
            duration_seconds = excluded.duration_seconds,
            video_codec = excluded.video_codec,
            capture_date = excluded.capture_date,
            capture_date_source = excluded.capture_date_source,
            camera_make = excluded.camera_make,
            camera_model = excluded.camera_model,
            orientation = excluded.orientation,
            input_size = excluded.input_size,
            input_modified = excluded.input_modified,
            extracted_at = excluded.extracted_at,
            status = excluded.status, error = excluded.error
        """,
        (file_id, extractor, version, r.media_kind, r.detected_format,
         r.width, r.height, r.duration_seconds, r.video_codec,
         r.capture_date, r.capture_date_source, r.camera_make,
         r.camera_model, r.orientation, input_size, input_modified,
         time.time(), r.status, r.error),
    )

def get_file_id(conn, root_id, path):
    row = conn.execute(
        "SELECT id FROM files WHERE root_id = ? AND path = ?", (root_id, path)
    ).fetchone()
    return row["id"]


def get_metadata(conn, file_id, extractor, version):
    return conn.execute(
        """
        SELECT status, input_size, input_modified FROM media_metadata
        WHERE file_id = ? AND extractor = ? AND extractor_version = ?
        """,
        (file_id, extractor, version),
    ).fetchone()


def get_fingerprint(conn, file_id):
    return conn.execute(
        "SELECT sha256, input_size, input_modified FROM fingerprints WHERE file_id = ?",
        (file_id,),
    ).fetchone()


def save_fingerprint(conn, file_id, sha256, size, modified):
    conn.execute(
        """
        INSERT INTO fingerprints (file_id, sha256, input_size, input_modified, computed_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT (file_id) DO UPDATE SET
            sha256 = excluded.sha256,
            input_size = excluded.input_size,
            input_modified = excluded.input_modified,
            computed_at = excluded.computed_at
        """,
        (file_id, sha256, size, modified, time.time()),
    )