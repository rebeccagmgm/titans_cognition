## 1. Freeze Inputs and Define Contracts

- [x] 1.1 Record the fixed TRADEFLOW V2 directory, Wiki Tree snapshot, Panorama link root, configuration and content hashes; fail on scope or snapshot drift.
- [x] 1.2 Add JSON Schemas and typed models for BusinessConcept, BusinessContext, AttributeExpression, Qualifier, TechnicalAsset references, six semantic relation types, Assertion, Evidence Ref and Manifest.
- [x] 1.3 Add fixture-first contract tests for allowed subject/object types, `EXPRESSION_OF`, multi-context reuse, open Qualifier dimensions, relation governance, dangling references and preserved Unknown/Conflict.
- [x] 1.4 Add an independent CLI/output directory for the context-enriched Projection that never writes V1, V2, Physical Facts or Wiki cache files.

## 2. Build Wiki Semantic Candidates

- [x] 2.1 Add deterministic parsing tests for `tree.jsonl`, duplicate page IDs, missing parents, depth/path reconstruction, escaped numbering, dates, ticket identifiers and retained original titles.
- [x] 2.2 Implement title/path normalization and candidate extraction for domain/product, object, subject, event, process, attribute, rule, document context and Unknown without converting directory parentage into business hierarchy.
- [x] 2.3 Build bounded Wiki candidate indexes for normalized labels, aliases, path tokens and document contexts; preserve pageId, snapshotId, ancestor path and error/visibility boundaries.
- [x] 2.4 Produce diagnostics for ambiguous types, noisy branches, failed child reads and pages requiring bounded正文 follow-up; do not fetch all Wiki正文.

## 3. Derive Data Semantic Candidates and Stable Expressions

- [x] 3.1 Add tests that derive reusable AttributeExpression candidates from V2 concepts, expressions, Facets, bindings and physical IDs without changing upstream files.
- [x] 3.2 Implement observed-expression materialization and deterministic expression-tree Projection; prohibit unobserved Facet Cartesian combinations and `NARROWER` publication for qualifier-only differences.
- [x] 3.3 Implement multi-to-many `APPEARS_IN` candidates, including generic/unknown context and evidence-bearing split suggestions only when definition, grain, calculation or usage differs.
- [x] 3.4 Aggregate `IMPLEMENTED_BY` first by normalized physical field expression and then by concrete `Schema.Table.Column`; retain `EXPRESSES/RELATED_TO` provenance from V2.

## 4. Map Wiki and Data Candidates with Evidence

- [x] 4.1 Add positive, negative and conflict fixtures for lexical overlap, bilingual alias, product/object context compatibility, document-context noise, same-label cross-context reuse and unsupported precision.
- [x] 4.2 Implement data-candidate-driven top-K Wiki recall with configurable per-expression, per-concept and正文-read budgets; reject unbounded all-pairs matching.
- [x] 4.3 Generate typed mapping Assertions with independent signals, counterevidence, method trace, internal ranking score and review status; prevent correlated signals from being counted as independent evidence.
- [x] 4.4 Add optional compact LLM review-pack preparation/import for ambiguous candidate types or mappings, preserving D-005 boundaries and preventing automatic write-back.

## 5. Validate the Information Model Before UI Work

- [x] 5.1 Run the fixed nominal-principal investigation and produce a readable JSON/Markdown card covering stable expressions, qualifiers, contexts, physical expressions, fields, tables, related concepts, evidence and conflicts.
- [x] 5.2 Verify that initial, dynamic and long/short dynamic nominal-principal expressions are reusable across contexts by default and that generic transaction-summary fields are not forced into a product context.
- [x] 5.3 Run at least one non-amount concept with different qualifier/relationship patterns to prove the five object types, six relations and open dimensions are not nominal-principal special cases.
- [x] 5.4 Evaluate the model Gate: fail on invented combinations, directory-as-business-tree conversion, forced context partition, invalid relation endpoints, hidden Unknown/Conflict or non-replayable hashes; retain failed artifacts.
- [x] 5.5 Run a surrogate bottom-data review over positive, ambiguous and counterexample concepts; block unreviewed corpus modifiers, expose cross-concept physical bindings and label/base mismatch, and separate orthogonal qualifier axes before handoff.
- [x] 5.6 Separate immutable semantic observations, machine hypotheses, versioned review decisions and the published projection; enforce deterministic publication reasons and prevent unpublished hypotheses from entering the main map.
- [x] 5.7 Move upstream Facet-to-Qualifier axis mapping into versioned case configuration and add source-to-publication counterexample Gates that do not depend only on already-created Conflict flags.

## 6. Deliver the Dual-Tree Three-Column Review Page

- [x] 6.1 After the model Gate passes, build compact indexes for global concept/expression search, navigation tree, expression tree, context relations, physical expression groups, evidence and Panorama links.
- [x] 6.2 Implement the left business navigation tree, middle faceted AttributeExpression matrix and right selected-expression detail with business-readable Chinese labels and technical details collapsed.
- [x] 6.3 Implement qualifier filtering over existing expressions only, alternate-path hints, related-concept separation, grouped physical names, paginated field/table expansion and back-navigation from tables.
- [ ] 6.4 Add browser tests for first-load bounds, search debounce, shard request races, large expression families, pagination, unknown contexts, evidence display and broken/missing Panorama targets.
- [ ] 6.5 Produce final nominal-principal and second-concept acceptance cards and obtain user review before changing the recommended review entry or claiming reader usability.

## 7. Verify and Document the Bounded Change

- [ ] 7.1 Run focused and full tests, schema/reference validation, deterministic replay, content-hash checks, JavaScript syntax/browser checks and sensitive-output scans.
- [x] 7.2 Update relevant project specs, README/current status and D-004 Wiki input decision only for behavior actually implemented; keep engineering completion, reader delivery, business acceptance and scale authorization separate.
- [x] 7.3 Run `openspec validate build-context-enriched-field-semantic-map --strict` and review the final diff for accidental Canonical writes, nominal-principal special cases, full-Wiki expansion, generated artifacts or secrets.
