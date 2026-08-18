# Surrogate review: native LineageHop projection

Date: 2026-08-18

Disposition: `ACCEPT`

## Scope and evidence

Reviewed the user-facing Plan/Machine Facts projection, the three Hop JSONL outputs, schemas, manifest gates, Bundle validator, and focused fixtures. This is an engineering surrogate review only; it does not grant business acceptance, reader acceptance, scale authorization, or cross-Schema validity.

## Counterexamples checked

- CTE and FROM-subquery chains retain native `HOP_TO_HOP` producer-to-consumer edges. Derived/unresolved inputs remain `PARTIAL_NATIVE` rather than being upgraded to `PROJECTED`.
- Rename and expand remain ordered Hop-level `via`; no Edge carries `via`.
- Final adapter-synthesized `SELECT *` expansion is `NOT_EVALUABLE` with `NATIVE_STAR_COLUMN_ANCHOR_UNAVAILABLE`, no head, and no orphan nodes.
- UNION fan-out keeps branch Hops and branch relation/ordinal metadata without fabricating a Setop Hop; mixed physical terminal plus downstream Hop is retained.
- Candidate, unresolved, scalar/EXISTS, and unsupported Lateral coverage remain degraded/unknown according to the contract.
- Validator fixtures cover missing Hop/Field/Relation/via endpoints, cycles, duplicate/semantic edges, branch ordinal validity, status truth-table violations, `has_downstream` mismatch, and origin-conservation mismatch against persisted column-lineage origins.
- Filter, Join, Group By, Window Role, Grain, and Cardinality are not represented as Hop edges or Hop flow kinds; Hop output remains `VALUE_LINEAGE` only.

## Decision

`ACCEPT` for this authorized projection change. The remaining failed checks are environmental or repository-baseline issues: two existing Machine Facts tests require ignored evidence files absent from this worktree, and the repository-wide TypeScript check has pre-existing `.ts` import/ParserRuleContext and `src/databricks/lower.ts` errors. These do not justify claiming full regression or typecheck closure.
