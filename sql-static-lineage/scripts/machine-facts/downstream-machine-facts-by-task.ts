import { existsSync, mkdirSync, readFileSync, readdirSync, renameSync, statSync, writeFileSync } from "node:fs";
import { basename, dirname, join, relative, resolve } from "node:path";

import { canonicalJson, normalizeName, sha256, stableRecords } from "./machine-facts-contract.ts";
import {
	DOWNSTREAM_LINEAGE_RUN_ID,
	DOWNSTREAM_LINEAGE_SCHEMA_VERSION,
	deriveDmGatedLineageEdges,
	deriveDmGatedScope,
	resolveDatabase,
	stableFactId,
	type DownstreamEdge,
	type DownstreamNode,
	type DownstreamSeed,
} from "./downstream-lineage-adapter.ts";
import {
	publishArtifactBundle,
	recoverArtifactState,
	writeCanonical,
	writeCanonicalJsonl,
	writeStatusFile,
} from "./machine-facts-runtime.ts";

type CsvRow = Record<string, string>;
type JsonRecord = Record<string, unknown>;
type StablePart = { path: string; rows: CsvRow[]; content_sha256: string };

const workspace = resolve(import.meta.dirname, "../../..");
const defaultSource = "output/szdata-recursive-downstream-20260818-sharded";
const defaultSeeds = "output/downstream-dive-20260818/seed-scope.csv";
const defaultFacts = "machine-facts/registry/tasks";
const defaultOutput = "machine-facts/staging/downstream-dm-gated-20260818";

function arg(args: readonly string[], name: string, fallback: string): string {
	const index = args.indexOf(name);
	return index >= 0 && args[index + 1] ? args[index + 1]! : fallback;
}

function parseCsv(text: string): CsvRow[] {
	const rows: string[][] = [];
	let row: string[] = [];
	let field = "";
	let quoted = false;
	for (let index = 0; index < text.length; index++) {
		const char = text[index]!;
		const next = text[index + 1] ?? "";
		if (quoted) {
			if (char === '"' && next === '"') {
				field += '"';
				index++;
			} else if (char === '"') quoted = false;
			else field += char;
			continue;
		}
		if (char === '"' && field.length === 0) quoted = true;
		else if (char === ",") {
			row.push(field);
			field = "";
		} else if (char === "\n") {
			row.push(field.endsWith("\r") ? field.slice(0, -1) : field);
			if (row.some((value) => value.length > 0)) rows.push(row);
			row = [];
			field = "";
		} else field += char;
	}
	if (field.length > 0 || row.length > 0) {
		row.push(field);
		if (row.some((value) => value.length > 0)) rows.push(row);
	}
	if (rows.length === 0) return [];
	const headers = rows[0]!.map((header) => header.trim());
	return rows
		.slice(1)
		.map((values) => Object.fromEntries(headers.map((header, index) => [header, values[index] ?? ""])));
}

function readCsv(path: string): CsvRow[] {
	return parseCsv(readFileSync(path, "utf8"));
}

function stableParts(directory: string): { parts: StablePart[]; skipped: string[] } {
	const parts: StablePart[] = [];
	const skipped: string[] = [];
	if (!existsSync(directory)) return { parts, skipped };
	for (const name of readdirSync(directory)
		.filter((entry) => /^part-.*\.csv$/i.test(entry))
		.sort()) {
		const path = join(directory, name);
		const before = statSync(path);
		const text = readFileSync(path, "utf8");
		const after = statSync(path);
		if (before.size !== after.size || before.mtimeMs !== after.mtimeMs) {
			skipped.push(path);
			continue;
		}
		parts.push({ path, rows: parseCsv(text), content_sha256: sha256(text) });
	}
	return { parts, skipped };
}

function relativePath(path: string): string {
	return relative(workspace, path).replace(/\\/g, "/");
}

function unique(values: readonly string[]): string[] {
	return [...new Set(values.map((value) => value.trim()).filter(Boolean))];
}

function parseTaskIds(raw: string): string[] {
	return unique(raw.split(/[|,;]/)).filter((value) => /^\d+$/.test(value));
}

function value(row: CsvRow | undefined, key: string): string {
	return String(row?.[key] ?? "").trim();
}

function addDbHint(map: Map<string, Set<string>>, tableName: string, dbName: string): void {
	const table = tableName.trim().toLowerCase();
	const db = dbName.trim();
	if (!table || !db) return;
	const values = map.get(table) ?? new Set<string>();
	values.add(db);
	map.set(table, values);
}

function loadLocalDbHints(factsRoot: string): Map<string, Set<string>> {
	const result = new Map<string, Set<string>>();
	if (!existsSync(factsRoot)) return result;
	const visit = (directory: string): void => {
		for (const entry of readdirSync(directory, { withFileTypes: true })) {
			const path = join(directory, entry.name);
			if (entry.isDirectory()) visit(path);
			else if (entry.name === "dataset-io.jsonl") {
				for (const line of readFileSync(path, "utf8").split(/\r?\n/)) {
					if (!line.trim()) continue;
					try {
						const row = JSON.parse(line) as JsonRecord;
						let physical = String(row.physical_dataset ?? "").trim();
						const datasetPrefix = physical.match(/^dataset:[^:]+:(.+)$/i);
						if (datasetPrefix) physical = datasetPrefix[1]!;
						const separator = physical.indexOf(".");
						if (separator > 0)
							addDbHint(result, physical.slice(separator + 1), physical.slice(0, separator));
					} catch {
						// Preserve malformed local evidence by ignoring only that line.
					}
				}
			}
		}
	};
	visit(factsRoot);
	return result;
}

function loadAuxiliaryDbHints(paths: readonly string[]): Map<string, Set<string>> {
	const result = new Map<string, Set<string>>();
	for (const path of paths) {
		if (!existsSync(path)) continue;
		for (const row of readCsv(path)) addDbHint(result, row.downstream_name ?? row.name ?? "", row.db_name ?? "");
	}
	return result;
}

function validateBundle(bundle: string): string[] {
	const errors: string[] = [];
	const manifestPath = join(bundle, "manifest.json");
	if (!existsSync(manifestPath)) return ["manifest.json is missing"];
	let manifest: JsonRecord;
	try {
		manifest = JSON.parse(readFileSync(manifestPath, "utf8")) as JsonRecord;
	} catch (error) {
		return [`manifest invalid: ${String(error)}`];
	}
	const factIds = new Set<string>();
	for (const output of (manifest.outputs as JsonRecord[] | undefined) ?? []) {
		const outputPath = join(bundle, String(output.path ?? ""));
		if (!existsSync(outputPath)) {
			errors.push(`missing output ${output.path}`);
			continue;
		}
		const bytes = readFileSync(outputPath);
		if (sha256(bytes) !== output.content_sha256) errors.push(`hash mismatch ${output.path}`);
		const rows = bytes
			.toString("utf8")
			.split(/\r?\n/)
			.filter(Boolean)
			.map((line) => JSON.parse(line) as JsonRecord);
		if (rows.length !== output.row_count) errors.push(`row count mismatch ${output.path}`);
		for (const row of rows) {
			const factId = String(row.fact_id ?? "");
			if (!factId) errors.push(`missing fact_id ${output.path}`);
			else if (factIds.has(factId)) errors.push(`duplicate fact_id ${factId}`);
			else factIds.add(factId);
			if (!String(row.evidence_file ?? "")) errors.push(`missing evidence_file ${factId}`);
			if (row.closure_status === "PARTIAL" && row.status === "COMPLETE")
				errors.push(`invalid COMPLETE partial fact ${factId}`);
		}
	}
	if (manifest.schema_version !== "1.2.0") errors.push("unsupported machine facts manifest version");
	if (manifest.fact_family !== "DOWNSTREAM_LINEAGE") errors.push("fact family is not DOWNSTREAM_LINEAGE");
	if (manifest.fact_status !== "PROVISIONAL" || manifest.closure_status !== "PARTIAL")
		errors.push("staging status boundary is invalid");
	if (manifest.status !== "SUCCESS") errors.push("artifact generation status is not SUCCESS");
	return [...new Set(errors)];
}

function publishBundle(
	root: string,
	manifest: JsonRecord,
	files: readonly [string, readonly JsonRecord[]][],
): { status: "CREATED" | "REUSED" | "REPLACED"; manifest_sha256: string } {
	const bundle = join(root, "bundle");
	const staging = join(root, `.staging-${process.pid}-${Date.now()}`);
	mkdirSync(staging, { recursive: true });
	const outputs: JsonRecord[] = [];
	for (const [name, records] of files) {
		const target = join(staging, name);
		const written = writeCanonicalJsonl(target, records);
		outputs.push({
			path: relative(staging, target).replace(/\\/g, "/"),
			schema_version: DOWNSTREAM_LINEAGE_SCHEMA_VERSION,
			...written,
		});
	}
	const finalManifest = { ...manifest, outputs };
	writeCanonical(join(staging, "manifest.json"), finalManifest);
	const errors = validateBundle(staging);
	if (errors.length) throw new Error(`staging validation failed: ${errors.join("; ")}`);
	return publishArtifactBundle({ root, staging, bundle, manifest: finalManifest, validateBundle });
}

function retireLegacyBatchRoot(outputRoot: string): void {
	const legacy = join(outputRoot, "registry", "tasks", DOWNSTREAM_LINEAGE_RUN_ID);
	if (!existsSync(legacy)) return;
	const destination = join(
		dirname(outputRoot),
		`_obsolete-downstream-batch-${Date.now()}`,
		DOWNSTREAM_LINEAGE_RUN_ID,
	);
	mkdirSync(dirname(destination), { recursive: true });
	renameSync(legacy, destination);
}

export function main(): void {
	const args = process.argv.slice(2);
	const source = resolve(workspace, arg(args, "--source", defaultSource));
	const seedsPath = resolve(workspace, arg(args, "--seeds", defaultSeeds));
	const factsRoot = resolve(workspace, arg(args, "--facts-root", defaultFacts));
	const outputRoot = resolve(workspace, arg(args, "--output", defaultOutput));
	const query = stableParts(join(source, "query-results"));
	const edgeParts = stableParts(join(source, "direct-edges"));
	const detailParts = stableParts(join(source, "table-details"));
	const allParts = [...query.parts, ...edgeParts.parts, ...detailParts.parts];
	const skipped = [...query.skipped, ...edgeParts.skipped, ...detailParts.skipped];
	const queryStatus = new Map<string, string>();
	for (const part of query.parts)
		for (const row of part.rows) queryStatus.set(value(row, "guid"), value(row, "status") || "UNKNOWN");
	const details = new Map<string, CsvRow>();
	for (const part of detailParts.parts)
		for (const row of part.rows) {
			const guid = value(row, "guid");
			if (guid) details.set(guid, { ...row, __evidence_file: relativePath(part.path) });
		}
	const seeds = readCsv(seedsPath)
		.filter((row) => value(row, "seed_guid"))
		.map((row): DownstreamSeed => ({
			guid: value(row, "seed_guid"),
			name: value(row, "seed_table_name"),
			db_name: value(row, "seed_db_name"),
			task_ids: parseTaskIds(value(row, "seed_task_ids")),
		}));
	const seedByGuid = new Map(seeds.map((seed) => [seed.guid, seed]));
	const localHints = loadLocalDbHints(factsRoot);
	const auxiliaryHints = loadAuxiliaryDbHints([
		resolve(workspace, "output/titans-collection-20260815/data/downstream-tables-tasks.csv"),
		resolve(workspace, "output/titans-collection-20260815/data/downstream-tables.csv"),
	]);
	const rawEdges: Array<{ row: CsvRow; evidence_file: string }> = [];
	for (const part of edgeParts.parts)
		for (const row of part.rows)
			if (value(row, "parent_guid") && value(row, "child_guid"))
				rawEdges.push({ row, evidence_file: relativePath(part.path) });
	const edgeByKey = new Map<string, { row: CsvRow; evidence_file: string }>();
	for (const item of rawEdges) {
		const key = `${value(item.row, "parent_guid")}\u0000${value(item.row, "child_guid")}`;
		const current = edgeByKey.get(key);
		if (!current || (!value(current.row, "child_db_name") && value(item.row, "child_db_name")))
			edgeByKey.set(key, item);
	}
	const nodes = new Map<string, DownstreamNode>();
	const nodeEvidence = new Map<string, { edge_db_name: string; evidence_file: string }>();
	for (const seed of seeds)
		nodes.set(seed.guid, { guid: seed.guid, name: seed.name, type: "hive_table", db_name: seed.db_name });
	for (const [guid, row] of details)
		nodes.set(guid, { guid, name: value(row, "name"), type: "hive_table", db_name: "" });
	for (const item of edgeByKey.values()) {
		const row = item.row;
		const parentGuid = value(row, "parent_guid");
		const childGuid = value(row, "child_guid");
		if (!nodes.has(parentGuid))
			nodes.set(parentGuid, {
				guid: parentGuid,
				name: value(row, "parent_name"),
				type: "hive_table",
				db_name: "",
			});
		if (!nodes.has(childGuid))
			nodes.set(childGuid, {
				guid: childGuid,
				name: value(row, "child_name"),
				type: value(row, "child_type"),
				db_name: "",
			});
		nodeEvidence.set(childGuid, { edge_db_name: value(row, "child_db_name"), evidence_file: item.evidence_file });
	}
	const resolutions = new Map<string, ReturnType<typeof resolveDatabase>>();
	for (const [guid, node] of nodes) {
		const detail = details.get(guid);
		const edge = nodeEvidence.get(guid);
		const seed = seedByGuid.get(guid);
		resolutions.set(
			guid,
			resolveDatabase({
				detail_status: value(detail, "status"),
				detail_db_name: value(detail, "db_name"),
				edge_db_name: edge?.edge_db_name,
				seed_db_name: seed?.db_name,
				local_fact_db_names: [...(localHints.get(normalizeName(node.name)) ?? [])],
				auxiliary_db_names: [...(auxiliaryHints.get(normalizeName(node.name)) ?? [])],
				evidence_file: value(detail, "__evidence_file") || edge?.evidence_file || relativePath(seedsPath),
			}),
		);
	}
	const resolvedNodes = new Map<string, DownstreamNode>();
	for (const [guid, node] of nodes) resolvedNodes.set(guid, { ...node, db_name: resolutions.get(guid)!.db_name });
	const edges: DownstreamEdge[] = [...edgeByKey.values()]
		.filter(({ row }) => queryStatus.get(value(row, "parent_guid")) === "SUCCESS")
		.map(({ row, evidence_file }) => ({
			parent_guid: value(row, "parent_guid"),
			parent_name: value(row, "parent_name"),
			parent_db_name: value(row, "parent_db_name"),
			child_guid: value(row, "child_guid"),
			child_name: value(row, "child_name"),
			child_type: value(row, "child_type"),
			child_db_name: value(row, "child_db_name"),
			query_status: "SUCCESS",
			evidence_file,
		}));
	const inputs_sha256 = sha256(
		canonicalJson({
			processed_parts: allParts.map((part) => [relativePath(part.path), part.content_sha256]),
			skipped,
		}),
	);
	const commonInputs = {
		inputs_sha256,
		source_directories: [
			relativePath(source),
			relativePath(resolve(workspace, defaultSeeds)),
			relativePath(factsRoot),
		],
		processed_parts: allParts.map((part) => ({
			path: relativePath(part.path),
			content_sha256: part.content_sha256,
			row_count: part.rows.length,
		})),
		skipped_unstable_parts: skipped.map(relativePath),
	};
	const commonMethod = {
		adapter: { name: "downstream-machine-facts-adapter", version: "0.1.0" },
		parser: { engine: "none", version: "n/a" },
		plan_adapter: { name: "downstream-lineage-adapter", version: "0.1.0" },
		dialect: "metadata",
		evidence_boundary: "PLATFORM_LINEAGE_PLUS_EXPLICIT_LOCAL_DB_HINTS",
	};
	const taskSeeds = new Map<string, DownstreamSeed[]>();
	for (const seed of seeds)
		for (const taskId of seed.task_ids ?? []) taskSeeds.set(taskId, [...(taskSeeds.get(taskId) ?? []), seed]);
	const publicationCounts = { CREATED: 0, REUSED: 0, REPLACED: 0 };
	const indexRows: JsonRecord[] = [];
	const totals = { lineage_edges: 0, table_details: 0, downstream_scope: 0, unresolved: 0, failed_details: 0 };
	const selfCheck: string[] = [];

	const toLineageFacts = (taskEdges: readonly DownstreamEdge[]): JsonRecord[] =>
		stableRecords(
			taskEdges.map((edge): JsonRecord => {
				const resolution = resolutions.get(edge.child_guid)!;
				return {
					fact_id: stableFactId("PLATFORM_LINEAGE_EDGE", {
						parent_guid: edge.parent_guid,
						child_guid: edge.child_guid,
					}),
					fact_type: "PLATFORM_LINEAGE_EDGE",
					run_id: DOWNSTREAM_LINEAGE_RUN_ID,
					parent_guid: edge.parent_guid,
					parent_name: edge.parent_name,
					parent_db_name: edge.parent_db_name,
					child_guid: edge.child_guid,
					child_name: edge.child_name,
					child_type: edge.child_type,
					child_db_name: edge.child_db_name,
					query_status: "SUCCESS",
					db_resolution_status: resolution.db_resolution_status,
					db_evidence_method: resolution.evidence_method,
					evidence_method: "SZDATA_TABLE_LINEAGE",
					evidence_file: edge.evidence_file,
					fact_status: "PROVISIONAL",
					closure_status: "PARTIAL",
				};
			}),
			(record) => String(record.fact_id),
		);
	const toDetailFacts = (
		ownerSeeds: readonly DownstreamSeed[],
		taskEdges: readonly DownstreamEdge[],
	): JsonRecord[] => {
		const guids = new Set(ownerSeeds.map((seed) => seed.guid));
		for (const edge of taskEdges) {
			guids.add(edge.parent_guid);
			guids.add(edge.child_guid);
		}
		return stableRecords(
			[...guids].map((guid): JsonRecord => {
				const node = resolvedNodes.get(guid) ?? nodes.get(guid)!;
				const detail = details.get(guid);
				const resolution = resolutions.get(guid)!;
				const status = value(detail, "status") || "UNRESOLVED";
				return {
					fact_id: stableFactId("TABLE_DETAIL", { guid }),
					fact_type: "TABLE_DETAIL",
					run_id: DOWNSTREAM_LINEAGE_RUN_ID,
					guid,
					name: node.name,
					qualified_name:
						value(detail, "qualified_name") ||
						(resolution.db_name ? `${resolution.db_name}.${node.name}` : ""),
					db_name: resolution.db_name,
					detail_status: status,
					evidence_method: status === "SUCCESS" ? "SZDATA_TABLE_DETAIL" : resolution.evidence_method,
					evidence_file: value(detail, "__evidence_file") || resolution.evidence_file,
					error: value(detail, "error"),
					fact_status: "PROVISIONAL",
					closure_status: "PARTIAL",
				};
			}),
			(record) => String(record.fact_id),
		);
	};

	retireLegacyBatchRoot(outputRoot);
	for (const [taskId, ownerSeeds] of [...taskSeeds.entries()].sort(
		([left], [right]) => Number(left) - Number(right),
	)) {
		const taskEdges = deriveDmGatedLineageEdges(ownerSeeds, resolvedNodes, edges);
		const lineageFacts = toLineageFacts(taskEdges);
		const detailFacts = toDetailFacts(ownerSeeds, taskEdges);
		const scopeFacts = deriveDmGatedScope(ownerSeeds, resolvedNodes, taskEdges) as unknown as JsonRecord[];
		const detailGuids = detailFacts.map((record) => String(record.guid));
		const unresolved = detailGuids.filter(
			(guid) => resolutions.get(guid)?.db_resolution_status === "UNRESOLVED",
		).length;
		const failedDetails = detailGuids.filter((guid) => value(details.get(guid), "status") !== "SUCCESS").length;
		const manifest = {
			schema_version: "1.2.0",
			fact_family: "DOWNSTREAM_LINEAGE",
			run_id: DOWNSTREAM_LINEAGE_RUN_ID,
			task_id: taskId,
			logical_source_id: "szdata-recursive-downstream-20260818",
			status: "SUCCESS",
			fact_status: "PROVISIONAL",
			closure_status: "PARTIAL",
			inputs: commonInputs,
			method: commonMethod,
			counts: {
				seed_count: ownerSeeds.length,
				lineage_edge_fact_count: lineageFacts.length,
				table_detail_fact_count: detailFacts.length,
				downstream_scope_fact_count: scopeFacts.length,
				unresolved_db_node_count: unresolved,
				failed_query_count: 0,
				failed_detail_count: failedDetails,
				pending_or_unexpanded_node_count: unresolved,
			},
			gates: {
				required_files: true,
				hash_integrity: true,
				fact_ids_unique: true,
				evidence_links: true,
				dm_gate: true,
			},
			boundaries: {
				business_logic_correctness: "NOT_EVALUATED",
				runtime_execution: "NOT_EVALUATED",
				business_rows_read: false,
				external_model_calls: 0,
				cross_task_field_stitching: "NOT_GENERATED",
			},
			crawler_still_running: true,
			dm_rule: { stop_prefix: "dm_", passthrough_db: "dm_otc_n" },
		};
		const taskRoot = join(outputRoot, "registry", "tasks", taskId);
		mkdirSync(taskRoot, { recursive: true });
		recoverArtifactState(taskRoot, validateBundle);
		writeStatusFile(join(taskRoot, "analysis-status.json"), {
			schema_version: "1.0.0",
			task_id: taskId,
			logical_source_id: manifest.logical_source_id,
			run_id: manifest.run_id,
			state: "ANALYZING",
			requested: { inputs_sha256 },
			current_manifest_sha256: null,
		});
		const publication = publishBundle(taskRoot, manifest, [
			["lineage-edges.jsonl", lineageFacts],
			["table-details.jsonl", detailFacts],
			["downstream-scope.jsonl", scopeFacts],
		]);
		publicationCounts[publication.status]++;
		const manifestHash = sha256(
			canonicalJson(JSON.parse(readFileSync(join(taskRoot, "bundle/manifest.json"), "utf8"))),
		);
		writeStatusFile(join(taskRoot, "analysis-status.json"), {
			schema_version: "1.0.0",
			task_id: taskId,
			logical_source_id: manifest.logical_source_id,
			run_id: manifest.run_id,
			state: "SUCCESS",
			requested: { inputs_sha256 },
			current_manifest_sha256: manifestHash,
		});
		indexRows.push({
			task_id: taskId,
			logical_source_id: manifest.logical_source_id,
			manifest_sha256: manifestHash,
			bundle_path: relative(outputRoot, join(taskRoot, "bundle")).replace(/\\/g, "/"),
			status: "SUCCESS",
			fact_family: "DOWNSTREAM_LINEAGE",
		});
		selfCheck.push(...validateBundle(join(taskRoot, "bundle")).map((error) => `${taskId}: ${error}`));
		totals.lineage_edges += lineageFacts.length;
		totals.table_details += detailFacts.length;
		totals.downstream_scope += scopeFacts.length;
		totals.unresolved += unresolved;
		totals.failed_details += failedDetails;
	}

	mkdirSync(join(outputRoot, "indexes"), { recursive: true });
	writeCanonicalJsonl(join(outputRoot, "indexes", "task-fact-index.jsonl"), indexRows);
	const unresolvedSeeds = seeds.filter((seed) => !(seed.task_ids ?? []).length);
	writeCanonicalJsonl(
		join(outputRoot, "indexes", "downstream-unresolved-seeds.jsonl"),
		unresolvedSeeds.map((seed): JsonRecord => ({
			fact_id: stableFactId("UNRESOLVED_SEED_TASK_ID", { seed_guid: seed.guid }),
			fact_type: "UNRESOLVED_SEED_TASK_ID",
			run_id: DOWNSTREAM_LINEAGE_RUN_ID,
			seed_guid: seed.guid,
			seed_name: seed.name,
			seed_db_name: seed.db_name,
			task_id: null,
			evidence_method: "SEED_SCOPE",
			evidence_file: relativePath(seedsPath),
			fact_status: "PROVISIONAL",
			closure_status: "PARTIAL",
		})),
	);
	writeFileSync(
		join(outputRoot, "README.md"),
		`# Downstream DM-gated staging Machine Facts\n\n按真实 seed_task_ids 拆分为 ${indexRows.length} 个 task bundle；这是独立的 downstream lineage machine-fact，暂不合入正式 task machine-facts。\n\n- task bundle：\`registry/tasks/<真实 task_id>/bundle/\`\n- status：每个 task bundle 同级的 \`analysis-status.json\`\n- index：\`indexes/task-fact-index.jsonl\`\n- 无真实 task_id 的 seed：${unresolvedSeeds.length} 条，见 \`indexes/downstream-unresolved-seeds.jsonl\`，不伪造 task_id。\n- 当前状态：PROVISIONAL + PARTIAL；crawler 仍在运行。\n- 后续 merge 必须按真实 task_id + fact_family=DOWNSTREAM_LINEAGE 增量挂接，不能覆盖原 SQL facts。\n`,
		"utf8",
	);
	console.log(
		JSON.stringify(
			{
				output: outputRoot,
				task_count: indexRows.length,
				seed_count: seeds.length,
				unresolved_seed_count: unresolvedSeeds.length,
				counts: { ...totals, failed_queries: 0, skipped_unstable_parts: skipped.length },
				publication: publicationCounts,
				self_check: selfCheck,
			},
			null,
			2,
		),
	);
}

if (process.argv[1] && basename(process.argv[1]).startsWith("downstream-machine-facts-by-task")) main();
