# Sift Architecture

**Status:** Phase 0 baseline  
**Last updated:** 2026-09-29

## Architectural goals

- Keep media processing local and usable without an account or always-on network.
- Scale from a small folder to a large multi-drive library without blocking the interface or exhausting memory.
- Make each analysis stage restartable, incremental, observable, and replaceable.
- Protect original files through read-only analysis and an explicit boundary for approved file actions.
- Keep UI, storage, operating-system integration, and AI/model implementations independently testable.
- Support a polished downloadable desktop app and a maintainable public repository.

## Proposed high-level structure

The following is a logical architecture. Specific language, framework, database, and model choices remain open until the Phase 0 decisions are reviewed.

```text
Desktop UI
  ├── Library and folder selection
  ├── Browse, search, and review
  └── Progress, settings, and safety confirmations
          │ typed application commands/events
Application services
  ├── Library and scan coordinator
  ├── Work queue and cancellation
  ├── Search and virtual collections
  └── Review and file-operation service
          │
Local domain services
  ├── Filesystem inventory and change detection
  ├── Metadata and fingerprinting
  ├── Source/media classification
  ├── Image/video feature extraction
  ├── Duplicate matching
  ├── Embedding and search index
  └── People/event grouping
          │
Local persistence
  ├── Library database and migrations
  ├── Derived thumbnails/features/cache
  └── Models and model manifests
          │
Selected local folders and drives (read during analysis)
```

## Module responsibilities

### Desktop UI

Owns presentation, navigation, accessibility, and user intent. It displays progress and results received through application services. It does not perform filesystem crawls, model inference, or direct database mutations.

### Application services

Coordinate workflows and enforce use-case rules: create/select a library, start or resume scans, schedule analysis, report progress, search, accept corrections, and request a reviewed file operation. They translate domain outcomes into UI-friendly events and errors.

### Scan coordinator and work queue

Enumerate a bounded amount of work, schedule stages according to prerequisites and resource limits, persist checkpoints, and handle pause, cancellation, retries, and changed-file invalidation. Jobs must be idempotent: retrying a job cannot create duplicate state or silently alter originals.

### Filesystem and media adapters

Contain OS-specific path handling, file identity, access checks, file watching where supported, media decoding, and safe file operations. Analysis adapters open source files read-only. The operation adapter is separate and only invoked after review approval.

### Analysis services

Implement metadata extraction, fingerprints, classification, visual feature extraction, duplicate candidate generation, embeddings, search, and grouping behind stable interfaces. Each result records its method/version and references its input fingerprint so stale outputs can be invalidated.

### Persistence

Store library records, roots, scan state, metadata, fingerprints, analysis results, user corrections, virtual collections, and operation history. Store large derived artifacts such as thumbnails and feature caches as managed files when appropriate, with database references and cleanup rules. Do not copy original media into app-managed storage.

### Model and codec management

Use an explicit local manifest for model/component identity, version, license, source, size, and checksum. Installation and updates must be visible to the user, verified, and separable from media scanning. No model may silently switch to remote inference.

## Processing pipeline

1. **Register roots:** save selected folders, exclusions, and library settings.
2. **Inventory:** enumerate eligible files and record file identity, size, times, and access outcome.
3. **Detect changes:** compare identity and metadata, then use content hashing as needed to confirm changes and detect exact duplicates.
4. **Extract metadata:** read supported image/video metadata and classify candidate file types.
5. **Build previews:** create bounded-size thumbnails and video keyframes using an explicit sampling policy.
6. **Analyze progressively:** run source classification, visual features, embeddings, and duplicate candidate generation according to configured priority and resource limits.
7. **Group and index:** update search indexes and provisional people/event groups; preserve user corrections separately from model output.
8. **Present:** expose available results incrementally, with their status, provenance, confidence, and errors.
9. **Review action:** produce a dry-run plan listing source and destination paths and conflicts; require explicit confirmation before executing supported operations.
10. **Record outcome:** save operation results, failures, and recovery information; never report a partial operation as fully successful.

## Data model concepts

The implementation should model these concepts separately, even if initial storage is relational:

- **Library:** settings, database identity, schema version, and managed cache location.
- **Root:** selected folder/volume and its inclusion/exclusion configuration.
- **File item:** current path, file identity when available, size, timestamps, access state, and detected kind.
- **Content fingerprint:** fingerprint algorithm/version and digest; distinguish quick candidate hashes from verified full-content hashes.
- **Media metadata:** extracted technical and embedded metadata with source and extraction status.
- **Analysis result:** stage, version, input fingerprint, result payload/reference, confidence, and completion/error status.
- **Relationship:** duplicate similarity, group membership, or other links between file items, with method and evidence.
- **User correction:** user-confirmed labels, exclusions, preferred representative, or group edits, stored independently of generated results.
- **Virtual collection:** query or explicit membership used for browsing without relocating media.
- **Operation plan and record:** reviewed intended changes, confirmation, per-item outcome, and recovery data where supported.

Paths can change and may be case-sensitive depending on filesystem. The system must not treat a path alone as a permanent identity. Volumes can be disconnected, file IDs may be unavailable, and duplicate contents may exist at multiple paths; data and UX must represent these cases explicitly.

## Incremental processing and invalidation

- Use a fast metadata/identity check to avoid re-reading unchanged content when reliable.
- Use versioned fingerprints and analysis records; a change in file content or relevant algorithm/model version invalidates only dependent stages.
- Persist stage completion and errors so an interrupted scan resumes safely.
- Keep user corrections distinct and do not erase them merely because a model or algorithm is updated.
- Treat file watcher events as hints; reconcile against actual filesystem state.
- Define cleanup for orphaned cache artifacts and removed roots, and explain the effect before deleting user-visible library data.

## Performance and resource policy

- The UI thread never waits for directory enumeration, media decoding, database-wide queries, or inference.
- Bound queue size, open file handles, decoder memory, thumbnail dimensions, and concurrent inference.
- Separate fast stages from expensive stages and publish partial results as soon as useful.
- Support user-configurable resource intensity and pause behavior; defaults should protect responsiveness.
- Analyze video through metadata and sampled frames first. Full decoding is reserved for a feature that needs it.
- Avoid retaining decoded frames or full-resolution images beyond the current bounded job.
- Measure stages on agreed representative hardware and collections before making speed claims.

## Privacy and security boundaries

- The filesystem reader has access only to user-selected roots and explicitly configured app data.
- Do not follow symbolic links or reparse points outside approved roots by default; make any expanded-scope behavior explicit.
- Validate paths again immediately before a file operation to account for changed paths, links, and volume state.
- Keep analysis read-only; isolate move, rename, or delete capabilities behind the reviewed operation service.
- Do not expose local service ports or accept remote control unless a future reviewed requirement authorizes it.
- Keep telemetry disabled for library-derived data; diagnostics must be opt-in, minimized, and scrubbed.
- Verify downloads and packaged components, and maintain a component/model license inventory.

## Failure handling and recovery

- Per-file failures are recorded and do not stop unrelated work.
- Interrupted jobs return to a known checkpoint or restart idempotently.
- Database migrations are versioned and backed up or otherwise recoverable before destructive schema changes.
- A disconnected drive is shown as unavailable; its records remain distinguishable from confirmed deletions.
- File actions are planned and checked before execution; where atomic multi-file operations are impossible, report each result and offer safe recovery steps.
- Corrupt databases, insufficient disk space, missing models, and unsupported formats receive actionable messages.

## Testing strategy for implementation phases

- Unit tests for fingerprints, classification rules, invalidation, grouping, and operation planning.
- Fixture-based tests with synthetic media and expected metadata/results; avoid committing private personal media.
- Integration tests for database migrations, interrupted/resumed scans, removable volumes, and partial failures.
- Platform tests for path semantics, permissions, links, and file operations.
- Performance tests on agreed library profiles, reporting hardware and settings.
- Privacy checks that verify no analysis path calls a remote inference or upload service.
- UI acceptance checks for accessibility, progress, cancellation, review, and recovery flows.

## Suggested repository layout

```text
docs/
  product/PRODUCT.md
  architecture/ARCHITECTURE.md
  decisions/
  development/ROADMAP.md
```

The eventual application layout should reflect the selected language and packaging tools. Keep platform integration and analysis components behind narrow module boundaries; avoid prematurely creating empty modules before their technology choices are approved.

## Phase 1 entry criteria

Before ingestion implementation starts, settle the technology stack and desktop shell, supported OS and formats, library database strategy, app-data location, file identity and scan semantics, and test fixture approach. Phase 1 should then implement folder selection, safe enumeration, persisted inventory, progress, and pause/cancel/resume with acceptance criteria agreed in the roadmap.
