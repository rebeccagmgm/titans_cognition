## 1. Contracts and Configuration

- [x] 1.1 Add typed configuration and JSON contracts for issue selection, Token limits, review Packs, model responses, revision candidates, errors, cache keys, and run Manifest without changing the V1 field-concept contracts.
- [x] 1.2 Add contract tests for all six actions, missing comments, non-authoritative field types, unknown Evidence IDs, duplicate members, stale Pack hashes, invalid action payloads, and preserved `ABSTAIN` outcomes.

## 2. Deterministic Selection and Pack Generation

- [x] 2.1 Add fixture-first tests proving that low cohesion, outliers, weak label support, relationship conflict, and mixed qualifier dimensions are ranked deterministically, while untriggered clusters are excluded and no field/concept-name special cases are required.
- [x] 2.2 Implement issue scoring with recorded signal values, thresholds, reasons, stable tie-breaking, `max_packs`, per-Pack limits, and whole-run Token-budget truncation.
- [x] 2.3 Implement deterministic representative, boundary, variant, outlier, and counterexample sampling from V1 concepts, links, diagnostics, and Physical Facts.
- [x] 2.4 Generate minimal normalized Packs and batch exports with stable Evidence IDs, allowed-content filtering, Prompt/schema versions, content hashes, and explicit missing-evidence markers.

## 3. Offline GPT Review and Validation

- [x] 3.1 Implement the `prepare` workflow that writes `selection.jsonl`, `packs.jsonl`, the bounded current-GPT batch artifact, and a replayable partial Manifest without requiring an SDK.
- [x] 3.2 Implement line-isolated response import, strict action-specific and Evidence-whitelist validation, normalized `revision_candidates.jsonl`, `responses.jsonl`, and preserved `errors.jsonl`.
- [x] 3.3 Implement content-addressed response-cache lookup and recording keyed by Pack, Prompt, response-contract, and model identity, while copying every used response and validation result into the run output.
- [x] 3.4 Keep any Provider SDK entry disabled and returning `NOT_EVALUABLE` unless a separately approved D-005 configuration is present; add tests that the deterministic and offline paths remain usable without it.

## 4. Comparison Review Projection

- [x] 4.1 Build a baseline-versus-candidate projection that shows selection reasons, action, affected concepts/fields, supporting evidence, counterevidence, undecided members, validation state, and candidate-only status.
- [x] 4.2 Extend the bounded-DOM review pattern with lazy detail rendering, field pagination, Worker-backed lookup, and links from concept to field, table, and existing Object Card.
- [x] 4.3 Add regression tests proving that rendering does not mutate V1 files, does not pre-render all fields, and preserves `ACCEPT/REJECT/DEFER` decisions separately if decisions are enabled.

## 5. TRADEFLOW Vertical Slice

- [x] 5.1 Run `prepare` against the fixed current TRADEFLOW field-concept result, confirm Pack contents remain within the D-005 allowlist, and record selected, skipped, estimated, and actual available Token counts.
- [x] 5.2 Process one bounded batch through the current GPT session, import the structured responses, and preserve valid, invalid, failed, and `ABSTAIN` cases without blocking the V1 output.
- [x] 5.3 Render and inspect the comparison page against known overbroad, naming, parent-child, and Facet ambiguities; report visible improvements, regressions, untouched scope, and remaining Unknowns without claiming overall accuracy or business acceptance.

## 6. Verification and Documentation

- [x] 6.1 Run focused tests, the full existing test suite, output-schema validation, replay/hash checks, and `openspec validate add-llm-assisted-field-concept-review --strict`.
- [x] 6.2 Document the three-stage offline command flow, output contracts, Token controls, cache semantics, D-005 boundary, rollback path, and the fact that SDK enablement and accepting candidates require separate authorization or follow-up change.
