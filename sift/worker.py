import os
import sqlite3
import threading
import time
from dataclasses import replace

from PySide6.QtCore import QObject, Signal

from . import database, fingerprint, metadata
from .scanner import scan_folder

MAX_ERRORS_SHOWN = 200


class ScanWorker(QObject):
    progress = Signal(int, str)   # items processed so far, current path
    stage_progress = Signal(str, int, int)  # stage, current bytes, total bytes
    scan_done = Signal(dict)      # final summary

    def __init__(self, root_path, db_path, force_rehash=False):
        super().__init__()
        self.root_path = root_path
        self.db_path = db_path
        self.force_rehash = force_rehash
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

    @staticmethod
    def _signature(path):
        info = os.stat(path)
        return info.st_size, info.st_mtime, info.st_mtime_ns

    @staticmethod
    def _item_signature(item):
        modified_ns = item.modified_ns
        if modified_ns is None and item.modified is not None:
            modified_ns = int(item.modified * 1_000_000_000)
        return item.size, item.modified, modified_ns

    def _mark_changed(self, conn, file_id, item, summary, stage):
        message = "File changed during scanning; retry it on the next scan"
        result = metadata.MetadataResult("failed", error=message, retryable=True)
        name, version = metadata.extractor_info(metadata.kind_for(item.path))
        if stage == "metadata":
            database.save_metadata(conn, file_id, name, version, result,
                                   item.size, item.modified, item.modified_ns)
            summary["meta_failed"] += 1
        else:
            database.save_fingerprint(conn, file_id, "", item.size, item.modified,
                                      item.modified_ns, status="failed", error=message)
            summary["fp_failed"] += 1
        database.mark_file_for_retry(conn, file_id, message)
        self._add_error(summary, item.path, message)

    def _process_file(self, conn, file_id, item, summary, total=0):
        """Run independent stages; return False only for cancellation."""
        if self._checkpoint():
            return False
        try:
            current = self._signature(item.path)
        except OSError as error:
            message = f"Could not stat file: {error}"
            self._mark_changed(conn, file_id, item, summary, "metadata")
            self._mark_changed(conn, file_id, item, summary, "fingerprint")
            self._add_error(summary, item.path, message)
            return True
        if current != self._item_signature(item):
            self._mark_changed(conn, file_id, item, summary, "metadata")
            self._mark_changed(conn, file_id, item, summary, "fingerprint")
            return True

        try:
            if not self._do_metadata(conn, file_id, item, summary):
                return False
        except sqlite3.Error:
            raise
        except Exception as error:  # noqa: BLE001 - Isolate unexpected per-file metadata failures.
            result = metadata.MetadataResult("failed", error=f"Metadata error: {error}",
                                             retryable=True)
            name, version = metadata.extractor_info(metadata.kind_for(item.path))
            database.save_metadata(conn, file_id, name, version, result,
                                   item.size, item.modified, item.modified_ns)
            summary["meta_failed"] += 1
            self._add_error(summary, item.path, result.error)

        if self._checkpoint():
            return False
        try:
            if not self._do_fingerprint(conn, file_id, item, summary, total):
                return False
        except sqlite3.Error:
            raise
        except Exception as error:  # noqa: BLE001 - Isolate unexpected per-file hashing failures.
            message = f"Fingerprint error: {error}"
            database.save_fingerprint(conn, file_id, "", item.size, item.modified,
                                      item.modified_ns, status="failed", error=message)
            summary["fp_failed"] += 1
            self._add_error(summary, item.path, message)
        return True

    def _do_metadata(self, conn, file_id, item, summary):
        kind = metadata.kind_for(item.path)
        name, version = metadata.extractor_info(kind)
        old = database.get_metadata(conn, file_id, name, version)
        if (old and old["status"] in ("ok", "unsupported", "failed")
                and not old["retryable"]
                and old["input_size"] == item.size
                and old["input_modified_ns"] == item.modified_ns):
            summary["meta_reused"] += 1
            return True

        if self._checkpoint():
            return False
        try:
            result = metadata.extract(item.path, kind, self._cancel.is_set)
        except metadata.MetadataCancelled:
            return False
        try:
            current = self._signature(item.path)
        except OSError:
            current = None
        if current != self._item_signature(item):
            result = metadata.MetadataResult("failed", error=
                "File changed during metadata extraction; retry it on the next scan",
                retryable=True)
            database.mark_file_for_retry(conn, file_id, result.error)
        database.save_metadata(conn, file_id, name, version, result,
                               item.size, item.modified, item.modified_ns)
        summary["meta_" + result.status] += 1
        if result.status == "failed":
            self._add_error(summary, item.path, result.error)
        return True

    def _do_fingerprint(self, conn, file_id, item, summary, total=0):
        old = database.get_fingerprint(conn, file_id)
        if (not self.force_rehash and old and old["status"] == "ok"
                and old["algorithm"] == "sha256"
                and old["algorithm_version"] == "1"
                and old["input_size"] == item.size
                and old["input_modified_ns"] == item.modified_ns):
            summary["fp_reused"] += 1
            return True
        before = self._signature(item.path)
        if before != self._item_signature(item):
            self._mark_changed(conn, file_id, item, summary, "fingerprint")
            return True
        last_report = [0.0]

        def report_bytes(current):
            now = time.monotonic()
            if current >= item.size or now - last_report[0] >= 0.15:
                self.stage_progress.emit("fingerprint", current, item.size)
                last_report[0] = now

        try:
            digest = fingerprint.sha256_file(item.path, self._checkpoint, report_bytes)
        except OSError as e:
            summary["fp_failed"] += 1
            database.save_fingerprint(conn, file_id, "", item.size, item.modified,
                                      item.modified_ns, status="failed",
                                      error=f"Could not fingerprint: {e}")
            self._add_error(summary, item.path, f"Could not fingerprint: {e}")
            return True
        if digest is None:
            return False  # cancelled
        try:
            after = self._signature(item.path)
        except OSError:
            after = None
        if after != before or after != self._item_signature(item):
            self._mark_changed(conn, file_id, item, summary, "fingerprint")
            return True
        database.save_fingerprint(conn, file_id, digest, item.size, item.modified,
                                  item.modified_ns)
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
        last_progress = 0.0
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

                if item.status == "ok" and item.modified_ns is None:
                    item = replace(item, modified_ns=self._signature(item.path)[2])

                database.save_file(conn, root_id, item, seen_at)
                total += 1
                now = time.monotonic()
                if total == 1 or now - last_progress >= 0.15:
                    self.progress.emit(total, item.path)
                    last_progress = now

                if item.status == "ok":
                    summary["scanned"] += 1
                    file_id = database.get_file_id(conn, root_id, item.path)
                    if not self._process_file(conn, file_id, item, summary):
                        summary["cancelled"] = True
                        final_status = "cancelled"
                        break
                else:
                    summary[item.status] += 1     # "skipped" or "failed"
                    if item.status == "failed":
                        summary["failed"] += 1
                    self._add_error(summary, item.path, item.error)

                if total % 25 == 0:
                    conn.commit()

            conn.commit()
            self.progress.emit(total, "")
        except Exception as e:  # noqa: BLE001 - Unexpected scan errors must mark the scan failed.
            final_status = "failed"
            summary["errors"].append(("(scan stopped unexpectedly)", str(e)))
        finally:
            if conn is not None:
                try:
                    if scan_id is not None:
                        database.finish_scan(conn, scan_id, final_status)
                except Exception as e:  # noqa: BLE001 - Report status-save failures during cleanup.
                    final_status = "failed"
                    summary["errors"].append(("(could not save scan status)", str(e)))
                finally:
                    conn.close()

        summary["status"] = final_status
        self.scan_done.emit(summary)
