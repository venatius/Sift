# Phase 4 similarity review — 2026-10-09, stage 3

Scope: selected-image candidate review over saved JPEG/PNG features. Sources:
`sift/visual_match.py`, `image_store.py`, `image_worker.py`, `image_browser.py`,
and synthetic regressions in `tests/test_phase4.py`.

Approval: user approved Phase 4 implementation and focused local commits;
Done still requires explicit approval. No pushes or tags.

## Review and recovery evidence

- Code-review-and-quality: main-agent review plus read-only GPT-6 Astra review.
  Astra found overlapping-root duplicate candidates and stale selection labels.
  Both fixed, with regression coverage. Ranking streams eligible rows ordered
  by path, collapses adjacent repeated paths, and retains at most 100 results.
- Debugging-and-error-recovery: first run had one failing new assertion because
  the test's deliberately rejected write left a transaction open. Explicitly
  rolling back that rejected write fixed the setup; production behavior was
  unchanged. Later focused run: 18 tests, OK (6.037 seconds).
- Sift safety review: query uses a read-only connection and a single snapshot.
  Removed synthetic sources plus patched file-open/stat functions prove matching
  does not access originals. No network modules, GPS extraction or file actions
  added. UI marks saved-only, uncertain results and truncation explicitly.
- Ruff check: all checks passed. Format check: all 34 files already formatted
  after adjusting new source lines manually; no formatter was run in write mode.

## Behavior and limitations

Exact SHA matches and flat images are excluded. Candidate thresholds are an
edge-hash distance of 8/64, average RGB delta 32/255, and aspect difference 10%.
These are conservative heuristic filters, not calibrated confidence scores;
crops, rotations and strong colour edits may be missed. Results may include
missing sources because queries intentionally use saved records. Rescan and
prepare refreshes data; the accepted equal-size/equal-mtime cache limitation
remains. Comparison takes time proportional to eligible library records.

Next: final synthetic stress, end-to-end verification, documentation, and user
real-window review. Phase 4 stays In progress.
