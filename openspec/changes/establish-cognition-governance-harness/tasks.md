## 1. Contract and Failure Fixtures

- [ ] 1.1 Add versioned Workflow Profile, Schema Case Pack and derived run-report Schemas with an explicit authority matrix and no arbitrary-command fields.
- [ ] 1.2 Add TRADEFLOW plus structurally different non-TRADEFLOW fixtures covering missing metadata, ambiguous relations, misleading names, invalid authorization, drifted hashes and Windows path escape/reparse cases.
- [ ] 1.3 Add tests proving reports only contain `derived_from` references/observations and cannot own Candidate, Evidence, Review Decision or delivery-status payloads.

## 2. Narrow Deterministic Runner

- [ ] 2.1 Implement a code-owned semantic-navigation operation registry with typed arguments and no shell-string execution.
- [ ] 2.2 Implement Profile/Case loading, authoritative authorization-reference checks and resolved-path boundary validation.
- [ ] 2.3 Enforce preflight, post-stage, pre-review, post-review and pre-finalize checkpoints in one Runner entry point.
- [ ] 2.4 Generate an immutable derived report with source hashes, checkpoint observations, model usage, conflicts and gaps while preserving source-owned statuses.
- [ ] 2.5 Add deterministic replay, drift localization, fixed-order and bypass-attempt tests plus a focused CLI entry.

## 3. Model and Review Guardrails

- [ ] 3.1 Enforce zero model calls by default, ambiguity triggers, authorization references, cumulative call/Token budgets and frozen-input cache keys.
- [ ] 3.2 Reject publication when required usage is `UNMEASURED`, budget is exhausted or review input leaks the implementer's expected answer.
- [ ] 3.3 Validate Reviewer output sources, disposition, decisive reasons and smallest next action without converting it into a domain Review Decision.

## 4. Semantic Navigation Vertical Slice

- [ ] 4.1 Add one semantic-navigation Workflow Profile that references existing Artifact roles and contains no TRADEFLOW-specific vocabulary or paths.
- [ ] 4.2 Add one TRADEFLOW Case Pack referencing the current frozen inputs, configs, Manifests, data policy, authorization records and budgets.
- [ ] 4.3 Run the Harness against current semantic-navigation artifacts and prove it neither changes the algorithm/page nor promotes current reader/business status.
- [ ] 4.4 Run `CONTRACT_ISOLATION_CHECK` on the non-TRADEFLOW fixture and prove no `CROSS_SCHEMA_VALIDATED` or equivalent label is emitted.

## 5. Thin Codex Adaptation

- [ ] 5.1 Use skill-creator to initialize `.agents/skills/govern-cognition-work` and implement a concise Skill that only invokes the Runner and reports its result.
- [ ] 5.2 Add one project-scoped, read-only `counterexample_reviewer` Agent with isolated input and a validated output contract.
- [ ] 5.3 Forward-test the Skill/Reviewer on uncontaminated positive, ambiguous and misleading-name fixtures within the configured total budget.

## 6. Validation and Surrogate Review

- [ ] 6.1 Run focused/full tests, OpenSpec strict validation, replay/hash checks, path-boundary tests and sensitive-output scans.
- [ ] 6.2 Perform independent surrogate review against duplicate state, bypassable checkpoints, TRADEFLOW leakage, model-cost drift and false completion; resolve in-scope REWORK and repeat.
- [ ] 6.3 Update only implemented command/workflow documentation and record `D-010` as the separate future real-Schema validation gate.
