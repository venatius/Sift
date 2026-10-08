# Development roadmap

## Phase status

| Phase | Status | Scope |
| --- | --- | --- |
| 0 | Baseline; checklist items remain | Product and architecture planning |
| 1 | Done | Safe scan and persisted inventory |
| 2 | Done | Metadata and fingerprints; see the accepted cache limitation below |
| 3 | Done | Read-only exact-duplicate groups from current successful SHA-256 fingerprints |
| 4 | In progress | JPEG/PNG thumbnail browsing, library filters, and visual-similarity review |

Phase status changes require explicit user approval. Future phases remain `Not
started` until their scope is approved; phase status is never advanced
automatically. Phase 3's approved scope is read-only exact-duplicate grouping
from current successful SHA-256 fingerprints, without file operations or
visual-similarity matching.

## Phase 2: metadata and fingerprints

- [x] Extract metadata and compute SHA-256 fingerprints as independent per-file
  stages.
- [x] Read hashes in bounded chunks and check pause/cancellation between
  chunks.
- [x] Reuse cached results using file identity, extractor/algorithm version,
  size, and nanosecond modification time.
- [x] Provide `force_rehash` to bypass fingerprint reuse and verify file
  contents.
- [x] Verify file signatures before and after processing and defer changed or
  disappeared files for retry.
- [x] Keep video metadata dependent on externally installed `ffprobe`.
- [x] Unit tests: the user reported 16 passing tests from their terminal on
  2026-10-02.

The cache can miss a content change that preserves both size and modification
time. `force_rehash` detects such changes when enabled. The review harness has
an outdated expectation for a corrupt synthetic `.dng`: a corrupt supported
RAW file is a metadata failure, while an unsupported extension such as `.xyz`
is unsupported.

## Phase 3: exact-duplicate review

- [x] Group inventory records that share a successful SHA-256 v1 fingerprint
  whose stored size and nanosecond modification time still match the inventory.
- [x] Exclude singleton, stale, failed, and unsupported fingerprint records.
- [x] Load results in a background thread and present paths and digest in the UI.
- [x] Keep this feature read-only: no file actions, and no visual-similarity
  matching.
- [x] Verify grouping, filtering, and background result delivery with synthetic
  database fixtures.

## Phase 4: image browsing and visual-similarity review

Scope approved on 2026-10-08: both thumbnail browsing with library filters and
local JPEG/PNG visual-similarity candidates. Completion still requires Elan's approval.

- [ ] Build versioned image features and small metadata-free thumbnails with Pillow.
- [ ] Keep image reads local, read-only, link-aware and bounded; report corrupt,
  changed, missing, animated, oversized and unsupported inputs per file.
- [ ] Preserve existing inventory and fingerprints with an additive, backed-up,
  idempotent feature-store extension; invalidate stale signatures and versions.
- [ ] Browse saved library records by folder, path text and image status with pagination.
- [ ] Show explainable similarity pairs separately from exact duplicates, with
  explicit uncertainty and limits; do not silently imply complete results when capped.
- [ ] Run decoding and database queries in cancellable background work; keep
  close/cancel safe, and preserve completed results across restart.
- [ ] Verify migrations, cache refresh/reuse, safety, failures, cancellation,
  synthetic stress cases and offscreen UI integration; record commands and limitations.
- [ ] Obtain the user's final real-window check and approval before marking Done.

Implementation stages: feature storage/analysis; filtered browsing; similarity
review; stress verification and documentation. Each stage receives a focused commit.
No file operations, GPS features, model downloads, network access, video/RAW
rendering or changes to `sha256_file` are included.
