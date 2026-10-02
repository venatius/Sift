# Sift Product Definition

**Status:** Phase 0 baseline  
**Last updated:** 2026-10-02

## Product

Sift is a polished desktop application that helps people understand and organize large collections of photos and videos stored on their own HDDs and SSDs. Users choose or drop folders into Sift. The app scans and analyzes the collection locally, then presents useful ways to find, group, and review the media without requiring users to move or rename their original files.

The product includes a downloadable desktop app, a product website, and a public source repository. Local privacy, user control, clear explanations, and dependable handling of large libraries are core product requirements.

## Problem and audience

People accumulate media across folders and drives, often with inconsistent names, repeated exports, screenshots, documents mixed in, and no reliable way to find related moments. Manual sorting takes too long and can damage carefully maintained folder structures. Cloud upload services can be unsuitable for private libraries or large collections.

Sift is for people with substantial personal or professional local media collections who want to find and understand what they have before deciding what to change.

## Product promise

Choose a local folder and Sift will build a searchable, understandable view of its media while leaving original files in place. Sift will identify likely duplicates, classify content, group related items, and recommend organization. Users remain in control of any action that changes files.

## Product principles

1. **Local by default:** media bytes and analysis stay on the user's computer. No account or cloud service is required for core functionality.
2. **Originals are protected:** scanning and organization views do not move, rename, edit, or delete source files.
3. **Review before change:** any operation that changes files requires an explicit, inspectable user decision and a recoverable path where feasible.
4. **Explain uncertainty:** inferred labels, matches, people, and events are presented as estimates with understandable evidence and confidence.
5. **Useful early, improves incrementally:** basic inventory and exact duplicate results arrive before expensive analysis; later runs reuse prior work.
6. **Handles real libraries:** progress, pause/resume, cancellation, errors, and resource controls are designed for large and mixed-quality collections.
7. **Accessible and polished:** clear language, keyboard support, responsive layouts, and thoughtful empty/error states are part of the product.

## Core user journey

1. Install and launch Sift without creating an account.
2. Choose one or more folders on local or removable HDD/SSD storage, or drag folders into the app.
3. Review the scan scope, exclusions, and privacy statement; start scanning.
4. See immediate inventory and progress, with the ability to pause or cancel.
5. Browse media through virtual categories, search, duplicate groups, and suggested people or event groupings.
6. Inspect why an item was classified or grouped, correct mistakes, and mark preferred items.
7. Review any proposed file operation, understand its impact, then explicitly approve or dismiss it.
8. Return later to an up-to-date library without redoing unchanged analysis.

## Scope for the first release

The first release should deliver a dependable local desktop workflow for selecting folders, inventorying supported media, finding exact and visually similar duplicates, browsing useful classifications, searching by visual content, and reviewing suggested groupings. It should support safe, explicit organization actions, but those actions should be limited to clearly previewed and recoverable operations.

The initial release should prioritize Windows, given the project environment, while keeping platform-dependent code isolated enough to support macOS later. Specific minimum OS versions, hardware targets, formats, and release platforms must be confirmed before implementation.

## Out of scope for the first release

- Cloud storage, cloud processing, required accounts, or telemetry containing media data.
- Automatic destructive cleanup or silent changes to original folders.
- A full photo editor, video editor, or general-purpose file manager.
- Guaranteed identity recognition, perfect event detection, or claims that machine-generated labels are always correct.
- Mobile apps and collaborative/shared libraries.
- A promise to support every codec, raw format, or legacy file type.

## Functional requirements

### Library and ingestion

- Add multiple folders and drives; show selected roots and scan scope before processing.
- Enumerate files without following directory links outside the selected scope by default.
- Support include/exclude rules and report inaccessible, unsupported, and changed files.
- Pause, resume, cancel, and retry work; preserve useful progress across app restarts.
- Detect added, removed, and changed files on later scans without unnecessarily repeating analysis.

### Inventory and analysis

- Record stable file identity information, paths, sizes, timestamps, media type, and available metadata.
- Separate source/document classification from photo/video media classification.
- Identify byte-identical files and visually similar candidates as distinct match types.
- Generate image/video features locally for classification, visual search, and grouping.
- Group likely people and events with controls to correct, merge, separate, or hide groupings.
- Represent categories and collections virtually; do not require copying or moving files to browse them.

### Browse, search, and review

- Provide thumbnail-based browsing, filters, sorting, and text/visual search as capabilities become available.
- Make model-generated results distinguishable from verified file metadata.
- Show confidence and useful reasons for classifications, duplicate matches, and group suggestions.
- Allow users to correct results and make those corrections durable across rescans where possible.
- Before a file operation, show exact affected paths, the proposed result, and consequences; require explicit confirmation.
- Provide undo or recovery guidance for supported operations and report partial failures accurately.

### Performance and reliability

- Prioritize fast inventory and exact duplicate detection before expensive inference.
- Use incremental processing, content fingerprints, cached derived data, bounded batches, and configurable concurrency.
- Avoid loading full-resolution collections into memory; use thumbnails and stream large media where possible.
- Expose progress by stage and useful estimates when available; do not claim false precision.
- Handle corrupt, unsupported, locked, and disconnected files without aborting the full scan.

## Privacy and data handling requirements

- Media files are read from their existing locations; Sift does not upload their contents.
- Core features work offline after installation and model acquisition.
- Any optional update or model download is initiated or disclosed clearly and contains no user media.
- Explain what metadata, thumbnails, indexes, embeddings, and caches Sift stores, and where it stores them.
- Provide a way to clear Sift's generated library data without changing original media.
- Do not include filenames, paths, thumbnails, embeddings, or other library-derived data in diagnostics sent outside the device.
- Document that third-party model or codec components run locally and identify their licenses and data behavior.

## Success measures

Phase 0 does not set numerical targets until representative collections and hardware are agreed. The first release should measure, locally and transparently:

- Time to first useful inventory and exact duplicate results.
- Scan completion and incremental rescan time on representative libraries.
- Memory, CPU, GPU, and disk use during each analysis stage.
- Precision and recall of duplicate suggestions, with exact and near-duplicate results reported separately.
- User correction rates for classifications and group suggestions.
- Successful recovery or undo rate for supported file actions.
- Crash, stalled-scan, and unrecoverable database error rates.

## Phase 0 completion checklist

- Product promise, principles, initial audience, and release scope are reviewed.
- [x] Supported media formats are decided.
- [ ] Representative test collections, minimum hardware, and minimum OS versions are decided.
- Privacy boundary and local-data retention behavior are approved.
- [x] The architecture document defines modules, data ownership, processing flow, and safety boundaries.
- Open technical choices have recorded decisions or explicit owners and due points.
- Phase 1 has acceptance criteria and is the only implementation phase authorized to begin next.
