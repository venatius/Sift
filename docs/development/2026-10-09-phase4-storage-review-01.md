# Phase 4 storage and decoding review

Date: 2026-10-09 (Asia/Dubai). Scope: image_analysis.py, image_store.py,
image_worker.py and the new test_phase4.py. Implementation/commits authorized;
final Done approval pending. Sources: current files, AGENTS.md and the Phase 4 roadmap.
Skills: code-review-and-quality, sift-db-migration, sift-safety-review.

Astra reviewed the stage independently. Its extension-routing assumption was
checked against metadata.py: content signatures are already used before extension
fallback. Nevertheless orientation is now taken from the opened image's orientation
tag only, making analysis independent of mutable saved metadata. GPS IFDs are never
traversed; fresh preview encoding carries no EXIF, XMP or ICC data.

Review actions: added end-to-end rotated-image coverage, descriptor identity mismatch,
changed-source-during-decode and late cancellation tests. Unsupported content and
corrupt supported JPEG/PNG have distinct statuses; no stale preview is returned.
Core schema stays version 3, with an optional versioned additive table and a backup
before first installation. An idempotency test preserves records/foreign keys and
checks the backup; no real database was used.

Executed with LOCALAPPDATA=test_data_auto/_appdata, TEMP/TMP=test_data_auto/_temp:
- python -m unittest discover -s tests -v: 39 tests passed before review additions.
- python -m unittest discover -s tests -p test_phase4.py -v: 10 passed after additions.
- python -m ruff check .: passed.
- python -m ruff format --check: identified new-file wrapping differences; adjusted
  those new lines manually. No formatter was run with write access.

Limitations: Pillow cancellation is cooperative around a bounded native decode.
Source component/descriptor/signature checks mitigate changes; they are not a
security boundary against an adversary concurrently replacing filesystem ancestors.
Equal-size/equal-timestamp changes retain the documented cache limitation; verify
contents during scanning to refresh the SHA-256 and invalidate dependent previews.
Next: commit this tested stage, then add the background library browser and similarity UI.
