import hashlib
import importlib
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication

from sift import database
from sift.duplicates import DuplicateWorker


class ExactDuplicateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt_app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.temp.name) / "sift.db")
        self.conn = database.connect(self.db_path)
        database.init_db(self.conn)
        self.root_id = database.add_root(self.conn, self.temp.name)

    def tearDown(self):
        self.conn.close()
        self.temp.cleanup()

    def add_file(
        self,
        name,
        digest,
        *,
        status="ok",
        algorithm="sha256",
        version="1",
        fingerprint_status="ok",
        matching_signature=True,
        size=42,
    ):
        path = str(Path(self.temp.name) / name)
        modified_ns = 123456789
        self.conn.execute(
            """INSERT INTO files
               (root_id, path, size, modified, modified_ns, status, last_seen)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (self.root_id, path, size, 1.0, modified_ns, status, 1.0),
        )
        file_id = self.conn.execute("SELECT id FROM files WHERE path = ?", (path,)).fetchone()["id"]
        database.save_fingerprint(
            self.conn,
            file_id,
            digest,
            size if matching_signature else size + 1,
            1.0,
            modified_ns,
            status=fingerprint_status,
            algorithm=algorithm,
            algorithm_version=version,
        )
        self.conn.commit()
        return path

    def test_groups_only_matching_current_successful_sha256_records(self):
        first = self.add_file("first.jpg", "a" * 64)
        second = self.add_file("second.jpg", "a" * 64)
        self.add_file("unique.jpg", "b" * 64)
        self.add_file("stale.jpg", "a" * 64, matching_signature=False)
        self.add_file("failed.jpg", "a" * 64, fingerprint_status="failed")
        self.add_file("wrong-algorithm.jpg", "a" * 64, algorithm="md5")
        self.add_file("wrong-version.jpg", "a" * 64, version="2")
        self.add_file("not-inventory.jpg", "a" * 64, status="retry")

        groups, empty_file_count = database.get_exact_duplicate_groups(self.conn)
        self.assertEqual(groups, [("a" * 64, [first, second])])
        self.assertEqual(empty_file_count, 0)

    def test_two_zero_byte_files_are_counted_without_a_group(self):
        empty_digest = hashlib.sha256(b"").hexdigest()
        self.add_file("empty-one.bin", empty_digest, size=0)
        self.add_file("empty-two.bin", empty_digest, size=0)

        groups, empty_file_count = database.get_exact_duplicate_groups(self.conn)

        self.assertEqual(groups, [])
        self.assertEqual(empty_file_count, 2)

    def test_nonempty_identical_files_still_form_a_group(self):
        first = self.add_file("same-one.bin", "f" * 64)
        second = self.add_file("same-two.bin", "f" * 64)

        groups, empty_file_count = database.get_exact_duplicate_groups(self.conn)

        self.assertEqual(groups, [("f" * 64, sorted([first, second]))])
        self.assertEqual(empty_file_count, 0)

    def test_overlapping_roots_do_not_duplicate_a_path_in_a_group(self):
        first = self.add_file("shared.jpg", "e" * 64)
        second = self.add_file("other.jpg", "e" * 64)
        nested_root = database.add_root(self.conn, str(Path(self.temp.name) / "nested"))
        self.conn.execute(
            """INSERT INTO files
               (root_id, path, size, modified, modified_ns, status, last_seen)
               VALUES (?, ?, ?, ?, ?, 'ok', ?)""",
            (nested_root, first, 42, 1.0, 123456789, 1.0),
        )
        nested_file_id = self.conn.execute(
            "SELECT id FROM files WHERE root_id = ? AND path = ?", (nested_root, first)
        ).fetchone()["id"]
        database.save_fingerprint(self.conn, nested_file_id, "e" * 64, 42, 1.0, 123456789)
        self.conn.commit()

        groups, empty_file_count = database.get_exact_duplicate_groups(self.conn)
        self.assertEqual(groups, [("e" * 64, sorted([first, second]))])
        self.assertEqual(empty_file_count, 0)

    def test_matching_files_from_different_roots_form_a_group(self):
        first = self.add_file("first-root/same.jpg", "1" * 64)
        second_root = database.add_root(self.conn, str(Path(self.temp.name) / "second-root"))
        second = str(Path(self.temp.name) / "second-root" / "same.jpg")
        self.conn.execute(
            """INSERT INTO files
               (root_id, path, size, modified, modified_ns, status, last_seen)
               VALUES (?, ?, ?, ?, ?, 'ok', ?)""",
            (second_root, second, 42, 1.0, 123456789, 1.0),
        )
        file_id = self.conn.execute(
            "SELECT id FROM files WHERE root_id = ? AND path = ?", (second_root, second)
        ).fetchone()["id"]
        database.save_fingerprint(self.conn, file_id, "1" * 64, 42, 1.0, 123456789)
        self.conn.commit()

        groups, empty_file_count = database.get_exact_duplicate_groups(self.conn)
        self.assertEqual(groups, [("1" * 64, sorted([first, second]))])
        self.assertEqual(empty_file_count, 0)

    def test_query_does_not_check_nonexistent_media_paths(self):
        first = self.add_file("missing-one.jpg", "2" * 64)
        second = self.add_file("missing-two.jpg", "2" * 64)

        with patch("os.stat", side_effect=AssertionError("media path was checked")):
            groups, empty_file_count = database.get_exact_duplicate_groups(self.conn)

        self.assertEqual(groups, [("2" * 64, sorted([first, second]))])
        self.assertEqual(empty_file_count, 0)

    def test_readonly_connection_rejects_writes(self):
        conn = database.connect_readonly(self.db_path)
        try:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM files").fetchone()[0], 0)
            with self.assertRaisesRegex(sqlite3.OperationalError, "readonly|read-only"):
                conn.execute(
                    "INSERT INTO roots (path, added_at) VALUES (?, ?)",
                    ("blocked-root", 2.0),
                )
        finally:
            conn.close()

    def test_background_worker_emits_read_only_groups(self):
        first = self.add_file("one.jpg", "c" * 64)
        second = self.add_file("two.jpg", "c" * 64)
        worker = DuplicateWorker(self.db_path)
        loop = QEventLoop()
        results = []
        errors = []
        worker.groups_ready.connect(
            lambda groups, empty_count: (results.append((groups, empty_count)), loop.quit())
        )
        worker.query_failed.connect(lambda error: (errors.append(error), loop.quit()))
        QTimer.singleShot(5000, loop.quit)
        worker.start()
        loop.exec()
        worker.wait()

        self.assertFalse(errors)
        self.assertEqual(results, [([("c" * 64, [first, second])], 0)])

    def test_background_worker_reports_database_errors(self):
        worker = DuplicateWorker(str(Path(self.temp.name) / "missing" / "sift.db"))
        loop = QEventLoop()
        errors = []
        worker.query_failed.connect(lambda error: (errors.append(error), loop.quit()))
        QTimer.singleShot(5000, loop.quit)
        worker.start()
        loop.exec()
        worker.wait()

        self.assertEqual(len(errors), 1)
        self.assertIn("unable to open database file", errors[0].lower())

    def test_ui_presents_groups_from_the_configured_database(self):
        first = self.add_file("ui-one.jpg", "d" * 64)
        second = self.add_file("ui-two.jpg", "d" * 64)
        with patch.dict(os.environ, {"LOCALAPPDATA": self.temp.name}):
            ui = importlib.import_module("sift.ui")
        with (
            patch.object(ui, "DB_PATH", self.db_path),
            patch.object(ui, "LEGACY_DB_PATH", str(Path(self.temp.name) / "no-legacy.db")),
        ):
            window = ui.MainWindow()
            window.find_exact_duplicates()
            worker = window.duplicate_worker
            loop = QEventLoop()
            worker.finished.connect(loop.quit)
            QTimer.singleShot(5000, loop.quit)
            loop.exec()
            worker.wait()

        report = window.report.toPlainText()
        self.assertIn("Found 1 exact duplicate group", report)
        self.assertIn(first, report)
        self.assertIn(second, report)
        self.assertIn("SHA-256 " + "d" * 64, report)
        self.assertIn("Rescan to refresh", report)
        self.assertIn("all saved library folders", report)
        self.assertIn("0 empty files (not listed as duplicates)", report)
        window.close()


if __name__ == "__main__":
    unittest.main()
