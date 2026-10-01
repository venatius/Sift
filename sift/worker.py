import threading
import time

from PySide6.QtCore import QObject, Signal

from . import database, fingerprint, metadata
from .scanner import scan_folder

MAX_ERRORS_SHOWN = 200


class ScanWorker(QObject):
    progress = Signal(int, str)   # items processed so far, current path
    scan_done = Signal(dict)      # final summary

    def __init__(self, root_path, db_path):
        super().__init__()
        self.root_path = root_path
        self.db_path = db_path
        self._cancel = threading.Event()
        self._running = threading.Event()
        self._running.set()  # set = allowed to run, cleared = paused

    def pause(self):
        self._running.clear()

    def resume(self):
        self._running.set()

    def cancel(self):
        self._cancel.set()
        self._running.set()  # wake up if paused so it can stop

    def _checkpoint(self):
        """Called between chunks of a big file: waits if paused, True if cancelled."""
        self._running.wait()
        return self._cancel.is_set()

    def _add_error(self, summary, path, message):
        if len(summary["errors"]) < MAX_ERRORS_SHOWN:
            summary["errors"].append((path, message))

    def _process_file(self, conn, file_id, item, summary):
        """Returns False only if the user cancelled mid-file."""
        if not self._do_metadata(conn, file_id, item, summary):
            return False
        return self._do_fingerprint(conn, file_id, item, summary)

    def _do_metadata(self, conn, file_id, item, summary):
        kind = metadata.kind_for(item.path)
        name, version = metadata.extractor_info(kind)
        old = database.get_metadata(conn, file_id, name, version)
        if (old and old["status"] in ("ok", "unsupported")
                and old["input_size"] == item.size
                and old["input_modified"] == item.modified):
            summary["meta_reused"] += 1
            return True

        try:
            result = metadata.extract(item.path, kind, self._cancel.is_set)
        except metadata.MetadataCancelled:
            return False
        database.save_metadata(conn, file_id, name, version, result,
                               item.size, item.modified)
        summary["meta_" + result.status] += 1
        if result.status == "failed":
            self._add_error(summary, item.path, result.error)
        return True

    def _do_fingerprint(self, conn, file_id, item, summary):
        old = database.get_fingerprint(conn, file_id)
        if (old and old["input_size"] == item.size
                and old["input_modified"] == item.modified):
            summary["fp_reused"] += 1
            return True
        try:
            digest = fingerprint.sha256_file(item.path, self._checkpoint)
        except OSError as e:
            summary["fp_failed"] += 1
            self._add_error(summary, item.path, f"Could not fingerprint: {e}")
            return True
        if digest is None:
            return False  # cancelled
        database.save_fingerprint(conn, file_id, digest, item.size, item.modified)
        summary["fp_done"] += 1
        return True

    def run(self):
        summary = {
            "scanned": 0, "skipped": 0, "failed": 0, "cancelled": False, "errors": [],
            "meta_ok": 0, "meta_unsupported": 0, "meta_failed": 0, "meta_reused": 0,
            "fp_done": 0, "fp_reused": 0, "fp_failed": 0,
        }
        conn = None
        scan_id = None
        final_status = "completed"
        total = 0
        try:
            conn = database.connect(self.db_path)
            root_id = database.add_root(conn, self.root_path)
            scan_id = database.start_scan(conn, root_id)
            seen_at = time.time()

            for item in scan_folder(self.root_path):
                self._running.wait()              # blocks here while paused
                if self._cancel.is_set():
                    summary["cancelled"] = True
                    final_status = "cancelled"
                    break

                database.save_file(conn, root_id, item, seen_at)
                total += 1
                self.progress.emit(total, item.path)

                if item.status == "ok":
                    summary["scanned"] += 1
                    file_id = database.get_file_id(conn, root_id, item.path)
                    if not self._process_file(conn, file_id, item, summary):
                        summary["cancelled"] = True
                        final_status = "cancelled"
                        break
                else:
                    summary[item.status] += 1     # "skipped" or "failed"
                    self._add_error(summary, item.path, item.error)

                if total % 25 == 0:
                    conn.commit()

            conn.commit()
            self.progress.emit(total, "")
        except Exception as e:
            final_status = "failed"
            summary["errors"].append(("(scan stopped unexpectedly)", str(e)))
        finally:
            if conn is not None:
                try:
                    if scan_id is not None:
                        database.finish_scan(conn, scan_id, final_status)
                except Exception as e:
                    final_status = "failed"
                    summary["errors"].append(("(could not save scan status)", str(e)))
                finally:
                    conn.close()

        summary["status"] = final_status
        self.scan_done.emit(summary)