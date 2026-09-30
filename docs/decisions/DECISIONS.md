# Sift Decision Log

Record decisions that affect product behavior or architecture. Each entry should include date, status, decision, alternatives considered, and consequences. Use **Proposed** until the owner accepts it; do not treat assumptions in design docs as settled choices.

## D-001: Local-only core processing

- **Date:** 2026-09-29
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
- **Status:** Open
- **Decision needed:** Choose database technology, library portability/backup behavior, default app-data/cache locations, and whether users can move the Sift library database.
- **Inputs needed:** Expected collection scale, multi-library needs, removable drive behavior, backup expectations, and disk-space budget.

## D-005: Supported formats and representative collections

- **Date:** 2026-09-29
- **Status:** Open
- **Decision needed:** Name first-release photo/video/document formats and establish privacy-safe benchmark collections and minimum hardware.
- **Inputs needed:** User's actual library mix, camera/phone formats, raw formats, common video codecs, and platform targets.

## D-006: AI model distribution and license policy

- **Date:** 2026-09-29
- **Status:** Open
- **Decision needed:** Decide which models ship with the app and which are downloaded on demand, plus model update, license, and offline installation behavior.
- **Inputs needed:** Bundle size limits, GPU/CPU targets, license compatibility, quality benchmarks, and user expectations for first launch.
