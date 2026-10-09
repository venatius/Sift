# Changelog

All notable changes to Sift are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Phase 4 image review: browse saved files with folder, path and preview-status
  filters, generate small JPEG/PNG previews, and review possible visual matches
  separately from exact duplicates. Matches are estimates based on saved data;
  missing files may remain listed, and capped results are clearly labeled.
- Background preview and matching jobs with cancellation and safe window closing.
- Versioned preview storage with a database backup before its first installation.
- Synthetic Phase 4 safety, failure, cache, UI and stress verification.
- Repository workflow guidance and a Phase 2 status synchronization check.
- Ruff and editor configuration for development.
- Tests for corrupt supported RAW files and unsupported file extensions.
- An exact duplicate finder that groups saved files with matching successful
  SHA-256 fingerprints across library folders. Empty files are counted
  separately and excluded from duplicate groups; lookup reads the database and
  does not inspect or change scanned files.

### Changed

- Refreshed the README with Windows setup, shipped features, saved-data limits,
  verification commands and project links; preserved the old handoff separately.
- Updated the repository map and generalized future-phase skill guidance.
- Phase 4 marked Done with Elan's explicit approval on 2026-10-09, following
  recorded synthetic verification and native Windows smoke checks.
- Recorded Phase 2 metadata, fingerprint, and RAW format verification details.

### Fixed

- Database errors during metadata or fingerprint processing now fail the scan;
  ordinary per-file errors remain isolated.
