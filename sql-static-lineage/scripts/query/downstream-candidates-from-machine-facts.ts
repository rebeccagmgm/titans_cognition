import { existsSync, mkdirSync, readFileSync, readdirSync, writeFileSync } from "node:fs";
import { join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { canonicalJson, canonicalJsonl, normalizeName } from "../machine-facts/machine-facts-contract.ts";

export const DOWNSTREAM_CANDIDATES_SCHEMA_VERSION = "machine-facts-downstream-candidates-v1";

type JsonRecord = Record<string, any>;

export interface DownstreamCandidateOptions {
	readonly factsRoot: string;
	readonly outputDir: string;
	readonly seeds: readonly string[];
	readonly allWriteAssets?: boolean;
}

interface LineRecord {
	readonly lineNumber: number;
	readonly value: JsonRecord;
}

function readJson(path: string): JsonRecord {
	return JSON.parse(readFileSync(path, "utf8")) as JsonRecord;
}

function readJsonl(path: string): LineRecord[] {
	if (!existsSync(path)) return [];
	return readFileSync(path, "utf8")
		.split(/\r?\n/)
		.map((line, index) => ({ line, lineNumber: index + 1 }))
		.filter(({ line }) => line.trim().length > 0)
		.map(({ line, lineNumber }) => ({ lineNumber, value: JSON.parse(line) as JsonRecord }));
}

function tableName(value: unknown): string {
	return normalizeName(String(value ?? ""));
}

function shortTableName(value: string): string {
	const parts = value.split(".");
	return parts[parts.length - 1] ?? value;
}

function seedMatch(
	physicalDataset: unknown,
	seedNames: readonly string[],
	uniqueShortSeeds: ReadonlyMap<string, string>,
): { seed: string; match: "EXACT" | "UNQUALIFIED" } | null {
	const dataset = tableName(physicalDataset);
	if (!dataset) return null;
	const exact = seedNames.find((seed) => seed === dataset);
	if (exact) return { seed: exact, match: "EXACT" };
	const short = uniqueShortSeeds.get(shortTableName(dataset));
	return short ? { seed: short, match: "UNQUALIFIED" } : null;
}

function taskBundlePath(factsRoot: string, taskId: string, file: string): string {
	return join(factsRoot, "registry", "tasks", taskId, "bundle", file);
}

function evidenceRef(factsRoot: string, path: string, lineNumber?: number): string {
	const relativePath = relative(factsRoot, path).replaceAll("\\", "/");
	return `machine-facts:${relativePath}${lineNumber ? `#L${lineNumber}` : ""}`;
}

function fieldSummary(
	fieldRecords: readonly LineRecord[],
	seed: string,
	observedDataset: string,
	matchBasis: "EXACT" | "UNQUALIFIED",
): JsonRecord {
	const matchesSeed = (value: unknown): boolean => {
		const normalized = tableName(value);
		return matchBasis === "EXACT"
			? normalized === tableName(observedDataset)
			: shortTableName(normalized) === shortTableName(seed);
	};
	const matched = fieldRecords.filter(({ value }) =>
		Array.isArray(value.input_fields) &&
		value.input_fields.some((input: JsonRecord) => matchesSeed(input.table)),
	);
	const inputFields = matched.flatMap(({ value }) =>
		(Array.isArray(value.input_fields) ? value.input_fields : [])
			.filter((input: JsonRecord) => matchesSeed(input.table))
			.map((input: JsonRecord) => `${tableName(input.table)}.${tableName(input.column)}`),
	);
	const statuses = [...new Set(matched.map(({ value }) => String(value.input_dependency_status ?? "UNKNOWN")))].sort();
	return {
		consumer_field_expression_count: matched.length,
		seed_input_field_count: new Set(inputFields).size,
		seed_input_dependency_statuses: statuses,
		unresolved_consumer_field_expression_count: matched.filter(({ value }) => value.input_dependency_status !== "PHYSICAL").length,
		field_expression_evidence_refs: matched.slice(0, 20).map(({ value }) => value.artifact_id).filter(Boolean),
	};
}

function outputAssetsForTask(
	options: DownstreamCandidateOptions,
	ioPath: string,
	writes: readonly LineRecord[],
): JsonRecord[] {
	const byDataset = new Map<string, JsonRecord>();
	for (const { value, lineNumber } of writes) {
		const key = tableName(value.physical_dataset);
		if (!key) continue;
		const current = byDataset.get(key);
		const ref = evidenceRef(options.factsRoot, ioPath, lineNumber);
		if (current) {
			current.evidence_refs = [...new Set([...(current.evidence_refs ?? []), ref])];
			current.observation_count = Number(current.observation_count ?? 0) + 1;
			continue;
		}
		byDataset.set(key, {
			physical_dataset: value.physical_dataset,
			dataset_id: value.dataset_id,
			provenance: value.provenance,
			resolution_status: value.resolution_status,
			observation_count: 1,
			evidence_refs: [ref],
		});
	}
	return [...byDataset.values()].sort((left, right) => tableName(left.physical_dataset).localeCompare(tableName(right.physical_dataset)));
}

function taskDirectoriesForFacts(factsRoot: string): string[] {
	const tasksRoot = join(factsRoot, "registry", "tasks");
	return existsSync(tasksRoot)
		? readdirSync(tasksRoot, { withFileTypes: true }).filter((entry) => entry.isDirectory()).map((entry) => entry.name).sort()
		: [];
}

function allWriteAssets(
	factsRoot: string,
	taskDirectories: readonly string[],
): string[] {
	const assets = new Set<string>();
	for (const taskId of taskDirectories) {
		const records = readJsonl(taskBundlePath(factsRoot, taskId, "dataset-io.jsonl"));
		for (const { value } of records) {
			if (value.direction === "WRITE") {
				const dataset = tableName(value.physical_dataset);
				if (dataset) assets.add(dataset);
			}
		}
	}
	return [...assets].sort();
}

export function discoverDownstreamCandidates(options: DownstreamCandidateOptions): {
	readonly manifest: JsonRecord;
	readonly candidates: JsonRecord[];
} {
	const taskDirectories = taskDirectoriesForFacts(options.factsRoot);
	const configuredSeeds = [...new Set(options.seeds.map(tableName).filter(Boolean))].sort();
	const seeds = options.allWriteAssets ? allWriteAssets(options.factsRoot, taskDirectories) : configuredSeeds;
	if (seeds.length === 0) throw new Error("at least one --seed is required");
	const uniqueShortSeeds = new Map<string, string>();
	for (const seed of seeds) {
		const short = shortTableName(seed);
		if (uniqueShortSeeds.has(short)) uniqueShortSeeds.delete(short);
		else uniqueShortSeeds.set(short, seed);
	}

	const candidates: JsonRecord[] = [];
	const seenCandidateKeys = new Set<string>();

	for (const taskId of taskDirectories) {
		const ioPath = taskBundlePath(options.factsRoot, taskId, "dataset-io.jsonl");
		const ioRecords = readJsonl(ioPath);
		const matchingReads = ioRecords.filter(({ value }) => value.direction === "READ" && seedMatch(value.physical_dataset, seeds, uniqueShortSeeds));
		if (matchingReads.length === 0) continue;
		const writes = ioRecords.filter(({ value }) => value.direction === "WRITE");
		const writeDatasets = new Set(writes.map(({ value }) => tableName(value.physical_dataset)).filter(Boolean));
		const statusPath = join(options.factsRoot, "registry", "tasks", taskId, "analysis-status.json");
		const status = existsSync(statusPath) ? readJson(statusPath) : { state: "MISSING" };
		const manifestPath = taskBundlePath(options.factsRoot, taskId, "manifest.json");
		const taskManifest = existsSync(manifestPath) ? readJson(manifestPath) : {};
		const fieldRecords = readJsonl(taskBundlePath(options.factsRoot, taskId, "field-expression-nodes.jsonl"));

		for (const read of matchingReads) {
			const match = seedMatch(read.value.physical_dataset, seeds, uniqueShortSeeds)!;
			if (writeDatasets.has(tableName(read.value.physical_dataset))) continue;
			const candidateKey = `${match.seed}|${taskId}|${tableName(read.value.physical_dataset)}`;
			if (seenCandidateKeys.has(candidateKey)) continue;
			seenCandidateKeys.add(candidateKey);
			const outputAssets = outputAssetsForTask(options, ioPath, writes);
			const statusName = status.state === "SUCCESS" && read.value.resolution_status === "RESOLVED" && outputAssets.length > 0
				? "CANDIDATE"
				: outputAssets.length === 0
					? "NOT_EVALUABLE"
					: "PARTIAL";
			candidates.push({
				candidate_id: `downstream:${match.seed}:${taskId}`,
				schema_version: DOWNSTREAM_CANDIDATES_SCHEMA_VERSION,
				hop: 1,
				candidate_status: statusName,
				seed_asset: {
					configured_name: match.seed,
					observed_physical_dataset: read.value.physical_dataset,
					match_basis: match.match,
				},
				consumer_task: {
					task_id: taskId,
					analysis_state: status.state,
					logical_source_id: taskManifest.logical_source_id,
					sql_sha256: taskManifest.inputs?.sql_sha256,
					sql_snapshot: taskManifest.inputs?.sql_snapshot,
				},
				seed_read: {
					dataset_id: read.value.dataset_id,
					physical_dataset: read.value.physical_dataset,
					provenance: read.value.provenance,
					resolution_status: read.value.resolution_status,
					statement_id: read.value.statement_id,
					evidence_ref: evidenceRef(options.factsRoot, ioPath, read.lineNumber),
				},
				downstream_outputs: outputAssets,
				field_summary: fieldSummary(fieldRecords, match.seed, String(read.value.physical_dataset), match.match),
				boundaries: {
					max_hops: 1,
					business_rows_read: false,
					semantic_layer_classification: "NOT_PERFORMED",
					complete_cross_task_field_stitching: "NOT_CLAIMED",
				},
			});
		}
	}

	candidates.sort((left, right) => String(left.candidate_id).localeCompare(String(right.candidate_id)));
	return {
		manifest: {
			schema_version: DOWNSTREAM_CANDIDATES_SCHEMA_VERSION,
			projection_type: "DIRECT_DOWNSTREAM_CANDIDATE_INVENTORY",
			status: candidates.length > 0 ? "SUCCESS" : "PARTIAL",
			seed_assets: seeds,
			seed_selection: options.allWriteAssets ? "ALL_TASK_WRITE_ASSETS" : "EXPLICIT_SEEDS",
			max_hops: 1,
			task_count_scanned: taskDirectories.length,
			candidate_count: candidates.length,
			candidate_status_counts: Object.fromEntries(
				["CANDIDATE", "PARTIAL", "NOT_EVALUABLE"].map((status) => [status, candidates.filter((candidate) => candidate.candidate_status === status).length]),
			),
			boundaries: {
				business_rows_read: false,
				schedule_execution: false,
				semantic_layer_classification: "NOT_PERFORMED",
				recursive_downstream_expansion: false,
			},
			method: {
				name: "scan-task-dataset-io",
				version: "1.0.0",
				input: "validated-or-observed task Machine Facts dataset-io and field-expression nodes",
			},
		},
		candidates,
	};
}

export function discoverTransitiveDownstreamCandidates(options: DownstreamCandidateOptions): {
	readonly manifest: JsonRecord;
	readonly candidates: JsonRecord[];
} {
	const direct = discoverDownstreamCandidates(options);
	const seedAssets = direct.manifest.seed_assets as string[];
	const directBySeed = new Map<string, JsonRecord[]>();
	for (const candidate of direct.candidates) {
		const seed = String(candidate.seed_asset?.configured_name ?? "");
		const rows = directBySeed.get(seed) ?? [];
		rows.push(candidate);
		directBySeed.set(seed, rows);
	}
	const uniqueShortAssets = new Map<string, string>();
	for (const seed of seedAssets) {
		const short = shortTableName(seed);
		if (uniqueShortAssets.has(short)) uniqueShortAssets.delete(short);
		else uniqueShortAssets.set(short, seed);
	}
	const resolveAsset = (value: unknown): string | null => {
		const normalized = tableName(value);
		if (!normalized) return null;
		if (directBySeed.has(normalized)) return normalized;
		return uniqueShortAssets.get(shortTableName(normalized)) ?? null;
	};

	const candidates: JsonRecord[] = [];
	for (const seed of seedAssets) {
		const queue: Array<{ asset: string; hop: number; path: JsonRecord[] }> = [{
			asset: seed,
			hop: 0,
			path: [{ kind: "ASSET", configured_name: seed }],
		}];
		const visitedAssets = new Set<string>([seed]);
		const visitedTasks = new Set<string>();
		while (queue.length > 0) {
			const state = queue.shift()!;
			for (const directCandidate of directBySeed.get(state.asset) ?? []) {
				const taskId = String(directCandidate.consumer_task?.task_id ?? "");
				if (!taskId || visitedTasks.has(taskId)) continue;
				visitedTasks.add(taskId);
				const hop = state.hop + 1;
				const taskPath = [...state.path, { kind: "TASK", task_id: taskId }];
				candidates.push({
					...directCandidate,
					candidate_id: `downstream:${seed}:${taskId}:hop${hop}`,
					hop,
					seed_asset: {
						configured_name: seed,
						configured_name: seed,
						observed_physical_dataset: seed,
						match_basis: "SEED_ASSET",
					},
					via_asset: directCandidate.seed_asset,
					via_seed_read: directCandidate.seed_read,
					path: taskPath,
					boundaries: {
						max_hops: null,
						business_rows_read: false,
						semantic_layer_classification: "NOT_PERFORMED",
						complete_cross_task_field_stitching: "NOT_CLAIMED",
					},
				});
				for (const output of directCandidate.downstream_outputs ?? []) {
					const nextAsset = resolveAsset(output.physical_dataset);
					if (!nextAsset || visitedAssets.has(nextAsset)) continue;
					visitedAssets.add(nextAsset);
					queue.push({
						asset: nextAsset,
						hop,
						path: [...taskPath, { kind: "ASSET", configured_name: nextAsset }],
					});
				}
			}
		}
	}

	candidates.sort((left, right) => String(left.candidate_id).localeCompare(String(right.candidate_id)));
	const maxHop = candidates.reduce((max, candidate) => Math.max(max, Number(candidate.hop ?? 0)), 0);
	return {
		manifest: {
			schema_version: DOWNSTREAM_CANDIDATES_SCHEMA_VERSION,
			projection_type: "TRANSITIVE_DOWNSTREAM_CANDIDATE_INVENTORY",
			status: candidates.length > 0 ? "SUCCESS" : "PARTIAL",
			seed_assets: seedAssets,
			seed_selection: direct.manifest.seed_selection,
			max_hops: maxHop,
			task_count_scanned: direct.manifest.task_count_scanned,
			direct_candidate_count: direct.candidates.length,
			candidate_count: candidates.length,
			candidate_status_counts: Object.fromEntries(
				["CANDIDATE", "PARTIAL", "NOT_EVALUABLE"].map((status) => [status, candidates.filter((candidate) => candidate.candidate_status === status).length]),
			),
			boundaries: {
				business_rows_read: false,
				schedule_execution: false,
				semantic_layer_classification: "NOT_PERFORMED",
				recursive_downstream_expansion: true,
				path_policy: "SHORTEST_PATH_PER_SEED_AND_CONSUMER_TASK",
				cycle_policy: "VISITED_ASSET_AND_TASK_DEDUPLICATION",
			},
			method: {
				name: "bfs-over-task-dataset-io",
				version: "1.0.0",
				input: "one-hop downstream candidate inventory generated from task Machine Facts",
			},
		},
		candidates,
	};
}

export function collapseDownstreamRange(candidates: readonly JsonRecord[]): JsonRecord[] {
	const range = new Map<string, JsonRecord>();
	for (const candidate of candidates) {
		const seed = String(candidate.seed_asset?.configured_name ?? "");
		const hop = Number(candidate.hop ?? 0);
		for (const output of Array.isArray(candidate.downstream_outputs) ? candidate.downstream_outputs : []) {
			const downstreamAsset = tableName(output.physical_dataset);
			if (!seed || !downstreamAsset) continue;
			const key = `${seed}|${downstreamAsset}`;
			const current = range.get(key);
			const taskId = String(candidate.consumer_task?.task_id ?? "");
			if (current) {
				current.min_hop = Math.min(Number(current.min_hop ?? hop), hop);
				current.consumer_task_ids = [...new Set([...(current.consumer_task_ids ?? []), taskId].filter(Boolean))].sort();
				current.evidence_refs = [...new Set([
					...(current.evidence_refs ?? []),
					candidate.via_seed_read?.evidence_ref,
					...(output.evidence_refs ?? []),
				].filter(Boolean))].sort();
				continue;
			}
			range.set(key, {
				range_id: `range:${seed}:${downstreamAsset}`,
				schema_version: "machine-facts-downstream-range-v1",
				seed_asset: seed,
				downstream_asset: output.physical_dataset,
				min_hop: hop,
				consumer_task_ids: taskId ? [taskId] : [],
				evidence_refs: [candidate.via_seed_read?.evidence_ref, ...(output.evidence_refs ?? [])].filter(Boolean).sort(),
			});
		}
	}
	return [...range.values()].sort((left, right) => String(left.range_id).localeCompare(String(right.range_id)));
}

function optionValues(argv: readonly string[], name: string): string[] {
	const values: string[] = [];
	for (let index = 0; index < argv.length; index += 1) {
		if (argv[index] === name && argv[index + 1]) values.push(argv[index + 1]!);
	}
	return values;
}

function optionValue(argv: readonly string[], name: string, fallback: string): string {
	const index = argv.indexOf(name);
	return index >= 0 && argv[index + 1] ? argv[index + 1]! : fallback;
}

if (process.argv[1] && resolve(process.argv[1]) === resolve(fileURLToPath(import.meta.url))) {
	const factsRoot = resolve(optionValue(process.argv.slice(2), "--facts-root", "machine-facts"));
	const outputDir = resolve(optionValue(process.argv.slice(2), "--output", join(factsRoot, "projections", "downstream-candidates")));
	const args = process.argv.slice(2);
	const seeds = optionValues(args, "--seed");
	const options = { factsRoot, outputDir, seeds, allWriteAssets: args.includes("--all-write-assets") };
	const result = args.includes("--recursive")
		? discoverTransitiveDownstreamCandidates(options)
		: discoverDownstreamCandidates(options);
	mkdirSync(outputDir, { recursive: true });
	writeFileSync(join(outputDir, "manifest.json"), canonicalJson(result.manifest), "utf8");
	writeFileSync(join(outputDir, "candidates.jsonl"), canonicalJsonl(result.candidates), "utf8");
	if (args.includes("--recursive")) {
		const range = collapseDownstreamRange(result.candidates);
		result.manifest.range_count = range.length;
		result.manifest.unique_downstream_asset_count = new Set(range.map((row) => row.downstream_asset)).size;
		result.manifest.unique_downstream_task_count = new Set(result.candidates.flatMap((candidate) => candidate.consumer_task?.task_id ? [candidate.consumer_task.task_id] : [])).size;
		writeFileSync(join(outputDir, "manifest.json"), canonicalJson(result.manifest), "utf8");
		writeFileSync(join(outputDir, "range.jsonl"), canonicalJsonl(range), "utf8");
	}
	console.log(JSON.stringify({ outputDir, ...result.manifest }));
}
