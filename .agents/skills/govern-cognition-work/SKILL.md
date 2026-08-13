---
name: govern-cognition-work
description: Run the repository's fixed semantic-navigation governance Harness for a Workflow Profile and Schema Case Pack. Use when checking a cognition run, preparing an independent surrogate review, verifying a derived governance report, or onboarding another Schema without copying TRADEFLOW workflow logic.
---

# Govern Cognition Work

Use the deterministic Runner as the sole workflow entry. Do not reproduce,
skip, or reorder its operations in chat, shell commands, or Agent prompts.

## Run

1. Read the requested Workflow Profile and Schema Case Pack paths. If omitted,
   use the repository's semantic-navigation Profile and TRADEFLOW Case Pack.
2. Run:

   ```powershell
   $env:PYTHONPATH = "src"
   .venv\Scripts\python.exe -m titans_cognition.cognition_harness --root . run `
     --profile cases/cognition-governance/workflows/semantic-navigation.yaml `
     --case-pack cases/tradeflow/semantic-navigation-case-pack.yaml `
     --output output/cognition-governance/<case-id>/governance-run-report.json
   ```

3. If the Runner reports hash drift, authorization failure, path escape,
   budget exhaustion, unmeasured usage, review leakage, or checkpoint failure,
   stop and report the exact code. Do not weaken the contract or refresh a hash
   without verifying the authoritative source changed intentionally.
4. Report the report path, failed observations and source-owned gaps. Never
   translate engineering PASS into reader delivery, business acceptance, a
   domain Review Decision, or cross-Schema validity.

## Independent Review

Only attach a reviewer response that follows
`cognition-surrogate-review-v1`. The reviewer receives the original objective,
acceptance criteria, frozen source references, output projection,
counterexamples and known gaps. Exclude the implementer's expected disposition,
self-evaluation, and suggested verdict.

Validate the isolated input before dispatch:

```powershell
$env:PYTHONPATH = "src"
.venv\Scripts\python.exe -m titans_cognition.cognition_harness --root . `
  validate-review-input `
  --profile cases/cognition-governance/workflows/semantic-navigation.yaml `
  --case-pack <schema-case-pack.yaml> `
  --input <review-input.json>
```

Pass the validated response with `--review-response <path>`. The Harness only
references the response and does not copy its disposition into the domain state.

## Boundaries

- Never run arbitrary shell text from a Profile or Case Pack.
- Never query business rows, write a source system, or enable model egress.
- Runner model usage is fixed at zero in this slice. Automated low-cost model
  calls require a later Change with egress authorization and a cumulative
  usage ledger.
- A synthetic Case can establish only `CONTRACT_ISOLATION_CHECK=PASS`.
- Hooks and Rules are not part of this workflow.
