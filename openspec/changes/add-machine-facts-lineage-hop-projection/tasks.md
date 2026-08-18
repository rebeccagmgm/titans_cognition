## 1. Contract and failing tests

- [x] 1.1 Add typed local Plan Hop records and Machine Facts Root/Node/Edge records, enums, method versions, and required bundle output declarations.
- [x] 1.2 Add JSON Schemas for the three Hop datasets and extend the Machine Facts Manifest schema with Hop counts and validation gates.
- [x] 1.3 Add failing fixtures for computed CTE, rename trail, FROM subquery, scalar/EXISTS flattening, final Star Expansion, UNION fan-out, mixed physical-terminal plus downstream Hop, shared DAG producer, and unresolved/unsupported coverage.
- [x] 1.4 Add failing validator tests for missing endpoints, cycles, duplicate/non-deterministic identities, invalid via references, count/hash mismatch, and FULL_HOP origin-conservation mismatch.

## 2. Native Hop projection

- [x] 2.1 Extend the Plan Adapter to retain Scope-to-local-Relation and Projection-to-local-Expression mappings for Project/Aggregate expressions without changing existing Relation or Base-Origin semantics.
- [x] 2.2 Implement deterministic native Hop coverage classification for FULL_HOP, FLAT_ORIGIN_ONLY, UNKNOWN_COVERAGE, and NOT_EVALUABLE, including explicit Star, scalar/EXISTS, unsupported Expr/Source, and missing Scope mapping outcomes.
- [x] 2.3 Serialize `lineageOf()` results into deduplicated local Root/Node/Edge facts while preserving Hop-level ordered via, physical terminals, shared DAG nodes, mixed terminal/downstream inputs, and Setop branch identity without fabricating Setop hops.
- [x] 2.4 Preserve native failures and degraded coverage as typed Plan/Machine Facts Unknown or Not Evaluable outcomes; never publish orphaned nodes or edges.

## 3. Machine Facts publication and validation

- [x] 3.1 Globalize every Hop Relation/Expression/Field endpoint and deterministic Hop/Edge ID in the Machine Facts writer, then publish the three sorted JSONL datasets.
- [x] 3.2 Extend Manifest generation, required-output validation, schema validation, referential integrity, DAG acyclicity, status truth-table checks, and FULL_HOP origin-conservation validation.
- [x] 3.3 Bump the relevant adapter/writer/schema versions so old bundles rebuild through existing recoverable publication; verify replacement and deterministic replay behavior.
- [x] 3.4 Update the SQL analysis documentation and the reusable Machine Facts contract documentation with VALUE_LINEAGE scope, coverage states, file responsibilities, and Consumer boundaries.

## 4. Verification and review

- [x] 4.1 Run the focused Hop/Plan/Machine Facts tests, the existing Machine Facts regression suite, and `npm run typecheck`; fix implementation defects without weakening assertions.
- [x] 4.2 Run strict OpenSpec validation and rebuild/replay a representative ignored Machine Facts bundle, confirming first-run replacement, second-run reuse, stable index bytes, and no generated artifacts tracked by Git.
- [x] 4.3 Perform code review and the mandatory independent surrogate review against CTE, rename, Star, UNION, mixed, unresolved, and rowset-control counterexamples; record `ACCEPT`, `REWORK`, `STOP`, or `DEFER` and remediate in-scope defects before handoff.
