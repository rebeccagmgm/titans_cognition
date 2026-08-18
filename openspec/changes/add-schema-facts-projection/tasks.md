## 1. Contract and source mapping

- [x] 1.1 Inventory the existing Schema Evidence, `schema-refs.jsonl`, `guid`, `dataset_id`/`field_id` builders, and `field-expression-nodes` inputs; record the compatibility fields used by the shared projection.
- [x] 1.2 Define the shared `manifest.json` and `index.jsonl` contracts, including publication status, table/column counts, fact paths, and evidence boundaries.
- [x] 1.3 Define the per-table `table.json` and `columns.jsonl` contracts, reusing existing `guid`, `logical_source_id`, `field_id`, `qualified_name`, and `metadata_qualified_name` semantics; keep `dataset_id` as an optional existing Task/Lineage association rather than a storage identity.
- [x] 1.4 Define the Table Storage Key priority: `guid`, then safe `metadata_qualified_name`, then safe `logical_source_id + qualified_name`; do not create a new Dataset Identity algorithm.

## 2. Shared and per-table projection implementation

- [x] 2.1 Implement publication of the shared `machine-facts/projections/schema-facts/` directory with one Manifest, one table index, and per-Table-Storage-Key table directories.
- [x] 2.2 Implement Table Fact projection for `guid`, current database, object type, table comment status, partition spec, DDL status/hash/reference, Metadata qualified name, and evidence references.
- [x] 2.3 Implement optional `observed_source_refs[]` from explicit Metadata source mappings using `relation_kind=OBSERVED_SOURCE_MAPPING`; do not emit inferred complete Lineage.
- [x] 2.4 Implement per-table Column Fact projection for `table_guid`, `dataset_id`, `field_id`, ordinal position, data type, column comment status/reason, raw definition, partition attributes, and evidence references.
- [x] 2.5 Implement deterministic ordering and publication of `index.jsonl`, `table.json`, and `columns.jsonl`, including explicit non-success states for unavailable evidence.

## 3. Boundary and compatibility checks

- [x] 3.1 Ensure the Schema Facts layout does not contain `schema_bundle_sha256` or `scope_sha256` directory layers and does not generate route- or Task-specific Schema Facts copies.
- [x] 3.2 Keep complete DDL in existing Schema Evidence/Snapshot and ensure per-table `ddl_ref` values never contain local absolute paths or copied full DDL.
- [x] 3.3 Ensure `guid`, `database_name`, `metadata_qualified_name`, and `observed_source_refs[]` do not participate in `dataset_id` or `field_id` calculation.
- [x] 3.4 Ensure the projection does not emit constraint facts, Candidate Key, Grain, Cardinality, business semantic, Semantic Review, or inferred complete Lineage records.
- [x] 3.5 Preserve existing Task Bundle layout and `schema-refs.jsonl` behavior; expose Schema Facts only as an additive shared Projection.

## 4. Tests and four-route validation

- [x] 4.1 Add tests for shared Manifest/index publication, per-Table-Storage-Key directory layout, deterministic ordering, and table/column file boundaries.
- [x] 4.2 Add fixture tests for `OBSERVED`, `ABSENT`, and `UNAVAILABLE` table/column comments, explicit database-name evidence, partition consistency, DDL references, and source-mapping evidence.
- [x] 4.3 Add identity regression tests proving that `guid`, `database_name`, `metadata_qualified_name`, and `observed_source_refs[]` do not change `dataset_id` or `field_id`.
- [x] 4.4 Add missing-GUID tests proving that tables fall back to `metadata_qualified_name` or `logical_source_id + qualified_name`, retain gap reasons, and never receive fabricated GUIDs.
- [x] 4.5 Run a four-route vertical slice for OPTION `86840`, TRS `86841`, KS-TRS `86842`, and FAST-TRS `220650`; verify table lookup by GUID, field joins to `field-expression-nodes`, and `d_ref_otc_option_deal` database/location/source evidence.
- [x] 4.6 Run the repository's relevant validation and test commands, and separately record evidence coverage gaps where source metadata cannot provide a field or mapping.

## 5. Documentation and handoff

- [x] 5.1 Update the relevant project contract/index documentation if the shared Schema Facts Projection becomes a supported Machine Facts consumer surface.
- [x] 5.2 Document the distinction between shared Schema Facts and downstream Task/route filtering, including the V1 non-goals and evidence boundary.
