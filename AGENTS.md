# Repository briefing

## Scope and repo map

Work in this repository root. Ignore any other copies of SIFT.

| Path | Responsibility |
| --- | --- |
| `main.py` | Application entry point |
| `sift/ui.py` | PySide6 desktop interface and progress reporting |
| `sift/scanner.py` | Selected-root file enumeration |
| `sift/worker.py` | Scan stages, persistence, pause/cancel, and progress |
| `sift/metadata.py` | Image, RAW, video, and audio metadata extraction |
| `sift/fingerprint.py` | Incremental SHA-256 fingerprints |
| `sift/database.py` | SQLite schema and library records |
| `tests/test_phase2.py` | Phase 2 unit tests and fixtures |
| `tests_tmp/` | Temporary review harness and generated artifacts; do not change its harness expectations |
| `docs/` | Product, architecture, decisions, and roadmap |
| `.agents/skills/` | Project skills |
| `scripts/` | Repository maintenance and sync checks |

## Phase table

| Phase | Status | Scope |
| --- | --- | --- |
| 0 | Baseline; checklist items remain | Product and architecture planning |
| 1 | Done | Safe scan and persisted inventory |
| 2 | Done | Metadata and fingerprints; see the accepted cache limitation below |
| 3 | Not started | Scope requires user approval |

Keep every phase status identical in this file and `docs/development/ROADMAP.md`.
Statuses change only with explicit user approval; never auto-advance a phase.
Phase 3 remains `Not started` until its scope is approved. Run
`python scripts/check_phase_status.py` after changing either status table. The
`phase-1-complete` and `phase-2-complete` tags are historical markers: never move
or delete tags.

## Hard rules

- Run `python -m unittest discover -s tests -v` from the repository root.
- Do not split `tests/test_phase2.py` unless asked. Add Phase 2 cases there.
- Do not change `sha256_file` or TODO tests unless explicitly asked.
- Do not change `tests_tmp/review_harness.py` to accommodate its stale corrupt
  DNG expectation. A corrupt supported RAW extension is `failed`; a truly
  unsupported extension such as `.xyz` is `unsupported`.
- Do not hide known failures or claim a check passed if it was blocked.
- Do not reformat existing files. For Ruff, report `check` and `format --check`
  results only.
- Do not commit unless asked. The user reviews and commits each completed group.
- Do not advance phase status without explicit user approval.
- Do not run the hook installer unless asked.
- Do not rewrite product promises or accepted architecture decisions.
- Do not move, delete, or retag Git tags.

## Conventions

- Requires Python 3.11 or newer; tested on 3.13.3 only.
- Keep tests in the existing unittest structure and use synthetic fixtures.
- Prefer small, scoped edits; preserve existing file formatting.
- Commit message style when requested: `type(scope): imperative summary`, for
  example `docs(phase2): sync completion status`.
- Use the project skills under `.agents/skills/` when they apply.

## Documentation sync

- Phase status is recorded in this file and `docs/development/ROADMAP.md`; keep
  the status text identical and run the sync script.
- When editing `PRODUCT.md` or `ARCHITECTURE.md`, update that file's
  **Last updated** date. When editing `DECISIONS.md`, date the changed decision
  entry; do not change an accepted decision's original date just because its
  notes were clarified.
- `PRODUCT.md` promises and `ARCHITECTURE.md` decisions require explicit user
  direction before wording changes. Keep product checklist edits scoped to
  status/checklist items unless directed otherwise.
- Show documentation diffs before saving when requested; preserve recorded
  test failures and distinguish intended format support from verified samples.

## Phase 2 facts

- Metadata and SHA-256 hashing are independent per-file stages. Hashing uses
  bounded chunks and checks pause/cancellation between chunks.
- Cache identity uses file ID, algorithm/extractor version, size, and
  nanosecond modification time. Equal size and timestamp can hide content
  changes; `force_rehash` bypasses fingerprint reuse to verify file contents.
- Signatures are checked before and after processing. Changed or disappeared
  files are deferred for retry. Video metadata requires external `ffprobe`.
- The user reported all 16 existing unit tests passed outside the Windows
  sandbox on 2026-10-02. A new corrupt-DNG/unsupported-extension test was added
  afterward and still needs the user's verification.

## Definition of done

- Requested changes are present in the intended files and reviewed as a group.
- Relevant tests and sync checks have results recorded; sandbox-blocked checks
  are clearly identified for the user to run.
- Ruff `check` and `format --check` results are reported without applying format
  changes.
- Required documentation dates and phase statuses are synchronized.
- The changed-file list is shown; no commit or hook installation is performed
  without the user's request.

## Permissions and approvals

- The sandbox is the actual filesystem/network protection boundary.
  `approval_policy = "on-request"` does not prompt for every write inside the
  writable workspace.
- `.codex/config.toml` sets workspace-write mode and disables sandbox network
  access. Do not expand access to work around a blocked check.
- Keep writes inside this repository. If a check needs access beyond the
  workspace, report the constraint and let the user run it or approve an
  appropriate path.
