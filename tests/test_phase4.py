"""Synthetic Phase 4 regressions; no real user library is accessed."""

import hashlib
import io
import os
import sqlite3
import tempfile
import time
import tracemalloc
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from sift import database, image_analysis, image_store, visual_match
from sift.image_browser import ImageBrowser
from sift.image_worker import ImageWorker, prepare
from sift.worker import ScanWorker


class ImageReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt_app = QApplication.instance() or QApplication([])

    def wait_for(self, condition, timeout=10):
        deadline = time.monotonic() + timeout
        while not condition() and time.monotonic() < deadline:
            self.qt_app.processEvents()
            time.sleep(0.005)
        self.qt_app.processEvents()
        self.assertTrue(condition(), "background UI operation exceeded its deadline")

    def setUp(self):
        sandbox = Path(__file__).resolve().parents[1] / "test_data_auto"
        sandbox.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=sandbox)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "images"
        self.root.mkdir()
        self.db_path = str(Path(self.temp.name) / "library.db")
        conn = database.connect(self.db_path)
        database.init_db(conn)
        conn.close()

    def picture(self, name="pattern.png", size=(64, 48), image_format="PNG"):
        path = self.root / name
        image = Image.new("RGB", size)
        image.putdata(
            [
                ((x * 13 + y * 7) % 256, (x * 3) % 256, (y * 5) % 256)
                for y in range(size[1])
                for x in range(size[0])
            ]
        )
        image.save(path, format=image_format)
        return path

    def scan(self):
        worker = ScanWorker(str(self.root), self.db_path)
        summaries = []
        worker.scan_done.connect(summaries.append)
        worker.run()
        self.assertEqual(summaries[0]["status"], "completed")
        return summaries[0]

    def analyze(self, path, **kwargs):
        info = path.stat()
        return image_analysis.analyze(
            str(path), str(self.root), info.st_size, info.st_mtime_ns, **kwargs
        )

    def matching_fixture(self):
        original = self.picture("original.png")
        (self.root / "exact.png").write_bytes(original.read_bytes())
        with Image.open(original) as image:
            image.save(self.root / "reencoded.png", compress_level=0)
        Image.new("RGB", (64, 48), "white").save(self.root / "flat.png")
        self.scan()
        prepare(self.db_path)
        conn = database.connect_readonly(self.db_path)
        try:
            row = conn.execute("SELECT id FROM files WHERE path = ?", (str(original),)).fetchone()
            return row[0]
        finally:
            conn.close()

    def test_similarity_excludes_exact_and_flat_and_never_opens_sources(self):
        file_id = self.matching_fixture()
        for path in self.root.iterdir():
            path.unlink()
        conn = database.connect_readonly(self.db_path)
        try:
            with (
                patch("builtins.open", side_effect=AssertionError("media read")),
                patch.object(
                    image_analysis.os, "stat", side_effect=AssertionError("filesystem check")
                ),
            ):
                result = visual_match.find_matches(conn, file_id)
            self.assertEqual(
                [Path(row["path"]).name for row in result["matches"]], ["reencoded.png"]
            )
            self.assertEqual(result["matches"][0]["distance"], 0)
            with self.assertRaises(sqlite3.OperationalError):
                conn.execute("DELETE FROM image_features")
            conn.rollback()
            with self.assertRaises(image_analysis.AnalysisCancelled):
                visual_match.find_matches(conn, file_id, cancel=lambda: True)
            self.assertFalse(conn.in_transaction)
        finally:
            conn.close()

    def test_similarity_rejects_stale_features_and_colour_aspect_hash_outliers(self):
        file_id = self.matching_fixture()
        for assignment in (
            "version = 'old'",
            "input_sha256 = 'old'",
            "input_size = 0",
            "dhash = 'ffffffffffffffff'",
            "red = 999",
            "height = 1",
        ):
            conn = database.connect(self.db_path)
            try:
                column = assignment.split(" = ")[0]
                before = list(conn.execute("SELECT file_id, " + column + " FROM image_features"))
                conn.execute(
                    "UPDATE image_features SET " + assignment + " WHERE file_id != ?", (file_id,)
                )
                conn.commit()
                self.assertEqual(visual_match.find_matches(conn, file_id)["matches"], [])
            finally:
                for row in before:
                    conn.execute(
                        "UPDATE image_features SET " + column + " = ? WHERE file_id = ?",
                        (row[1], row[0]),
                    )
                conn.commit()
                conn.close()

    def test_similarity_cross_root_deduplication_limit_and_midstream_cancel(self):
        file_id = self.matching_fixture()
        nested = self.root / "nested"
        nested.mkdir()
        with Image.open(self.root / "original.png") as image:
            image.save(nested / "candidate.png", compress_level=1)
        self.scan()
        worker = ScanWorker(str(nested), self.db_path)
        worker.run()
        prepare(self.db_path)
        conn = database.connect_readonly(self.db_path)
        try:
            result = visual_match.find_matches(conn, file_id)
            self.assertEqual(result["matched"], 2)
            self.assertEqual(len({row["path"] for row in result["matches"]}), 2)
            with patch.object(visual_match, "MAX_RESULTS", 1):
                result = visual_match.find_matches(conn, file_id)
            self.assertEqual(len(result["matches"]), 1)
            self.assertTrue(result["truncated"])
            nested_id = conn.execute(
                "SELECT id FROM roots WHERE path = ?", (str(nested),)
            ).fetchone()[0]
            candidate_id = conn.execute(
                "SELECT id FROM files WHERE root_id = ?", (nested_id,)
            ).fetchone()[0]
            self.assertEqual(
                visual_match.find_matches(conn, candidate_id, nested_id)["matches"], []
            )
            calls = []

            def cancel():
                calls.append(True)
                return len(calls) > 2

            with self.assertRaises(image_analysis.AnalysisCancelled):
                visual_match.find_matches(conn, file_id, cancel=cancel)
            self.assertFalse(conn.in_transaction)
        finally:
            conn.close()

    def test_similarity_ui_displays_candidates_without_accumulating_results(self):
        file_id = self.matching_fixture()
        browser = ImageBrowser(self.db_path)
        browser.open()
        try:
            browser.load_first_page()
            self.wait_for(lambda: browser.worker is None)
            for index in range(browser.tree.topLevelItemCount()):
                item = browser.tree.topLevelItem(index)
                if str(self.root / "original.png") == item.text(2):
                    browser.tree.setCurrentItem(item)
            self.assertTrue(browser.similar_btn.isEnabled())
            for _ in range(2):
                browser.find_similar()
                self.wait_for(lambda: browser.worker is None)
                self.assertEqual(browser.matches.topLevelItemCount(), 1)
            self.assertIn("saved features only", browser.details.toPlainText())
            browser.tree.setCurrentItem(browser.tree.topLevelItem(0))
            self.assertEqual(browser.matches.topLevelItemCount(), 0)
            self.assertGreater(file_id, 0)
        finally:
            browser.reject()

    def test_stress_ten_thousand_saved_candidates_have_bounded_results(self):
        file_id = self.matching_fixture()
        conn = database.connect(self.db_path)
        try:
            reference = conn.execute("SELECT * FROM files WHERE id = ?", (file_id,)).fetchone()
            for index in range(10_000):
                candidate_id = conn.execute(
                    """INSERT INTO files(root_id,path,size,modified,modified_ns,status,last_seen)
                       VALUES (?,?,?,?,?,'ok',0)""",
                    (
                        reference["root_id"],
                        str(self.root / f"stress-{index:05}.png"),
                        reference["size"],
                        reference["modified"],
                        reference["modified_ns"],
                    ),
                ).lastrowid
                digest = f"{index:064x}"
                conn.execute(
                    """INSERT INTO fingerprints
                       SELECT ?, ?, input_size,input_modified,input_modified_ns,
                              algorithm,algorithm_version,status,error,computed_at
                       FROM fingerprints WHERE file_id = ?""",
                    (candidate_id, digest, file_id),
                )
                conn.execute(
                    """INSERT INTO image_features
                       SELECT ?,version,input_size,input_modified_ns,?,'ok',NULL,
                              thumbnail,dhash,red,green,blue,width,height,low_detail
                       FROM image_features WHERE file_id = ?""",
                    (candidate_id, digest, file_id),
                )
            conn.commit()
        finally:
            conn.close()
        conn = database.connect_readonly(self.db_path)
        tracemalloc.start()
        started = time.monotonic()
        try:
            result = visual_match.find_matches(conn, file_id)
            _, peak = tracemalloc.get_traced_memory()
            self.assertEqual(result["matched"], 10_001)
            self.assertEqual(len(result["matches"]), 100)
            self.assertTrue(result["truncated"])
            self.assertLess(peak, 12 * 1024 * 1024)
            rows, more = image_store.browse(conn)
            self.assertEqual(len(rows), 60)
            self.assertTrue(more)
            print(
                f"Phase 4 stress: 10,001 candidates, {time.monotonic() - started:.3f}s, "
                f"Python peak {peak / 1024:.1f} KiB; 100 results, 60-row page"
            )
        finally:
            tracemalloc.stop()
            conn.close()

    def test_stress_background_batch_reuses_previews_and_keeps_event_loop_live(self):
        paths = [self.picture(f"batch-{index:03}.png", (128, 96)) for index in range(120)]
        before = [
            (hashlib.sha256(path.read_bytes()).hexdigest(), path.stat().st_mtime_ns)
            for path in paths
        ]
        self.scan()
        ticks = []
        timer = QTimer()
        timer.timeout.connect(lambda: ticks.append(time.monotonic()))
        timer.start(5)
        worker = ImageWorker(self.db_path, "prepare")
        results = []
        errors = []
        worker.result_ready.connect(results.append)
        worker.failed.connect(errors.append)
        started = time.monotonic()
        worker.start()
        try:
            self.wait_for(lambda: not worker.isRunning(), timeout=45)
            self.assertEqual(errors, [])
            self.assertEqual(results[0]["prepared"], 120)
            self.assertGreater(len(ticks), 1)
            self.assertEqual(prepare(self.db_path)["reused"], 120)
            self.assertEqual(
                before,
                [
                    (hashlib.sha256(path.read_bytes()).hexdigest(), path.stat().st_mtime_ns)
                    for path in paths
                ],
            )
            print(
                f"Phase 4 batch: 120 images, {time.monotonic() - started:.3f}s, "
                f"{len(ticks)} UI timer ticks; all originals preserved"
            )
        finally:
            timer.stop()
            worker.cancel()
            worker.wait(45_000)

    def test_animation_rejected_and_gps_ifd_never_traversed(self):
        animated = self.root / "animated.png"
        Image.new("RGB", (8, 8), "red").save(
            animated, save_all=True, append_images=[Image.new("RGB", (8, 8), "blue")]
        )
        with self.assertRaisesRegex(ValueError, "Animated"):
            self.analyze(animated)
        path = self.picture("gps-source.jpg", image_format="JPEG")
        exif = Image.Exif()
        exif[0x0112] = 6
        exif[0x8825] = {1: "N", 2: (1, 2, 3)}
        with Image.open(path) as image:
            image.save(self.root / "gps-exif.jpg", exif=exif)
        path = self.root / "gps-exif.jpg"
        with patch.object(Image.Exif, "get_ifd", side_effect=AssertionError("GPS IFD read")):
            features = self.analyze(path)
        with Image.open(io.BytesIO(features.thumbnail)) as thumbnail:
            self.assertEqual(thumbnail.getexif(), {})

    def test_cancel_keeps_completed_preview_and_restart_reuses_it(self):
        for index in range(3):
            self.picture(f"resume-{index}.png")
        self.scan()
        saved = []
        original_save = image_store.save

        def save_then_cancel(*args, **kwargs):
            original_save(*args, **kwargs)
            saved.append(True)

        with (
            patch.object(image_store, "save", side_effect=save_then_cancel),
            self.assertRaises(image_analysis.AnalysisCancelled),
        ):
            prepare(self.db_path, cancel=lambda: bool(saved))
        summary = prepare(self.db_path)
        self.assertEqual((summary["reused"], summary["prepared"]), (1, 2))

    def test_main_window_waits_for_browser_job_on_close(self):
        with patch.dict(os.environ, {"LOCALAPPDATA": str(Path(self.temp.name) / "appdata")}):
            from sift import image_worker, ui

        started = []

        def waiting_prepare(db_path, **options):
            started.append(True)
            while not options["cancel"]():
                time.sleep(0.005)
            raise image_analysis.AnalysisCancelled

        with (
            patch.object(ui, "DB_PATH", self.db_path),
            patch.object(ui, "LEGACY_DB_PATH", str(Path(self.temp.name) / "absent.db")),
        ):
            window = ui.MainWindow()
            window.show()
            window.browse_library()
            browser = window.image_browser
            self.wait_for(lambda: browser.worker is None)
            with patch.object(image_worker, "prepare", side_effect=waiting_prepare):
                browser.prepare_images()
                self.wait_for(lambda: bool(started))
                window.close()
                self.wait_for(lambda: window.image_browser is None)
            self.assertFalse(window.isVisible())
            window.deleteLater()

    def test_decode_content_orientation_transparency_and_original_preservation(self):
        path = self.picture("disguised.xyz", (400, 200), "JPEG")
        before = (hashlib.sha256(path.read_bytes()).hexdigest(), path.stat().st_mtime_ns)
        result = self.analyze(path, orientation=6)
        self.assertEqual((result.width, result.height), (128, 256))
        with Image.open(io.BytesIO(result.thumbnail)) as preview:
            self.assertEqual(preview.info, {})
        self.assertEqual(
            before, (hashlib.sha256(path.read_bytes()).hexdigest(), path.stat().st_mtime_ns)
        )
        transparent = self.root / "transparent.png"
        Image.new("RGBA", (10, 10), (255, 0, 0, 0)).save(transparent)
        result = self.analyze(transparent)
        self.assertEqual((result.red, result.green, result.blue), (255, 255, 255))
        self.assertTrue(result.low_detail)

    def test_decode_limits_and_cancellation(self):
        path = self.picture()
        with patch.object(image_analysis, "MAX_PIXELS", 100), self.assertRaises(ValueError):
            self.analyze(path)
        with patch.object(image_analysis, "MAX_BYTES", 1), self.assertRaises(ValueError):
            self.analyze(path)
        with self.assertRaises(image_analysis.AnalysisCancelled):
            self.analyze(path, cancel=lambda: True)
        path.write_bytes(b"corrupt image")
        with self.assertRaises(OSError):
            self.analyze(path)

    def test_root_and_ancestor_links_are_rejected(self):
        path = self.picture()
        link = self.root.parent / "linked-root"
        try:
            link.symlink_to(self.root, target_is_directory=True)
        except OSError as error:
            self.skipTest(str(error))
        with self.assertRaises(OSError):
            image_analysis.source_signature(str(link / path.name), str(link))
        nested = self.root / "nested-link"
        nested.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(OSError):
            image_analysis.source_signature(str(nested / path.name), str(self.root))

    def test_embedded_orientation_and_metadata_not_copied_through_preparation(self):
        path = self.root / "oriented.xyz"
        image = Image.new("RGB", (40, 20), "red")
        exif = Image.Exif()
        exif[274] = 6
        exif[271] = "Synthetic camera"
        image.save(path, format="JPEG", exif=exif)
        self.scan()
        self.assertEqual(prepare(self.db_path)["prepared"], 1)
        conn = database.connect_readonly(self.db_path)
        row = image_store.browse(conn)[0][0]
        conn.close()
        with Image.open(io.BytesIO(row["thumbnail"])) as thumbnail:
            self.assertEqual(thumbnail.size, (20, 40))
            self.assertEqual(thumbnail.info, {})
            self.assertEqual(len(thumbnail.getexif()), 0)

    def test_changed_decode_identity_race_and_late_cancellation_are_not_saved(self):
        path = self.picture()
        self.scan()
        original_thumbnail = Image.Image.thumbnail

        def mutate_after_thumbnail(image, *args, **kwargs):
            original_thumbnail(image, *args, **kwargs)
            path.write_bytes(b"changed during decode")

        with patch.object(Image.Image, "thumbnail", new=mutate_after_thumbnail):
            result = prepare(self.db_path)
        self.assertEqual(result["failed"], 1)
        conn = database.connect_readonly(self.db_path)
        self.assertIsNone(image_store.browse(conn)[0][0]["thumbnail"])
        conn.close()

        self.picture()
        self.scan()
        signature = image_analysis.source_signature(str(path), str(self.root))
        with (
            patch.object(
                image_analysis,
                "source_signature",
                return_value=(*signature[:3], signature[3] + 1),
            ),
            self.assertRaises(OSError),
        ):
            self.analyze(path)

        decoded = []

        def cancel_after_thumbnail(image, *args, **kwargs):
            original_thumbnail(image, *args, **kwargs)
            decoded.append(True)

        with (
            patch.object(Image.Image, "thumbnail", new=cancel_after_thumbnail),
            self.assertRaises(image_analysis.AnalysisCancelled),
        ):
            prepare(self.db_path, force=True, cancel=lambda: bool(decoded))
        self.assertTrue(decoded)
        conn = database.connect_readonly(self.db_path)
        self.assertEqual(
            conn.execute("SELECT COUNT(*) FROM image_features WHERE status = 'ok'").fetchone()[0], 0
        )
        conn.close()

    def test_corrupt_supported_and_unsupported_statuses_are_separate(self):
        (self.root / "corrupt.jpg").write_bytes(b"not JPEG")
        (self.root / "unknown.xyz").write_bytes(b"unsupported")
        self.scan()
        summary = prepare(self.db_path)
        self.assertEqual((summary["failed"], summary["unsupported"]), (1, 1))
        conn = database.connect_readonly(self.db_path)
        self.assertEqual(len(image_store.browse(conn, status="failed")[0]), 1)
        self.assertEqual(len(image_store.browse(conn, status="unsupported")[0]), 1)
        conn.close()

    def test_migration_backup_is_idempotent_and_preserves_core(self):
        self.picture()
        self.scan()
        conn = image_store.install(self.db_path)
        self.assertEqual(conn.execute("PRAGMA user_version").fetchone()[0], 3)
        self.assertEqual(conn.execute("PRAGMA foreign_keys").fetchone()[0], 1)
        count = database.count_files(conn)
        conn.close()
        backups = list(Path(self.temp.name).glob("*.bak"))
        self.assertEqual(len(backups), 1)
        old = database.connect(str(backups[0]))
        self.assertFalse(image_store.installed(old))
        self.assertEqual(database.count_files(old), count)
        old.close()
        conn = image_store.install(self.db_path)
        self.assertEqual(database.count_files(conn), count)
        self.assertEqual(len(list(Path(self.temp.name).glob("*.bak"))), 1)
        with self.assertRaises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO image_features VALUES (999,'v',1,1,'x','ok',"
                "NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL)"
            )
        conn.close()

    def test_cache_reuse_refresh_version_and_verified_digest(self):
        path = self.picture()
        self.scan()
        self.assertEqual(prepare(self.db_path)["prepared"], 1)
        self.assertEqual(prepare(self.db_path)["reused"], 1)
        self.assertEqual(prepare(self.db_path, force=True)["prepared"], 1)
        conn = database.connect(self.db_path)
        conn.execute("UPDATE image_features SET version = 'obsolete'")
        conn.commit()
        conn.close()
        self.assertEqual(prepare(self.db_path)["prepared"], 1)
        conn = database.connect(self.db_path)
        conn.execute("UPDATE fingerprints SET sha256 = ?", ("f" * 64,))
        conn.commit()
        self.assertEqual(image_store.browse(conn)[0][0]["image_status"], "pending")
        conn.close()
        self.assertEqual(prepare(self.db_path)["prepared"], 1)
        path.write_bytes(b"changed")
        self.assertEqual(prepare(self.db_path)["failed"], 1)
        conn = database.connect(self.db_path)
        self.assertIsNone(image_store.browse(conn)[0][0]["thumbnail"])
        conn.close()

    def test_per_file_failure_and_missing_source_do_not_abort_preparation(self):
        missing = self.picture("missing.png")
        self.picture("good.png")
        self.scan()
        missing.unlink()
        result = prepare(self.db_path)
        self.assertEqual((result["prepared"], result["failed"]), (1, 1))
        with (
            patch.object(image_store, "save", side_effect=sqlite3.OperationalError("disk")),
            self.assertRaises(sqlite3.OperationalError),
        ):
            prepare(self.db_path, force=True)

    def test_browse_combined_filters_literal_search_and_pagination(self):
        self.picture("100%_photo.png")
        self.picture("other.png")
        self.scan()
        conn = database.connect_readonly(self.db_path)
        rows, more = image_store.browse(conn, text="%_")
        self.assertEqual(len(rows), 1)
        self.assertFalse(more)
        self.assertEqual(rows[0]["image_status"], "pending")
        conn.close()
        prepare(self.db_path)
        conn = database.connect_readonly(self.db_path)
        root_id = image_store.roots(conn)[0]["id"]
        rows, more = image_store.browse(conn, root_id=root_id, text="%_", status="ready")
        self.assertEqual(len(rows), 1)
        self.assertEqual(image_store.browse(conn, root_id=-1)[0], [])
        with patch.object(image_store, "PAGE_SIZE", 1):
            first, more = image_store.browse(conn)
            self.assertTrue(more)
            second, more = image_store.browse(conn, after=first[0]["id"])
            self.assertFalse(more)
            self.assertNotEqual(first[0]["id"], second[0]["id"])
        conn.close()

    def test_background_browser_filters_and_preparation_display(self):
        self.picture("100%_photo.png")
        self.picture("other.png")
        self.scan()
        browser = ImageBrowser(self.db_path)
        browser.open()
        try:
            browser.load_first_page()
            self.assertFalse(browser.apply_btn.isEnabled())
            self.wait_for(lambda: browser.worker is None)
            self.assertEqual(browser.tree.topLevelItemCount(), 2)
            browser.prepare_images()
            self.wait_for(lambda: browser.worker is None)
            self.assertIn("Preparation complete", browser.details.toPlainText())
            browser.search.setText("%_")
            browser.status_filter.setCurrentIndex(browser.status_filter.findData("ready"))
            browser.load_first_page()
            self.wait_for(lambda: browser.worker is None)
            self.assertEqual(browser.tree.topLevelItemCount(), 1)
            self.assertFalse(browser.tree.topLevelItem(0).icon(0).isNull())
            browser.tree.setCurrentItem(browser.tree.topLevelItem(0))
            self.assertIn("100%_photo.png", browser.details.toPlainText())
        finally:
            browser.reject()

    def test_browser_close_cancels_active_job_and_keeps_worker_alive_until_finished(self):
        from sift import image_worker

        started = []

        def waiting_prepare(db_path, **options):
            started.append(True)
            while not options["cancel"]():
                time.sleep(0.005)
            raise image_analysis.AnalysisCancelled

        browser = ImageBrowser(self.db_path)
        browser.open()
        with patch.object(image_worker, "prepare", side_effect=waiting_prepare):
            browser.prepare_images()
            self.wait_for(lambda: bool(started))
            browser.reject()
            self.assertIsNotNone(browser.worker)
            self.wait_for(lambda: browser.worker is None)
        self.assertFalse(browser.isVisible())

    def test_browser_database_failure_is_visible_and_controls_recover(self):
        browser = ImageBrowser(str(Path(self.temp.name) / "does-not-exist.db"))
        browser.open()
        browser.load_first_page()
        self.wait_for(lambda: browser.worker is None)
        self.assertEqual(browser.status_label.text(), "Image job failed")
        self.assertTrue(browser.details.toPlainText())
        self.assertTrue(browser.apply_btn.isEnabled())
        browser.reject()

    def test_browser_failed_page_and_changed_filter_preserve_pagination(self):
        self.picture("first.png")
        self.picture("second.png")
        self.scan()
        browser = ImageBrowser(self.db_path)
        browser.open()
        try:
            with patch.object(image_store, "PAGE_SIZE", 1):
                browser.load_first_page()
                self.wait_for(lambda: browser.worker is None)
                first_id = browser._rows[0]["id"]
                self.assertTrue(browser.next_btn.isEnabled())
                with patch.object(
                    image_store, "browse", side_effect=sqlite3.OperationalError("fault")
                ):
                    browser.next_page()
                    self.wait_for(lambda: browser.worker is None)
                self.assertEqual(browser._after, 0)
                self.assertEqual(browser._history, [])
                self.assertEqual(browser._rows[0]["id"], first_id)
                with patch.object(
                    image_store, "browse", side_effect=image_analysis.AnalysisCancelled
                ):
                    browser.next_page()
                    self.wait_for(lambda: browser.worker is None)
                self.assertEqual(browser._after, 0)
                browser.next_page()
                self.wait_for(lambda: browser.worker is None)
                second_id = browser._rows[0]["id"]
                self.assertNotEqual(first_id, second_id)
                for error in (
                    sqlite3.OperationalError("fault"),
                    image_analysis.AnalysisCancelled(),
                ):
                    with patch.object(image_store, "browse", side_effect=error):
                        browser.previous_page()
                        self.wait_for(lambda: browser.worker is None)
                    self.assertEqual(browser._rows[0]["id"], second_id)
                    self.assertEqual(browser._history, [0])
                browser.previous_page()
                self.wait_for(lambda: browser.worker is None)
                self.assertEqual(browser._rows[0]["id"], first_id)
                browser.search.setText("second")
                self.assertFalse(browser.next_btn.isEnabled())
                browser.load_first_page()
                self.wait_for(lambda: browser.worker is None)
                self.assertIn("second.png", browser._rows[0]["path"])
                self.assertEqual(browser._history, [])
        finally:
            browser.reject()
