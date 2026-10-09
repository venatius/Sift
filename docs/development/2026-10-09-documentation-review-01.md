# Markdown review — 2026-10-09, post-Phase-4 cleanup

## Scope and approval

Reviewed the 20 existing maintained Markdown files: README, AGENTS, CHANGELOG,
PRODUCT, ARCHITECTURE, DECISIONS, ROADMAP, eight dated development records, and
the five project-local skill instructions. Excluded generated fixtures, virtual
environment, Git internals and `tests_tmp`. Sources are the copied SIFT repository,
its phase tables, source modules, pinned requirements and recorded verification.
User authorized documentation cleanup, README update, commit/push to venatius/Sift,
and creation/push of `phase-4-complete`. No application or test changes authorized
or needed. Phase 4 remains Done; future scope is not approved by this cleanup.

## Findings and actions

| Priority | Document | Finding and action |
| --- | --- | --- |
| Medium | README.md | Current guidance was mixed with an obsolete October 3 handoff. Added current status, Windows launch commands, shipped workflow, saved-data limits, checks and links. Preserved the old handoff in a separate dated snapshot. |
| Medium | AGENTS.md | Repo map omitted duplicate/image modules and newer tests; test note was outdated. Updated only map and dated evidence pointer; all safety/approval rules retained, under 150 lines. |
| Low | phase-status-sync/SKILL.md | Phase-specific wording could encourage an obsolete Phase 3 assumption. Generalized to future unapproved phases, with current tables authoritative. |
| Low | CHANGELOG.md | Removed an unnecessary gap and recorded this documentation cleanup. Historical entries retained. |
| Informational | ROADMAP.md | Phase 4 Done matches approval and AGENTS. No further phase advanced; no change needed. |
| Review needed | PRODUCT.md | Phase 0 baseline still says only Phase 1 is authorized next. Current release goals exceed shipped behavior. Preserve product promises; a future approved review should label baseline/current scope and revisit hardware/OS benchmarks, retention and first-release acceptance. |
| Review needed | ARCHITECTURE.md | Baseline says technology choices remain open although D-003 accepts a stack, and contains Phase 1-only content-read rules. Its future design includes services/models/video previews not implemented today. Propose a dated current-implementation appendix mapping actual modules, schema v3 plus optional image_features, BLOB previews, and saved-only read queries; do not rewrite accepted decisions in this cleanup. |
| Review needed | DECISIONS.md | Preserve accepted D-001 through D-005 and historical real-file results. D-006 model/packaging decisions remain open. ARW real-sample qualification, hardware/OS minimums and Python 3.11 compatibility require evidence or explicit decisions; documentation cleanup cannot settle them. |
| Historical | Eight dated development records | Earlier In progress statuses, pending next steps, failed assertions, test counts and absolute synthetic paths describe their recorded runs. Leave unchanged; current README/phase tables supersede their operational status. |
| Informational | Four other project skills | Development, migration, safety and verification instructions remain applicable. No unnecessary rewrite or new skill folders. |

The VEN OS index links to README's `#current-handoff`; restoring that heading fixes
the route within SIFT without changing the VEN OS repository. The Python floor
remains 3.11+, tested only on 3.13.3; Ruff's `py313` target remains an explicit future
compatibility review item. No pyproject rule changes made.

## Skill run and verification

Skill-creator used for the narrow phase-sync instruction update. Preserved its
frontmatter, discovery behavior, paths and approval boundaries. This uniquely
dated output records the skill run; no new folders or dependencies were created.
The project exempts doc-only edits from code-review/debugging skill routing.

Check current phase synchronization, Markdown local link targets, AGENTS line
count, diff whitespace and the skill validator before committing. Unit tests are
not rerun for documentation-only changes; README's 55-test count cites the prior
record, not a new result. Validation outcomes are appended below.

Next: commit and push only these SIFT documentation files, then create and push
the new completion tag after confirming it does not already exist remotely.
Outstanding product/architecture reviews above remain proposals, not new scope.

## Validation outcomes

- `python scripts/check_phase_status.py`: exit 0, Phases 1–4 Done and synchronized.
- `python -m ruff check .`: exit 0; no findings.
- `python -m ruff format --check .`: exit 0; no formatting changes applied.
- Local Markdown check: 22 maintained files including the two new records;
  12 links/anchors resolved, including README's current-handoff route.
- `git diff --check`: clean; AGENTS has 149 lines; application/tests unchanged.
- Skill-creator `quick_validate.py` could not run: the project environment lacks
  `yaml` (PyYAML). No package installed to work around it. A direct check of the
  unchanged two-field frontmatter and generalized approval boundary passed;
  this is not a substitute for full YAML validation. No unfinished scaffold added.
- The previously recorded Python launcher warning remains non-blocking.
