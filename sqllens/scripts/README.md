# Local analysis scripts

These scripts are case-specific helpers around the sqllens library. Run them
from the `sqllens/` repository root so their evidence and output paths resolve
consistently.

| Directory | Purpose |
| --- | --- |
| `plans/` | Logical Plan Facts, Grain Inference, fingerprints, and their contract/schema helpers |
| `analysis/` | One-off or case-specific lineage, schema, and processing-graph analysis |
| `demos/` | Small interactive demonstrations and manual API probes |
| `verification/` | Golden, processing-graph, and minimal-path checks |

Generated files go under `output/` and are ignored by Git. The checked-in
`golden/` directory is different: it is a regression baseline and must remain
versioned and stable.

Typical commands:

```text
npx tsx scripts/plans/plan-118141.ts
npx tsx scripts/verification/verify-golden.ts
npx tsx scripts/plans/plan-batch.ts
npx tsx scripts/analysis/indicator-processing-graph.ts
npx tsx scripts/analysis/minimal-causal-path-assembler.ts
npx tsx scripts/query/minimal-causal-paths-from-machine-facts.ts
npx tsx scripts/analysis/case-learn-86840.ts
npx tsx scripts/verification/verify-minimal-causal-paths.ts
npx tsx scripts/verification/verify-case-learn-86840.ts
```

The indicator processing graph enables the adapter's optional structured
expression dependencies. Minimal-path queries live in the case processing
profile. The Machine Facts query entry point contains its own path assembly
logic and consumes validated bundles through the query projection; it does not
depend on the legacy processing-graph assembler. The legacy assembler and its
verifier remain available for the older processing-graph output. The verifier
removes critical write, read, task-flow, expression-feed, control-value, and
null-filter evidence in memory and requires the result to degrade from `PASS`.

The scripts consume local evidence snapshots and do not alter the sqllens
library under `src/`.

`case-learn-86840.ts` is a bounded reader-facing replay for one producer task.
It writes eight numbered stage artifacts (`01-input.json` through
`08-graph-slice.json`) under `output/case-learn-86840/`; the output is a
learning projection, not a new canonical graph source.
