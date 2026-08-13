# Reusable Semantic Navigation Status

Date: 2026-08-13

## Current status

| Dimension | Status | Meaning |
|---|---|---|
| Engineering implementation | PROTOTYPE_ACCEPTED_WITH_UNKNOWNS | Contract, configuration, layered projection, bounded Wiki context, tests and review loop exist. |
| Reader delivery | NOT_DELIVERED | The new navigation has not replaced the existing field-semantic-map entry and still requires user review. |
| Business acceptance | NOT_ACCEPTED | No business owner has accepted the full navigation or the unresolved queue. |
| Scale authorization | PROHIBITED | The method has not been authorized for unrestricted Schema-wide semantic inference. |

## Evidence boundary

The 2026-08-13 TRADEFLOW replay observed 1,375 business-concept rows. The
configuration-scoped recall produced 12 single-area candidates, 1 multi-area
conflict, and 1,362 `UNKNOWN_BUSINESS_CONCEPT` rows. Unknowns remain visible;
this count is not treated as a cleanup failure or business conclusion.

The prototype is based on read-only metadata artifacts and bounded Wiki
candidates. It does not read business rows, write source systems, write
Canonical facts, or infer that Wiki hierarchy is business hierarchy.

## Reader entry

The review entry is the Change-local proposal and surrogate-review material:

- `openspec/changes/establish-reusable-semantic-navigation/review/navigation-proposal-v2.md`
- `openspec/changes/establish-reusable-semantic-navigation/review/surrogate-review-v2.md`

The existing field semantic-map entry remains unchanged pending explicit user
acceptance.
