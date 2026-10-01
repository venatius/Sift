# Sift Decision Log

Record decisions that affect product behavior or architecture. Each entry should include date, status, decision, alternatives considered, and consequences. Use **Proposed** until the owner accepts it; do not treat assumptions in design docs as settled choices.

## D-001: Local-only core processing

- **Date:** 2026-09-30
- **Status:** Accepted product constraint
- **Decision:** Core media scanning, analysis, indexing, search, and grouping run locally. Media content and library-derived data are not uploaded.
- **Reason:** Privacy-first product promise and user-provided project direction.
- **Consequences:** Models and dependencies must be available locally; performance and disk requirements need clear communication. Optional component downloads must not transmit library data.

## D-002: Preserve originals during analysis

- **Date:** 2026-09-29
- **Status:** Accepted product constraint
- **Decision:** Scanning and virtual organization do not move, rename, edit, or delete original files. File-changing actions require a separate reviewed and confirmed operation.
- **Reason:** Prevent accidental damage and maintain trust.
- **Consequences:** The library database and derived-data store are separate from user media; operation planning, conflict checks, and recovery become explicit requirements.

## D-003: Implementation technology and platform scope

- **Date:** 2026-09-30
- **Status:** Accepted for Phase 1 (installer, packaging, and model choices remain open)
- **Decision:** Python for the application, PySide6 (Qt for Python) for the desktop UI, and Python's built-in sqlite3 for local storage. Windows is the first target platform.
- **Alternatives considered:** Other desktop shells and languages were not compared in depth. This stack was chosen because Python suits the planned local analysis and is approachable for learning.
- **Consequences:** Packaging/installer approach and AI model choices are deferred, since the Phase 1 scanner does not need them. Revisit before Phase 2 if analysis needs outgrow this stack.

## D-004: Library database and derived-data location

- **Date:** 2026-09-29
- **Status:** Accepted for Phase 1 (library portability and backup behavior remain open)
- **Decision:** Use SQLite and store the database in the user's local application data directory. On Windows, use `%LOCALAPPDATA%\Sift\sift.db`.
- **Reason:** Keep generated library data out of the source tree and outside folders that Sift scans.
- **Consequences:** The database remains local to this Windows user account and is not automatically portable with the source folder. Library backup and relocation behavior remain future decisions.

## D-005: Supported formats and representative collections

- **Date:** 2026-10-01
- **Status:** Accepted for Phase 2 (benchmark collections and minimum hardware remain open)
- **Decision:** Phase 2 extracts metadata from common phone photos and videos. All regular files get a SHA-256 fingerprint regardless of format. Formats outside the table below (RAW/DNG, documents, etc.) are recorded as "unsupported" for metadata but still fingerprinted. A format is only listed as supported after it was tested on real sample files.
- **Metadata kept:**
  - Images: detected format, width, height, capture date and its source field (no timezone assumed), camera make/model, orientation.
  - Videos: detected container, width, height, duration, video codec, creation time and its source tag, device make/model when present.
  - Filesystem size and modified time stay separate from embedded dates.
- **Location data:** GPS is not read or stored in Phase 2 (including video location tags). Handling will be decided before it is added.
- **Extractors:**

  | Format                                  | Extractor                                 |
  | --------------------------------------- | ----------------------------------------- |
  | JPEG, PNG, GIF, WebP, BMP, TIFF         | Pillow 12.3.0                             |
  | HEIC/HEIF                               | Pillow with pillow-heif 1.8.0             |
  | MP4, MOV, M4V, 3GP, MKV, AVI, WebM, MTS | External ffprobe; development environment: 9.0.2-full_build-www.gyan.dev |
  | Everything else                         | none (recorded as unsupported)            |

- **Tested formats:** (fill in after the manual check)
- **Development setup:** ffprobe is an external FFmpeg executable, not a Python dependency. On Windows, the observed environment installed package `Gyan.FFmpeg` 9.0.2 through WinGet (`winget install --id Gyan.FFmpeg --exact`). Gyan.dev full builds are GPLv3; Sift does not bundle or download them. See [Gyan.dev build details](https://www.gyan.dev/ffmpeg/builds/) and [FFmpeg licensing](https://ffmpeg.org/legal.html).
- **Image validation:** Pillow's decompression-bomb warning is ignored while reading metadata; hard decompression-bomb errors and decoder errors remain per-file failures.
- **Synthetic test coverage:** generated files exercise the listed extraction paths, but do not qualify formats for the real-sample **Tested formats** list above.

## D-006: AI model distribution and license policy

- **Date:** 2026-09-29
- **Status:** Open
- **Decision needed:** Decide which models ship with the app and which are downloaded on demand, plus model update, license, and offline installation behavior.
- **Inputs needed:** Bundle size limits, GPU/CPU targets, license compatibility, quality benchmarks, and user expectations for first launch.
