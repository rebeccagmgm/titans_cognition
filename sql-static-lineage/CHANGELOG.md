# 1.8.0 (2026-07-23)


### Bug Fixes

* clausesOf anchors FROM across templated fills (bec7e29)


### Features

* Token.consumedAs: per-occurrence keyword/identifier/type verdicts (fd4e68b)

# 1.7.0 (2026-07-22)


### Bug Fixes

* **databricks:** top-level LIMIT/OFFSET reach the IR (2d17e4d)


### Features

* frameAt, clausesOf, setOpArmsOf: the debugger's where-is-what surfaces (b7ef6bd)
* reserved/soft keyword split + completion candidate decoration (anvil asks) (03f4703)
* scripting compounds model their inner statements (snowflake, databricks) (9e14e70)
* Spark-gate temp-view threading + snowflake scripting honesty (6aa04f3), closes #40
* **tsql:** DECLARE variable linking and declared-type flow (555a46c)
* **tsql:** routine frames: procedure/function signatures and bodies in the IR (65efca2)

# 1.6.0 (2026-07-20)


### Bug Fixes

* **infer:** databricks types corrected against Spark's own analyzer (430 -> 5) (1d4bd8e), closes #40
* **infer:** databricks wrong-type count is ZERO; per-column baseline + unit pins (8212306)
* **postgres:** registry rules corrected against pg_proc.dat, ledger emptied (4acfae0)


### Features

* **api:** dialectVocabulary(dialect) - the per-dialect token catalog as data (7430155)
* debt burn-down: completion prefix-pruning, fold sweep, small grammar fixes (7a5011e)
* DQL grammar/IR compliance pass (zero known non-compliance at parse + lower) (c89d6a5)
* parameter and variable IR modeling across all dialects (c1e9c21)

## 1.5.1 (2026-07-16)


### Bug Fixes

* **completion:** dangling-dot fallback resolves a templated source's columns (d83a063)
* **symbols:** table Sym.name shows display spelling, not the folded key (0cc6499), closes #38

# 1.5.0 (2026-07-16)


### Bug Fixes

* **lineage:** origins stay display-facing after the identity/display split (0398389)
* **tests:** AdventureWorks extractor captures every CREATE TABLE in a batch (d0dbb6f), closes #38


### Features

* **completion:** CTE candidates, namespace segment completion, qualifier-filtered columns (920c862), closes #38
* **ir:** every table source carries its structured relation name (405c5d9)
* **ir:** QualifiedName - the structured relation name, with per-dialect namespace configs (f63417e)
* **ir:** relation is the one truth - TableSource.name retired (3f94bf1), closes #38
* **scope,qualify:** resolution consumes qualified-name keys - suffix matching, validation, ambiguity (7adacb0), closes #38

# 1.4.0 (2026-07-15)


### Bug Fixes

* **completion:** the token being typed is the caret token (56f4da3), closes #36
* **minijinja:** unresolved template sources take the raw tag text as their name, never the fill (36cb274), closes #35


### Features

* **completion:** templateCandidates receives the whole call; numeric literal args carry values (ef35ade), closes #37

# 1.3.0 (2026-07-15)


### Bug Fixes

* **fold:** ASCII-only identifier folding for sqlite, postgres, duckdb and redshift (095d994), closes [hi#bit](https://github.com/hi/issues/bit) #22
* **parse:** cap expected-token enumeration in syntax error messages (037ce88), closes #31


### Features

* **signature:** authored descriptions for the license-blocked dialects (9ce4995)
* **signature:** canonical renderSignature with vendor bracket notation (eabbdbc), closes #33
* **signature:** databricks function descriptions from Apache Spark's builtin reference (c171f05)
* **signature:** every function name now links to vendor documentation (91a2b65), closes #safe_casting
* **signature:** harvest one-line descriptions from the permissively licensed doc sources (6a535f9)
* **signature:** per-function anchors on the docUrls where the source provides them (b105fe5)
* **signature:** per-name function docs tables with vendor docUrl for every dialect (1b5d969), closes #34
* **signature:** sqlite function descriptions from the public-domain doc bundle (51fb4b1)

# 1.2.0 (2026-07-14)


### Bug Fixes

* **bigquery:** named-argument calls never populated argNames (1b93e1c)
* **ci:** treat Context7 too-early cooldown as soft skip (bb2b256)
* **completion:** lex the placeholder, not raw text, on templated documents (7dfb293)
* **completion:** resolve ref/source relation columns in broken-input column completion (574e975)
* **pivot:** thread the dialect through aliased-pivot source resolution (e310f18)
* **signature:** correct the hand-curated tables against the reconciliation evidence (df54288)
* **signature:** every call-shaped line in a doc block is a candidate; overrides cut to the proven residue (6592e6b)
* **signature:** postgres substring's positional form verified against pg_proc, count optional (1d1609f)
* **signature:** syntaxsql fences with trailing whitespace were invisible to the harvester (a441a80)
* **signature:** tsql harvester emits real optionality instead of flattening brackets (65f9bb0)
* **snowflake:** EXTRACT's date-part operand was dropped from the lowered call args (2960252)
* **snowflake:** named-argument calls never populated argNames (4434921)


### Features

* **completion:** complete inside jinja tags via a host candidate contract (REQ2b) (b1846a5)
* **completion:** detect bare, nested, and control-tag jinja call slots (38d9852)
* **completion:** jinjaSlotAt — neutral jinja completion-slot detection (REQ2a) (a18610f)
* **dialect:** add internal DialectBehavior interface + delegating registry (777f0b3)
* **dialect:** behaviorOf carrier resolves a scope's behavior from its dialect tag (caf2186)
* **duckdb:** model PIVOT/UNPIVOT onto the shared IR; dynamic pivot resolves to unknown (0df2c86)
* **minijinja:** recover incomplete/mid-typing tags as call nodes (REQ1) (4a7abc6)
* require a supported dialect; drop the silent default-dialect fallback (4502813)
* **signature:** eight reconciliation-driven harvester widenings (0ad1e47)
* **signature:** harvested signature tables for databricks and snowflake (cd04a36)
* **signature:** harvested signature tables for duckdb and postgres (95dcc2c)
* **signature:** harvested signature tables for trino and bigquery (f4f9aed)
* **signature:** one generated signature table per dialect, origin per entry (722492f)
* **signature:** overload sets per name (8e8072b)
* **signature:** redshift, mysql and sqlite join the harvest; every dialect now doc-derived (92500cf)

# 1.1.0 (2026-07-11)


### Bug Fixes

* context7.json description under the 200-char schema cap (validation rejected the whole file) (c67a25c)
* **mysql:** bar reserved LEFT/RIGHT as identifiers so bare LEFT/RIGHT JOIN parse (d9cdcae)
* **mysql:** bounded docs-corpus grammar gaps — 13 cited constructs (wave 1) (5a8e47a)
* **mysql:** collect union trailing into-tail arm; pin join/order-by-subquery tests (d67c8be)
* **mysql:** compute part spans for fused DOT_ID tokens — a.b gets per-part addressability (no grammar change needed) (5f84cbe)
* **mysql:** DOT_ID part spans for unspaced a.b — per-part editor addressability restored (52b39ed)
* **mysql:** fractional literal without exponent is DECIMAL, not double (f5b5482)
* **mysql:** require SEMI between batch statements — quantified-subquery mis-split root fix (SLL floors 11→6, 612→33) (2d93aa1)
* **mysql:** reserved-word audit + SEMI-required batching — the completion round (f83e75d)
* **mysql:** reserved-word identifier audit, the LEFT/RIGHT class checked systematically (f3f2cb7)
* **sqlite:** docs scraper sees past leading comments; bucketed corpus layout (81daa91)
* **sqlite:** join_step sub-rule — Join.cst spans the full construct (grammar corrected in place per repo policy) (2d3e1c1)
* **sqlite:** populate SelectExpr.subqueries with expression subqueries (scalar/IN/EXISTS) (05300c9)
* **sqlite:** register sign() in SQLITE_FUNCTION_RETURNS (d39d25f)


### Features

* **dialects:** sqlite + mysql — two new first-class dialects (grammar → parse → lower → full semantic layer) (a421559)
* **mysql:** corpus gate green (b687271)
* **mysql:** docs-corpus scraper for the MySQL 8.4 reference manual (5dd2b9f)
* **mysql:** docs-corpus tier green — the second gate (5aeb132)
* **mysql:** fork + split grammar from grammars-v4 (63a4dc4)
* **mysql:** inference, fold rule, derived-dialect wiring (d7c1c76)
* **mysql:** lower CST to IR (055af7f)
* **mysql:** parse wrapper + smoke test (cde9ff3)
* **mysql:** register in compile-enforced dialect maps (5a17648)
* **mysql:** test matrix, tool registries, docs — Track B finisher (R7) (0074bd4)
* **mysql:** the 8.0.19+ query-expression restructure (wave 2) (71df3e4)
* **sqlite:** corpus gate green (8d28524)
* **sqlite:** docs-corpus tier green (e0c1923)
* **sqlite:** fork + split grammar from grammars-v4 (7a32407)
* **sqlite:** inference, fold rule, derived-dialect wiring (d87000e)
* **sqlite:** lower CST to IR (8ac1a37)
* **sqlite:** parse wrapper + smoke test (c296dd7)
* **sqlite:** register in compile-enforced dialect maps (65faaba)
* **sqlite:** test matrix, tool registries, docs (b698904)

# 1.0.0 (2026-07-10)


* refactor(api)!: jinja entry points move to the sql-static-lineage/minijinja subpath — parseTemplated/tokenizeTemplated/TagNode/regions/variants leave the main barrel; the neutral TemplateEngine contract stays (0d51d95)
* refactor(api)!: rename adapter map to derived dialects, drop dbt vocabulary (f2373e2)


### Bug Fixes

* **api:** drop dead ParserRuleContext imports left by the ParseResult consolidation; exports test covers all 12 IR types (b382178)
* **document:** setop output-column matching folds raw-name provenance on both sides — quoted projections no longer drop on asymmetric-fold dialects (7300058)
* **document:** union column entries speak the fold vocabulary (fold-normalized, quote-preserving names; star-expanded spans anchor on the star) — anvil retirement blockers (a14b51a)
* **document:** union diagnostics key folds line:column (lexer-error collision); setop-root output columns answered via qualification (or visibly gapped); comment pins (c726a33)
* **minijinja:** TemplateVariant.active.armIndex stays required (0 + syntheticEmpty discriminator — anvil contract is additive); nested else-less fixture pins the synthetic path (af16756)
* **qualify:** columnsOfSource returns typed columns for schema-known tables via tableSourceColumns — the plan's sourceColumns wiring dropped types (dc77bd5)
* **session,document:** cell-aware cursor verbs — doc.nodeAt delegation + new SqlDocument.referencesAt/lineageAt absorbing the LSP multi-statement dance; session works past statement 1 (b9623c7)
* **tests:** engine-contract fill-leak fixture actually reaches the scrub path (brief's fixture parsed clean); subpath header comment de-contradicted (2519425)


### Features

* **api:** barrel-complete — PipeStage/GraphTableSource/WindowSpec/… union members, NodeHit+nodeAt, endPosition, ParserRuleContext, one shared ParseResult; delete the LSP node-at shim (736913c)
* **completion:** completeAt — uniform cursor-verb name; complete stays as deprecated alias (no break) (de12f8a)
* **dialects:** postgresql -> postgres alias (alternate engine-name spelling; anvil-requested, unattested-adapter caveat documented) (13e8ef6)
* **document:** doc.variants — engine.variants() consumed; each arm a lazy SqlDocument sharing the cache family (a variant IS a document) (b337fb4)
* **document:** templated cell cache keyed on engine+provider version; withText carries the engine; version bump invalidates (4585515)
* **document:** the unified door — SqlDocument accepts templating: TemplateEngine (+provider); templated docs ride the single-cell path with doc.templated facets; plain path byte-untouched (90ee6a7)
* **document:** union views — unionSymbols/unionDiagnostics/unionCtes/unionOutputColumns across variant docs; span+identity(+name) dedup, first-live-arm representative spans; the consumer never reasons about arms (907cc5e)
* **document:** variantAt(offset) — cursor routing to the arm where the byte has structure; session delegates (d6a649c)
* **lineage:** node-keyed origins — ColumnLineage.projection + Lineage.originsOfNode; duplicate output names disambiguated (cf39238)
* **minijinja:** minijinja() engine factory + sql-static-lineage/minijinja subpath + runnable engine-contract suite (main barrel untouched) (94a6023)
* **minijinja:** synthetic empty-else arm — an optional {% if %} body is also ABSENT in exactly one variant (A8b); enumeration stays linear (af27433)
* **minijinja:** tagOf/nodeOf/diagnosticsOf on TemplatedParseResult — direct two-spine joins replace span-containment correlation (a723b0f)
* **qualify:** public Qualification.columnsOfSource — per-source schema-resolved columns, side-effect-free (anvil fold-in) (29666df)
* **scope:** public walk(scopes) + scopeOf(node) — the node→scope join every consumer re-derived by hand (95f567d)
* **session:** SqlSession — the verb-shaped facade over one document; pure delegation, uniform offset anchors, flattened template facets (bb1b0c0)
* **symbols:** Span carries absolute offsets (start/end exclusive) — one span vocabulary; multi-cell shifting covered (6922d01)
* **symbols:** Sym.node back-reference + public symbolAt — absorbs the LSP's sym-at workaround (2ab6dce)
* **template:** neutral TemplateEngine contract — result/options types move to src/template/engine.ts; minijinja re-exports (no public change yet) (068dcc7)


### BREAKING CHANGES

* import { minijinja, parseTemplated, tokenizeTemplated } from "sql-static-lineage/minijinja" (in-repo: src/minijinja/index.js). The main barrel keeps TemplateEngine/TemplatedParseResult/TemplatedParseOptions and the whole TemplateProvider family unchanged.
* ADAPTER_DIALECTS / adapterDialect are renamed to
DERIVED_DIALECTS / resolveDialect.

## 0.1.1 (2026-07-09)


### Bug Fixes

* **tests:** pin minijinja golden-gate fixtures to LF — CRLF checkout broke it on non-Windows (a29f4dc)
* **tests:** tier-1 corpus-dependent tests hard-throw instead of skip when SQL_CORPUS_DIR is unset (833aba5)
