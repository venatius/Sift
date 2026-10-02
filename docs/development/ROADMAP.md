# Development roadmap

## Phase status

| Phase | Status | Scope |
| --- | --- | --- |
| 0 | Baseline; checklist items remain | Product and architecture planning |
| 1 | Done | Safe scan and persisted inventory |
| 2 | Done | Metadata and fingerprints; see the accepted cache limitation below |
| 3 | Not started | Scope requires user approval |

Phase status changes require explicit user approval. Future phases remain `Not
started` until their scope is approved; phase status is never advanced
automatically.

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
