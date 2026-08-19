## Purpose

为下游表详情提供一个受控、可恢复的实时 task_id 解析能力，使后续 Machine Facts staging 能使用真实任务归属，并保留限流、失败和未解析证据边界。

## ADDED Requirements

### Requirement: Resolve task IDs from physical table evidence

The resolver SHALL accept persisted downstream table-detail records containing a stable table GUID and qualified table name, and SHALL query the read-only SZData task inspection capability to discover structured Horae task IDs for each physical table.

#### Scenario: Qualified name includes a data-source suffix

- **WHEN** an input qualified name contains a suffix such as `db_name.table_name@source`
- **THEN** the resolver SHALL query the `db_name.table_name` portion while preserving the original qualified name and GUID in the output evidence

#### Scenario: One table has multiple structured tasks

- **WHEN** SZData returns more than one structured task for a table
- **THEN** the resolver SHALL preserve all distinct task IDs in stable output order

### Requirement: Execute queries conservatively

The resolver SHALL issue at most one table task-inspection query at a time, use the detail-only read path, and enforce a configurable delay between normal queries.

#### Scenario: Normal serial processing

- **WHEN** more than one unresolved table remains
- **THEN** the resolver SHALL finish the current table query before starting the next and SHALL wait at least the configured normal interval between queries

#### Scenario: Rate limit is reported

- **WHEN** the platform response indicates user-level rate limiting or HTTP 429 semantics
- **THEN** the resolver SHALL classify the row as `RATE_LIMITED`, apply only the configured bounded backoff/retry policy, and SHALL stop with a checkpoint if the limit persists

### Requirement: Preserve evidence states and failures

The resolver SHALL distinguish confirmed task mappings, confirmed empty task results, partial task responses, rate limits, timeouts, authentication failures, command failures, and malformed responses.

#### Scenario: Preserve incomplete input evidence

- **WHEN** an input row has a stable GUID but no qualified table name
- **THEN** the resolver SHALL emit `INPUT_INVALID` with `MISSING_QUALIFIED_NAME`, SHALL NOT invoke `task-inspect`, and SHALL retain the row for audit rather than treating it as `NO_TASKS`

#### Scenario: Query fails before a business result is returned

- **WHEN** the OpenCLI process times out, requires authentication, exits unsuccessfully, or returns malformed JSON
- **THEN** the resolver SHALL preserve an explicit non-success status and SHALL NOT classify the table as `NO_TASKS` or `NOT_FOUND`

#### Scenario: Task response is partial

- **WHEN** the structured response contains task-level errors or a partial top-level status
- **THEN** the resolver SHALL retain any task IDs returned and mark the row `PARTIAL`

### Requirement: Support resumable local output

The resolver SHALL checkpoint one mapping row after each query into a local CSV artifact containing the source identity, normalized query table, status, task IDs, attempt count, check time, evidence level, and error class.

#### Scenario: Resume after an interrupted or rate-limited run

- **WHEN** the resolver starts with an existing mapping CSV
- **THEN** it SHALL skip rows already in resolved states and SHALL retry only unresolved rows while preserving prior results

#### Scenario: Checkpoint contains not-yet-queried inputs

- **WHEN** a run stops before all input rows have been queried
- **THEN** the checkpoint SHALL retain those inputs as `PENDING` rather than dropping them or fabricating a result

### Requirement: Bound directory input scope

When the input is a directory, the resolver SHALL support a caller-provided maximum number of `part-*.csv` files and SHALL select files in deterministic filename order before reading them.

#### Scenario: Process the first bounded set of shards

- **WHEN** the caller supplies a directory and a maximum of 50 input files
- **THEN** the resolver SHALL read only the first 50 sorted `part-*.csv` files and SHALL not inspect later shards

#### Scenario: Process a single input file

- **WHEN** the caller supplies one CSV file rather than a directory
- **THEN** the resolver SHALL process that file regardless of the directory-file limit

### Requirement: Keep Machine Facts merge separate

The resolver SHALL only produce the task-ID mapping evidence and SHALL NOT write formal Machine Facts, replace existing task bundles, or execute a merge.

#### Scenario: Mapping run completes

- **WHEN** all input rows reach a terminal mapping state
- **THEN** the resolver SHALL leave `machine-facts/registry/tasks` unchanged and report the mapping artifact for a separately authorized staging step
