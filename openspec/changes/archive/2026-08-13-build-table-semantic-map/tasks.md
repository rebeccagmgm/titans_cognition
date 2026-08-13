## 1. Freeze Scope and Define Contracts

- [x] 1.1 Re-read the current dirty worktree and active field/classification Changes, record overlapping files and preserve all parallel edits without resetting or rewriting their outputs.
- [x] 1.2 Freeze the 477-table TRADEFLOW Physical Facts run, 233-table classification run, fixed field-semantics/context run, Wiki Tree and approved cached body pages with logical locations, hashes and availability states.
- [x] 1.3 Add typed schemas and validation fixtures for table profiles, open context/anchor/responsibility candidates, three table-group kinds, group memberships, table relations, Assertions, Evidence Refs, Review Decisions and Manifest.
- [x] 1.4 Define a versioned relation-predicate registry with endpoint, direction, symmetry and minimum-evidence rules; include a safe `RELATED_TO`/Unknown fallback and reject invalid precise relations.
- [x] 1.5 Add an independent configuration and CLI/output directory for table semantics with hard limits for variant rules, structural neighbors, Wiki recall/body reads, candidates, relations, investigation cards and review shards.

## 2. Build Physical Variant and Structural Investigation Inputs

- [x] 2.1 Add positive, ambiguous and negative fixtures for date suffixes, numeric suffixes, `_BAK`, `_V*`, multiple possible parents, missing base tables and genuinely standalone suffixed tables.
- [x] 2.2 Implement conservative physical-name normalization and compare object type, comments, column signatures and keys before emitting `LIKELY_VARIANT`, `COMPETING_PARENT`, `STANDALONE` or Unknown dispositions.
- [x] 2.3 Verify that all 477 TRADEFLOW tables receive an explicit subject or variant disposition and that the 244 previously excluded tables cannot disappear from counts or review navigation.
- [x] 2.4 Import the fixed similarity edges and Leiden memberships as `STRUCTURAL_NEIGHBORHOOD` investigation hints with their original graph lineage and method scores, without converting them into business groups or independent business evidence.
- [x] 2.5 Add regression tests covering the observed mixed structural family containing configuration, fee, approval, report and business-record tables, proving that it is not published as a business collaboration group.

## 3. Derive Table-Level Signals and Field Support Summaries

- [x] 3.1 Add fixtures for product master tables, contract extensions, legs, events, current/history holdings, parameters, approval trails, operational audit logs, risk-validation records, reporting/writeback tables and mapping/configuration relations.
- [x] 3.2 Implement table-name and table-comment candidate extraction as separate signals with explicit source roots, abstention and counterexample handling for `REF`, `PARAM`, `LOG`, `REPORT`, `RESULT`, `MAPPING` and similar tokens.
- [x] 3.3 Build bounded physical-field summaries for anchor IDs, event markers, business dates, source/target pairs, configuration IDs and approval/audit fields; treat shared fields as recall evidence rather than declared foreign keys.
- [x] 3.4 Import the fixed field-semantic/context results as optional support, distinction or counterevidence and preserve each field candidate's original provenance and status.
- [x] 3.5 Implement root-source aggregation that prevents table-name-to-field-context-to-table-label circular support and prevents field counts or majority voting from producing table labels.
- [x] 3.6 Add disabled, missing, drifted and partially invalid field-input tests proving that field assistance becomes `NOT_EVALUABLE` without silently switching runs or blocking independent table evidence.

## 4. Build Bounded Wiki Evidence

- [x] 4.1 Parse the fixed Wiki Tree into original titles, ancestor paths and document contexts while retaining production-event, project, test, year and team-space noise as navigation context only.
- [x] 4.2 Build table-driven Top-K Wiki recall from table names, comments, anchor candidates and field-support summaries with configured per-table and total budgets.
- [x] 4.3 Read only fixed cached or explicitly approved bounded body pages, record pageId/version/hash/section or snippet locations, and distinguish `MENTIONS_TABLE`, usage description and explicit multi-table association evidence.
- [x] 4.4 Add regression tests for a holdings page located under production-event management and for a body page explicitly listing core table associations, proving that directory parentage is not converted into a table category.
- [x] 4.5 Preserve Wiki errors, missing bodies, truncation and ambiguous matches as diagnostics or `NOT_EVALUABLE`; do not crawl the full Wiki or infer coverage from the directory snapshot.

## 5. Generate Table Assertions, Relations and Collaboration Groups

- [x] 5.1 Implement open multi-value BusinessContext, BusinessAnchor and TableResponsibility candidates with Candidate/Competing/Unknown/Not Evaluable outcomes and method-local non-probability rankings.
- [x] 5.2 Generate table-relation candidates through the predicate registry, requiring endpoint validation, direction, direct evidence, counterevidence and downgrade to `RELATED_TO` or Unknown when precision is unsupported.
- [x] 5.3 Generate `BUSINESS_COLLABORATION_GROUP` candidates around supported anchors, require a responsibility for every member, allow one table in multiple groups and prohibit structural similarity as the sole membership basis.
- [x] 5.4 Persist every label, membership and relation as an Assertion with Evidence, Counterevidence, root-source families, method trace and optional Review Decision; never emit automatic `ACCEPTED`.
- [x] 5.5 Import old propagated labels only as visibly separate structural-propagation hints and prevent propagation-only candidates from entering the recommended table profile without new direct support.
- [x] 5.6 Add contract and regression tests for cross-product shared tables, competing responsibilities, invalid relation endpoints, missing evidence references, rejected reviews and preservation of original candidates after review.

## 6. Validate the Information Model with Five Investigation Sets

- [x] 6.1 Produce a TRS collaboration investigation card covering OTC parent trade, TRS contract, leg, event, event detail, current/history holding and deal allocation with member responsibilities and unresolved links.
- [x] 6.2 Produce an option collaboration investigation card covering OTC parent trade, option contract, structure, lifecycle event and margin parameters, including contrasts with the TRS group.
- [x] 6.3 Produce a current/history holding card that distinguishes shared business identity from temporal form and tests the `CURRENT_HISTORY` relation without claiming row-level history completeness.
- [x] 6.4 Produce a name-counterexample card that distinguishes contract masters from reference configuration, contract payload from generic parameters, approval/audit/risk logs, and regulatory/writeback/trade reports.
- [x] 6.5 Produce a mapping card that distinguishes mapping configuration, runtime mapped relation, main/sub contract relation and source/EOD deal mapping.
- [x] 6.6 Evaluate the model Gate for structure-as-business leakage, silent variant loss, field voting, Wiki-directory hierarchy, circular evidence, unsupported precise relations, hidden Conflict/Unknown and replay drift; retain failed cards and diagnostics.
- [x] 6.7 Stop before full review-page construction if any critical Gate check fails, and present the five cards and failure reasons for user review rather than optimizing label coverage.

## 7. Build the Review Projection Only After the Gate

- [x] 7.1 After the model Gate passes, build compact indexes for contexts, anchors, collaboration groups, responsibilities, tables, variants, structural neighborhoods, relations, evidence, Conflict and Unknown.
- [x] 7.2 Implement shallow navigation from business context to anchor/collaboration group, member responsibility and table profile while reusing one `asset_id` when a table appears in multiple entries.
- [x] 7.3 Add dedicated physical-variant and structural-neighborhood views that show member differences and limitations without presenting them as business hierarchies.
- [x] 7.4 Show direct candidates, structural-only hints, counterevidence, Unknown, review decisions, field-support summaries and Panorama Object Card links with technical scores collapsed and never rendered as probabilities.
- [x] 7.5 Add browser tests for first-load bounds, search/filter behavior, shard races, pagination, multi-entry back-navigation, missing Panorama targets, failed evidence and variant expansion.
- [x] 7.6 Obtain user review of the fixed TRS, option and counterexample journeys before changing any recommended project entry or claiming reader usability. On 2026-08-12 the user explicitly delegated this bounded reader evaluation to the agent. Disposition: `ACCEPT_WITH_UNKNOWNS` for the five fixed investigation journeys as a table-investigation entry; this is not acceptance of all table semantics, production truth, reader delivery, business acceptance or scale authorization.

## 8. Verify, Document and Hand Off the Bounded Change

- [x] 8.1 Run focused and full tests, schema/reference validation, deterministic replay, content-hash comparisons, sensitive-output scans and checks proving that no business rows or upstream writes occurred.
- [x] 8.2 Compare the new profiles against the fixed 903 old classification candidates and report corrected distinctions, retained useful hints, unresolved cases and evidence-source changes without publishing an accuracy rate absent independent truth.
- [x] 8.3 Update relevant project specs, README/current status and input decision records only for behavior actually implemented; keep engineering Gate, reader delivery, business acceptance and scale authorization separate.
- [x] 8.4 Run `openspec validate build-table-semantic-map --strict` and review the final diff for accidental field-side edits, hidden variant exclusions, hardcoded ontology, full-Wiki expansion, generated artifacts or secrets.

## 9. Rework Findings from the Mandatory Surrogate Review

Tasks 7.1-7.5 record the initial pre-REWORK implementation. The tightened Gate invalidated that generated review Projection; task 9.8 records the evidence-gated rebuild after the option-event gap was closed.

- [x] 9.1 Record the 2026-08-12 `REWORK` disposition in proposal/spec/design/tasks, preserving the original 43/44 implementation history and keeping user review incomplete.
- [x] 9.2 Add failing fixtures and implement a discovery-layer responsibility signal that preserves observed comment/field expressions separately from the seed registry; prevent `REF`, `LOG`, `REPORT` and `PARAM` seed hits from becoming recommended responsibilities without independent support.
- [x] 9.3 Link field candidates and physical-field combinations to specific table Assertions as support, distinction, counterevidence or `NOT_USED`, preserving field provenance/status and root-source deduplication without voting.
- [x] 9.4 Make Wiki Top-K recall fair under the total budget, emit per-table coverage/truncation diagnostics and add an order-invariance regression test.
- [x] 9.5 Keep configured journeys as investigation sets and publish a business collaboration group only when every member has responsibility evidence from a source other than the configured membership itself and the evidence-gated semantic relation graph is connected.
- [x] 9.6 Add bounded candidate relations for the fixed TRS and option journeys, using precise predicates only when their minimum evidence is met and explicit `RELATED_TO` or Unknown gaps otherwise.
- [x] 9.7 Strengthen the information-model Gate against missing critical responsibilities, disconnected or relation-empty groups, field-summary-only assistance, Wiki order bias and vacuous precise-relation passes; retain failed cards and do not render a ready recommendation entry.
- [x] 9.8 Rebuild the five cards and review Projection only after the strengthened Gate, showing discovery expressions, assertion-level field roles, rejected collaboration groups and unresolved relation gaps.
- [x] 9.9 Run focused/full tests, schema/reference validation, deterministic replay, content-hash comparison and OpenSpec strict validation, then perform the mandatory surrogate review and record `ACCEPT`, `REWORK`, `STOP` or `DEFER` without completing task 7.6 on the user's behalf. Disposition: `REWORK`; the explicit `KEY_LEG_ID` bridge now connects the TRS journey, while the option-event member still lacks an evidence-gated connection.

## 10. Close the Authorized Option-Event Evidence Gap

- [x] 10.1 Freeze the authorized one-row testdb aggregate with query fingerprint, timestamp, endpoints, key fields, counts, cardinality and explicit non-production limitations; store no business key values or row samples.
- [x] 10.2 Add failing tests and implement evidence validation that emits precise `EVENT_OF` only when event keys are non-null, fully matched to a unique contract key and independently supported by event table metadata; otherwise downgrade to `RELATED_TO` or Unknown.
- [x] 10.3 Rebuild the table-semantic result, rerun the strengthened Gate and render the review Projection only if all critical checks pass; expose the test-snapshot boundary in relation evidence.
- [x] 10.4 Run full tests, deterministic replay, sensitive-output scan, OpenSpec strict validation, code review and mandatory surrogate review; do not complete user review task 7.6 or claim business acceptance. Disposition: `ACCEPT`; the frozen TEST aggregate is non-empty, internally consistent, scope-bound to verified endpoint keys, and remains explicitly non-production evidence.
