# Changelog

## v2.2 packaging correction — 2026-10-02

- Always open Overview on startup instead of restoring the last tool page.
- Store release preferences separately from development and legacy settings.
- Reset copied preferences when they belong to another PC or user profile.
- Reject settings, logs, and runtime caches when creating the release ZIP.
- Preserve each user's own recent history and theme across subsequent launches.

## v2.2 — 2026-10-01

### GUI and workflow

- Introduced the PySide6 workspace with grouped navigation and consistent
  typography, control sizing, spacing, and diagnostic panels.
- Added persistent White, Grey, and Black themes across the application.
- Added Overview health indicators, quick actions, and recent target history.
- Added command search (`Ctrl+K`), module shortcuts, and searchable local help.
- Added background progress and cancellation, with one active task across pages.
- Clarified file/folder selection requirements and operation summaries.
- Included all eight tools in the complete Windows release, including BML editing.

### Runway Fixer

- Snap small RunwayDim heading errors to the closest valid runway end within
  a configurable 4–6° cone (default 5°).
- Preserve headings matching either runway end regardless of First/Second priority.
- Use priority outside the cone; add Force to explicitly override the protection.
- Explain heading decisions in diagnostics and show embedded before/after maps.
- Support runway list, assignment, heading, crossing, and taxi-path checks.

### Backups and safer writes

- Added timestamped snapshots with original filenames, restore layout, manifests,
  and copy-back instructions.
- Added a shared backup setting and configurable destination for standard tools.
- Kept BML save backup selection separate from the global setting.
- Preserve XML declarations, CRLF, BOMs, comments, and unrelated whitespace
  when changing values, instead of reserializing whole documents.
- Recheck inputs before commit and provide atomic writes and coordinated rollback.
- Preserve completed batch commits on cancellation and report them clearly.

### Tool improvements

- Parking moves require a preview and reject stale source data on apply.
- Offset Fixer supports XY, rotation, Z, heading, and value changes;
  repeated setters with unchanged values produce no writes or backups.
- BML Editor supports v1 texture IDs/skinsets and v2 material renaming,
  with verified recompression and coordinated Parent.dat/materials.mtl updates.
- Added single/batch workflows, structured service results, and diagnostics
  across the migrated database tools.

### Distribution and verification

- Made the PySide6 GUI the repository's main application: app.py, src/, tests/,
  tools/, and build scripts now live at the public repository root.
- Removed the previous StructureAdjuster.py GUI and nested rework directory
  from the current public source tree; existing Git history remains available.
- Publish source without the BML editor implementation; include BML capability
  in the complete Windows binary. Public-source builds use the SourceEdition name.
- Keep the full local source separate from the reviewed public Git checkout.
- Record public source hashes and exclude private implementation and binaries
  from source commits.
- Corrected a frozen Qt startup failure caused by an incompatible Poppler ICU DLL.
- Passed automated local and public-source service, GUI, and publication tests.
- Passed 24 copied-theater XML acceptance tests; all 9,198 installed original
  XML hashes remained unchanged.
- Verified embedded BML modules and startup of the full Windows bundle.

### Known limitations

- The complete binary cannot be rebuilt from public source alone because the
  BML editor implementation is maintained separately.
- The portable ZIP requires the executable and `_internal` folder together.
- Installer and automatic updater integration remain planned.
- Frozen-binary verification covers startup, rather than an automated GUI edit.
