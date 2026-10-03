# Changelog

All notable changes to Sift are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Repository workflow guidance and a Phase 2 status synchronization check.
- Ruff and editor configuration for development.
- Tests for corrupt supported RAW files and unsupported file extensions.
- An exact duplicate finder that groups saved files with matching successful
  SHA-256 fingerprints across library folders. Empty files are counted
  separately and excluded from duplicate groups; lookup reads the database and
  does not inspect or change scanned files.

### Changed

- Recorded Phase 2 metadata, fingerprint, and RAW format verification details.

### Fixed

- Database errors during metadata or fingerprint processing now fail the scan;
  ordinary per-file errors remain isolated.
