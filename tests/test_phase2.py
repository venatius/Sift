import hashlib
import importlib
import os
import sqlite3
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from sift import database, fingerprint, metadata
from sift.scanner import scan_folder
from sift.worker import ScanWorker


class PhaseTwoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt_app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "library"
        self.root.mkdir()
        self.db_path = str(Path(self.temp.name) / "sift.db")
        conn = database.connect(self.db_path)
        database.init_db(conn)
        conn.close()

    def tearDown(self):
        self.temp.cleanup()

    def run_worker(self, force_rehash=False):
        worker = ScanWorker(str(self.root), self.db_path, force_rehash=force_rehash)
        results = []
        worker.scan_done.connect(results.append)
        worker.run()
        self.assertEqual(len(results), 1)
        return results[0]

    def test_hash_empty_small_multichunk_and_progress(self):
        path = Path(self.temp.name) / "bytes.bin"
        callbacks = []
        for value in (b"", b"abc", b"abcdefgh"):
            path.write_bytes(value)
            with patch.object(fingerprint, "CHUNK", 3):
                actual = fingerprint.sha256_file(path, progress_callback=callbacks.append)
            self.assertEqual(actual, hashlib.sha256(value).hexdigest())
        self.assertIn(3, callbacks)
        self.assertIn(8, callbacks)

    def test_hash_cancel_between_chunks(self):
        path = Path(self.temp.name) / "large.bin"
        path.write_bytes(b"abcdefgh")
        calls = []

        def stop_after_first_chunk():
            calls.append(True)
            return len(calls) > 1

        with patch.object(fingerprint, "CHUNK", 3):
            self.assertIsNone(fingerprint.sha256_file(path, stop_after_first_chunk))

    def test_metadata_success_corrupt_and_unsupported(self):
        image_path = self.root / "photo.jpg"
        Image.new("RGB", (17, 11), "red").save(image_path)
        result = metadata.extract_image_metadata(str(image_path))
        self.assertEqual((result.status, result.detected_format, result.width, result.height),
                         ("ok", "JPEG", 17, 11))

        corrupt = self.root / "broken.jpg"
        corrupt.write_bytes(b"not an image")
        self.assertEqual(metadata.extract_image_metadata(str(corrupt)).status, "failed")
        self.assertEqual(metadata.extract(str(corrupt), None, lambda: False).status,
                         "unsupported")

    def test_corrupt_raw_and_unsupported_extension_statuses(self):
        corrupt_raw = self.root / "broken.dng"
        corrupt_raw.write_bytes(b"not a RAW image")
        raw_kind = metadata.kind_for(str(corrupt_raw))
        self.assertEqual(raw_kind, "raw")
        self.assertEqual(metadata.extract(str(corrupt_raw), raw_kind,
                                          lambda: False).status, "failed")

        unsupported = self.root / "unknown.xyz"
        unsupported.write_bytes(b"not a supported media file")
        unsupported_kind = metadata.kind_for(str(unsupported))
        self.assertIsNone(unsupported_kind)
        self.assertEqual(metadata.extract(str(unsupported), unsupported_kind,
                                          lambda: False).status, "unsupported")

    def test_content_signature_overrides_unfamiliar_extension(self):
        image_path = self.root / "photo.payload"
        Image.new("RGB", (8, 6), "blue").save(image_path, format="PNG")
        self.assertEqual(metadata.kind_for(str(image_path)), "image")
        self.assertEqual(metadata.extract_image_metadata(str(image_path)).status, "ok")

        video_path = self.root / "clip.payload"
        video_path.write_bytes(b"\x00\x00\x00\x18ftypisom" + b"\x00" * 4)
        self.assertEqual(metadata.kind_for(str(video_path)), "video")

    def test_video_missing_tool_and_malformed_output(self):
        with patch.object(metadata, "ffprobe_path", return_value=None):
            self.assertIn("ffprobe not found", metadata.extract_video_metadata(
                str(self.root / "missing.mp4"), lambda: False).error)
        with patch.object(metadata, "ffprobe_path", return_value="ffprobe"), \
                patch.object(metadata, "_run_ffprobe", return_value=(0, b"{bad", b"")):
            self.assertEqual(metadata.extract_video_metadata(
                str(self.root / "bad.mp4"), lambda: False).status, "failed")

        audio_only = b'{"streams":[{"codec_type":"audio"}],"format":{}}'
        with patch.object(metadata, "ffprobe_path", return_value="ffprobe"), \
                patch.object(metadata, "_run_ffprobe", return_value=(0, audio_only, b"")):
            result = metadata.extract_video_metadata(
                str(self.root / "audio-only.mp4"), lambda: False)
            self.assertEqual((result.status, result.media_kind), ("ok", "audio"))

        stream_data = (b'{"streams":[{"codec_type":"audio","codec_name":"aac",'
                       b'"sample_rate":"48000","channels":2,"channel_layout":"stereo",'
                       b'"bit_rate":"128000"}],"format":{"format_name":"mov,mp4",'
                       b'"duration":"2.5"}}')
        with patch.object(metadata, "ffprobe_path", return_value="ffprobe"), \
                patch.object(metadata, "_run_ffprobe", return_value=(0, stream_data, b"")):
            result = metadata.extract_video_metadata(
                str(self.root / "audio-only.mp4"), lambda: False)
        self.assertEqual((result.audio_codec, result.audio_sample_rate,
                          result.audio_channels, result.audio_channel_layout,
                          result.audio_bit_rate, result.duration_seconds),
                         ("aac", 48000, 2, "stereo", 128000, 2.5))

    def test_raw_decode_extracts_metadata_without_rendering(self):
        self.assertEqual(metadata.extractor_info("raw"), ("rawpy", "0.27.1+sift2"))

        class RawOther:
            @property
            def timestamp(self):
                raise RuntimeError("optional metadata unavailable")

        class RawImage:
            sizes = type("Sizes", (), {"width": 4000, "height": 3000})()
            other = RawOther()

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

        fake_rawpy = type("RawPy", (), {
            "__version__": "test",
            "imread": staticmethod(lambda path: RawImage()),
            "postprocess": staticmethod(lambda *args: self.fail("must not render")),
        })
        for extension in (".dng", ".nef", ".arw"):
            path = self.root / f"raw{extension}"
            path.write_bytes(b"II*\x00synthetic raw fixture")
            self.assertEqual(metadata.kind_for(str(path)), "raw")
            with patch.object(metadata, "rawpy", fake_rawpy):
                result = metadata.extract(str(path), "raw", lambda: False)
            self.assertEqual((result.status, result.media_kind, result.width, result.height),
                             ("ok", "image", 4000, 3000))

    def test_database_schema_v3_has_audio_fields(self):
        conn = database.connect(self.db_path)
        self.assertEqual(conn.execute("PRAGMA user_version").fetchone()[0], 3)
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(media_metadata)")}
        self.assertTrue({"audio_codec", "audio_sample_rate", "audio_channels",
                         "audio_channel_layout", "audio_bit_rate"}.issubset(columns))
        conn.close()

    def test_database_migration_preserves_phase1_records_and_enforces_fks(self):
        old_path = Path(self.temp.name) / "phase1.db"
        old = sqlite3.connect(old_path)
        old.executescript("""
            CREATE TABLE roots (id INTEGER PRIMARY KEY, path TEXT NOT NULL UNIQUE, added_at REAL NOT NULL);
            CREATE TABLE files (id INTEGER PRIMARY KEY, root_id INTEGER NOT NULL REFERENCES roots(id),
                path TEXT NOT NULL, size INTEGER, modified REAL, status TEXT NOT NULL, error TEXT,
                last_seen REAL NOT NULL, UNIQUE(root_id, path));
            CREATE TABLE scans (id INTEGER PRIMARY KEY, root_id INTEGER NOT NULL REFERENCES roots(id),
                started_at REAL NOT NULL, ended_at REAL, status TEXT NOT NULL);
            INSERT INTO roots VALUES (1, 'fixture-root', 1.0);
            INSERT INTO files VALUES (1, 1, 'fixture-root/file', 3, 1.0, 'ok', NULL, 1.0);
        """)
        old.commit()
        old.close()
        new_path = Path(self.temp.name) / "migrated.db"
        self.assertTrue(database.migrate_database(old_path, new_path))
        conn = database.connect(new_path)
        database.init_db(conn)
        self.assertEqual(conn.execute("SELECT path FROM files WHERE id=1").fetchone()[0],
                         "fixture-root/file")
        self.assertEqual(conn.execute("PRAGMA foreign_keys").fetchone()[0], 1)
        with self.assertRaises(sqlite3.IntegrityError):
            conn.execute("INSERT INTO files(root_id,path,status,last_seen) VALUES (99,'x','ok',1)")
        conn.close()
        self.assertTrue(old_path.exists())

    def test_cache_reuse_and_force_rehash(self):
        (self.root / "one.bin").write_bytes(b"same data")
        first = self.run_worker()
        second = self.run_worker()
        self.assertEqual(first["fp_done"], 1)
        self.assertEqual(second["fp_reused"], 1)
        forced = self.run_worker(force_rehash=True)
        self.assertEqual(forced["fp_done"], 1)

    def test_worker_emits_byte_progress(self):
        (self.root / "progress.bin").write_bytes(b"p" * (2 * 1024 * 1024))
        worker = ScanWorker(str(self.root), self.db_path)
        progress = []
        worker.stage_progress.connect(lambda stage, current, total:
                                       progress.append((stage, current, total)))
        worker.run()
        self.assertTrue(progress)
        self.assertEqual(progress[-1], ("fingerprint", 2 * 1024 * 1024,
                                        2 * 1024 * 1024))

    def test_metadata_and_fingerprint_fail_independently(self):
        (self.root / "one.bin").write_bytes(b"payload")
        with patch.object(metadata, "extract", side_effect=RuntimeError("metadata fault")):
            result = self.run_worker()
        self.assertEqual(result["meta_failed"], 1)
        self.assertEqual(result["fp_done"], 1)

        (self.root / "one.bin").write_bytes(b"new payload")
        with patch.object(fingerprint, "sha256_file", side_effect=RuntimeError("hash fault")):
            result = self.run_worker()
        self.assertEqual(result["meta_unsupported"], 1)
        self.assertEqual(result["fp_failed"], 1)
        conn = database.connect(self.db_path)
        self.assertEqual(conn.execute("SELECT status FROM fingerprints").fetchone()[0], "failed")
        conn.close()

    def test_changed_during_hash_is_not_saved_as_success(self):
        path = self.root / "changing.bin"
        path.write_bytes(b"before")

        def mutate_then_hash(file_path, should_stop, progress_callback):
            digest = hashlib.sha256(Path(file_path).read_bytes()).hexdigest()
            Path(file_path).write_bytes(b"after!")
            return digest

        with patch.object(fingerprint, "sha256_file", side_effect=mutate_then_hash):
            result = self.run_worker()
        self.assertEqual(result["fp_failed"], 1)
        conn = database.connect(self.db_path)
        row = conn.execute("SELECT status, sha256 FROM fingerprints").fetchone()
        self.assertEqual((row["status"], row["sha256"]), ("failed", ""))
        self.assertEqual(conn.execute("SELECT status FROM files").fetchone()[0], "retry")
        conn.close()

    def test_changed_during_metadata_is_not_saved_as_success(self):
        path = self.root / "changing.png"
        Image.new("RGB", (4, 4), "green").save(path)

        def mutate_then_extract(file_path, kind, cancel_check):
            Path(file_path).write_bytes(b"changed content")
            return metadata.MetadataResult("ok", "image", "PNG")

        with patch.object(metadata, "extract", side_effect=mutate_then_extract):
            result = self.run_worker()
        self.assertGreaterEqual(result["meta_failed"], 1)
        conn = database.connect(self.db_path)
        self.assertEqual(conn.execute("SELECT status FROM media_metadata").fetchone()[0], "failed")
        self.assertEqual(conn.execute("SELECT status FROM files").fetchone()[0], "retry")
        conn.close()

    def test_root_symlink_is_not_followed(self):
        outside = Path(self.temp.name) / "outside"
        outside.mkdir()
        (outside / "secret.txt").write_text("fixture")
        link = Path(self.temp.name) / "linked-root"
        try:
            link.symlink_to(outside, target_is_directory=True)
        except OSError as error:
            self.skipTest(f"Symlink creation unavailable: {error}")
        items = list(scan_folder(str(link)))
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].status, "skipped")

    def test_offscreen_ui_reports_progress_errors_and_persistence(self):
        (self.root / "broken.jpg").write_bytes(b"not an image")
        (self.root / "notes.txt").write_text("fixture")
        with patch.dict("os.environ", {"LOCALAPPDATA": str(Path(self.temp.name) / "appdata")}):
            ui = importlib.import_module("sift.ui")
        with patch.object(ui, "DB_PATH", self.db_path), \
                patch.object(ui, "LEGACY_DB_PATH", str(Path(self.temp.name) / "no-legacy.db")):
            window = ui.MainWindow()
            window.folder = str(self.root)
            window.start_scan()
            deadline = time.monotonic() + 10
            while window.thread is not None and time.monotonic() < deadline:
                self.qt_app.processEvents()
                time.sleep(0.01)
            self.qt_app.processEvents()
            self.assertIsNone(window.thread)
            self.assertEqual(window.count_label.text(), "Files found: 2")
            self.assertIn("unsupported", window.report.toPlainText().lower())
            self.assertIn("failed", window.report.toPlainText().lower())
            self.assertIn("errors", window.status_label.text().lower())
            conn = database.connect(self.db_path)
            self.assertEqual(database.count_files(conn), 2)
            conn.close()
            window.close()

    def test_offscreen_ui_cancellation_keeps_inventory(self):
        (self.root / "large.bin").write_bytes(b"fixture")
        with patch.dict("os.environ", {"LOCALAPPDATA": str(Path(self.temp.name) / "appdata")}):
            ui = importlib.import_module("sift.ui")
        started = threading.Event()

        def waiting_hash(path, should_stop=None, progress_callback=None):
            started.set()
            while not should_stop():
                time.sleep(0.005)
            return None

        with patch.object(ui, "DB_PATH", self.db_path), \
                patch.object(ui, "LEGACY_DB_PATH", str(Path(self.temp.name) / "no-legacy.db")), \
                patch.object(fingerprint, "sha256_file", side_effect=waiting_hash):
            window = ui.MainWindow()
            window.folder = str(self.root)
            window.start_scan()
            deadline = time.monotonic() + 5
            while not started.is_set() and time.monotonic() < deadline:
                self.qt_app.processEvents()
                time.sleep(0.005)
            self.assertTrue(started.is_set())
            self.qt_app.processEvents()
            self.assertEqual(window.count_label.text(), "Files found: 1")
            window.cancel_scan()
            deadline = time.monotonic() + 5
            while window.thread is not None and time.monotonic() < deadline:
                self.qt_app.processEvents()
                time.sleep(0.005)
            self.qt_app.processEvents()
            self.assertIsNone(window.thread)
            self.assertIn("cancelled", window.status_label.text().lower())
            conn = database.connect(self.db_path)
            self.assertEqual(database.count_files(conn), 1)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM fingerprints").fetchone()[0], 0)
            conn.close()
            window.close()

if __name__ == "__main__":
    unittest.main()
