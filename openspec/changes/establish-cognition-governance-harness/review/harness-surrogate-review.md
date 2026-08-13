# Cognition Governance Harness Surrogate Review

## Disposition

`ACCEPT` — engineering surrogate review only. This does not grant user or
business acceptance and does not authorize cross-Schema scale-out.

## Reviewed result

- Runner: `src/titans_cognition/cognition_harness.py`
- TRADEFLOW Case: `cases/tradeflow/semantic-navigation-case-pack.yaml`
- Synthetic isolation Case: `tests/fixtures/cognition_harness/nova-rates-case-pack.yaml`
- TRADEFLOW report id: `02d1baab31d065ae77f92788`
- Synthetic isolation report id: `cdc12ade3589d292419bdb8e`

## Review loop

The same independent, read-only reviewer completed six rounds. Five `REWORK`
rounds found and drove fixes for forged reports, self-reported isolation,
unbound review inputs, model-usage bypasses, non-authoritative policy sources,
non-`ACCEPT` completion, projection-role and Manifest weaknesses, TRADEFLOW
leakage, empty counterexamples, and count-preserving fixture substitutions.

The sixth round returned `ACCEPT` after independently retesting:

- Manifest output path containment, existence and content hashes;
- complete canonical synthetic-fixture and semantic-config isolation;
- object/field comments, relation reasons, misleading-name reasons and policy
  substitutions with unchanged counts;
- report derivation, checkpoint order, authority, zero model usage and review
  binding attacks from earlier rounds.

Focused Harness tests passed (`38`), the complete test suite passed with six
expected skips, and OpenSpec strict validation passed `11/11`.

## Remaining boundary

The current TRADEFLOW governance report intentionally preserves
`INDEPENDENT_REVIEW_NOT_ATTACHED` for the semantic-navigation result. The
Harness engineering review above is not a substitute for the user's business
review of that result. No reader or business status was promoted.

## Smallest next action

Present the current TRADEFLOW semantic-navigation result to the user for
business review. Do not expand the Harness or claim cross-Schema validation.
