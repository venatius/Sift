---
name: phase-status-sync
description: Keep every phase status in AGENTS.md and the development roadmap synchronized.
---

# Phase status synchronization

1. Treat user-approved statuses as authoritative. Do not infer completion or
   automatically advance a phase. Phase 3 is `Not started` until its scope is
   explicitly approved.
2. Keep the phase table in `AGENTS.md` identical to the one in
   `docs/development/ROADMAP.md`, including every phase number and status.
3. Run `python scripts/check_phase_status.py` from the repository root after a
   status-table change.
4. Never move or delete a Git tag to reflect a phase status.
