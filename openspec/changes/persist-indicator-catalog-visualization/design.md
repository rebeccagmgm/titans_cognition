## Context

See `proposal.md` for the motivation and user-visible scope. The current page is a hand-maintained file below `context-enriched-field-semantic-map`; that directory is replaced as a unit by the context-map writer. The indicator snapshot is a separate evidence product with a manifest and JSONL, so it needs a separate projection owner.

## Goals / Non-Goals

**Goals:**

- Add one small, explicit catalog-review generation path keyed to a snapshot ID.
- Make the generated page self-contained and deterministic enough for local review.
- Keep counts, business definitions, catalog gaps, and unavailable source fields honest and inspectable.
- Publish only after input validation and preserve the source hashes in metadata.

**Non-Goals:**

- Do not add a generic metadata platform, database, server, authentication, or external model call.
- Do not enrich indicators from Wiki, SQL execution, or business rows.
- Do not modify the semantics of `build-context-semantic-map` or merge this page into its atomic directory.
- Do not treat catalog labels or business definitions as validated business acceptance.

## Decisions

### 1. Use a dedicated catalog projection command

Add a narrow CLI entry point that takes `--snapshot-dir` and `--output`, rather than hiding catalog generation inside the context-map command. This keeps ownership aligned with the input evidence product and avoids the existing atomic-directory replacement. A manually copied HTML file is rejected because it cannot be reproduced or protected from rebuilds.

### 2. Publish under a snapshot-scoped stable directory

The command writes to an output such as `output/indicator-catalog-review/<snapshot-id>/` (the exact root remains configurable), containing the HTML page and a projection manifest. The final directory is replaced atomically only after validation and complete generation; it is never a child of `context-enriched-field-semantic-map`.

### 3. Treat the snapshot as the sole semantic source

Normalize only the fields already present in the JSONL. Missing `catalog` becomes an explicit uncategorized node. Missing processing SQL remains an explicit unavailable value. Business definition is copied into the detail payload and escaped at render time; no name-based fallback is allowed.

### 4. Compute counts from the filtered row set

The browser-side projection keeps the full validated row set and derives visible rows from the current filter. Branch badges and the summary are recalculated from those visible rows, while a separate snapshot-total badge prevents a filtered count from being mistaken for completeness.

### 5. Validate and verify without broadening evidence scope

Validation checks manifest/JSONL readability, declared count, unique IDs, and output metadata. Tests use a small fixture for deterministic grouping/filtering and an integration-style rebuild check that proves an unrelated context-map replacement does not remove the catalog deliverable. No production or business-row access is introduced.

## Risks / Trade-offs

- [Risk] A self-contained HTML file can become large for thousands of indicators. → Mitigation: keep the page static and snapshot-scoped; measure size in verification, and defer sharding unless the fixture or real snapshot demonstrates a need.
- [Risk] Source catalog paths may be incomplete or inconsistent. → Mitigation: preserve an explicit uncategorized branch and report source counts; never silently discard rows.
- [Risk] A stable output can be mistaken for accepted business truth. → Mitigation: show snapshot ID, source hashes, unavailable-field wording, and evidence-boundary text in the page and manifest.
- [Risk] Existing dirty worktree contains ad-hoc visualization scripts. → Mitigation: implementation tasks must identify the owned entry point and tests explicitly; do not rely on or delete those scripts implicitly.

## Migration Plan

1. Implement the command, projection manifest, and tests behind the new Change.
2. Generate the page for the `20260812-refresh` snapshot and compare total/unique counts and representative detail fields with the JSONL.
3. Run the context-map build in a temporary output and verify the catalog deliverable remains readable.
4. Retire the manually copied page only after the new deliverable passes the surrogate review; rollback is to stop invoking the new command and keep the source snapshot unchanged.

## Surrogate Review Disposition

`ACCEPT` for this bounded proposal only, not for reader delivery or business acceptance. The critical acceptance conditions are that the 8,674-row snapshot is neither expanded nor silently reduced, the 335 source rows without a catalog path remain visible under an explicit gap node, filter counts are derived from visible rows, and missing processing SQL is labeled as unavailable rather than inferred. Any implementation that fails one of these conditions is `REWORK` before handoff.
