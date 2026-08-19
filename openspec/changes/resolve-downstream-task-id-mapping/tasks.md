## 1. Contract and input boundary

- [x] 1.1 Confirm the live read-only `task-inspect --table --include detail` command contract and input fields from `table-details/part-*.csv`.
- [x] 1.2 Define controlled removal of `@source` suffixes while preserving the original qualified name and GUID.

## 2. Resolver implementation

- [x] 2.1 Implement one-at-a-time task inspection with configurable normal interval and Windows `opencli.cmd` resolution.
- [x] 2.2 Implement explicit result classification for success, no-task, partial, rate-limited, timeout, authentication, command, and parse outcomes.
- [x] 2.3 Implement atomic per-row CSV checkpointing, `PENDING` placeholders, resolved-row skipping, and unresolved-row resume.
- [x] 2.4 Add bounded rate-limit backoff and stop behavior when the platform limit persists.
- [x] 2.5 Add deterministic `--max-input-files` selection for bounded `part-*.csv` directory runs.
- [x] 2.6 Re-run local regression after the final rate-limit marker, progress-flush, shard-bound, missing-name, and checkpoint-lock patch.

## 3. Tests and documentation

- [x] 3.1 Add simulated tests for suffix normalization, multiple task IDs, partial responses, rate-limit classification, and resume behavior.
- [x] 3.2 Document the resolver command, default pacing, output states, and boundary from mapping evidence to Machine Facts staging.
- [x] 3.3 Verify the final script against the current repository test, compile, lint, and strict OpenSpec commands after the last implementation patch.

## 4. Live evidence and handoff

- [x] 4.1 Run a bounded trial on `table-details/part-00001.csv` and preserve the produced mapping checkpoint.
- [x] 4.2 Confirm the live trial stops on persistent user-level rate limiting without modifying formal Machine Facts.
- [x] 4.3 Resume unresolved rows after the platform rate-limit window recovered and inspect status counts and task-ID multiplicity.
- [ ] 4.4 Validate that resolved task IDs correspond to existing formal task bundles before any separate staging-generation work.
