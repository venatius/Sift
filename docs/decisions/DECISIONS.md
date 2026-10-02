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
- **Python compatibility (clarification, 2026-10-02):** Requires Python 3.11 or newer; tested on 3.13.3 only.
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
- **Validation updated:** 2026-10-02
- **Status:** Accepted for Phase 2 (benchmark collections and minimum hardware remain open)
- **Decision:** Phase 2 extracts metadata from the explicitly listed formats below. All regular files get a SHA-256 fingerprint regardless of format. Other formats are recorded as "unsupported" for metadata but still fingerprinted. Format support is based on content decoding, not the file extension alone.
- **Metadata kept:**
  - Images: detected format, width, height, capture date and its source field (no timezone assumed), camera make/model, orientation.
  - Video: detected container, width, height, duration, video codec, creation time and its source tag, device make/model when present.
  - Audio-only streams: detected container, duration, audio codec, sample rate, channel count/layout, and bit rate when present.
  - RAW still images: decoded visible dimensions and decoder-provided capture timestamp when present; camera make/model and orientation are not guaranteed by the RAW decoder and remain empty unless available through an agreed extractor.
  - Filesystem size and modified time stay separate from embedded dates.
- **Location data:** GPS is not read or stored in Phase 2 (including video location tags). Handling will be decided before it is added.
- **Extractors:**

  | Format                                  | Extractor                                 |
  | --------------------------------------- | ----------------------------------------- |
  | JPEG, PNG, GIF, WebP, BMP, TIFF         | Pillow 12.3.0                             |
  | HEIC/HEIF                               | Pillow with pillow-heif 1.8.0             |
  | DNG, NEF, ARW still images              | rawpy 0.27.1 (LibRaw); no demosaicing/rendering |
  | MP4, MOV, M4V, 3GP, MKV, AVI, WebM, MTS | External ffprobe; development environment: 9.0.2-full_build-www.gyan.dev |
  | Audio-only streams in supported containers above, plus MP3, M4A, AAC, WAV, FLAC, OGG, OPUS, WMA, AIFF, MKA | External ffprobe |
  | Everything else                         | none (recorded as unsupported)            |

- **Tested formats:** JPEG, HEIC/HEIF, TIFF, MP4, MOV, AVI, and WebM were exercised on real sample files before audio/RAW support. Audio-only AAC in MP4 was subsequently confirmed in the user-provided testing folder. DNG and NEF have synthetic mocked unit coverage and subsequently decoded real Nikon Z9 samples; the Sony ARW sample produced a LibRaw I/O error, so real-file ARW support remains unverified.
- **Development setup:** ffprobe is an external FFmpeg executable, not a Python dependency. On Windows, the observed environment installed package `Gyan.FFmpeg` 9.0.2 through WinGet (`winget install --id Gyan.FFmpeg --exact`). Gyan.dev full builds are GPLv3; Sift does not bundle or download them. See [Gyan.dev build details](https://www.gyan.dev/ffmpeg/builds/) and [FFmpeg licensing](https://ffmpeg.org/legal.html).
- **RAW component version and licenses:** The installed `rawpy==0.27.1` distribution declares `License-Expression: MIT`; its `LICENSE` begins “The MIT License (MIT).” The distribution includes the LGPL-2.1 text for LibRaw in `LICENSE.LibRaw`, which begins “GNU LESSER GENERAL PUBLIC LICENSE / Version 2.1, February 1999.” The installed build reports `libraw_version` and `libraw_version_compiled` as 0.22.1. LibRaw is dual-licensed under LGPL-2.1 or CDDL-1.0. Sources: [rawpy 0.27.1 on PyPI](https://pypi.org/project/rawpy/0.27.1/), [rawpy source](https://github.com/letmaik/rawpy), [LibRaw source](https://github.com/LibRaw/LibRaw), and [LibRaw licensing](https://www.libraw.org/about).
- **Open packaging item:** Confirm bundled LibRaw version and license notices before packaging or distribution.
- **Image validation:** Pillow's decompression-bomb warning is ignored while reading metadata; hard decompression-bomb errors and decoder errors remain per-file failures.
- **RAW validation:** rawpy/LibRaw reads dimensions and an optional capture timestamp without postprocessing; Sift does not render or demosaic a full image. DNG and NEF decoded on the tested Nikon Z9 samples; the tested Sony ARW sample returned a LibRaw I/O error. DNG, NEF, and ARW are intended extractor inputs, but support is not established for every camera/file variant.
- ARW is listed as intended handling but unverified; if it cannot be verified on a real file, move it to unsupported-for-metadata.
- **Audio validation:** ffprobe inspects streams and selects a primary non-thumbnail video stream when present, otherwise a primary audio stream. Container parsing succeeds only when a decodable audio/video stream exists; initialization-only or otherwise incomplete files may therefore remain unsupported or fail per file.
- **Synthetic test coverage:** generated files exercise the listed extraction paths, but do not qualify formats for the real-sample **Tested formats** list above.
- **Unsupported media:** RAW extensions other than DNG, NEF, and ARW, unknown codecs, and containers without a decodable audio or video stream remain unsupported or report a per-file decode failure. All still receive SHA-256 fingerprints.
- **Real-file test result before audio/RAW additions:** 138 files were scanned and fingerprinted; 128 metadata extractions succeeded, 9 were unsupported, and one malformed MP4 failed metadata extraction. A second scan reused metadata for all 138 files and forced fingerprint verification recomputed all 138.
- **Latest real-file test:** 138 files scanned, all 138 SHA-256 fingerprints completed, metadata results were 132 successful, 4 unsupported, and 2 failed. Both audio-only AAC MP4 samples parsed as audio (AAC, 22,050 Hz, 2 channels). The Nikon Z9 DNG and NEF samples decoded successfully (5392×3592 and 5408×3608); their optional capture timestamp was unavailable. The Sony ARW sample returned a LibRaw I/O error, and the malformed MP4 remains a per-file failure. Capture/device fields appear only when embedded in a file.

## D-006: AI model distribution and license policy

- **Date:** 2026-09-29
- **Status:** Open
- **Decision needed:** Decide which models ship with the app and which are downloaded on demand, plus model update, license, and offline installation behavior.
- **Inputs needed:** Bundle size limits, GPU/CPU targets, license compatibility, quality benchmarks, and user expectations for first launch.
