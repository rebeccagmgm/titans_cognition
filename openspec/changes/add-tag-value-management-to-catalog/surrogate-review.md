# Independent surrogate review

## Scope

- Reader artifact: `C:\Users\13246\.opencli\tag-snapshot-output\20260813-refresh-full\tag-catalog-review-v6\20260813T170944+0800\index.html`
- Source: clean real `scope=all` snapshot `20260813T170944+0800`
- Projection: 17,969 tag values, 2,425 listed tag dimensions, 2,669 dimension details, and 23,084 tag-dimension relation rows

## Checks

- Snapshot completeness: manifest reports `COMPLETE`, 17,969/17,969 tag values, 2,425/2,425 listed dimensions, cumulative 2,669 dimension details, and zero unresolved requests.
- Source-window falsification: the former adapter stopped at 10,000/17,969 yet wrote `COMPLETE`. The repaired adapter marks short fetches `PARTIAL` and uses only source-supported filters whose child totals equal their parent total.
- Resume falsification: tests cover loss of expected dimension totals, cumulative detail-count drift, and relation-only dimension IDs after timeout. Empty pages no longer erase known totals.
- Positive case: tag records use `tagId` and dimension records use `tagDimId`; the page has separate management tabs and separate summary counts.
- Tree precedence: a tag uses cataloged linked dimensions first, its own catalog only when no linked dimension has a catalog, and the explicit missing-catalog branch only when neither source provides a catalog.
- Corrected result: 14,446 unique tags are in formal catalog branches; 3,523 reference known dimensions whose source snapshot still has no catalog and are displayed as “未分类（源快照）”. No tag remains in “关联维度不在当前快照”.
- Type preservation: all 17,969 tags are first grouped by the platform type code: 11,566 holding and 6,403 combination. All 2,669 dimension details are likewise grouped: 814 holding and 1,855 combination.
- Missing-catalog split: the 3,523 affected tags remain under their type branches (2,689 holding and 834 combination); the 558 source dimensions without catalogs split into 239 holding and 319 combination.
- Mapper counterexample: the old snapshot name `tagTypeName=标签` conflicts with `tagTypeCode=1`. The projection and repaired mapper prefer the preserved code and display `持仓`; a regression test also covers a conflicting dimension name/code pair.
- Dimension-side gap: 558 of the 2,669 captured dimension details have no source catalog: 463 are in the 2,425-row management list and 95 are relation-only supplements. This is a source configuration/evidence gap, not a missing snapshot row and not a locally inferred business category.
- Count integrity: every tree-node count is a distinct tag count, so the root remains 17,969 even though the snapshot contains 23,084 relation rows.
- Relation boundary: source relation status remains visible; local dimension presence is checked independently and is not treated as proof that a relation is invalid.
- Reader behavior: evidence-gap branches are placed after formal catalog branches and collapsed by default; selecting a card updates only its highlight and detail panel, preserving expanded tree state.
- SQL boundary: this refresh intentionally included dimension details but not SQL. The page shows unavailable SQL rather than borrowing SQL from another snapshot.
- Static checks: 11 tag-catalog tests pass; generated page JavaScript parses successfully with Node; OpenCLI command validation and the 195-test shared-core suite pass.
- Independent V6 review: `ACCEPT`; both trees place type first, preserve missing-catalog evidence below type, contain no unknown IDs or cross-type top-level placement, and selection does not rerender the tree. Reviewed page SHA-256: `acf2a2ae0b735f745eefbd3baa2542a609fc29ca6d649bad9c5b2efff10723f6`.
- Display refinement: a leading platform container `分类` is hidden from both reader trees while the raw `catalogPath` and any non-leading or sole `分类` segment remain intact. Every absent-catalog case, including tags without a linked dimension, now uses `未分类（源快照）`.
- Dimension governance fields: management-list values supplement blank detail values without overwriting detail evidence. The IPO审核阶段 detail shows `ipo_aud_stg`, 持仓, composite `N`, security `2级`, group filtering `N`, status code `18`, `dm_index_n.hold_tag_relation`, and its source description; the unavailable status name remains `-` rather than being inferred.
- Independent refinement review: first disposition was `REWORK` for an inconsistent no-relation branch and missing precedence coverage. After remediation, round two returned `ACCEPT`; selection still updates the detail panel without rerendering the tree. Reviewed page SHA-256: `ADEA1C328F41E7378ACAE4950C48A5AD180A40D9DD4D2215E9B46CFC1E228040`.

## Disposition

`ACCEPT`

Accepted as a bounded engineering projection and complete source snapshot under the observed source totals. It is not business acceptance: 558 captured dimensions still have no configured source catalog, affecting 3,523 tags. “持仓/组合” is a platform-returned type, while the directory field remains platform metadata rather than a verified business taxonomy.

## Unified V7 reader review

- V7 replaces the two management tabs with one `类型 → 目录 → 标签维度 → 标签` reader tree while keeping `tagDimId`, `tagId`, details, and relation evidence separate.
- Dimension nodes use a restrained purple treatment and tag leaves use a restrained green treatment; selecting either object updates only the detail panel and selected style, without rerendering the tree.
- The first independent review returned `REWORK`: same-name dimensions could share one clickable node, and tags without captured relations could attach directly to a directory branch.
- Remediation keys dimension entries by `tagDimId`, adds explicit dimension-evidence nodes, rejects unsafe `snapshotId` path components, and adds same-name, missing-relation, Oracle SQL formatting, JavaScript compilation, and path-boundary tests.
- Actual V7 audit: 0 multi-ID dimension nodes, 0 tags outside dimension nodes, 17,969 unique tags represented by 22,411 relation-aware entries, and 2,669 unique dimensions represented by 3,127 type/catalog entries. Repeated entries do not change the unique-object summaries.
- Round-two independent disposition: `ACCEPT`; reviewed page SHA-256: `267b57af3011528169da728e93702d7c49d6fc873878e2630bf14e581ef3c49b`.
- Dimension-detail simplification: removed the redundant reverse “关联标签” list and added “打标调度ID/系统标签调度ID”. Empty, null, dash, and empty-array variants render as “未配置”; runtime JavaScript assertions and independent review returned `ACCEPT`.

## Task-ID evidence correction review

- The first real-sample audit confirmed `tagdim102837=243650/未配置`, `tagdim102831=243052/243632`, and `tagdim101634=未配置/未配置`, but returned `REWORK` because the projection manifest did not hash the management-list file that supplied task IDs.
- Remediation deduplicates task IDs, lets non-empty list evidence supplement empty detail arrays, restores persisted list rows on resume, hashes `tag-dimensions.jsonl` in the projection manifest, and labels task evidence `ID_ONLY` with `workflowRecordsFetched=0`.
- Final independent disposition: `ACCEPT`; all 2,669 projected dimensions match the normalized task source, no duplicate IDs/relations or empty details were found, and task IDs are explicitly not presented as task details, execution results, or authorization. Reviewed page SHA-256: `3d2830a64532394728c41eb7e782e5099330dc0a47fe7e94fc7d9166fb0664a0`.
