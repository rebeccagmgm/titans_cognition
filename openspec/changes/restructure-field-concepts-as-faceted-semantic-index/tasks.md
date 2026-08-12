## 1. Freeze Baseline and Define V2 Contracts

- [ ] 1.1 Record the fixed TRADEFLOW Physical Facts, 233-table scope, V1 field-concept run, ontology-review and LLM-review paths/hashes without modifying their contents.
- [ ] 1.2 Add typed V2 configuration and JSON schemas for supported/provisional base concepts, DOMAIN/TECHNICAL/UNRESOLVED semantic scope, source/alias/variant expressions, per-field semantic results, field facets and the run Manifest.
- [ ] 1.3 Add fixture-first contract tests for valid references, run-scoped IDs, deterministic canonical keys, support status, semantic scope, inference outcomes, candidate bindings, expression kinds/statuses, Facet records and rejected dangling references.
- [ ] 1.4 Add an independent `discover-field-semantics` CLI/output path that refuses scope drift and never writes into V1 or Physical Facts directories.

## 2. Normalize Source Expressions and Extract Decorations

- [ ] 2.1 Add tests for Unicode/case/spacing/connector normalization, snake/camel/digit tokenization and preservation of original field/comment text.
- [ ] 2.2 Implement typed extraction of dictionary markers, enum/value-domain text, date/time formats, units, currency codes, precision/scaling notes, deprecation notes and implementation remarks.
- [ ] 2.3 Add regression tests proving recognized decorations do not become standalone base concepts while their original text and source locator remain available.
- [ ] 2.4 Add quarantine diagnostics for truncated, concatenated, suspicious-typo and unresolved-abbreviation expressions without auto-correcting Physical Facts.

## 3. Decompose Head Concepts and Facets

- [ ] 3.1 Add tests covering center-word priority over prefixes and stages, including expense, interest, income and capital expressions prefixed by current-day or period markers.
- [ ] 3.2 Implement deterministic head-concept candidate extraction using field/comment tokens, corpus recurrence and low-weight table context while keeping declared type non-authoritative.
- [ ] 3.3 Define versioned, concept-agnostic Facet dimensions for temporal stage, direction, currency basis, party role, lifecycle stage, measure state, unit/format/sequence and unresolved qualifiers.
- [ ] 3.4 Implement multi-Facet decomposition so modifier combinations bind to one base concept rather than generating a Cartesian hierarchy.
- [ ] 3.5 Preserve competing head candidates and UNKNOWN outcomes when evidence is insufficient instead of assigning an `Other` concept.
- [ ] 3.6 Add metamorphic tests that replace named acceptance concepts with synthetic center words while preserving modifier structure, proving the same Facet and outcome logic applies without concept-name branches.
- [ ] 3.7 Implement evidence-bearing DOMAIN/TECHNICAL/UNRESOLVED scope candidates for generic audit, synchronization, provenance and configuration patterns without hiding any field or using table/concept-specific rules.

## 4. Build Alias, Variant and Candidate Relationships

- [ ] 4.1 Add tests distinguishing exact normalized aliases, supported bilingual/abbreviation alias candidates, qualified variants, approximate competitors and unrelated lookalikes.
- [ ] 4.2 Implement high-precision alias classes and a validation gate that rejects normalized-identical parent/child or duplicate base-concept output.
- [ ] 4.3 Reuse bounded n-gram, TF-IDF, token and context similarity only for Alias/Variant/competing-concept recall; prevent clusters or dendrogram levels from becoming published `is-a` structure.
- [ ] 4.4 Keep resolvable single-member expressions searchable as PROVISIONAL concepts or Variants, implement the configured independent-support gate for SUPPORTED concepts, and record its field/object/expression counts in the Manifest.
- [ ] 4.5 Generate explicit CONFLICT/review candidates for cross-context same labels, numeric suffix slots, suspicious spellings and near-tied concepts without automatic merge.

## 5. Write Canonical Results and Quality Gates

- [ ] 5.1 Write deterministic, stable-order `base_concepts.jsonl`, `concept_expressions.jsonl`, `field_semantic_results.jsonl`, `field_facets.jsonl` and `manifest.json` with content hashes and method versions.
- [ ] 5.2 Add cross-file validation for Physical `column_id`, concept/expression/binding/Facet references, allowed statuses, source locators and input scope hashes.
- [ ] 5.3 Add structural quality gates for zero normalized-identical hierarchy artifacts, zero recognized-decoration base concepts, preserved UNKNOWN/COMPETING/CONFLICT and absence of field/table/concept-specific algorithm branches.
- [ ] 5.4 Generate a V1-to-V2 comparison Projection aligned by `column_id`, without treating either V1 nodes or existing LLM suggestions as accepted truth.

## 6. Run the Canonical TRADEFLOW Gate Before UI Work

- [ ] 6.1 Run V2 against the fixed TRADEFLOW 233-table input and verify V1, ontology-review, LLM-review and Physical Facts hashes remain unchanged.
- [ ] 6.2 Produce a lightweight JSON/Markdown comparison for duplicate hierarchy artifacts, decoration-derived concepts, supported/provisional concepts, DOMAIN/TECHNICAL/UNRESOLVED distribution, Alias/Variant, Facet coverage and Conflict/Unknown outcomes.
- [ ] 6.3 Execute the five representative investigations—nominal principal, counterparty, execution time, margin and trade direction—directly against Canonical files, showing field/table lookup, Facet composition, regressions and unresolved gaps without using their names in algorithm configuration.
- [ ] 6.4 Evaluate the semantic-shape Gate: require structural invariants, deterministic replay and result-level bidirectional lookup; record clearly that this does not prove overall member semantics.
- [ ] 6.5 If the Gate fails, retain the failed run and report, stop full review-page work, and do not invoke full-tree LLM repair or expand scope.

## 7. Deliver Scalable Bidirectional Review After the Gate

- [ ] 7.1 After task 6.4 passes, add compact Projection indexes for concept-to-binding, Facet-to-binding, semantic-scope-to-binding, column/table-to-binding and normalized-expression search.
- [ ] 7.2 Build a lazy, paginated V2 review page with concept and Facet filters, Alias/Variant views, Conflict/Unknown views and links to tables/Object Cards and the frozen V1 baseline.
- [ ] 7.3 Add browser-independent DOM/static tests proving initial rendering and per-interaction rendering stay within configured bounds rather than scaling with all fields.
- [ ] 7.4 Verify the V2 page and pipeline do not read table/business-topic classification inputs while all results retain stable `column_id` and `asset_id` connection points for a future independent Projection.
- [ ] 7.5 Record visible investigation improvements, regressions and remaining evidence gaps; if the final page adds no value beyond the lightweight report, keep the report as the delivery and restore the V1 page as default.

## 8. Verify and Document the Bounded Change

- [ ] 8.1 Run focused tests, the full existing test suite, linting, schema/reference validation and deterministic replay/hash checks.
- [ ] 8.2 Update relevant project specs and user documentation for the V2 command, contracts, staged Gate, V1 rollback path, candidate boundary, no-row-data rule, D-005 boundary and fixed TRADEFLOW scope.
- [ ] 8.3 Run `openspec validate restructure-field-concepts-as-faceted-semantic-index --strict` and review the final diff for regressions, accidental scope expansion, secrets and generated-output leakage.
