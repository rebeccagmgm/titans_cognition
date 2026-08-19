import { describe, expect, it } from "vitest";
import {
	deriveDmGatedScope,
	isDmDatabase,
	resolveDatabase,
	stableFactId,
	type DownstreamEdge,
	type DownstreamNode,
} from "../scripts/machine-facts/downstream-lineage-adapter.ts";

const node = (guid: string, name: string, db_name: string): DownstreamNode => ({
	guid,
	name,
	db_name,
	type: "hive_table",
});

const edge = (
	parent_guid: string,
	child_guid: string,
	evidence_file = "direct-edges/part-00001.csv",
): DownstreamEdge => ({
	parent_guid,
	parent_name: parent_guid,
	parent_db_name: "",
	child_guid,
	child_name: child_guid,
	child_type: "hive_table",
	child_db_name: "",
	query_status: "SUCCESS",
	evidence_file,
});

describe("downstream lineage adapter", () => {
	it("recognizes only dm_* as DM and keeps dm_otc_n expandable", () => {
		expect(isDmDatabase("dm_otc_n")).toBe(true);
		expect(isDmDatabase("ods_n")).toBe(false);
	});

	it("gates pre-DM unknown nodes and stops non-passthrough DM nodes", () => {
		const nodes = new Map<string, DownstreamNode>([
			["seed", node("seed", "seed", "ods_n")],
			["unknown", node("unknown", "unknown", "")],
			["dm", node("dm", "dm", "dm_other")],
			["after-dm", node("after-dm", "after-dm", "dm_other")],
		]);
		const edges = [edge("seed", "unknown"), edge("unknown", "dm"), edge("dm", "after-dm")];
		const scope = deriveDmGatedScope([{ guid: "seed", name: "seed", db_name: "ods_n" }], nodes, edges);
		expect(scope).toEqual([]);
	});

	it("allows dm_otc_n pass-through and deduplicates by seed and downstream", () => {
		const nodes = new Map<string, DownstreamNode>([
			["seed", node("seed", "seed", "ods_n")],
			["dm", node("dm", "dm", "dm_otc_n")],
			["child", node("child", "child", "dm_other")],
		]);
		const edges = [edge("seed", "dm"), edge("dm", "child"), edge("dm", "child", "direct-edges/part-00002.csv")];
		const scope = deriveDmGatedScope([{ guid: "seed", name: "seed", db_name: "ods_n" }], nodes, edges);
		expect(scope.map((row) => [row.downstream_guid, row.min_hop])).toEqual([
			["child", 2],
			["dm", 1],
		]);
		expect(scope.every((row) => row.fact_status === "PROVISIONAL" && row.closure_status === "PARTIAL")).toBe(true);
	});

	it("produces a deterministic fact id", () => {
		const value = { seed_guid: "seed", downstream_guid: "child" };
		expect(stableFactId("DOWNSTREAM_DM_GATED_SCOPE", value)).toBe(stableFactId("DOWNSTREAM_DM_GATED_SCOPE", value));
	});

	it("uses only unique local database hints and preserves ambiguity", () => {
		expect(resolveDatabase({ local_fact_db_names: ["dm_otc_n", "dm_otc_n"] })).toMatchObject({
			db_name: "dm_otc_n",
			db_resolution_status: "RESOLVED",
			evidence_method: "LOCAL_FACT_UNIQUE_DB_HINT",
		});
		expect(resolveDatabase({ local_fact_db_names: ["dm_otc_n", "dm_index_n"] })).toMatchObject({
			db_name: "",
			db_resolution_status: "UNRESOLVED",
			evidence_method: "UNRESOLVED",
		});
	});

	it("respects the evidence precedence", () => {
		expect(
			resolveDatabase({
				detail_status: "SUCCESS",
				detail_db_name: "dm_detail",
				edge_db_name: "dm_edge",
				local_fact_db_names: ["dm_local"],
			}),
		).toMatchObject({ db_name: "dm_detail", evidence_method: "SZDATA_TABLE_DETAIL" });
	});
});
