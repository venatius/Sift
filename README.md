# Sift
Privacy-first local AI media organization

## Development setup

Requires Python 3.11 or newer; tested on 3.13.3 only.
Create and activate a virtual environment,
then install the pinned Python dependencies with `python -m pip install -r requirements.txt`.
Run the synthetic fixture suite with `python -m unittest discover -s tests -v`.

Video metadata requires the external `ffprobe` executable on `PATH`; it is part
of FFmpeg and is not installed by the Python requirements. One Windows option
is `winget install --id Gyan.FFmpeg --exact`. The Gyan.dev full builds are
GPLv3-licensed; review the [build details](https://www.gyan.dev/ffmpeg/builds/)
and [FFmpeg license information](https://ffmpeg.org/legal.html). Sift does not
download or bundle FFmpeg. The current development environment uses
`ffprobe 9.0.2-full_build-www.gyan.dev`.

RAW metadata for DNG, NEF, and ARW files uses the pinned `rawpy` package and its
LibRaw decoder. Sift reads dimensions and an available capture timestamp only;
it does not render/demosaic RAW pixels. This explicit extension scope does not
promise support for every camera RAW variant. Audio-only metadata uses ffprobe
for audio streams in supported containers and common audio files. Results may
include codec, duration, sample rate, channels/layout, and bit rate when present.

The app stores its SQLite library under `%LOCALAPPDATA%\Sift\sift.db`. Scanning
and media analysis are local and read-only. Set `LOCALAPPDATA` to a temporary
directory when running isolated tests.

## Current handoff

As of 2026-10-03:

- Latest commit: `267cdeb` — “Fix remaining ruff findings” (2026-10-02).
- Working tree: `AGENTS.md` had an uncommitted change when inspected. This handoff update also changes `README.md`; review both before committing. No commit was made.
- Environment: `.venv/` exists, but this run did not validate its interpreter or dependencies.
- Next action: review the two documentation changes, then verify `test_corrupt_raw_and_unsupported_extension_statuses` with the repository's full command: `python -m unittest discover -s tests -v`. This test still needs user verification; no tests were run during this handoff update.

Before resuming later, check `git status --short` and `git log -1` and refresh this dated snapshot if the repository has changed. Phase status remains governed by this repository's `AGENTS.md` and `docs/development/ROADMAP.md`; Phase 3 requires Elan's explicit approval.
