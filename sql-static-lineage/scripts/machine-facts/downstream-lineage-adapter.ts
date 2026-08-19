import { canonicalJson, normalizeName, sha256, stableRecords } from "./machine-facts-contract.ts";

export const DOWNSTREAM_LINEAGE_SCHEMA_VERSION = "downstream-lineage-machine-facts-v1";
export const DOWNSTREAM_LINEAGE_RUN_ID = "downstream-dm-gated-20260818";

export type DownstreamNode = {
	guid: string;
	name: string;
	type: string;
	db_name: string;
};

export type DownstreamEdge = {
	parent_guid: string;
	parent_name: string;
	parent_db_name: string;
	child_guid: string;
	child_name: string;
	child_type: string;
	child_db_name: string;
	query_status: "SUCCESS";
	evidence_file: string;
};

export type DownstreamSeed = {
	guid: string;
	name: string;
	db_name: string;
	task_ids?: readonly string[];
};

export type DatabaseResolutionEvidence = {
	detail_status?: string;
	detail_db_name?: string;
	edge_db_name?: string;
	seed_db_name?: string;
	local_fact_db_names?: readonly string[];
	auxiliary_db_names?: readonly string[];
	evidence_file?: string;
};

export type DatabaseResolution = {
	db_name: string;
	db_resolution_status: "RESOLVED" | "UNRESOLVED";
	evidence_method:
		| "SZDATA_TABLE_DETAIL"
		| "SZDATA_TABLE_LINEAGE"
		| "SEED_SCOPE"
		| "LOCAL_FACT_UNIQUE_DB_HINT"
		| "LOCAL_AUXILIARY_UNIQUE_DB_HINT"
		| "UNRESOLVED";
	evidence_file: string;
};

export type DownstreamScopeRecord = {
	fact_id: string;
	fact_type: "DOWNSTREAM_DM_GATED_SCOPE";
	run_id: string;
	seed_guid: string;
	seed_name: string;
	downstream_guid: string;
	downstream_name: string;
	downstream_type: string;
	downstream_db_name: string;
	min_hop: number;
	first_dm_guid: string;
	first_dm_name: string;
	first_dm_db_name: string;
	gate_status: "DM_REACHED";
	db_resolution_status: "RESOLVED" | "UNRESOLVED";
	evidence_method: "DERIVED_FROM_PLATFORM_LINEAGE_AND_TABLE_DETAIL";
	evidence_file: string;
	fact_status: "PROVISIONAL";
	closure_status: "PARTIAL";
};

type TraversalState = {
	guid: string;
	hop: number;
	dmReached: boolean;
	firstDm: DownstreamNode | null;
};

function buildAdjacency(edges: readonly DownstreamEdge[]): Map<string, DownstreamEdge[]> {
	const adjacency = new Map<string, DownstreamEdge[]>();
	for (const edge of edges) {
		if (edge.query_status !== "SUCCESS") continue;
		const bucket = adjacency.get(edge.parent_guid) ?? [];
		bucket.push(edge);
		adjacency.set(edge.parent_guid, bucket);
	}
	for (const bucket of adjacency.values()) {
		bucket.sort((left, right) =>
			`${left.child_guid}\u0000${left.evidence_file}`.localeCompare(
				`${right.child_guid}\u0000${right.evidence_file}`,
			),
		);
	}
	return adjacency;
}

export function stableFactId(factType: string, value: unknown): string {
	return `${factType.toLowerCase()}:${sha256(canonicalJson({ factType, value })).slice(0, 32)}`;
}

export function isDmDatabase(dbName: string): boolean {
	return normalizeName(dbName).startsWith("dm_");
}

export function isPassthroughDmDatabase(dbName: string): boolean {
	return normalizeName(dbName) === "dm_otc_n";
}

export function isResolvedNode(node: DownstreamNode): boolean {
	return Boolean(node.db_name.trim());
}

function uniqueDatabaseName(values: readonly string[] | undefined): string {
	const names = [...new Set((values ?? []).map((value) => value.trim()).filter(Boolean))];
	return names.length === 1 ? names[0]! : "";
}

export function resolveDatabase(evidence: DatabaseResolutionEvidence): DatabaseResolution {
	const detailDbName = evidence.detail_db_name?.trim() ?? "";
	if (evidence.detail_status === "SUCCESS" && detailDbName) {
		return {
			db_name: detailDbName,
			db_resolution_status: "RESOLVED",
			evidence_method: "SZDATA_TABLE_DETAIL",
			evidence_file: evidence.evidence_file ?? "",
		};
	}
	const edgeDbName = evidence.edge_db_name?.trim() ?? "";
	if (edgeDbName) {
		return {
			db_name: edgeDbName,
			db_resolution_status: "RESOLVED",
			evidence_method: "SZDATA_TABLE_LINEAGE",
			evidence_file: evidence.evidence_file ?? "",
		};
	}
	const seedDbName = evidence.seed_db_name?.trim() ?? "";
	if (seedDbName) {
		return {
			db_name: seedDbName,
			db_resolution_status: "RESOLVED",
			evidence_method: "SEED_SCOPE",
			evidence_file: evidence.evidence_file ?? "",
		};
	}
	const localFactDbName = uniqueDatabaseName(evidence.local_fact_db_names);
	if (localFactDbName) {
		return {
			db_name: localFactDbName,
			db_resolution_status: "RESOLVED",
			evidence_method: "LOCAL_FACT_UNIQUE_DB_HINT",
			evidence_file: evidence.evidence_file ?? "",
		};
	}
	const auxiliaryDbName = uniqueDatabaseName(evidence.auxiliary_db_names);
	if (auxiliaryDbName) {
		return {
			db_name: auxiliaryDbName,
			db_resolution_status: "RESOLVED",
			evidence_method: "LOCAL_AUXILIARY_UNIQUE_DB_HINT",
			evidence_file: evidence.evidence_file ?? "",
		};
	}
	return {
		db_name: "",
		db_resolution_status: "UNRESOLVED",
		evidence_method: "UNRESOLVED",
		evidence_file: evidence.evidence_file ?? "",
	};
}

export function deriveDmGatedScope(
	seeds: readonly DownstreamSeed[],
	nodes: ReadonlyMap<string, DownstreamNode>,
	edges: readonly DownstreamEdge[],
): DownstreamScopeRecord[] {
	const adjacency = buildAdjacency(edges);

	const records = new Map<string, DownstreamScopeRecord>();
	for (const seed of seeds) {
		const seedNode = nodes.get(seed.guid) ?? {
			guid: seed.guid,
			name: seed.name,
			type: "hive_table",
			db_name: seed.db_name,
		};
		const seedIsDm = isDmDatabase(seedNode.db_name);
		const initialState: TraversalState = {
			guid: seed.guid,
			hop: 0,
			dmReached: seedIsDm,
			firstDm: seedIsDm ? seedNode : null,
		};
		const queue: TraversalState[] = [initialState];
		const visited = new Set<string>();

		while (queue.length > 0) {
			const state = queue.shift()!;
			const stateKey = `${state.guid}\u0000${state.dmReached ? "DM" : "PRE_DM"}`;
			if (visited.has(stateKey)) continue;
			visited.add(stateKey);

			for (const edge of adjacency.get(state.guid) ?? []) {
				const child = nodes.get(edge.child_guid) ?? {
					guid: edge.child_guid,
					name: edge.child_name,
					type: edge.child_type,
					db_name: edge.child_db_name,
				};
				const childResolved = isResolvedNode(child);
				const childIsDm = childResolved && isDmDatabase(child.db_name);
				const childDmReached = state.dmReached || childIsDm;
				const firstDm = state.firstDm ?? (childIsDm ? child : null);

				// Before DM, an unresolved database cannot be classified as DM or
				// non-DM. Preserve the direct edge elsewhere, but stop this branch.
				if (!state.dmReached && !childResolved) continue;

				if (childDmReached) {
					const record: DownstreamScopeRecord = {
						fact_id: stableFactId("DOWNSTREAM_DM_GATED_SCOPE", {
							seed_guid: seed.guid,
							downstream_guid: child.guid,
						}),
						fact_type: "DOWNSTREAM_DM_GATED_SCOPE",
						run_id: DOWNSTREAM_LINEAGE_RUN_ID,
						seed_guid: seed.guid,
						seed_name: seed.name,
						downstream_guid: child.guid,
						downstream_name: child.name,
						downstream_type: child.type,
						downstream_db_name: child.db_name,
						min_hop: state.hop + 1,
						first_dm_guid: firstDm?.guid ?? "",
						first_dm_name: firstDm?.name ?? "",
						first_dm_db_name: firstDm?.db_name ?? "",
						gate_status: "DM_REACHED",
						db_resolution_status: childResolved ? "RESOLVED" : "UNRESOLVED",
						evidence_method: "DERIVED_FROM_PLATFORM_LINEAGE_AND_TABLE_DETAIL",
						evidence_file: edge.evidence_file,
						fact_status: "PROVISIONAL",
						closure_status: "PARTIAL",
					};
					const key = `${seed.guid}\u0000${child.guid}`;
					const previous = records.get(key);
					if (!previous || record.min_hop < previous.min_hop) records.set(key, record);
				}

				// Unknown nodes are a hard boundary even after DM. Other DM
				// databases are terminal; only dm_otc_n is expandable.
				if (!childResolved || (childIsDm && !isPassthroughDmDatabase(child.db_name))) continue;
				queue.push({ guid: child.guid, hop: state.hop + 1, dmReached: childDmReached, firstDm });
			}
		}
	}

	return stableRecords(
		[...records.values()],
		(record) => `${record.seed_guid}\u0000${record.downstream_guid}`,
	) as DownstreamScopeRecord[];
}

/**
 * Return only direct edges reachable from the supplied seeds under the same
 * DM gate used for scope facts. This gives a downstream fact an owner task
 * without pretending that every platform edge belongs to every task.
 */
export function deriveDmGatedLineageEdges(
	seeds: readonly DownstreamSeed[],
	nodes: ReadonlyMap<string, DownstreamNode>,
	edges: readonly DownstreamEdge[],
): DownstreamEdge[] {
	const adjacency = buildAdjacency(edges);
	const selected = new Map<string, DownstreamEdge>();
	for (const seed of seeds) {
		const seedNode = nodes.get(seed.guid) ?? {
			guid: seed.guid,
			name: seed.name,
			type: "hive_table",
			db_name: seed.db_name,
		};
		const seedIsDm = isDmDatabase(seedNode.db_name);
		const queue: TraversalState[] = [
			{
				guid: seed.guid,
				hop: 0,
				dmReached: seedIsDm,
				firstDm: seedIsDm ? seedNode : null,
			},
		];
		const visited = new Set<string>();
		while (queue.length > 0) {
			const state = queue.shift()!;
			const stateKey = `${state.guid}\u0000${state.dmReached ? "DM" : "PRE_DM"}`;
			if (visited.has(stateKey)) continue;
			visited.add(stateKey);
			for (const edge of adjacency.get(state.guid) ?? []) {
				selected.set(`${edge.parent_guid}\u0000${edge.child_guid}`, edge);
				const child = nodes.get(edge.child_guid) ?? {
					guid: edge.child_guid,
					name: edge.child_name,
					type: edge.child_type,
					db_name: edge.child_db_name,
				};
				const childResolved = isResolvedNode(child);
				const childIsDm = childResolved && isDmDatabase(child.db_name);
				const childDmReached = state.dmReached || childIsDm;
				if (!state.dmReached && !childResolved) continue;
				if (!childResolved || (childIsDm && !isPassthroughDmDatabase(child.db_name))) continue;
				queue.push({
					guid: child.guid,
					hop: state.hop + 1,
					dmReached: childDmReached,
					firstDm: state.firstDm ?? (childIsDm ? child : null),
				});
			}
		}
	}
	return [...selected.values()].sort((left, right) =>
		`${left.parent_guid}\u0000${left.child_guid}`.localeCompare(`${right.parent_guid}\u0000${right.child_guid}`),
	);
}
