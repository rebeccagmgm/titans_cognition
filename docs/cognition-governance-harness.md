# Cognition Governance Harness

This repository contains a narrow governance runner for the semantic-navigation
workflow. It coordinates existing authoritative artifacts; it does not create a
second Candidate, Evidence, Review Decision, or reader/business delivery state.

## Contract

- `cases/cognition-governance/workflows/semantic-navigation.yaml` owns the
  reusable stage order, required Artifact roles, checkpoints and model policy.
- A Schema Case Pack owns only Schema-specific references, local policy and
  budget. TRADEFLOW uses `cases/tradeflow/semantic-navigation-case-pack.yaml`.
- The code-owned operation registry is fixed. Profile and Case files cannot
  provide commands, scripts or alternate stage order.
- The generated JSON is a rebuildable `DERIVED_AUDIT_PROJECTION`. Its
  `derived_from` references point back to OpenSpec, Manifests, review material
  and the current status baseline.
- Model calls default to zero. This first slice authorizes no model egress and
  gives the TRADEFLOW and synthetic Cases a zero call/Token budget.

## Run

```powershell
$env:PYTHONPATH = "src"
.venv\Scripts\python.exe -m titans_cognition.cognition_harness --root . run `
  --profile cases/cognition-governance/workflows/semantic-navigation.yaml `
  --case-pack cases/tradeflow/semantic-navigation-case-pack.yaml `
  --output output/cognition-governance/tradeflow-semantic-navigation-v1/governance-run-report.json
```

Verify an existing report:

```powershell
$env:PYTHONPATH = "src"
.venv\Scripts\python.exe -m titans_cognition.cognition_harness --root . verify-report `
  --report output/cognition-governance/tradeflow-semantic-navigation-v1/governance-run-report.json
```

A changed authoritative file produces `HASH_DRIFT`; update a Case hash only
after confirming the source changed intentionally. Path escape, reparse-point,
self-authorization, arbitrary-command, budget and review-leakage failures must
not be bypassed.

## What this proves

The TRADEFLOW run proves that the Harness can audit the current frozen
semantic-navigation inputs without changing its algorithm, page, or current
reader/business status. The NOVA_RATES synthetic fixture proves only
`CONTRACT_ISOLATION_CHECK=PASS` under a different structure with missing
metadata, an ambiguous relation and a misleading name.

It does not prove cross-Schema business validity. Open decision `D-010` remains
the gate for selecting and validating a second real Schema in a later Change.
Hooks, Rules, an Evidence Scout and a general Agent runtime are intentionally
outside this slice.
