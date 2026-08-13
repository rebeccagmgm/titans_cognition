## 1. Input contract and projection ownership

- [x] 1.1 Add the narrow catalog-review CLI entry point with explicit snapshot and output arguments, without coupling it to `build-context-semantic-map`.
- [x] 1.2 Implement manifest/JSONL validation for readable inputs, declared record count, unique indicator IDs, and source hashes; fail before publishing on mismatch.
- [x] 1.3 Implement snapshot-scoped atomic publication with a projection manifest that records snapshot ID, input paths/hashes, counts, and generated page path.

## 2. Catalog review projection

- [x] 2.1 Generate a self-contained review page from only source JSONL fields, including the explicit uncategorized branch for indicators without a catalog path.
- [x] 2.2 Render business definition and available source metadata in the detail panel, with explicit unavailable wording for processing SQL and other absent fields.
- [x] 2.3 Implement indicator selection and filter behavior across names, IDs, catalog labels, status, and business definition.
- [x] 2.4 Recompute visible indicator counts for the summary and every displayed branch while retaining a separate validated snapshot total.

## 3. Verification and delivery checks

- [x] 3.1 Add fixture tests for count/uniqueness validation, uncategorized grouping, business-definition retention, and unavailable-field rendering.
- [x] 3.2 Add a browser or DOM smoke check for filtering, branch-count updates, and clicking a concrete indicator to show its detail.
- [x] 3.3 Generate the projection for the `20260812-refresh` snapshot and verify 8,674 unique indicators, source-gap preservation, and manifest/page hashes.
- [x] 3.4 Re-run an unrelated context-semantic-map build against a temporary output and verify the catalog deliverable remains readable.
- [x] 3.5 Perform the mandatory surrogate review on representative cataloged, uncataloged, filtered, and missing-field cases; record `ACCEPT`, `REWORK`, `STOP`, or `DEFER` before handoff.
