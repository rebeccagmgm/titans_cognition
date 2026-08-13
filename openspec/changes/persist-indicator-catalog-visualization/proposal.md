## Why

The indicator catalog review page is currently a manually copied projection under a generated output directory. The context-map build atomically replaces that directory, so the page disappears; the surviving page also needs an explicit contract for snapshot counts, missing catalog paths, business definitions, and source-data gaps.

## What Changes

- Add a deterministic, officially generated indicator-catalog review projection for a named indicator snapshot.
- Place the projection in a stable deliverable location that is not removed by unrelated atomic context-map rebuilds.
- Preserve the snapshot's unique indicator count and expose counts for the current filtered view and catalog nodes.
- Include business definitions when present and represent absent processing SQL or source fields as explicit unavailable states rather than inferred content.
- Add bounded verification that the projection survives a rebuild and remains aligned with the snapshot manifest and JSONL.

## Capabilities

### New Capabilities

- `indicator-catalog-visualization`: Generate and review a deterministic, filterable catalog tree and indicator detail panel from a pinned indicator snapshot, with evidence-bound metadata and stable output handling.

### Modified Capabilities

- None.

## Impact

- A small generator/projection entry point and its tests in the TITANS Cognition project.
- The indicator snapshot review deliverable and its manifest/index metadata; no source-system writes, business-row reads, or external model calls.
- Existing context-semantic-map generation remains unchanged except that its atomic output replacement must not be treated as the owner of this separate catalog deliverable.
