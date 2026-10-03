---
name: sift-phase-verify
description: Verify a Sift development phase with the repository's synthetic end-to-end checks and safety rules.
---

# Sift phase verification

Use when a Sift phase is ready for verification. Run `python scripts/verify_phase.py`, read `test_data_auto/verify_report.md`, and compare its results with that phase's checklist in `docs/development/ROADMAP.md` and the Definition of done in `AGENTS.md`.

- Do not fix, omit, or downgrade failures silently. List remaining failures by severity and say when a check was blocked or skipped.
- Never mark a phase Done without the user's explicit approval. Report the current synchronized phase status.
- Never claim a blocked check passed. If sandbox access blocks an authorized check, follow `AGENTS.md` and request approval before trying outside the sandbox.
- Never access the real Sift database or create, edit, or delete anything outside this repository. The verifier may manage fixtures only under `test_data_auto/`.
- Summarize automated results separately from what only the user can verify: opening the real window, responsiveness during a large scan, and behavior with real phone files.
