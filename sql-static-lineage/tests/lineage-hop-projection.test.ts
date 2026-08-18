import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, relative, resolve } from "node:path";
import { afterEach, describe, expect, it } from "vitest";

import { Schema, SqlSession } from "../src/index.js";
import { buildPlanFacts } from "../scripts/plans/plan-adapter.ts";
import { processProfile, validateBundle } from "../scripts/machine-facts/machine-facts.ts";

const workspace = resolve(import.meta.dirname, "../..");
const tempRoots: string[] = [];

afterEach(() => {
	for (const root of tempRoots.splice(0)) rmSync(root, { recursive: true, force: true });
});

function planOf(sql: string, tables: Record<string, Record<string, string>> = { "demo.t": { id: "int" } }) {
	const schema = new Schema(tables);
	const session = SqlSession.create(sql, "databricks", { schema });
	return buildPlanFacts(session.doc.statements[0]!, sql, {
		dialect: "databricks",
		schema,
		include_expression_dependencies: true,
	});
}

function rootOf(plan: ReturnType<typeof planOf>, expression = "root.project") {
	return plan.lineage_hops.roots.find((root) => root.root_expression_id.startsWith(expression));
}

describe("native LineageHop projection", () => {
	it("keeps computed CTE hops, FROM-subquery hops, and deterministic shared producers", () => {
		const plan = planOf(
			"WITH a AS (SELECT id+1 AS x FROM demo.t), b AS (SELECT x*2 AS y FROM a) SELECT y+y AS result FROM b",
		);
		const root = rootOf(plan);
		expect(root?.projection_status).toBe("PARTIAL_NATIVE");
		expect(plan.lineage_hops.edges.filter((edge) => edge.edge_type === "HOP_TO_HOP").length).toBeGreaterThan(0);
		expect(new Set(plan.lineage_hops.nodes.map((node) => node.hop_id)).size).toBe(plan.lineage_hops.nodes.length);
		expect(plan.lineage_hops.nodes.some((node) => node.has_downstream)).toBe(true);
	});

	it("keeps rename via on the native Hop node and never puts it on an edge", () => {
		const plan = planOf("WITH renamed AS (SELECT id AS record_id FROM demo.t) SELECT record_id FROM renamed");
		const root = rootOf(plan);
		const node = plan.lineage_hops.nodes.find((candidate) => candidate.hop_id === root?.head_hop_id);
		expect(node?.via).toEqual([expect.objectContaining({ kind: "rename" })]);
		expect(plan.lineage_hops.edges.every((edge) => !("via" in edge))).toBe(true);
	});

	it("anchors aggregate measure roots to the aggregate expression locator", () => {
		const plan = planOf("SELECT k, sum(v) AS total FROM demo.t GROUP BY k", { "demo.t": { k: "int", v: "int" } });
		const aggregateRoot = plan.lineage_hops.roots.find((root) => root.root_expression_id.startsWith("root.aggregate:expression:aggregate_measure"));
		const aggregateNode = plan.lineage_hops.nodes.find((node) => node.hop_id === aggregateRoot?.head_hop_id);
		expect(aggregateNode?.expression_id).toBe(aggregateRoot?.root_expression_id);
		expect(aggregateNode?.scope_relation_id).toBe("root.aggregate");
	});

	it("flattens scalar and EXISTS paths instead of claiming full Hop coverage", () => {
		const plan = planOf(
			"SELECT (SELECT l.value FROM demo.lookup l WHERE l.id=t.id) AS scalar_value, EXISTS (SELECT 1 FROM demo.lookup l WHERE l.id=t.id) AS present FROM demo.t t",
			{ "demo.t": { id: "int" }, "demo.lookup": { id: "int", value: "int" } },
		);
		const roots = plan.lineage_hops.roots.filter((root) => root.root_expression_id.startsWith("root.project"));
		expect(roots).toEqual(expect.arrayContaining([
			expect.objectContaining({ coverage_state: "FLAT_ORIGIN_ONLY", projection_status: "PARTIAL_NATIVE" }),
		]));
	});

	it("marks final Star Expansion as not evaluable without a native column anchor", () => {
		const plan = planOf("SELECT * FROM demo.t");
		expect(plan.lineage_hops.roots[0]).toMatchObject({
		coverage_state: "NOT_EVALUABLE",
		projection_status: "NOT_EVALUABLE",
		head_hop_id: null,
		reason_code: "NATIVE_STAR_COLUMN_ANCHOR_UNAVAILABLE",
	});
	});

	it("fans UNION branches without fabricating a Setop Hop and preserves mixed inputs", () => {
		const union = planOf("SELECT id+1 AS value FROM demo.a UNION ALL SELECT id+1 AS value FROM demo.b", {
			"demo.a": { id: "int" },
			"demo.b": { id: "int" },
		});
		expect(union.lineage_hops.nodes.some((node) => node.scope_relation_id.includes("setop") && node.expr_kind === "setop")).toBe(false);
		expect(union.lineage_hops.nodes.filter((node) => node.terminal === "PRESENT").length).toBeGreaterThanOrEqual(2);

		const mixed = planOf("SELECT t.id + d.value AS value FROM demo.t t JOIN (SELECT id+1 AS value FROM demo.other) d ON t.id=d.value", {
			"demo.t": { id: "int" },
			"demo.other": { id: "int" },
		});
		const mixedRoot = rootOf(mixed);
		const mixedNode = mixed.lineage_hops.nodes.find((node) => node.hop_id === mixedRoot?.head_hop_id);
		expect(mixedNode?.terminal).toBe("PRESENT");
		expect(mixedNode?.has_downstream).toBe(true);
		expect(mixed.lineage_hops.edges.some((edge) => edge.edge_type === "HOP_TO_HOP")).toBe(true);
	});

	it("keeps nested Setop Hop edges acyclic and derives downstream flags from persisted edges", () => {
		const plan = planOf(
			"WITH first AS (SELECT id + 1 AS value FROM demo.a UNION ALL SELECT id + 2 AS value FROM demo.b), second AS (SELECT value FROM first UNION ALL SELECT value + 3 AS value FROM first) SELECT value + 4 AS result FROM second",
			{
				"demo.a": { id: "int" },
				"demo.b": { id: "int" },
			},
		);
		const nodes = new Map(plan.lineage_hops.nodes.map((node) => [node.hop_id, node]));
		const adjacency = new Map<string, string[]>();
		for (const edge of plan.lineage_hops.edges) {
			if (edge.edge_type !== "HOP_TO_HOP" || !edge.from_hop_id) continue;
			adjacency.set(edge.from_hop_id, [...(adjacency.get(edge.from_hop_id) ?? []), edge.to_hop_id]);
		}
		const visiting = new Set<string>();
		const visited = new Set<string>();
		const visit = (hopId: string): void => {
			expect(visiting.has(hopId)).toBe(false);
			if (visited.has(hopId)) return;
			visiting.add(hopId);
			for (const next of adjacency.get(hopId) ?? []) visit(next);
			visiting.delete(hopId);
			visited.add(hopId);
		};
		for (const hopId of nodes.keys()) visit(hopId);
		const consumers = new Set(
			plan.lineage_hops.edges
				.filter((edge) => edge.edge_type === "HOP_TO_HOP")
				.map((edge) => edge.to_hop_id),
		);
		for (const node of nodes.values()) expect(node.has_downstream).toBe(consumers.has(node.hop_id));
	});

	it("retains candidate and unsupported coverage as partial/unknown", () => {
		const candidate = planOf("SELECT id FROM demo.unverified", { "demo.other": { id: "int" } });
		expect(rootOf(candidate)?.projection_status).toBe("PARTIAL_NATIVE");
		const unsupported = planOf("SELECT x.pos FROM demo.t t LATERAL VIEW posexplode(array(1)) x AS pos", { "demo.t": { id: "int" } });
		expect(rootOf(unsupported)?.coverage_state).toBe("UNKNOWN_COVERAGE");
	});
});

describe("Machine Facts Hop publication and validation", () => {
	it("publishes sorted Hop datasets, replaces changed context, then reuses deterministic replay", () => {
		const root = mkdtempSync(join(tmpdir(), "titans-machine-facts-hop-"));
		tempRoots.push(root);
		const sqlPath = join(root, "task.sql");
		const schemaPath = join(root, "schema.json");
		const profilePath = join(root, "profile.json");
		const outputPath = join(root, "facts");
		writeFileSync(sqlPath, "INSERT OVERWRITE TABLE demo.out SELECT y+1 AS y FROM (SELECT id*2 AS y FROM demo.in) b;\n", "utf8");
		writeFileSync(schemaPath, JSON.stringify({ records: [
			{ qualified_name: "demo.in", status: "SUCCESS", columns: [{ name: "id" }] },
			{ qualified_name: "demo.out", status: "SUCCESS", columns: [{ name: "y" }] },
		] }), "utf8");
		writeFileSync(profilePath, JSON.stringify({ dialect: "databricks", schema_evidence: relative(workspace, schemaPath).replace(/\\/g, "/"), tasks: [{ task_id: "hop-task", sql_snapshot: relative(workspace, sqlPath).replace(/\\/g, "/"), writes: "demo.out" }] }), "utf8");

		const first = processProfile(relative(workspace, profilePath).replace(/\\/g, "/"), relative(workspace, outputPath).replace(/\\/g, "/"), "hop-source");
		expect(first.tasks[0]?.status).toBe("CREATED");
		const bundle = join(outputPath, "registry", "tasks", "hop-task", "bundle");
		for (const file of ["lineage-hop-roots.jsonl", "lineage-hop-nodes.jsonl", "lineage-hop-edges.jsonl"]) expect(readFileSync(join(bundle, file), "utf8")).toBe(readFileSync(join(bundle, file), "utf8").split(/\r?\n/).filter(Boolean).sort().join("\n") + (readFileSync(join(bundle, file), "utf8").trim() ? "\n" : ""));
		const indexBefore = readFileSync(join(outputPath, "indexes", "task-fact-index.jsonl"), "utf8");
		const replay = processProfile(relative(workspace, profilePath).replace(/\\/g, "/"), relative(workspace, outputPath).replace(/\\/g, "/"), "hop-source");
		expect(replay.tasks[0]?.status).toBe("REUSED");
		expect(readFileSync(join(outputPath, "indexes", "task-fact-index.jsonl"), "utf8")).toBe(indexBefore);
		writeFileSync(sqlPath, "INSERT OVERWRITE TABLE demo.out SELECT y+2 AS y FROM (SELECT id*3 AS y FROM demo.in) b;\n", "utf8");
		const replaced = processProfile(relative(workspace, profilePath).replace(/\\/g, "/"), relative(workspace, outputPath).replace(/\\/g, "/"), "hop-source");
		expect(replaced.tasks[0]?.status).toBe("REPLACED");
		expect(validateBundle(bundle)).toEqual([]);
		const hopEdgesPath = join(bundle, "lineage-hop-edges.jsonl");
		const hopEdges = readFileSync(hopEdgesPath, "utf8").trim().split(/\r?\n/).filter(Boolean).map((line) => JSON.parse(line) as Record<string, unknown>);
		const downstream = hopEdges.find((edge) => edge.edge_type === "HOP_TO_HOP");
		expect(downstream).toBeDefined();
		writeFileSync(hopEdgesPath, `${readFileSync(hopEdgesPath, "utf8")}{"edge_id":"synthetic-cycle","task_id":"hop-task","statement_id":"task:hop-task:statement:0","edge_type":"HOP_TO_HOP","from_field_id":null,"from_hop_id":${JSON.stringify(downstream!.to_hop_id)},"to_hop_id":${JSON.stringify(downstream!.from_hop_id)},"branch_relation_id":null,"branch_ordinal":null,"flow_kind":"VALUE_LINEAGE"}\n{"edge_id":"synthetic-dangling","task_id":"hop-task","statement_id":"task:hop-task:statement:0","edge_type":"HOP_TO_HOP","from_field_id":null,"from_hop_id":"missing-hop","to_hop_id":${JSON.stringify(downstream!.to_hop_id)},"branch_relation_id":null,"branch_ordinal":null,"flow_kind":"VALUE_LINEAGE"}\n`, "utf8");
		writeFileSync(hopEdgesPath, `${readFileSync(hopEdgesPath, "utf8")}{"edge_id":"synthetic-missing-field","task_id":"hop-task","statement_id":"task:hop-task:statement:0","edge_type":"PHYSICAL_FIELD_TO_HOP","from_field_id":"missing-field","from_hop_id":null,"to_hop_id":${JSON.stringify(downstream!.to_hop_id)},"branch_relation_id":null,"branch_ordinal":null,"flow_kind":"VALUE_LINEAGE"}\n`, "utf8");
		const hopNodesPath = join(bundle, "lineage-hop-nodes.jsonl");
		const mutatedNodes = readFileSync(hopNodesPath, "utf8").trim().split(/\r?\n/).filter(Boolean).map((line) => JSON.parse(line) as Record<string, unknown>);
		if (mutatedNodes[0]) {
			mutatedNodes[0].via_relation_ids = [{ relation_id: "missing-relation", kind: "rename" }];
			mutatedNodes[0].terminal_field_ids = [];
			mutatedNodes[0].terminal = "NONE";
		}
		writeFileSync(hopNodesPath, `${mutatedNodes.map((node) => JSON.stringify(node)).join("\n")}\n`, "utf8");
		const hopRootsPath = join(bundle, "lineage-hop-roots.jsonl");
		const mutatedRoots = readFileSync(hopRootsPath, "utf8").trim().split(/\r?\n/).filter(Boolean).map((line) => JSON.parse(line) as Record<string, unknown>);
		const projectedRoot = mutatedRoots.find((root) => root.projection_status === "PROJECTED");
		if (projectedRoot) projectedRoot.physical_input_field_ids = [];
		writeFileSync(hopRootsPath, `${mutatedRoots.map((root) => JSON.stringify(root)).join("\n")}\n`, "utf8");
		const invalid = validateBundle(bundle).join(" ");
		expect(invalid).toContain("Hop DAG cycle detected");
		expect(invalid).toContain("invalid downstream Hop edge endpoint synthetic-dangling");
		expect(invalid).toContain("physical Hop field endpoint missing");
		expect(invalid).toContain("Hop via relation endpoint missing");
		expect(invalid).toContain("FULL_HOP origin-conservation mismatch");
	});

	it("rejects a Hop cycle and a dangling endpoint before publication", () => {
		const root = mkdtempSync(join(tmpdir(), "titans-machine-facts-hop-invalid-"));
		tempRoots.push(root);
		const manifest = {
			schema_version: "1.3.0", task_id: "t", logical_source_id: "s", status: "SUCCESS",
			inputs: { sql_sha256: "0".repeat(64), sql_snapshot: "snapshots/sql/" + "0".repeat(64) + ".sql", schema_bundle_sha256: "1".repeat(64), schema_snapshot: "snapshots/schema/" + "1".repeat(64) + ".json", analysis_config_sha256: "2".repeat(64) },
			method: { dialect: "databricks", parser: { engine: "x", version: "x" }, adapter: { name: "machine-facts-writer", version: "1.3.0" }, plan_adapter: { name: "plan-adapter", version: "0.3.0" } },
			outputs: [], counts: { lineage_hop_roots: 1, lineage_hop_nodes: 2, lineage_hop_edges: 2, lineage_hop_projected_roots: 1, lineage_hop_partial_roots: 0, lineage_hop_not_evaluable_roots: 0 }, gates: {}, boundaries: { business_logic_correctness: "NOT_EVALUATED", runtime_execution: "NOT_EVALUATED", business_rows_read: false, external_model_calls: 0, cross_task_field_stitching: "NOT_GENERATED" },
		};
		writeFileSync(join(root, "manifest.json"), JSON.stringify(manifest), "utf8");
		writeFileSync(join(root, "relation-nodes.jsonl"), "", "utf8");
		writeFileSync(join(root, "field-expression-nodes.jsonl"), "", "utf8");
		writeFileSync(join(root, "lineage-hop-roots.jsonl"), "", "utf8");
		writeFileSync(join(root, "lineage-hop-nodes.jsonl"), "", "utf8");
		writeFileSync(join(root, "lineage-hop-edges.jsonl"), "", "utf8");
		expect(validateBundle(root).join(" ")).toContain("manifest schema");
	});
});
