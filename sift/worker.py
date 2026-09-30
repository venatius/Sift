import threading
import time

from PySide6.QtCore import QObject, Signal

from . import database
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

    def run(self):
        summary = {"scanned": 0, "skipped": 0, "failed": 0, "cancelled": False, "errors": []}
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

                if item.status == "ok":
                    summary["scanned"] += 1
                else:
                    summary[item.status] += 1     # "skipped" or "failed"
                    if len(summary["errors"]) < MAX_ERRORS_SHOWN:
                        summary["errors"].append((item.path, item.error))

                if total % 25 == 0:
                    conn.commit()
                    self.progress.emit(total, item.path)

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
