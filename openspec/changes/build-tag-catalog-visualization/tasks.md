## 1. Freeze and validate the tag snapshot input

- [x] 1.1 Define the explicit snapshot input contract for `detail-manifest.json`, `dimension-details.jsonl`, `catalog-tree.json`, and `dimension-sql/`.
- [x] 1.2 Validate manifest counts, unique `tagDimId`, readable JSON/JSONL, declared SQL files, and source hashes before publication.
- [x] 1.3 Add fixtures for a nested path, missing path, duplicate ID, malformed record, missing SQL, `FOUND` SQL, and `GENERATED_LOCAL` SQL.

## 2. Build the multi-level tag catalog projection

- [x] 2.1 Implement path parsing using an explicit, tested delimiter/encoding rule and preserve unparseable paths in a visible fallback branch.
- [x] 2.2 Build directory nodes and tag-dimension leaf nodes without losing any source record.
- [x] 2.3 Add uncategorized/source-missing grouping and node/summary counts derived from the visible subset.
- [x] 2.4 Add bounded filtering by tag name, ID, catalog path, status, and description.

## 3. Render tag details and dimension SQL evidence

- [x] 3.1 Render source-backed tag fields, evidence status, snapshot identifier, and source references in the detail panel.
- [x] 3.2 Add safe SQL file resolution, existence checks, SHA-256 verification, and a readable SQL view or link.
- [x] 3.3 Distinguish `FOUND`, `GENERATED_LOCAL`, and unavailable SQL in both metadata and reader-facing text.
- [x] 3.4 Keep task SQL, task logs, SQL execution, and business-row access out of the projection.
- [x] 3.5 Add display-only SQL syntax highlighting while preserving the raw SQL text and line structure.

## 4. Publish and verify the reader artifact

- [x] 4.1 Add a dedicated snapshot-scoped generation entry point and atomic output publication with projection manifest.
- [x] 4.2 Add DOM/browser smoke checks for tree navigation, filtering, count updates, detail selection, and SQL display.
- [x] 4.3 Generate the projection from the current 2,424-dimension snapshot and verify record preservation, catalog grouping, and SQL evidence counts.
- [x] 4.4 Verify malformed or mismatched input does not replace an existing valid projection.
- [x] 4.5 Perform independent surrogate review on representative cataloged, unclassified, found-SQL, locally-generated-SQL, and unavailable-SQL cases; record `ACCEPT`, `REWORK`, `STOP`, or `DEFER`.
