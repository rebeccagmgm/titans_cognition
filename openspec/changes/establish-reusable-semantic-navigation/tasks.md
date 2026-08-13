## 1. Freeze Inputs and Define the Navigation Contract

- [x] 1.1 Read-only freeze the current field semantic map, table semantic map, fixed Wiki Tree inputs, and relevant configuration manifests.
- [x] 1.2 Define versioned schemas for business navigation entries, business concepts, attribute expressions, field attributes, qualifier axes, physical implementations, evidence, and review states.
- [x] 1.3 Define explicit separation between business navigation Projection, candidate observations, review decisions, and published entries.
- [x] 1.4 Add deterministic fixtures for positive, ambiguous, negative, same-label/different-meaning, and Wiki-conflict cases.

## 2. Build the Reusable Business Navigation Skeleton

- [x] 2.1 Create a versioned OTC derivatives business skeleton covering participants, products/underlyings, inquiry/order/trade, contract/structure, lifecycle, position/risk, valuation/performance, execution/clearing/settlement, reference/configuration, and operations/reporting/data processing.
- [x] 2.2 Define multi-entry behavior and boundary labels for overlapping areas such as lifecycle versus settlement and participant versus role.
- [x] 2.3 Define open extension behavior for business areas and concepts absent from the current Schema.
- [x] 2.4 Add tests proving the skeleton is a navigation candidate/configuration and cannot create unsupported business facts by itself.

## 3. Abstract Reusable Field Attributes and Qualifier Axes

- [x] 3.1 Define reusable attribute axes for identifier, role, state, direction, measure, currency, time, configuration, and audit semantics.
- [x] 3.2 Implement separation of business concept, attribute expression, field attribute, and qualifier evidence.
- [x] 3.3 Add corpus-driven discovery for new attribute shapes and keep them as open candidates when no axis is sufficient.
- [x] 3.4 Add tests for cross-concept reuse such as trade/contract/position identifiers and for misleading suffixes.

## 4. Reconcile Business Knowledge, Wiki, and Physical Evidence

- [x] 4.1 Map financial/derivatives vocabulary and Wiki title/path/context candidates into bounded navigation and context evidence.
- [x] 4.2 Enforce that Wiki directory structure and lexical hits cannot publish business hierarchy or relations without independent physical or textual evidence.
- [x] 4.3 Preserve source, method, supporting evidence, counterevidence, and NOT_EVALUABLE/Unknown boundaries for every candidate.
- [x] 4.4 Add tests for Wiki/data agreement, Wiki/data conflict, missing Wiki input, and structure-only false positives.

## 5. Produce the Concept Detail Projection

- [x] 5.1 Render a concept detail projection with attribute expressions, field attributes, qualifier axes, business contexts, related concepts, physical implementations, and evidence states as separate sections.
- [x] 5.2 Ensure one concept and one physical asset can be referenced from multiple navigation entries without duplicated facts.
- [x] 5.3 Split the unresolved queue into actionable reasons: unknown concept, unknown attribute, unknown qualifier, role/relationship pending, insufficient evidence, and conflict.
- [x] 5.4 Add reader-facing tests for representative nominal-principal, counterparty, trade/order, position, and margin concepts.

## 6. Run the Proposal-to-Review Improvement Loop

- [x] 6.1 Produce the first navigation proposal and a bounded prototype from the frozen inputs.
- [x] 6.2 Perform an independent surrogate review over positive, ambiguous, counterexample, and misleading-name cases.
- [x] 6.3 Record one disposition per review round: ACCEPT, REWORK, STOP, or DEFER, with decisive reasons and the smallest next action.
- [x] 6.4 Apply only in-scope corrections, regenerate the prototype, and repeat review until the disposition is ACCEPT or a documented STOP/DEFER boundary is reached.
- [x] 6.5 Verify that no rule introduced for one concept or Schema is silently promoted to a global business rule.

## 7. Deterministic Validation and Handoff

- [x] 7.1 Run focused tests, full tests, schema/reference validation, deterministic replay, output hash checks, and sensitive-output scans.
- [x] 7.2 Validate the method on a second concept or Schema configuration without changing core logic.
- [x] 7.3 Review the final diff for source writes, closed classification leakage, Wiki overreach, hidden Unknown/Conflict, and generated artifacts in Git.
- [x] 7.4 Update project status and reader-entry documentation with separate engineering, reader-delivery, business-acceptance, and scale-authorization states.
- [ ] 7.5 Present the resulting navigation Projection and review report for explicit user acceptance before replacing the existing field semantic map entry.
