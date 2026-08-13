## 1. Contract and Failure Fixtures

- [x] 1.1 Add versioned Workflow Profile, Schema Case Pack and derived run-report Schemas with an explicit authority matrix and no arbitrary-command fields.
- [x] 1.2 Add TRADEFLOW plus structurally different non-TRADEFLOW fixtures covering missing metadata, ambiguous relations, misleading names, invalid authorization, drifted hashes and Windows path escape/reparse cases.
- [x] 1.3 Add tests proving reports only contain `derived_from` references/observations and cannot own Candidate, Evidence, Review Decision or delivery-status payloads.

## 2. Narrow Deterministic Runner

- [x] 2.1 Implement a code-owned semantic-navigation operation registry with typed arguments and no shell-string execution.
- [x] 2.2 Implement Profile/Case loading, authoritative authorization-reference checks and resolved-path boundary validation.
- [x] 2.3 Enforce preflight, post-stage, pre-review, post-review and pre-finalize checkpoints in one Runner entry point.
- [x] 2.4 Generate an immutable derived report with source hashes, checkpoint observations, model usage, conflicts and gaps while preserving source-owned statuses.
- [x] 2.5 Add deterministic replay, drift localization, fixed-order and bypass-attempt tests plus a focused CLI entry.

## 3. Model and Review Guardrails

- [x] 3.1 Enforce zero model calls for this slice, validate ambiguity triggers and authorization references, and keep a deterministic frozen-input review key.
- [x] 3.2 Reject nonzero, negative or `UNMEASURED` model usage and review input that leaks the implementer's expected answer.
- [x] 3.3 Validate Reviewer output sources, disposition, decisive reasons and smallest next action without converting it into a domain Review Decision.

## 4. Semantic Navigation Vertical Slice

- [x] 4.1 Add one semantic-navigation Workflow Profile that references existing Artifact roles and contains no TRADEFLOW-specific vocabulary or paths.
- [x] 4.2 Add one TRADEFLOW Case Pack referencing the current frozen inputs, configs, Manifests, data policy, authorization records and budgets.
- [x] 4.3 Run the Harness against current semantic-navigation artifacts and prove it neither changes the algorithm/page nor promotes current reader/business status.
- [x] 4.4 Run `CONTRACT_ISOLATION_CHECK` on the non-TRADEFLOW fixture and prove no `CROSS_SCHEMA_VALIDATED` or equivalent label is emitted.

## 5. Thin Codex Adaptation

- [x] 5.1 Use skill-creator to initialize `.agents/skills/govern-cognition-work` and implement a concise Skill that only invokes the Runner and reports its result.
- [x] 5.2 Add one project-scoped, read-only `counterexample_reviewer` Agent with isolated input and a validated output contract.
- [x] 5.3 Forward-test the Skill/Reviewer input contract on uncontaminated positive, ambiguous and misleading-name fixtures while the Runner budget remains zero.

## 6. Validation and Surrogate Review

- [x] 6.1 Run focused/full tests, OpenSpec strict validation, replay/hash checks, path-boundary tests and sensitive-output scans.
- [x] 6.2 Perform independent surrogate review against duplicate state, bypassable checkpoints, TRADEFLOW leakage, model-cost drift and false completion; resolve in-scope REWORK and repeat.
- [x] 6.3 Update only implemented command/workflow documentation and record `D-010` as the separate future real-Schema validation gate.
