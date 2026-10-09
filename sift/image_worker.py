"""Background preparation and database-only browsing of saved images."""

import sqlite3
import threading
import time
from pathlib import Path

from PIL import UnidentifiedImageError
from PySide6.QtCore import QThread, Signal

from . import database, image_analysis, image_store


def prepare(db_path, root_id=None, force=False, cancel=lambda: False, progress=None):
    summary = {"prepared": 0, "reused": 0, "failed": 0, "unsupported": 0, "errors": []}
    image_analysis.checkpoint(cancel)
    conn = image_store.install(db_path)
    last_report = 0.0
    try:
        for row in image_store.source_rows(conn, root_id):
            image_analysis.checkpoint(cancel)
            try:
                signature = image_analysis.source_signature(row["path"], row["root"])
                if signature[:2] != (row["size"], row["modified_ns"]):
                    raise OSError("File changed since scanning; rescan first")
                if not force and image_store.cached(conn, row):
                    summary["reused"] += 1
                    continue
                features = image_analysis.analyze(
                    row["path"],
                    row["root"],
                    row["size"],
                    row["modified_ns"],
                    row["orientation"],
                    cancel,
                )
            except image_analysis.AnalysisCancelled:
                raise
            except sqlite3.Error:
                raise
            except Exception as error:  # noqa: BLE001 - One decoder/file failure must not abort preparation.
                supported_suffix = Path(row["path"]).suffix.lower() in {".jpg", ".jpeg", ".png"}
                category = (
                    "unsupported"
                    if isinstance(error, UnidentifiedImageError) and not supported_suffix
                    else "failed"
                )
                summary[category] += 1
                image_store.save(conn, row, error=str(error), status=category)
                if len(summary["errors"]) < 100:
                    summary["errors"].append((row["path"], str(error)))
            else:
                image_store.save(conn, row, features)
                summary["prepared"] += 1
            if progress and time.monotonic() - last_report >= 0.1:
                progress(dict(summary))
                last_report = time.monotonic()
    finally:
        conn.close()
    return summary


class ImageWorker(QThread):
    result_ready = Signal(object)
    failed = Signal(str)
    cancelled = Signal()
    progress = Signal(object)

    def __init__(self, db_path, operation, **options):
        super().__init__()
        self.db_path = db_path
        self.operation = operation
        self.options = options
        self._cancel = threading.Event()

    def cancel(self):
        self._cancel.set()

    def run(self):
        conn = None
        try:
            image_analysis.checkpoint(self._cancel.is_set)
            if self.operation == "prepare":
                result = prepare(
                    self.db_path,
                    **self.options,
                    cancel=self._cancel.is_set,
                    progress=self.progress.emit,
                )
            else:
                conn = database.connect_readonly(self.db_path)
                conn.set_progress_handler(lambda: int(self._cancel.is_set()), 1000)
                if self.operation == "browse":
                    rows, has_more = image_store.browse(conn, **self.options)
                    result = {"rows": rows, "has_more": has_more, "roots": image_store.roots(conn)}
                else:
                    raise ValueError("Unknown image operation")
            image_analysis.checkpoint(self._cancel.is_set)
            self.result_ready.emit(result)
        except image_analysis.AnalysisCancelled:
            self.cancelled.emit()
        except Exception as error:  # noqa: BLE001 - Always report background job errors to the UI.
            if self._cancel.is_set():
                self.cancelled.emit()
            else:
                self.failed.emit(str(error))
        finally:
            if conn is not None:
                conn.close()
