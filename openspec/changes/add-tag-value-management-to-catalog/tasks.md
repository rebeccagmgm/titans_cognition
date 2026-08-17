## 1. Define and validate the dual-object input contract

- [x] 1.1 Add fixture inputs for all-scope, dimension-only, partial relation, duplicate-ID, malformed JSONL, and incomplete manifest cases.
- [x] 1.2 Implement snapshot input discovery for tag values, tag dimensions, and tag-dimension relation records with explicit adopted-file metadata.
- [x] 1.3 Validate object-specific IDs, declared counts, relation keys, and scope evidence without treating missing tag-value data as an empty tag set.

## 2. Build the tag value and relation model

- [x] 2.1 Normalize platform tag-value fields including `tagId`, `tagName`, status, catalog, generation condition, and dimension references while retaining raw source fields.
- [x] 2.2 Normalize tag-dimension records and preserve the existing dimension SQL evidence, formatting, and highlighting behavior.
- [x] 2.3 Build explicit bidirectional `(tagId, tagDimId)` relation indexes with `FOUND`, `PARTIAL`, `COMMAND_EXEC`, and unavailable states.
- [x] 2.4 Keep dimension-only snapshots usable while exposing a visible `TAG_VALUES_NOT_CAPTURED` state.

## 3. Render two management views

- [x] 3.1 Add separate “标签管理” and “标签维度管理” navigation and independent summary counts.
- [x] 3.2 Render tag-value details with tag ID, name, status, catalog, generation condition, and linked dimensions.
- [x] 3.3 Render dimension details with linked tags, source/result metadata, evidence fields, and formatted highlighted SQL.
- [x] 3.4 Add bounded search and selection behavior across the correct object type without conflating IDs.
- [x] 3.5 Display snapshot scope, source files, relation coverage, and all missing/partial evidence states.

## 4. Integrate and verify delivery

- [x] 4.1 Extend the CLI generation entry point to accept the dual-object snapshot and publish atomically.
- [x] 4.2 Add DOM/static smoke checks for view switching, filtering, tag-to-dimension navigation, reverse navigation, and SQL display.
- [x] 4.3 Generate a projection from a real `scope=all` snapshot and verify object counts, relation preservation, and evidence statuses.
- [x] 4.4 Run independent surrogate review against positive, partial, missing, and misleading-ID cases; record the disposition and fix in-scope defects before handoff.

## 5. Repair and refresh the source snapshot

- [x] 5.1 Reproduce the 10,000-row result-window truncation and add a failing test proving that a short fetch cannot be `COMPLETE`.
- [x] 5.2 Implement dynamic `tagType` / `status` / `isCompoundLabels` partitioning with parent-child total conservation checks.
- [x] 5.3 Preserve expected totals and cumulative detail counts across resume; restore relation-only dimension IDs from the persisted relation file.
- [x] 5.4 Generate a clean all-scope snapshot and verify 17,969/17,969 tags, 2,425/2,425 listed dimensions, 2,669 cumulative dimension details, 23,084 unique relations, and zero unresolved requests.
- [x] 5.5 Regenerate the reader projection from the clean snapshot and repeat static tests plus independent surrogate review.

## 6. Preserve holding versus combination type

- [x] 6.1 Add mapper regression tests proving `tagType/tagClas` codes `1/2` map to `持仓/组合` for tag values, dimension lists, and dimension details.
- [x] 6.2 Correct the OpenCLI SZData snapshot mapper while retaining the original type codes.
- [x] 6.3 Add “类型（持仓/组合）” as the first tree level in both management views, including compatibility for pre-fix snapshots.
- [x] 6.4 Regenerate the reader projection and verify type counts, missing-catalog nesting, selection behavior, and OpenSpec consistency.
- [x] 6.5 Hide the leading platform catalog container `分类` in both reader trees while preserving the raw source path and non-leading occurrences; label absent source catalogs as `未分类（源快照）`.
- [x] 6.6 Restore and display dimension identity and governance fields retained by the management-list snapshot, including English name, composite flag, security level, group-filter flag, status code, description, and result table.

## 7. Unify the reader catalog

- [x] 7.1 Replace the two management tabs with one `类型 → 目录 → 标签维度 → 标签` tree while preserving distinct IDs, details, evidence states, and unique-object summary counts.
- [x] 7.2 Add restrained visual differentiation for dimension nodes and tag leaves, and preserve expansion state when either object is selected.
- [x] 7.3 Add regression coverage for multi-dimension tag entries, missing relations/catalogs, search, unique counts, and selection behavior; regenerate V7 and complete independent surrogate review.

## 8. Simplify dimension details

- [x] 8.1 Remove the redundant reverse “关联标签” section from dimension details and display marking/system task IDs with an explicit “未配置” empty state.
- [x] 8.2 Regenerate V7 and verify the selected dimension detail against the source snapshot.

## 9. Correct task-ID precedence

- [x] 9.1 Reproduce duplicate list task records and empty detail task arrays with failing OpenCLI and projection tests.
- [x] 9.2 Deduplicate task IDs, restore persisted management-list rows on resume, and let their non-empty task evidence supplement empty detail fields in both new snapshots and existing-snapshot projection.
- [x] 9.3 Regenerate V7 and verify one marking-only, one marking-plus-system, and one genuinely unconfigured real dimension.
- [x] 9.4 Hash the management-list source in the projection manifest and label task evidence as `ID_ONLY` when workflow records are not captured.
- [x] 9.5 Merge missing-catalog dimension and relation entries by `tagDimId` so each dimension appears once under `未分类（源快照）`.
