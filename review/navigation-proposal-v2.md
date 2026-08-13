# Semantic Navigation Proposal v2

## Changes from v1

- Added a real observed-concept area-candidate inventory using the versioned
  financial/derivatives seed configuration.
- Added explicit `UNKNOWN_BUSINESS_CONCEPT` and `MULTI_AREA_CANDIDATE` reasons.
- Kept area matches as candidates requiring evidence; no candidate is published
  solely because of a lexical seed.
- Added a configuration-scope regression test so a term added for one case does
  not become a global rule.

## TRADEFLOW replay summary

| Result | Count |
|---|---:|
| Observed business concepts | 1,375 |
| Single-area candidates | 12 |
| Multi-area conflicts | 1 |
| Unknown business concepts | 1,362 |

The high Unknown count is retained. The current observed labels include many
technical or weakly interpretable expressions; promoting them into a business
area would create false coverage. The queue is therefore a required review
surface, not a cleanup failure.

## Surrogate disposition

**ACCEPT** for the bounded engineering Projection, **with Unknowns retained**.

This means the method and boundaries are acceptable for continued development:
the skeleton is open, area mapping is configuration-scoped, multiple matches are
visible, and unclassified concepts are not silently discarded. It does not mean
the navigation is user-accepted, business-accepted, or ready to replace the
existing field semantic map.
