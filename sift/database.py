import sqlite3
import time
from pathlib import Path
from urllib.parse import quote
from uuid import uuid4


def connect(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def connect_readonly(db_path):
    """Open an existing SQLite database without write access."""
    path = quote(Path(db_path).absolute().as_posix(), safe="/:")
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
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
    schema_version = conn.execute("PRAGMA user_version").fetchone()[0]
    if schema_version > 3:
        raise RuntimeError(
            f"Database schema version {schema_version} is newer than this app supports"
        )
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
            modified_ns INTEGER,
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
            audio_codec TEXT,
            audio_sample_rate INTEGER,
            audio_channels INTEGER,
            audio_channel_layout TEXT,
            audio_bit_rate INTEGER,
            capture_date TEXT,
            capture_date_source TEXT,
            camera_make TEXT,
            camera_model TEXT,
            orientation INTEGER,
            input_size INTEGER,
            input_modified REAL,
            input_modified_ns INTEGER,
            extracted_at REAL NOT NULL,
            status TEXT NOT NULL,
            error TEXT,
            retryable INTEGER NOT NULL DEFAULT 0,
            UNIQUE (file_id, extractor, extractor_version)
        );
        CREATE TABLE IF NOT EXISTS fingerprints (
            file_id INTEGER PRIMARY KEY REFERENCES files(id),
            sha256 TEXT NOT NULL,
            input_size INTEGER,
            input_modified REAL,
            input_modified_ns INTEGER,
            algorithm TEXT NOT NULL DEFAULT 'sha256',
            algorithm_version TEXT NOT NULL DEFAULT '1',
            status TEXT NOT NULL DEFAULT 'ok',
            error TEXT,
            computed_at REAL NOT NULL
        );
    """)
    migrations = {
        "files": {"modified_ns": "INTEGER"},
        "media_metadata": {
            "input_modified_ns": "INTEGER",
            "retryable": "INTEGER NOT NULL DEFAULT 0",
            "audio_codec": "TEXT",
            "audio_sample_rate": "INTEGER",
            "audio_channels": "INTEGER",
            "audio_channel_layout": "TEXT",
            "audio_bit_rate": "INTEGER",
        },
        "fingerprints": {
            "input_modified_ns": "INTEGER",
            "algorithm": "TEXT NOT NULL DEFAULT 'sha256'",
            "algorithm_version": "TEXT NOT NULL DEFAULT '1'",
            "status": "TEXT NOT NULL DEFAULT 'ok'",
            "error": "TEXT",
        },
    }
    conn.execute("BEGIN IMMEDIATE")
    try:
        for table, columns in migrations.items():
            existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
            for column, definition in columns.items():
                if column not in existing:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
        conn.execute(
            "UPDATE files SET modified_ns = CAST(modified * 1000000000 AS INTEGER) WHERE modified_ns IS NULL AND modified IS NOT NULL"
        )
        conn.execute(
            "UPDATE media_metadata SET input_modified_ns = CAST(input_modified * 1000000000 AS INTEGER) WHERE input_modified_ns IS NULL AND input_modified IS NOT NULL"
        )
        conn.execute(
            "UPDATE fingerprints SET input_modified_ns = CAST(input_modified * 1000000000 AS INTEGER) WHERE input_modified_ns IS NULL AND input_modified IS NOT NULL"
        )
        conn.execute("PRAGMA user_version = 3")
        conn.commit()
    except Exception:
        conn.rollback()
        raise


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
        INSERT INTO files (root_id, path, size, modified, modified_ns, status, error, last_seen)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (root_id, path) DO UPDATE SET
            size = excluded.size,
            modified = excluded.modified,
            modified_ns = excluded.modified_ns,
            status = excluded.status,
            error = excluded.error,
            last_seen = excluded.last_seen
        """,
        (
            root_id,
            item.path,
            item.size,
            item.modified,
            item.modified_ns,
            item.status,
            item.error,
            seen_at,
        ),
    )


def get_files(conn, limit=1000):
    return conn.execute(
        "SELECT path, size, modified, status, error, last_seen FROM files ORDER BY path LIMIT ?",
        (limit,),
    ).fetchall()


def count_files(conn):
    return conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]


def get_exact_duplicate_groups(conn):
    """Return eligible exact groups and the count of fingerprinted empty files."""
    rows = conn.execute(
        """
        SELECT DISTINCT fingerprints.sha256, files.path, files.size
        FROM fingerprints
        JOIN files ON files.id = fingerprints.file_id
        WHERE fingerprints.status = 'ok'
          AND fingerprints.algorithm = 'sha256'
          AND fingerprints.algorithm_version = '1'
          AND files.status = 'ok'
          AND fingerprints.input_size = files.size
          AND fingerprints.input_modified_ns = files.modified_ns
          AND fingerprints.sha256 != ''
        ORDER BY fingerprints.sha256, files.path
        """
    ).fetchall()
    groups = []
    empty_file_count = 0
    current_digest = None
    current_paths = []
    for row in rows:
        if row["size"] == 0:
            empty_file_count += 1
            continue
        if row["sha256"] != current_digest:
            if len(current_paths) > 1:
                groups.append((current_digest, current_paths))
            current_digest = row["sha256"]
            current_paths = []
        current_paths.append(row["path"])
    if len(current_paths) > 1:
        groups.append((current_digest, current_paths))
    return groups, empty_file_count


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


def save_metadata(
    conn, file_id, extractor, version, r, input_size, input_modified, input_modified_ns
):
    conn.execute(
        """
        INSERT INTO media_metadata (file_id, extractor, extractor_version,
            media_kind, detected_format, width, height, duration_seconds,
            video_codec, audio_codec, audio_sample_rate, audio_channels,
            audio_channel_layout, audio_bit_rate, capture_date, capture_date_source, camera_make,
            camera_model, orientation, input_size, input_modified, input_modified_ns,
            extracted_at, status, error, retryable)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (file_id, extractor, extractor_version) DO UPDATE SET
            media_kind = excluded.media_kind,
            detected_format = excluded.detected_format,
            width = excluded.width, height = excluded.height,
            duration_seconds = excluded.duration_seconds,
            video_codec = excluded.video_codec,
            audio_codec = excluded.audio_codec,
            audio_sample_rate = excluded.audio_sample_rate,
            audio_channels = excluded.audio_channels,
            audio_channel_layout = excluded.audio_channel_layout,
            audio_bit_rate = excluded.audio_bit_rate,
            capture_date = excluded.capture_date,
            capture_date_source = excluded.capture_date_source,
            camera_make = excluded.camera_make,
            camera_model = excluded.camera_model,
            orientation = excluded.orientation,
            input_size = excluded.input_size,
            input_modified = excluded.input_modified,
            input_modified_ns = excluded.input_modified_ns,
            extracted_at = excluded.extracted_at,
            status = excluded.status, error = excluded.error,
            retryable = excluded.retryable
        """,
        (
            file_id,
            extractor,
            version,
            r.media_kind,
            r.detected_format,
            r.width,
            r.height,
            r.duration_seconds,
            r.video_codec,
            r.audio_codec,
            r.audio_sample_rate,
            r.audio_channels,
            r.audio_channel_layout,
            r.audio_bit_rate,
            r.capture_date,
            r.capture_date_source,
            r.camera_make,
            r.camera_model,
            r.orientation,
            input_size,
            input_modified,
            input_modified_ns,
            time.time(),
            r.status,
            r.error,
            int(r.retryable),
        ),
    )


def get_file_id(conn, root_id, path):
    row = conn.execute(
        "SELECT id FROM files WHERE root_id = ? AND path = ?", (root_id, path)
    ).fetchone()
    return row["id"]


def get_metadata(conn, file_id, extractor, version):
    return conn.execute(
        """
        SELECT status, input_size, input_modified, input_modified_ns, retryable FROM media_metadata
        WHERE file_id = ? AND extractor = ? AND extractor_version = ?
        """,
        (file_id, extractor, version),
    ).fetchone()


def get_fingerprint(conn, file_id):
    return conn.execute(
        "SELECT sha256, input_size, input_modified, input_modified_ns, algorithm, "
        "algorithm_version, status, error FROM fingerprints WHERE file_id = ?",
        (file_id,),
    ).fetchone()


def save_fingerprint(
    conn,
    file_id,
    sha256,
    size,
    modified,
    modified_ns,
    status="ok",
    error=None,
    algorithm="sha256",
    algorithm_version="1",
):
    conn.execute(
        """
        INSERT INTO fingerprints (file_id, sha256, input_size, input_modified,
            input_modified_ns, algorithm, algorithm_version, status, error, computed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (file_id) DO UPDATE SET
            sha256 = excluded.sha256,
            input_size = excluded.input_size,
            input_modified = excluded.input_modified,
            input_modified_ns = excluded.input_modified_ns,
            algorithm = excluded.algorithm,
            algorithm_version = excluded.algorithm_version,
            status = excluded.status,
            error = excluded.error,
            computed_at = excluded.computed_at
        """,
        (
            file_id,
            sha256,
            size,
            modified,
            modified_ns,
            algorithm,
            algorithm_version,
            status,
            error,
            time.time(),
        ),
    )


def mark_file_for_retry(conn, file_id, message):
    conn.execute("UPDATE files SET status = 'retry', error = ? WHERE id = ?", (message, file_id))
