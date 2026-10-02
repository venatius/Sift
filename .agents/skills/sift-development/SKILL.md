---
name: sift-development
description: Work on the Sift repository while preserving its test, data-safety, and review conventions.
---

# Sift development

- Run `python -m unittest discover -s tests -v` from the repository root.
- Keep Phase 2 tests in `tests/test_phase2.py`; do not change `sha256_file` or
  TODO tests without an explicit request.
- A corrupt file with a supported RAW extension is a decode failure. A truly
  unsupported extension is unsupported.
- The Windows sandbox may block test temporary directories. If setup fails for
  that reason, report it; the user may run the suite in their own terminal.
- Do not reformat existing files, move or delete tags, commit changes, or run
  the hook installer unless requested.
- Treat the sandbox as the protection boundary. `on-request` approval does not
  prompt for every write inside the workspace.
