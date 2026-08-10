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

## Implementation discipline

- Enforce the stage gates: finish V1A Panorama before V1B cognition work; validate one V1B vertical slice and its Gold Set before V1C full-scale inference.
- Do not implement V1C Object Family, Field Concept, Wiki/LLM enrichment, or all-object deep inference merely because their target contracts already exist.
- Add tests for parsing, rule behavior, output-schema validation, evidence linkage, and failure preservation.
- Keep generated data, model responses, DuckDB files, and secrets out of Git.
- Update the relevant Spec module when an implemented behavior intentionally changes a contract.
