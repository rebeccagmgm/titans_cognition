# TITANS Cognition Agent Rules

## Project purpose

This project reconstructs an evidence-grounded cognitive map from read-only TITANS test-database metadata. V1 has two scopes: a broad `TITANS Panorama` and one deep method-validation case, `TITANS_TRADEFLOW`. It is not a generic metadata platform.

## Read before changing anything

1. Read `README.md` and `CONTEXT.md`.
2. Read `docs/spec/README.md`.
3. Read only the Spec modules relevant to the current change, plus any directly referenced module.
4. Check `docs/spec/12-open-decisions.md`; do not silently decide unresolved security, data-access, or provider questions.

## Hard boundaries

- Oracle access is read-only and metadata-only for V1.
- Broad extraction may cover only the explicitly configured Panorama Schema allowlist. Full structural and semantic inference applies only to explicitly configured Deep Cases.
- Do not query business rows, run profiling, write source systems, or execute jobs.
- Do not hardcode or print credentials, JDBC strings, internal hosts, tokens, Wiki secrets, or model API keys.
- Do not send internal metadata, comments, DDL, or Wiki content to an external model unless the data-egress decision is explicitly approved.
- LLM output is always a candidate. It must never overwrite physical facts or human review decisions.
- Preserve parser failures, uncertainty, counterevidence, and Unknown outcomes.

## Architecture boundaries

- V1 uses typed result datasets in Parquet/JSON/YAML and DuckDB for local analysis.
- Do not add PostgreSQL, Neo4j, DataHub, OpenMetadata, pgvector, message queues, remote workers, multi-user services, or authentication without an accepted scope change.
- Do not turn V1 into a generic ontology or metadata framework before the method is validated on a second Schema.
- Do not apply TRADEFLOW-validated deep rules or semantic labels to every Panorama Schema merely because its physical metadata was extracted.
- Use SQLGlot as one parser with explicit partial/failure states, not as an infallible lineage source.
- Keep deterministic extraction/analysis runnable without the LLM stage.

## Result integrity

- Every candidate must identify its method and supporting evidence.
- Numeric model or algorithm scores are method-local ranking signals, not calibrated probabilities.
- Human review is a decision, not evidence.
- Candidate clusters are run-scoped; reviewed families or concepts must not inherit unstable cluster identity implicitly.
- Generated maps and Object Cards are projections of canonical facts and typed candidate datasets, not independent sources of truth.

## Mandatory surrogate review

Before presenting a new or materially changed semantic map, classification, label system, table group, relation map, investigation card, review UI, or information-model Gate for user review, perform an independent surrogate review first.

- Review the user-facing result, not merely its tests, schemas, row counts, or successful generation.
- Challenge the proposed taxonomy. Examples and seed labels must not silently become a closed classification system.
- Check representative positive cases, ambiguous cases, and name-based counterexamples.
- For each critical table, concept, group, or relation, distinguish direct evidence, supporting field evidence, configuration seeds, inference, counterevidence, and Unknown.
- Fields may support, distinguish, or refute a table-level judgment, but field counts or token matches must not vote a table into a business category.
- A business group must explain evidenced collaboration among its members; configured membership or structural similarity alone is not a business relation.
- Inspect relation direction, predicate meaning, and evidence. Shared keys, naming, Wiki directory context, and absence of foreign keys are investigation leads rather than confirmation.
- Attempt to falsify every Gate with critical missing roles, disconnected groups, unsupported relations, misleading names, uneven evidence coverage, and vacuous-pass cases.
- Verify that the reader UI exposes uncertainty and evidence boundaries instead of presenting candidates as accepted truth.
- Record one disposition: `ACCEPT`, `REWORK`, `STOP`, or `DEFER`, with the decisive reasons and the smallest next action.

This surrogate review is an engineering and reader-value judgment made on the user's behalf when they are unavailable. It must not mark a user-review task complete, set `business_acceptance=ACCEPTED`, or grant scale authorization. If defects are within the authorized change, fix them and repeat the review before handoff. If remediation requires a material scope expansion or a user-owned business decision, stop and request direction.

## Implementation discipline

- Enforce the stage gates: finish V1A Panorama before V1B cognition work; validate one V1B vertical slice and its Gold Set before V1C full-scale inference.
- Do not implement V1C Object Family, Field Concept, Wiki/LLM enrichment, or all-object deep inference merely because their target contracts already exist.
- Add tests for parsing, rule behavior, output-schema validation, evidence linkage, and failure preservation.
- Keep generated data, model responses, DuckDB files, and secrets out of Git.
- Update the relevant Spec module when an implemented behavior intentionally changes a contract.
