## Context

The current downstream crawler persists table GUIDs, database names, and qualified names, but those records do not reliably carry the Horae task owner needed by the Machine Facts layout. The live SZData route is read-only and rate-limited at user level. See `proposal.md` for the motivation and current progress.

## Goals / Non-Goals

**Goals:**

- Make table-to-task resolution a bounded, serial, resumable operation.
- Preserve source identity, query normalization, platform evidence level, and failure class in a local checkpoint.
- Make rate limiting stop-safe so a later run can resume without repeating confirmed work.
- Keep the mapping phase independent from Machine Facts generation and merge.

**Non-Goals:**

- No bulk platform query, scheduler execution, SQL retrieval, row access, or database write.
- No attempt to infer task IDs from table names, seed task IDs, or local naming heuristics when SZData does not return them.
- No automatic staging generation, formal registry replacement, or merge behavior.

## Decisions

### Use the existing read-only task inspection route

The resolver calls the current `task-inspect --table --include detail` contract because it returns structured task IDs for a qualified table and avoids fetching SQL. `table`/DDL aggregation and direct HTTP calls are not used: they add unrelated metadata work and were the source of avoidable rate-limit pressure.

### Serialize calls and checkpoint after every result

The default normal interval is 15 seconds, with `concurrency=1`. Each completed response is atomically written to the output CSV. A `PENDING` row is written for inputs not yet queried so a crash cannot silently shrink the scope.

### Treat rate limiting as a control state

Rate-limit markers are detected from both human-readable and stable ASCII fragments because Windows command output may be decoded imperfectly. The first limit can receive a bounded exponential backoff; a persistent limit stops the run with exit code 2. This avoids turning repeated retries into additional platform pressure.

### Use status classes instead of a binary match flag

`SUCCESS` and `NO_TASKS` are resolved states. `PARTIAL`, `RATE_LIMITED`, `TIMEOUT`, `AUTH_REQUIRED`, `COMMAND_ERROR`, and parse errors remain unresolved or review-required states. A failed query never becomes `NO_TASKS`.

### Resolve the Windows executable explicitly

Python cannot necessarily start the PowerShell `opencli` shim by its bare command name. On Windows the runner prefers `opencli.cmd`, which is directly executable by Python; it falls back to the platform command name on other systems.

### Bound shard directories before reading

Directory input is sorted by `part-*.csv` filename and optionally truncated by `--max-input-files`. This makes a canary or staged run explicit and prevents a command intended for the first 50 shards from silently expanding to the full directory.

## Risks / Trade-offs

- **[Risk]** A 15-second interval reduces throughput and a full shard may take a long time. → **Mitigation:** output is resumable; users can tune the interval without changing the evidence contract.
- **[Risk]** The platform limit window may exceed the default backoff. → **Mitigation:** persistent rate limiting stops rather than looping; rerun later resumes only unresolved rows.
- **[Risk]** A table may have multiple or partial task results. → **Mitigation:** retain all returned IDs and mark partial responses explicitly; downstream staging must decide whether partial evidence is acceptable.
- **[Risk]** `NO_TASKS` can be mistaken for missing metadata. → **Mitigation:** emit it only for a successful structured response with no task IDs; command, timeout, auth, and parse failures use separate states.
- **[Risk]** Some persisted table-detail rows contain a GUID but no qualified table name. → **Mitigation:** record `INPUT_INVALID / MISSING_QUALIFIED_NAME` without issuing an empty-table query, and retain the row for audit.
- **[Risk]** Local checkpoint is mistaken for formal Machine Facts. → **Mitigation:** keep the output under `output/`, document the boundary, and never write the formal registry from this resolver.

## Migration Plan

1. Run the resolver on one stable `table-details/part-*.csv` input and inspect status counts and task-ID multiplicity.
2. Resume unresolved rows after the SZData rate-limit window recovers.
3. Validate the completed mapping against source GUIDs and task bundle existence before using it as input to a separately authorized staging change.
4. If the resolver is interrupted or produces an invalid checkpoint, preserve the CSV for diagnosis and rerun; do not alter formal Machine Facts.
