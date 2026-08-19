import { mkdtempSync, mkdirSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, describe, expect, it } from "vitest";

import { collapseDownstreamRange, discoverDownstreamCandidates, discoverTransitiveDownstreamCandidates } from "../scripts/query/downstream-candidates-from-machine-facts.ts";

const roots: string[] = [];

afterEach(() => {
	for (const root of roots.splice(0)) rmSync(root, { recursive: true, force: true });
});

function writeTask(root: string, taskId: string, io: readonly Record<string, unknown>[], fields: readonly Record<string, unknown>[]): void {
	const taskRoot = join(root, "registry", "tasks", taskId);
	const bundleRoot = join(taskRoot, "bundle");
	mkdirSync(bundleRoot, { recursive: true });
	writeFileSync(join(taskRoot, "analysis-status.json"), JSON.stringify({ state: "SUCCESS", task_id: taskId }), "utf8");
	writeFileSync(
		join(bundleRoot, "manifest.json"),
		JSON.stringify({ task_id: taskId, logical_source_id: "gfhive-test", inputs: { sql_sha256: `sql-${taskId}`, sql_snapshot: `snapshots/sql/${taskId}.sql` } }),
		"utf8",
	);
	writeFileSync(join(bundleRoot, "dataset-io.jsonl"), `${io.map((record) => JSON.stringify(record)).join("\n")}\n`, "utf8");
	writeFileSync(join(bundleRoot, "field-expression-nodes.jsonl"), `${fields.map((record) => JSON.stringify(record)).join("\n")}\n`, "utf8");
}

describe("downstream candidates from Machine Facts", () => {
	it("finds one-hop consumers, keeps outputs and field coverage, and ignores unrelated tables", () => {
		const root = mkdtempSync(join(tmpdir(), "titans-downstream-candidates-"));
		roots.push(root);
		writeTask(
			root,
			"107491",
			[
				{ task_id: "107491", direction: "READ", dataset_id: "dataset:gfhive-test:pdata_n.t98_otc_deri_comp_sale_info", physical_dataset: "pdata_n.t98_otc_deri_comp_sale_info", provenance: "SQL_PLAN", resolution_status: "RESOLVED", statement_id: "s1" },
				{ task_id: "107491", direction: "WRITE", dataset_id: "dataset:gfhive-test:t98_otc_comp_sale_adtnl_det", physical_dataset: "t98_otc_comp_sale_adtnl_det", provenance: "SQL_PARSE", resolution_status: "RESOLVED", statement_id: "s1" },
				{ task_id: "107491", direction: "WRITE", dataset_id: "dataset:gfhive-test:t98_otc_comp_sale_adtnl_det", physical_dataset: "t98_otc_comp_sale_adtnl_det", provenance: "SQL_PARSE", resolution_status: "RESOLVED", statement_id: "s2" },
			],
			[
				{ output_name: "dyna_nom_prin", input_fields: [{ table: "pdata_n.t98_otc_deri_comp_sale_info", column: "dyna_nom_prin" }], input_dependency_status: "PHYSICAL", artifact_id: "sql:107491" },
			],
		);
		writeTask(
			root,
			"999999",
			[
				{ task_id: "999999", direction: "READ", dataset_id: "dataset:gfhive-test:pdata_n.t98_otc_deri_comp_sale_info_other", physical_dataset: "pdata_n.t98_otc_deri_comp_sale_info_other", provenance: "SQL_PLAN", resolution_status: "RESOLVED", statement_id: "s1" },
				{ task_id: "999999", direction: "WRITE", dataset_id: "dataset:gfhive-test:unrelated", physical_dataset: "unrelated", provenance: "SQL_PARSE", resolution_status: "RESOLVED", statement_id: "s1" },
			],
			[],
		);

		const result = discoverDownstreamCandidates({ factsRoot: root, outputDir: join(root, "out"), seeds: ["t98_otc_deri_comp_sale_info"] });
		expect(result.manifest).toMatchObject({ status: "SUCCESS", candidate_count: 1, max_hops: 1, task_count_scanned: 2 });
		expect(result.candidates[0]).toMatchObject({
			candidate_id: "downstream:t98_otc_deri_comp_sale_info:107491",
			candidate_status: "CANDIDATE",
			seed_asset: { match_basis: "UNQUALIFIED", observed_physical_dataset: "pdata_n.t98_otc_deri_comp_sale_info" },
			consumer_task: { task_id: "107491", analysis_state: "SUCCESS" },
			field_summary: { consumer_field_expression_count: 1, seed_input_field_count: 1, unresolved_consumer_field_expression_count: 0 },
		});
		expect(result.candidates[0]!.downstream_outputs).toHaveLength(1);
		expect(result.candidates[0]!.downstream_outputs[0]).toMatchObject({ observation_count: 2 });
	});

	it("can use every task WRITE asset as a seed and excludes task-internal self reads", () => {
		const root = mkdtempSync(join(tmpdir(), "titans-downstream-all-writes-"));
		roots.push(root);
		writeTask(root, "100", [
			{ task_id: "100", direction: "WRITE", dataset_id: "dataset:gfhive-test:model_a", physical_dataset: "model_a", provenance: "SQL_PARSE", resolution_status: "RESOLVED", statement_id: "s1" },
		], []);
		writeTask(root, "200", [
			{ task_id: "200", direction: "READ", dataset_id: "dataset:gfhive-test:model_a", physical_dataset: "model_a", provenance: "SQL_PLAN", resolution_status: "RESOLVED", statement_id: "s1" },
			{ task_id: "200", direction: "WRITE", dataset_id: "dataset:gfhive-test:downstream_a", physical_dataset: "downstream_a", provenance: "SQL_PARSE", resolution_status: "RESOLVED", statement_id: "s1" },
		], []);
		writeTask(root, "300", [
			{ task_id: "300", direction: "READ", dataset_id: "dataset:gfhive-test:downstream_a", physical_dataset: "downstream_a", provenance: "SQL_PLAN", resolution_status: "RESOLVED", statement_id: "s1" },
			{ task_id: "300", direction: "WRITE", dataset_id: "dataset:gfhive-test:downstream_b", physical_dataset: "downstream_b", provenance: "SQL_PARSE", resolution_status: "RESOLVED", statement_id: "s1" },
		], []);
		writeTask(root, "400", [
			{ task_id: "400", direction: "READ", dataset_id: "dataset:gfhive-test:downstream_a", physical_dataset: "downstream_a", provenance: "SQL_PLAN", resolution_status: "RESOLVED", statement_id: "s1" },
			{ task_id: "400", direction: "WRITE", dataset_id: "dataset:gfhive-test:downstream_a", physical_dataset: "downstream_a", provenance: "SQL_PARSE", resolution_status: "RESOLVED", statement_id: "s1" },
		], []);

		const result = discoverDownstreamCandidates({ factsRoot: root, outputDir: join(root, "out"), seeds: [], allWriteAssets: true });
		expect(result.manifest).toMatchObject({ seed_selection: "ALL_TASK_WRITE_ASSETS", seed_assets: ["downstream_a", "downstream_b", "model_a"], task_count_scanned: 4, candidate_count: 2 });
		expect(result.candidates.map((candidate) => candidate.candidate_id)).toEqual([
			"downstream:downstream_a:300",
			"downstream:model_a:200",
		]);
	});

	it("walks the full downstream closure and keeps the shortest task path", () => {
		const root = mkdtempSync(join(tmpdir(), "titans-downstream-transitive-"));
		roots.push(root);
		writeTask(root, "100", [
			{ task_id: "100", direction: "WRITE", dataset_id: "dataset:gfhive-test:model_a", physical_dataset: "model_a", provenance: "SQL_PARSE", resolution_status: "RESOLVED", statement_id: "s1" },
		], []);
		writeTask(root, "200", [
			{ task_id: "200", direction: "READ", dataset_id: "dataset:gfhive-test:model_a", physical_dataset: "model_a", provenance: "SQL_PLAN", resolution_status: "RESOLVED", statement_id: "s1" },
			{ task_id: "200", direction: "WRITE", dataset_id: "dataset:gfhive-test:downstream_a", physical_dataset: "downstream_a", provenance: "SQL_PARSE", resolution_status: "RESOLVED", statement_id: "s1" },
		], []);
		writeTask(root, "300", [
			{ task_id: "300", direction: "READ", dataset_id: "dataset:gfhive-test:downstream_a", physical_dataset: "downstream_a", provenance: "SQL_PLAN", resolution_status: "RESOLVED", statement_id: "s1" },
			{ task_id: "300", direction: "WRITE", dataset_id: "dataset:gfhive-test:downstream_b", physical_dataset: "downstream_b", provenance: "SQL_PARSE", resolution_status: "RESOLVED", statement_id: "s1" },
		], []);

		const result = discoverTransitiveDownstreamCandidates({ factsRoot: root, outputDir: join(root, "out"), seeds: [], allWriteAssets: true });
		expect(result.manifest).toMatchObject({ projection_type: "TRANSITIVE_DOWNSTREAM_CANDIDATE_INVENTORY", candidate_count: 3, max_hops: 2, direct_candidate_count: 2 });
		const modelCandidates = result.candidates.filter((candidate) => candidate.seed_asset.configured_name === "model_a");
		expect(modelCandidates.map((candidate) => candidate.candidate_id)).toEqual([
			"downstream:model_a:200:hop1",
			"downstream:model_a:300:hop2",
		]);
		expect(modelCandidates[1]!.path).toEqual([
			{ kind: "ASSET", configured_name: "model_a" },
			{ kind: "TASK", task_id: "200" },
			{ kind: "ASSET", configured_name: "downstream_a" },
			{ kind: "TASK", task_id: "300" },
		]);
		const range = collapseDownstreamRange(result.candidates);
		expect(range.filter((row) => row.seed_asset === "model_a")).toMatchObject([
			{ seed_asset: "model_a", downstream_asset: "downstream_a", min_hop: 1 },
			{ seed_asset: "model_a", downstream_asset: "downstream_b", min_hop: 2 },
		]);
	});
});
