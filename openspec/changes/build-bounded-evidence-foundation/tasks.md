## 1. Contracts and fixed inputs

- [ ] 1.1 Re-read the current dirty worktree and preserve all unrelated V1A/V1B changes; synchronize the accepted delta with `docs/spec` without rewriting historical run artifacts.
- [ ] 1.2 Define and validate the new Panorama classification result schemas, inference states, source-family provenance fields, graph lineage fields, Manifest entries and output paths.
- [x] 1.3 Add a classification configuration with hard limits for blocking, top-k edges, graph size, Leiden parameters, propagation iterations, candidate counts, Evidence Pack size, LLM calls and retries.
- [x] 1.4 Register Wiki `175428801` as a fixed read-only cached source with page/hash/timestamp metadata, and create a reviewable classification vocabulary that excludes people, partners and staffing data.
- [x] 1.5 Resolve the algorithm dependency choice through a bounded Windows install/license check and lock only the selected sparse-matrix and Leiden packages; do not add service infrastructure.

## 2. Schema matching and sparse graph

- [ ] 2.1 Extract the reusable name, column, type, key and dependency feature primitives from the current TRADEFLOW sample implementation while preserving its public behavior and regression tests.
- [x] 2.2 Implement versioned multi-view Schema Matching signals with separate scores, availability masks, root source references and explicit non-probability semantics.
- [x] 2.3 Implement bounded candidate-pair blocking, IDF treatment of common tokens, stricter cross-Schema admission and mutual top-k edge selection.
- [x] 2.4 Persist schema match signals and the sparse similarity graph with method/config hashes, `graph_run_id`, blocking reasons, signal decomposition and explicit missing-capability states.

## 3. Candidate family discovery

- [x] 3.1 Implement deterministic Leiden execution with fixed seed, resolution, weight method and run-scoped community identifiers.
- [x] 3.2 Classify partitions as publishable candidate family, weak family or singleton/Unknown using multi-view and connectivity checks, retaining edge and outlier explanations for every member.
- [x] 3.3 Add synthetic and regression tests proving that a Leiden partition is not automatically a business category and that weak/singleton communities are not promoted.

## 4. Weak supervision and bounded propagation

- [ ] 4.1 Implement labeling-function outputs with `ABSTAIN`, classification dimension, `source_family`, root source references and raw method trace for Wiki, physical names, comments and declared structure.
- [x] 4.2 Implement source-family aggregation and conflict detection; explicitly reject `LF_CLUSTER_NEIGHBOR` and prevent candidate family membership or repeated name rules from increasing independent support counts.
- [x] 4.3 Implement one multi-dimension, clamped Label Propagation stage over the existing graph with configured convergence and iteration bounds, cross-Schema restrictions and per-object candidate limits.
- [x] 4.4 Emit business-class candidates and task-level Single/Competing/Unknown/Not Evaluable results with propagation paths and limitations; never emit automatic `ACCEPTED` decisions.
- [x] 4.5 Add audit tests showing that graph-derived family, graph neighborhood and propagation do not appear as three independent evidence sources.

## 5. Conditional LLM interpretation

- [x] 5.1 Implement bounded candidate-family Evidence Packs, Prompt/output schemas, Evidence ID allowlists, counterevidence retention and content-addressed cache keys without adding autonomous tool access.
- [x] 5.2 Implement the default disabled/Not Evaluable path and one bounded validated execution path that can be enabled only after D-005 records an approved Provider, account and metadata/Wiki egress scope.
- [x] 5.3 Treat valid LLM outputs as provenance-bearing weak label proposals rather than new evidence; preserve Respond/Abstain, invalid references, one repair retry and terminal failures.
- [ ] 5.4 Add contract tests for disabled mode, cache replay, Abstain, fabricated asset IDs, invalid Evidence IDs, retry exhaustion and non-blocking per-pack failure.

## 6. Readback and verification

- [x] 6.1 Generate a minimal local `classification-review` Projection showing candidate families, business-class candidates, conflicts, Unknown, source-family lineage and the “not business accepted” boundary.
- [x] 6.2 Verify deterministic replay on synthetic fixtures and a bounded real Schema run, including identical hashes, stable Leiden output under fixed configuration, graph/iteration/cost ceilings and failure preservation.
- [ ] 6.3 Run the approved Panorama allowlist once without LLM, record counts, edge/family distributions, Unknown/conflict rates, runtime and peak output size, and stop if configured ceilings are exceeded.
- [x] 6.4 If D-005 is approved, run only the configured bounded LLM family sample and verify cache/readback; otherwise record LLM as Not Evaluable without blocking deterministic completion.
- [x] 6.5 Run the full unit/contract suite, OpenSpec strict validation, sensitive-output scan and map link checks; document what the result proves and explicitly does not prove.
- [x] 6.6 Present the review Projection and a small stratified set of strong families, weak families, conflicts and Unknowns for user review; do not start `deliver-and-validate-business-panorama` in this Change.
