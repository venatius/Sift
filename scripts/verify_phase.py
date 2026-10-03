"""Run repeatable, synthetic end-of-phase verification for Sift."""

import ast
import hashlib
import os
import re
import shutil
import stat
import subprocess
import sys
import traceback
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUTO_ROOT = ROOT / "test_data_auto"
LIBRARY_ROOT = AUTO_ROOT / "library"
APP_DATA_ROOT = AUTO_ROOT / "_appdata"
TEMP_ROOT = AUTO_ROOT / "_temp"
REPORT_PATH = AUTO_ROOT / "verify_report.md"


@dataclass
class CheckResult:
    name: str
    status: str
    detail: str


class Verification:
    def __init__(self):
        self.results = []
        self.notes = []
        self.command_logs = []

    def record(self, name, passed, detail):
        status = "PASS" if passed else "FAIL"
        self.results.append(CheckResult(name, status, str(detail)))

    def skip(self, name, detail):
        self.results.append(CheckResult(name, "SKIPPED", str(detail)))

    def fail(self, name, detail):
        self.record(name, False, detail)

    def report_text(self):
        lines = [
            "# Sift phase verification report",
            "",
            f"Repository: `{ROOT}`",
            "Fixture source: generated synthetic files under `test_data_auto/library/`.",
            "The real user database and files outside the repository were not used.",
            "",
            "## Checks",
            "",
        ]
        for result in self.results:
            lines.append(f"- **{result.status}: {result.name}** — {result.detail}")
        lines.extend(("", "## Scan details", ""))
        if self.notes:
            lines.extend(f"- {note}" for note in self.notes)
        else:
            lines.append("- No additional notes.")
        if self.command_logs:
            lines.extend(("", "## Command output logs", ""))
            lines.extend(f"- `{path.relative_to(ROOT).as_posix()}`" for path in self.command_logs)
        failed = [result for result in self.results if result.status == "FAIL"]
        skipped = [result for result in self.results if result.status == "SKIPPED"]
        lines.extend(("", "## Summary", ""))
        lines.append(
            f"{len(self.results) - len(failed) - len(skipped)} passed, "
            f"{len(failed)} failed, {len(skipped)} skipped."
        )
        if failed:
            lines.append("Exact failing checks:")
            lines.extend(f"- {result.name}: {result.detail}" for result in failed)
        if failed:
            lines.append("Overall result: **FAIL**.")
        elif skipped:
            lines.append("Overall result: **PASS WITH SKIPPED CHECKS**.")
        else:
            lines.append("Overall result: **PASS**.")
        return "\n".join(lines) + "\n"


def safe_prepare_fixture_root():
    expected = (ROOT / "test_data_auto").absolute()
    if AUTO_ROOT.absolute() != expected or AUTO_ROOT.parent.resolve() != ROOT.resolve():
        raise RuntimeError("Refusing to prepare fixtures outside the repository root")
    if AUTO_ROOT.is_symlink() or (hasattr(os.path, "isjunction") and os.path.isjunction(AUTO_ROOT)):
        raise RuntimeError("Refusing to remove a symlink or junction at test_data_auto/")
    if AUTO_ROOT.exists():
        if not AUTO_ROOT.is_dir():
            raise RuntimeError("test_data_auto exists but is not a directory")
        shutil.rmtree(AUTO_ROOT)
    AUTO_ROOT.mkdir()
    LIBRARY_ROOT.mkdir()
    APP_DATA_ROOT.mkdir()
    TEMP_ROOT.mkdir()


def create_fixtures(verification):
    from PIL import Image

    nested = LIBRARY_ROOT / "subfolder"
    nested.mkdir()
    (LIBRARY_ROOT / "nested-empty" / "deeper-empty").mkdir(parents=True)

    identical_bytes = b"synthetic duplicate fixture\n"
    pair_a = LIBRARY_ROOT / "identical-a.bin"
    pair_b = nested / "identical-b.bin"
    pair_a.write_bytes(identical_bytes)
    pair_b.write_bytes(identical_bytes)
    (LIBRARY_ROOT / "unique.bin").write_bytes(b"unique synthetic file\n")
    (LIBRARY_ROOT / "empty-a.bin").write_bytes(b"")
    (LIBRARY_ROOT / "empty-b.bin").write_bytes(b"")
    near_copy = LIBRARY_ROOT / "near-copy.bin"
    near_copy.write_bytes(identical_bytes[:-2] + b"X\n")
    (LIBRARY_ROOT / ".hidden-fixture").write_bytes(b"hidden synthetic file\n")
    Image.new("RGB", (3, 2), (32, 96, 160)).save(LIBRARY_ROOT / "tiny.jpg", format="JPEG")
    Image.new("RGB", (2, 3), (160, 96, 32)).save(LIBRARY_ROOT / "tiny.png", format="PNG")
    (LIBRARY_ROOT / "corrupt.jpg").write_bytes(b"not a JPEG image")
    (LIBRARY_ROOT / "corrupt.dng").write_bytes(b"not a RAW image")
    (LIBRARY_ROOT / "unsupported.xyz").write_bytes(b"unsupported synthetic bytes")

    unreadable = LIBRARY_ROOT / "unreadable-folder"
    unreadable.mkdir()
    unreadable_mode = None
    try:
        original_mode = stat.S_IMODE(unreadable.stat().st_mode)
    except OSError as error:
        original_mode = None
        verification.skip(
            "Unreadable-folder handling",
            f"skipped: could not inspect fixture folder permissions ({error})",
        )
    if original_mode is not None:
        try:
            os.chmod(unreadable, 0)
        except OSError as error:
            verification.skip(
                "Unreadable-folder handling",
                f"skipped: could not change fixture folder permissions ({error})",
            )
        else:
            try:
                with os.scandir(unreadable):
                    pass
            except OSError as error:
                unreadable_mode = original_mode
                verification.notes.append(f"Unreadable-folder fixture enabled: {error}")
            else:
                os.chmod(unreadable, original_mode)
                verification.skip(
                    "Unreadable-folder handling",
                    "skipped: this platform/account could not make the fixture unreadable",
                )

    root_link = AUTO_ROOT / "selected-root-link"
    inner_link = LIBRARY_ROOT / "linked-subfolder"
    root_link_supported = False
    inner_link_supported = False
    try:
        root_link.symlink_to(LIBRARY_ROOT, target_is_directory=True)
        root_link_supported = True
    except (OSError, NotImplementedError) as error:
        verification.skip(
            "Selected-root symlink",
            f"skipped: this platform/account could not create directory symlinks ({error})",
        )
    try:
        inner_link.symlink_to(nested, target_is_directory=True)
        inner_link_supported = True
    except (OSError, NotImplementedError) as error:
        verification.skip(
            "Nested directory symlink",
            f"skipped: this platform/account could not create directory symlinks ({error})",
        )

    return {
        "pair_a": pair_a,
        "pair_b": pair_b,
        "pair_digest": hashlib.sha256(identical_bytes).hexdigest(),
        "near_copy": near_copy,
        "root_link": root_link if root_link_supported else None,
        "inner_link": inner_link if inner_link_supported else None,
        "unreadable": unreadable if unreadable_mode is not None else None,
        "unreadable_mode": unreadable_mode,
    }


def fixture_snapshot(root):
    snapshot = {}
    for current, directories, filenames in os.walk(root, followlinks=False):
        current_path = Path(current)
        directories[:] = [name for name in directories if not (current_path / name).is_symlink()]
        for filename in filenames:
            path = current_path / filename
            try:
                info = path.lstat()
                if not stat.S_ISREG(info.st_mode):
                    continue
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
            except OSError as error:
                raise RuntimeError(f"Could not snapshot fixture {path}: {error}") from error
            snapshot[path] = (digest, info.st_mtime_ns)
    return snapshot


def check(verification, name, passed, detail):
    verification.record(name, passed, detail)


def run_worker(worker_type, root, db_path):
    summaries = []
    worker = worker_type(str(root), str(db_path))
    worker.scan_done.connect(summaries.append)
    worker.run()
    if len(summaries) != 1:
        raise RuntimeError(f"worker returned {len(summaries)} summaries, expected one")
    return summaries[0]


def read_database(database, db_path, root_path):
    conn = database.connect(str(db_path))
    try:
        root_row = conn.execute("SELECT id FROM roots WHERE path = ?", (str(root_path),)).fetchone()
        if root_row is None:
            raise RuntimeError(f"scan root was not persisted: {root_path}")
        root_id = root_row["id"]
        rows = conn.execute(
            """
            SELECT files.path, media_metadata.status AS metadata_status,
                   fingerprints.sha256, fingerprints.status AS fingerprint_status
            FROM files
            LEFT JOIN media_metadata ON media_metadata.file_id = files.id
            LEFT JOIN fingerprints ON fingerprints.file_id = files.id
            WHERE files.root_id = ?
            ORDER BY files.path
            """,
            (root_id,),
        ).fetchall()
        fingerprint_counts = dict(
            conn.execute("SELECT status, COUNT(*) FROM fingerprints GROUP BY status").fetchall()
        )
        return rows, fingerprint_counts
    finally:
        conn.close()


def duplicate_results(database, db_path):
    if not callable(getattr(database, "get_exact_duplicate_groups", None)):
        return None
    if not callable(getattr(database, "connect_readonly", None)):
        return None
    conn = database.connect_readonly(str(db_path))
    try:
        return database.get_exact_duplicate_groups(conn)
    finally:
        conn.close()


def verify_behavior(verification, fixtures, before_snapshot):
    os.environ["LOCALAPPDATA"] = str(APP_DATA_ROOT)
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    os.environ["TEMP"] = str(TEMP_ROOT)
    os.environ["TMP"] = str(TEMP_ROOT)
    sys.path.insert(0, str(ROOT))

    try:
        from sift import database, metadata, ui
        from sift.scanner import scan_folder
        from sift.worker import ScanWorker
    except Exception as error:  # noqa: BLE001 - Report any import-time dependency failure.
        verification.fail("Load project scan modules", f"{type(error).__name__}: {error}")
        return

    expected_db = APP_DATA_ROOT / "Sift" / "sift.db"
    check(
        verification,
        "Application database is isolated under test_data_auto",
        Path(ui.DB_PATH).absolute() == expected_db.absolute()
        and Path(ui.DB_PATH).is_relative_to(AUTO_ROOT),
        f"LOCALAPPDATA={APP_DATA_ROOT}; database={ui.DB_PATH}; no real window created",
    )

    conn = database.connect(ui.DB_PATH)
    try:
        database.init_db(conn)
    finally:
        conn.close()

    if fixtures["root_link"] is not None:
        root_link_items = list(scan_folder(str(fixtures["root_link"])))
        root_link_safe = (
            len(root_link_items) == 1
            and root_link_items[0].status == "skipped"
            and "link" in (root_link_items[0].error or "").lower()
        )
        check(
            verification,
            "Selected-root symlink is not followed",
            root_link_safe,
            f"scanner returned {[(item.status, item.error) for item in root_link_items]}",
        )
    else:
        verification.skip("Selected-root symlink safety", "skipped: symlink creation unavailable")

    inventory = list(scan_folder(str(LIBRARY_ROOT)))
    if fixtures["inner_link"] is not None:
        link_path = os.path.normcase(os.path.abspath(str(fixtures["inner_link"])))
        link_prefix = link_path + os.sep
        link_not_followed = all(
            not os.path.normcase(os.path.abspath(item.path)).startswith(link_prefix)
            for item in inventory
        )
        check(
            verification,
            "Nested directory symlink is not followed",
            link_not_followed,
            f"inventory contains {len(inventory)} entries; link entry is not traversed",
        )
    else:
        verification.skip(
            "Nested directory symlink safety", "skipped: symlink creation unavailable"
        )
    if fixtures["unreadable"] is not None:
        unreadable_item = next(
            (item for item in inventory if item.path == str(fixtures["unreadable"])), None
        )
        check(
            verification,
            "Unreadable folder is recorded and does not stop scanning",
            unreadable_item is not None and unreadable_item.status == "failed",
            f"scanner result={unreadable_item}",
        )

    file_paths = {item.path for item in inventory}
    check(
        verification,
        "Fixture inventory includes hidden and nested files",
        str(LIBRARY_ROOT / ".hidden-fixture") in file_paths
        and str(fixtures["pair_b"]) in file_paths,
        f"scanner yielded {len(inventory)} inventory entries",
    )

    first = run_worker(ScanWorker, LIBRARY_ROOT, ui.DB_PATH)
    first_rows, first_fp_counts = read_database(database, ui.DB_PATH, LIBRARY_ROOT)
    persisted_count = len(first_rows)
    check(
        verification,
        "Initial headless scan completes despite per-file failures",
        first.get("status") == "completed"
        and first.get("meta_failed", 0) > 0
        and first.get("scanned", 0) > 0,
        f"status={first.get('status')}; scanned={first.get('scanned')}; "
        f"metadata failed={first.get('meta_failed')}; errors={len(first.get('errors', []))}",
    )
    check(
        verification,
        "Initial scan persists each inventory entry once",
        persisted_count == len(inventory),
        f"scanner entries={len(inventory)}; persisted rows={persisted_count}",
    )
    check(
        verification,
        "Corrupt JPEG is recorded as a per-file metadata failure",
        any(
            row["path"] == str(LIBRARY_ROOT / "corrupt.jpg") and row["metadata_status"] == "failed"
            for row in first_rows
        ),
        "corrupt.jpg metadata status read from the temporary database",
    )
    check(
        verification,
        "Corrupt supported RAW is failed and unsupported extension is unsupported",
        any(
            row["path"] == str(LIBRARY_ROOT / "corrupt.dng") and row["metadata_status"] == "failed"
            for row in first_rows
        )
        and any(
            row["path"] == str(LIBRARY_ROOT / "unsupported.xyz")
            and row["metadata_status"] == "unsupported"
            for row in first_rows
        ),
        "corrupt.dng and unsupported.xyz statuses read from the temporary database",
    )

    verification.notes.append(
        "Initial scan counts: inventory rows={}; metadata ok/unsupported/failed={}/{}/{}; "
        "fingerprints computed/reused/failed={}/{}/{}.".format(
            persisted_count,
            first.get("meta_ok", 0),
            first.get("meta_unsupported", 0),
            first.get("meta_failed", 0),
            first.get("fp_done", 0),
            first.get("fp_reused", 0),
            first.get("fp_failed", 0),
        )
    )
    for path, message in first.get("errors", []):
        verification.notes.append(f"Initial per-file error: `{path}` — {message}")
    verification.notes.append(f"Initial fingerprint status counts: {first_fp_counts}")

    if callable(getattr(database, "get_exact_duplicate_groups", None)):
        results = duplicate_results(database, ui.DB_PATH)
        if results is None:
            verification.skip("Exact duplicate finder", "skipped: not implemented")
        else:
            initial_groups, initial_empty_count = results
            pair_group = next(
                (paths for digest, paths in initial_groups if digest == fixtures["pair_digest"]),
                None,
            )
            check(
                verification,
                "Identical nonempty fixture pair is grouped",
                pair_group == sorted([str(fixtures["pair_a"]), str(fixtures["pair_b"])]),
                f"group={pair_group}",
            )
            grouped_paths = {path for _, paths in initial_groups for path in paths}
            check(
                verification,
                "Near-copy does not appear in an exact group",
                str(fixtures["near_copy"]) not in grouped_paths,
                f"near-copy path={fixtures['near_copy']}",
            )
            check(
                verification,
                "Empty files are excluded from duplicate groups and counted",
                initial_empty_count == 2
                and all(
                    str(LIBRARY_ROOT / name) not in grouped_paths
                    for name in ("empty-a.bin", "empty-b.bin")
                ),
                f"empty file count={initial_empty_count}; empty paths are absent from groups",
            )
    else:
        verification.skip("Exact duplicate finder", "skipped: not implemented")

    successful_before = sum(
        1
        for row in first_rows
        if row["fingerprint_status"] == "ok" and row["metadata_status"] is not None
    )
    second = run_worker(ScanWorker, LIBRARY_ROOT, ui.DB_PATH)
    second_rows, second_fp_counts = read_database(database, ui.DB_PATH, LIBRARY_ROOT)
    check(
        verification,
        "Second scan does not duplicate inventory rows",
        len(second_rows) == persisted_count,
        f"first rows={persisted_count}; second rows={len(second_rows)}",
    )
    check(
        verification,
        "Second scan reuses unchanged successful fingerprints",
        second.get("status") == "completed" and second.get("fp_reused", 0) == successful_before,
        f"eligible prior fingerprints={successful_before}; reused={second.get('fp_reused')}; "
        f"status={second.get('status')}",
    )
    verification.notes.append(
        "Second scan counts: metadata reused={}; fingerprints reused={}; statuses={}; status={}.".format(
            second.get("meta_reused", 0),
            second.get("fp_reused", 0),
            second_fp_counts,
            second.get("status"),
        )
    )

    old_digest = fixtures["pair_digest"]
    before_edit = fixture_snapshot(LIBRARY_ROOT)
    fixtures["pair_a"].write_bytes(fixtures["pair_a"].read_bytes() + b"\x00changed")
    edited_info = fixtures["pair_a"].stat()
    os.utime(
        fixtures["pair_a"],
        ns=(edited_info.st_atime_ns, edited_info.st_mtime_ns + 2_000_000_000),
    )
    edited_snapshot = fixture_snapshot(LIBRARY_ROOT)
    edited_digest = edited_snapshot[fixtures["pair_a"]][0]
    check(
        verification,
        "Deliberately edited fixture changed content and modification time",
        edited_digest != old_digest
        and edited_snapshot[fixtures["pair_a"]][1] != before_edit[fixtures["pair_a"]][1],
        f"old digest={old_digest}; new digest={edited_digest}",
    )

    if callable(getattr(database, "get_exact_duplicate_groups", None)):
        stale_results = duplicate_results(database, ui.DB_PATH)
        if stale_results is None:
            verification.skip("Stale duplicate behavior", "skipped: not implemented")
        else:
            stale_groups, _ = stale_results
            stale_pair = next(
                (paths for digest, paths in stale_groups if digest == old_digest), None
            )
            check(
                verification,
                "Database-only duplicate query stays stale until rescan",
                stale_pair == sorted([str(fixtures["pair_a"]), str(fixtures["pair_b"])]),
                "the saved inventory has not yet been refreshed after the fixture edit",
            )

    third = run_worker(ScanWorker, LIBRARY_ROOT, ui.DB_PATH)
    final_rows, final_fp_counts = read_database(database, ui.DB_PATH, LIBRARY_ROOT)
    changed_row = next(row for row in final_rows if row["path"] == str(fixtures["pair_a"]))
    check(
        verification,
        "Rescan refreshes the deliberately changed fingerprint",
        third.get("status") == "completed"
        and changed_row["sha256"] == edited_digest
        and changed_row["sha256"] != old_digest,
        f"status={third.get('status')}; saved digest={changed_row['sha256']}; "
        f"expected digest={edited_digest}",
    )
    if callable(getattr(database, "get_exact_duplicate_groups", None)):
        refreshed_results = duplicate_results(database, ui.DB_PATH)
        if refreshed_results is None:
            verification.skip("Refreshed duplicate result", "skipped: not implemented")
        else:
            refreshed_groups, refreshed_empty_count = refreshed_results
            refreshed_paths = {
                path for digest, paths in refreshed_groups if digest == old_digest for path in paths
            }
            check(
                verification,
                "Refreshed duplicate finder drops the now-stale pair",
                not {str(fixtures["pair_a"]), str(fixtures["pair_b"])}.issubset(refreshed_paths),
                f"old-digest paths after rescan={sorted(refreshed_paths)}",
            )
            check(
                verification,
                "Empty-file summary remains stable after rescan",
                refreshed_empty_count == 2,
                f"empty file count={refreshed_empty_count}",
            )

    after_snapshot = fixture_snapshot(LIBRARY_ROOT)
    unchanged_paths = set(before_snapshot) - {fixtures["pair_a"]}
    unchanged_ok = all(
        before_snapshot[path] == after_snapshot.get(path) for path in unchanged_paths
    )
    changed_ok = after_snapshot.get(fixtures["pair_a"]) == edited_snapshot[fixtures["pair_a"]]
    same_file_set = set(before_snapshot) == set(after_snapshot)
    check(
        verification,
        "Fixture bytes and mtimes are unchanged except for the deliberate edit",
        unchanged_ok and changed_ok and same_file_set,
        f"unchanged fixture files verified={len(unchanged_paths)}; deliberate edit={fixtures['pair_a']}",
    )
    verification.notes.append(
        "Final fingerprint status counts: {}; third scan computed/reused={}/{}.".format(
            final_fp_counts, third.get("fp_done", 0), third.get("fp_reused", 0)
        )
    )
    for path, message in third.get("errors", []):
        verification.notes.append(f"Final per-file error: `{path}` — {message}")

    # Check source-level safety properties against the implementation actually loaded.
    banned_modules = {"requests", "httpx", "urllib.request", "socket", "webbrowser"}
    network_imports = []
    for source_path in sorted((ROOT / "sift").glob("*.py")):
        tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                modules = [node.module or ""]
            else:
                continue
            network_imports.extend(
                f"{source_path.relative_to(ROOT)}:{node.lineno}:{module}"
                for module in modules
                if module in banned_modules
            )
    check(
        verification,
        "Sift modules have no direct network-client imports",
        not network_imports,
        ", ".join(network_imports) if network_imports else "no direct network-client imports found",
    )
    metadata_fields = {
        field.name.lower() for field in metadata.MetadataResult.__dataclass_fields__.values()
    }
    schema_conn = database.connect_readonly(ui.DB_PATH)
    try:
        schema_columns = {
            row["name"].lower() for row in schema_conn.execute("PRAGMA table_info(media_metadata)")
        }
    finally:
        schema_conn.close()
    gps_terms = {"gps", "latitude", "longitude"}
    gps_fields = sorted(
        name for name in metadata_fields | schema_columns if any(term in name for term in gps_terms)
    )
    check(
        verification,
        "Metadata result and database schema contain no GPS fields",
        not gps_fields,
        ", ".join(gps_fields) if gps_fields else "no GPS, latitude, or longitude fields found",
    )

    verification.notes.append(
        f"Final library database file rows={len(final_rows)}; "
        f"fingerprint status counts={final_fp_counts}."
    )


def command_environment():
    environment = os.environ.copy()
    environment["LOCALAPPDATA"] = str(APP_DATA_ROOT)
    environment["TEMP"] = str(TEMP_ROOT)
    environment["TMP"] = str(TEMP_ROOT)
    environment["QT_QPA_PLATFORM"] = "offscreen"
    environment["NO_COLOR"] = "1"
    return environment


def run_project_command(verification, name, arguments):
    command = [sys.executable, *arguments]
    command_text = subprocess.list2cmdline(command)
    log_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", name).strip("._")
    log_path = AUTO_ROOT / f"{log_name}.log"
    try:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            env=command_environment(),
            capture_output=True,
            text=True,
            errors="replace",
            timeout=600,
            check=False,
        )
        output = (completed.stdout or "") + ("\n" if completed.stdout and completed.stderr else "")
        output += completed.stderr or ""
        log_path.write_text(output, encoding="utf-8")
        verification.command_logs.append(log_path)
        if completed.returncode == 0:
            detail = f"`{command_text}` exited 0"
            status = True
        else:
            status = False
            detail = f"`{command_text}` exited {completed.returncode}"
            if name == "ruff format --check .":
                paths = sorted(
                    {
                        line.strip()
                        for line in re.findall(
                            r"^\s*-->\s+(.+?):\d+:\d+", output, flags=re.MULTILINE
                        )
                    }
                )
                if paths:
                    detail += "; files needing formatting: " + ", ".join(paths)
            excerpt = output.strip().splitlines()
            if excerpt:
                detail += "; output: " + " | ".join(excerpt[-8:])[:1600]
        if status and output.strip():
            summary_lines = output.strip().splitlines()[-4:]
            detail += "; output: " + " | ".join(summary_lines)[:900]
        verification.record(name, status, detail)
    except (OSError, subprocess.TimeoutExpired) as error:
        verification.fail(name, f"BLOCKED running `{command_text}`: {error}")
        verification.command_logs.append(log_path)
        try:
            log_path.write_text(str(error), encoding="utf-8")
        except OSError:
            pass


def run_commands(verification):
    run_project_command(
        verification,
        "python -m unittest discover -s tests -v",
        ["-m", "unittest", "discover", "-s", "tests", "-v"],
    )
    run_project_command(verification, "ruff check .", ["-m", "ruff", "check", "."])
    run_project_command(
        verification,
        "ruff format --check .",
        ["-m", "ruff", "format", "--check", "."],
    )
    run_project_command(
        verification,
        "python scripts/check_phase_status.py",
        ["scripts/check_phase_status.py"],
    )


def write_report(verification):
    try:
        safe_root = (
            AUTO_ROOT.absolute() == (ROOT / "test_data_auto").absolute()
            and AUTO_ROOT.parent.resolve() == ROOT.resolve()
            and not AUTO_ROOT.is_symlink()
            and not (hasattr(os.path, "isjunction") and os.path.isjunction(AUTO_ROOT))
        )
        if safe_root and AUTO_ROOT.is_dir():
            REPORT_PATH.write_text(verification.report_text(), encoding="utf-8")
        else:
            verification.fail(
                "Write verification report",
                "refused to write because test_data_auto is missing or is not a safe repo directory",
            )
    except OSError as error:
        verification.fail("Write verification report", f"{error}")


def main():
    verification = Verification()
    fixtures = None
    before_snapshot = None
    fixture_setup_ok = False
    try:
        safe_prepare_fixture_root()
        fixtures = create_fixtures(verification)
        before_snapshot = fixture_snapshot(LIBRARY_ROOT)
        fixture_setup_ok = True
        verification.record(
            "Synthetic fixtures created and baseline SHA-256/mtime recorded",
            bool(before_snapshot),
            f"{len(before_snapshot)} files under test_data_auto/library/",
        )
    except Exception as error:  # noqa: BLE001 - Preserve an actionable fixture-setup failure.
        verification.fail(
            "Prepare synthetic fixtures",
            f"{type(error).__name__}: {error}\n{traceback.format_exc(limit=2)}",
        )

    if fixture_setup_ok and fixtures is not None and before_snapshot is not None:
        try:
            verify_behavior(verification, fixtures, before_snapshot)
        except Exception as error:  # noqa: BLE001 - Capture end-to-end failures in the report.
            verification.fail(
                "End-to-end scan verification",
                f"{type(error).__name__}: {error}\n{traceback.format_exc(limit=4)}",
            )
        finally:
            if fixtures.get("unreadable_mode") is not None:
                try:
                    os.chmod(fixtures["unreadable"], fixtures["unreadable_mode"])
                except OSError as error:
                    verification.fail("Restore fixture folder permissions", str(error))
        run_commands(verification)
    else:
        verification.skip("End-to-end scan verification", "skipped: fixture setup failed")
        for name in (
            "python -m unittest discover -s tests -v",
            "ruff check .",
            "ruff format --check .",
            "python scripts/check_phase_status.py",
        ):
            verification.skip(name, "skipped: refusing to run without a safe fixture directory")
    write_report(verification)

    failed = [item for item in verification.results if item.status == "FAIL"]
    passed = [item for item in verification.results if item.status == "PASS"]
    skipped = [item for item in verification.results if item.status == "SKIPPED"]
    print(f"Sift verification: {len(passed)} passed, {len(failed)} failed, {len(skipped)} skipped")
    print(f"Report: {REPORT_PATH}")
    if failed:
        print("Failing checks:")
        for item in failed:
            print(f"- {item.name}: {item.detail}")
        return 1
    if skipped:
        print("Skipped checks:")
        for item in skipped:
            print(f"- {item.name}: {item.detail}")
        print("No failing checks; verification completed with skips.")
    else:
        print("No failing checks.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
