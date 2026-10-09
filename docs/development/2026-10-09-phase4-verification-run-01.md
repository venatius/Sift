# Sift phase verification report

Repository: `C:\Users\elans\OneDrive\Desktop\VEN OS\projects\SIFT`
Fixture source: generated synthetic files under `test_data_auto/library/`.
The real user database and files outside the repository were not used.

## Checks

- **SKIPPED: Unreadable-folder handling** — skipped: this platform/account could not make the fixture unreadable
- **PASS: Synthetic fixtures created and baseline SHA-256/mtime recorded** — 14 files under test_data_auto/library/
- **PASS: Application database is isolated under test_data_auto** — LOCALAPPDATA=C:\Users\elans\OneDrive\Desktop\VEN OS\projects\SIFT\test_data_auto\_appdata; database=C:\Users\elans\OneDrive\Desktop\VEN OS\projects\SIFT\test_data_auto\_appdata\Sift\sift.db; no real window created
- **PASS: Selected-root symlink is not followed** — scanner returned [('skipped', 'Selected folder is a link; not followed')]
- **PASS: Nested directory symlink is not followed** — inventory contains 15 entries; link entry is not traversed
- **PASS: Fixture inventory includes hidden and nested files** — scanner yielded 15 inventory entries
- **PASS: Initial headless scan completes despite per-file failures** — status=completed; scanned=14; metadata failed=2; errors=3
- **PASS: Initial scan persists each inventory entry once** — scanner entries=15; persisted rows=15
- **PASS: Corrupt JPEG is recorded as a per-file metadata failure** — corrupt.jpg metadata status read from the temporary database
- **PASS: Corrupt supported RAW is failed and unsupported extension is unsupported** — corrupt.dng and unsupported.xyz statuses read from the temporary database
- **PASS: Identical nonempty fixture pair is grouped** — group=['C:\\Users\\elans\\OneDrive\\Desktop\\VEN OS\\projects\\SIFT\\test_data_auto\\library\\identical-a.bin', 'C:\\Users\\elans\\OneDrive\\Desktop\\VEN OS\\projects\\SIFT\\test_data_auto\\library\\subfolder\\identical-b.bin']
- **PASS: Near-copy does not appear in an exact group** — near-copy path=C:\Users\elans\OneDrive\Desktop\VEN OS\projects\SIFT\test_data_auto\library\near-copy.bin
- **PASS: Empty files are excluded from duplicate groups and counted** — empty file count=2; empty paths are absent from groups
- **PASS: Second scan does not duplicate inventory rows** — first rows=15; second rows=15
- **PASS: Second scan reuses unchanged successful fingerprints** — eligible prior fingerprints=14; reused=14; status=completed
- **PASS: Deliberately edited fixture changed content and modification time** — old digest=4970f5423347db3dcbad66137928e3938dc16a3a59c3022beab0d1324005e61b; new digest=4229c7d1eec1fe7b7980be85864bc9795b67d4a24825dcebb39f1aa60f39af0f
- **PASS: Database-only duplicate query stays stale until rescan** — the saved inventory has not yet been refreshed after the fixture edit
- **PASS: Rescan refreshes the deliberately changed fingerprint** — status=completed; saved digest=4229c7d1eec1fe7b7980be85864bc9795b67d4a24825dcebb39f1aa60f39af0f; expected digest=4229c7d1eec1fe7b7980be85864bc9795b67d4a24825dcebb39f1aa60f39af0f
- **PASS: Refreshed duplicate finder drops the now-stale pair** — old-digest paths after rescan=[]
- **PASS: Empty-file summary remains stable after rescan** — empty file count=2
- **PASS: Phase 4 preview preparation and cache reuse** — first={'prepared': 4, 'reused': 0, 'failed': 1, 'unsupported': 9, 'errors': [('C:\\Users\\elans\\OneDrive\\Desktop\\VEN OS\\projects\\SIFT\\test_data_auto\\library\\.hidden-fixture', 'cannot identify image file <_io.BufferedReader name=3>'), ('C:\\Users\\elans\\OneDrive\\Desktop\\VEN OS\\projects\\SIFT\\test_data_auto\\library\\corrupt.dng', 'cannot identify image file <_io.BufferedReader name=3>'), ('C:\\Users\\elans\\OneDrive\\Desktop\\VEN OS\\projects\\SIFT\\test_data_auto\\library\\corrupt.jpg', 'cannot identify image file <_io.BufferedReader name=3>'), ('C:\\Users\\elans\\OneDrive\\Desktop\\VEN OS\\projects\\SIFT\\test_data_auto\\library\\empty-a.bin', 'cannot identify image file <_io.BufferedReader name=3>'), ('C:\\Users\\elans\\OneDrive\\Desktop\\VEN OS\\projects\\SIFT\\test_data_auto\\library\\empty-b.bin', 'cannot identify image file <_io.BufferedReader name=3>'), ('C:\\Users\\elans\\OneDrive\\Desktop\\VEN OS\\projects\\SIFT\\test_data_auto\\library\\identical-a.bin', 'cannot identify image file <_io.BufferedReader name=3>'), ('C:\\Users\\elans\\OneDrive\\Desktop\\VEN OS\\projects\\SIFT\\test_data_auto\\library\\near-copy.bin', 'cannot identify image file <_io.BufferedReader name=3>'), ('C:\\Users\\elans\\OneDrive\\Desktop\\VEN OS\\projects\\SIFT\\test_data_auto\\library\\unique.bin', 'cannot identify image file <_io.BufferedReader name=3>'), ('C:\\Users\\elans\\OneDrive\\Desktop\\VEN OS\\projects\\SIFT\\test_data_auto\\library\\unsupported.xyz', 'cannot identify image file <_io.BufferedReader name=3>'), ('C:\\Users\\elans\\OneDrive\\Desktop\\VEN OS\\projects\\SIFT\\test_data_auto\\library\\subfolder\\identical-b.bin', 'cannot identify image file <_io.BufferedReader name=3>')]}; second={'prepared': 0, 'reused': 4, 'failed': 1, 'unsupported': 9, 'errors': [('C:\\Users\\elans\\OneDrive\\Desktop\\VEN OS\\projects\\SIFT\\test_data_auto\\library\\.hidden-fixture', 'cannot identify image file <_io.BufferedReader name=3>'), ('C:\\Users\\elans\\OneDrive\\Desktop\\VEN OS\\projects\\SIFT\\test_data_auto\\library\\corrupt.dng', 'cannot identify image file <_io.BufferedReader name=3>'), ('C:\\Users\\elans\\OneDrive\\Desktop\\VEN OS\\projects\\SIFT\\test_data_auto\\library\\corrupt.jpg', 'cannot identify image file <_io.BufferedReader name=3>'), ('C:\\Users\\elans\\OneDrive\\Desktop\\VEN OS\\projects\\SIFT\\test_data_auto\\library\\empty-a.bin', 'cannot identify image file <_io.BufferedReader name=3>'), ('C:\\Users\\elans\\OneDrive\\Desktop\\VEN OS\\projects\\SIFT\\test_data_auto\\library\\empty-b.bin', 'cannot identify image file <_io.BufferedReader name=3>'), ('C:\\Users\\elans\\OneDrive\\Desktop\\VEN OS\\projects\\SIFT\\test_data_auto\\library\\identical-a.bin', 'cannot identify image file <_io.BufferedReader name=3>'), ('C:\\Users\\elans\\OneDrive\\Desktop\\VEN OS\\projects\\SIFT\\test_data_auto\\library\\near-copy.bin', 'cannot identify image file <_io.BufferedReader name=3>'), ('C:\\Users\\elans\\OneDrive\\Desktop\\VEN OS\\projects\\SIFT\\test_data_auto\\library\\unique.bin', 'cannot identify image file <_io.BufferedReader name=3>'), ('C:\\Users\\elans\\OneDrive\\Desktop\\VEN OS\\projects\\SIFT\\test_data_auto\\library\\unsupported.xyz', 'cannot identify image file <_io.BufferedReader name=3>'), ('C:\\Users\\elans\\OneDrive\\Desktop\\VEN OS\\projects\\SIFT\\test_data_auto\\library\\subfolder\\identical-b.bin', 'cannot identify image file <_io.BufferedReader name=3>')]}
- **PASS: Phase 4 saved metadata-free bounded previews** — ready previews=4; metadata-free and <=256 pixels=True
- **PASS: Phase 4 visually identical re-encoding is a candidate** — candidates=1; matched=1
- **PASS: Fixture bytes and mtimes are unchanged except for the deliberate edit** — unchanged fixture files verified=13; deliberate edit=C:\Users\elans\OneDrive\Desktop\VEN OS\projects\SIFT\test_data_auto\library\identical-a.bin
- **PASS: Sift modules have no direct network-client imports** — no direct network-client imports found
- **PASS: Metadata result and database schema contain no GPS fields** — no GPS, latitude, or longitude fields found
- **PASS: python -m unittest discover -s tests -v** — `"C:\Users\elans\OneDrive\Desktop\VEN OS\projects\SIFT\.venv\Scripts\python.exe" -m unittest discover -s tests -v` exited 0; output: ---------------------------------------------------------------------- | Ran 54 tests in 22.535s |  | OK
- **PASS: ruff check .** — `"C:\Users\elans\OneDrive\Desktop\VEN OS\projects\SIFT\.venv\Scripts\python.exe" -m ruff check .` exited 0; output: All checks passed! |  | Failed to find real location of C:\Python313\python.exe
- **PASS: ruff format --check .** — `"C:\Users\elans\OneDrive\Desktop\VEN OS\projects\SIFT\.venv\Scripts\python.exe" -m ruff format --check .` exited 0; output: 36 files already formatted |  | Failed to find real location of C:\Python313\python.exe
- **PASS: python scripts/check_phase_status.py** — `"C:\Users\elans\OneDrive\Desktop\VEN OS\projects\SIFT\.venv\Scripts\python.exe" scripts/check_phase_status.py` exited 0; output: Phase statuses synchronized: 0: Baseline; checklist items remain; 1: Done; 2: Done; 3: Done; 4: In progress |  | Failed to find real location of C:\Python313\python.exe

## Scan details

- Initial scan counts: inventory rows=15; metadata ok/unsupported/failed=4/8/2; fingerprints computed/reused/failed=14/0/0.
- Initial per-file error: `C:\Users\elans\OneDrive\Desktop\VEN OS\projects\SIFT\test_data_auto\library\corrupt.dng` — Could not decode RAW image: b'Input/output error'
- Initial per-file error: `C:\Users\elans\OneDrive\Desktop\VEN OS\projects\SIFT\test_data_auto\library\corrupt.jpg` — Not a readable image (corrupt or wrong format)
- Initial per-file error: `C:\Users\elans\OneDrive\Desktop\VEN OS\projects\SIFT\test_data_auto\library\linked-subfolder` — Link not followed
- Initial fingerprint status counts: {'ok': 14}
- Second scan counts: metadata reused=14; fingerprints reused=14; statuses={'ok': 14}; status=completed.
- Final fingerprint status counts: {'ok': 14}; third scan computed/reused=1/13.
- Final per-file error: `C:\Users\elans\OneDrive\Desktop\VEN OS\projects\SIFT\test_data_auto\library\linked-subfolder` — Link not followed
- Final library database file rows=15; fingerprint status counts={'ok': 14}.

## Command output logs

- `test_data_auto/python_-m_unittest_discover_-s_tests_-v.log`
- `test_data_auto/ruff_check.log`
- `test_data_auto/ruff_format_--check.log`
- `test_data_auto/python_scripts_check_phase_status.py.log`

## Summary

29 passed, 0 failed, 1 skipped.
Overall result: **PASS WITH SKIPPED CHECKS**.
