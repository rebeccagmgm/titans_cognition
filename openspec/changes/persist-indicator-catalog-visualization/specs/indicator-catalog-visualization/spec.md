## Purpose

Provide a durable reader-facing projection of one pinned indicator snapshot, so catalog exploration remains available after other generated outputs are rebuilt and does not overstate what the source snapshot contains.

## ADDED Requirements

### Requirement: Generate a durable snapshot-bound catalog projection

The system SHALL accept an explicit indicator snapshot directory containing its manifest and JSONL records, validate that the records are uniquely identified, and write the catalog review projection to a stable snapshot-scoped deliverable location outside any unrelated atomically replaced output directory.

#### Scenario: Successful generation from a pinned snapshot

- **WHEN** the requested snapshot directory contains a readable manifest and indicator JSONL with unique indicator IDs
- **THEN** the system writes the HTML review page and machine-readable projection metadata under a directory named or otherwise keyed by the snapshot ID
- **AND** the metadata records the source manifest path, source JSONL path, source hashes, record count, and generated page path

#### Scenario: Invalid or mismatched snapshot input

- **WHEN** the manifest is missing, the JSONL cannot be read, or the declared count/IDs do not match the records
- **THEN** generation fails with a bounded validation error and does not publish a partially generated deliverable

### Requirement: Preserve source semantics and evidence boundaries in the review UI

The projection SHALL preserve every unique indicator in the source snapshot, place indicators with no catalog path under an explicit source-missing or uncategorized node, and display business definition and other available source fields without inventing processing SQL or business meaning.

#### Scenario: Missing catalog or unavailable processing SQL

- **WHEN** an indicator has no catalog path or the snapshot has no processing-SQL field
- **THEN** the tree shows the indicator under an explicit `未归类（源数据无目录）` path and the detail panel shows `未采集（源快照没有该字段）` for processing SQL
- **AND** the UI does not imply that the missing value is false, empty by business rule, or inferred from a name

#### Scenario: Business definition is available

- **WHEN** an indicator contains a business definition in the snapshot
- **THEN** selecting that indicator exposes the business definition in the detail panel and the value is retained verbatim apart from safe display escaping

### Requirement: Filter counts and detail selection reflect the visible snapshot subset

The review page SHALL support text filtering across indicator names, IDs, catalog labels, status, and business definition; node badges and the summary SHALL count only currently visible indicators, while the page SHALL retain the snapshot total for comparison.

#### Scenario: Filtered catalog view

- **WHEN** a user enters a search term that matches a subset of indicators
- **THEN** nonmatching indicator rows and empty branches are hidden, node counts and the summary update to the matching count, and the snapshot total remains separately visible

#### Scenario: Selecting a concrete indicator

- **WHEN** a user clicks a visible indicator row
- **THEN** the detail panel shows that row's source-backed fields, including business definition when present, and remains associated with the selected indicator while filters are applied or cleared

### Requirement: Rebuilds do not delete the catalog deliverable

The catalog projection SHALL be generated as an owned deliverable of the catalog command or pipeline and SHALL remain readable after an unrelated context-semantic-map build replaces its own output directory.

#### Scenario: Unrelated context-map rebuild

- **WHEN** the context-semantic-map build completes an atomic replacement of its generated directory
- **THEN** the previously generated snapshot-scoped catalog page and metadata remain present and readable at their stable deliverable location

