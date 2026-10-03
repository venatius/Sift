---
name: sift-safety-review
description: Review Sift changes against the repository's media, filesystem, privacy, and database safety rules.
---

# Sift safety review

Use when reviewing a Sift diff or verification result. Read the safety rules in `AGENTS.md`, then trace affected code paths and tests against them.

Review whether the change:

- Reads originals without modifying, moving, renaming, or deleting them, and does not follow symlinks or junctions, including a selected root.
- Keeps the database under `%LOCALAPPDATA%\Sift`, uses parameterized SQL, and enables foreign keys on every connection.
- Keeps each file failure isolated, avoids network access and telemetry, and does not read or store GPS/location data.
- Rejects stale cached results when the stored input signature no longer matches; account for the documented equal-size/equal-timestamp limitation.
- Preserves data during migrations and tests only with synthetic or throwaway copies.

Report findings by severity (Critical, High, Medium, Low, Informational), with file/line evidence and impact. Distinguish verified behavior from assumptions. Do not change code unless implementation was separately requested.
