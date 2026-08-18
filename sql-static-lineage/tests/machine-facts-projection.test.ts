import { appendFileSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, relative, resolve } from "node:path";
import { afterEach, describe, expect, it } from "vitest";

import { assembleMinimalCausalPaths } from "../scripts/query/minimal-causal-paths-from-machine-facts.ts";
import { loadMachineFactsGraphInputs } from "../scripts/query/machine-facts-graph-projection.ts";
import { processProfile } from "../scripts/machine-facts/machine-facts.ts";

const workspace = resolve(import.meta.dirname, "../..");
const roots: string[] = [];

afterEach(() => {
	for (const root of roots.splice(0)) rmSync(root, { recursive: true, force: true });
});

describe("machine facts projection consumer", () => {
	it("assembles configured causal paths from task bundles without the indicator graph JSONL", () => {
		const root = mkdtempSync(join(tmpdir(), "titans-machine-facts-projection-"));
		roots.push(root);
		const factsRoot = join(root, "machine-facts");
		const profilePath = "cases/indicator-journey-rgstcomp-mthend/processing-graph-profile.json";
		processProfile(profilePath, relative(workspace, factsRoot).replace(/\\/g, "/"), "gfhive-test");

		const inputs = loadMachineFactsGraphInputs(resolve(workspace, profilePath), factsRoot);
		const result = assembleMinimalCausalPaths(inputs);

		expect(result.status).toBe("PASS");
		expect(result.paths.map((path) => [path.pathId, path.status])).toEqual([
			["value-flow-option-dyna-nom-prin", "COMPLETE"],
			["rowset-control-skip-report", "COMPLETE"],
		]);
		expect(
			readFileSync(join(factsRoot, "registry", "tasks", "162610", "bundle", "manifest.json"), "utf8"),
		).toContain("machine-facts-writer");

		appendFileSync(
			join(factsRoot, "registry", "tasks", "162610", "bundle", "field-expression-nodes.jsonl"),
			'{"tampered":true}\n',
			"utf8",
		);
		expect(() => loadMachineFactsGraphInputs(resolve(workspace, profilePath), factsRoot)).toThrow(
			/invalid Machine Facts Bundle 162610/,
		);
	});

	it("rejects a profile whose SQL snapshot no longer matches the current Bundle", () => {
		const root = mkdtempSync(join(tmpdir(), "titans-machine-facts-projection-sql-drift-"));
		roots.push(root);
		const factsRoot = join(root, "machine-facts");
		const profilePath = resolve(workspace, "cases/indicator-journey-rgstcomp-mthend/processing-graph-profile.json");
		processProfile(profilePath, factsRoot, "gfhive-test");
		const drifted = JSON.parse(readFileSync(profilePath, "utf8")) as { tasks: Array<{ sql_snapshot: string }> };
		drifted.tasks[0]!.sql_snapshot = drifted.tasks[1]!.sql_snapshot;
		const driftedPath = join(root, "drifted-profile.json");
		writeFileSync(driftedPath, JSON.stringify(drifted), "utf8");

		expect(() => loadMachineFactsGraphInputs(driftedPath, factsRoot)).toThrow(
			/SQL snapshot hash mismatch for task 162610/,
		);
	});

	it("does not report COMPLETE when the producer expression is unresolved", () => {
		const root = mkdtempSync(join(tmpdir(), "titans-machine-facts-projection-producer-gap-"));
		roots.push(root);
		const factsRoot = join(root, "machine-facts");
		const profilePath = resolve(workspace, "cases/indicator-journey-rgstcomp-mthend/processing-graph-profile.json");
		processProfile(profilePath, factsRoot, "gfhive-test");
		const inputs = loadMachineFactsGraphInputs(profilePath, factsRoot);
		const producer = inputs.fieldExpressions.find((field) => field.task_id === "86840" && String(field.output).toLowerCase() === "dyna_nom_prin");
		expect(producer).toBeDefined();
		producer!.input_dependency_status = "UNRESOLVED";
		producer!.expression.input_dependency_status = "UNRESOLVED";
		producer!.expression.input_columns = producer!.expression.input_columns.map((input: Record<string, unknown>) => ({
			...input,
			resolution: "UNRESOLVED",
			physical: null,
		}));

		const result = assembleMinimalCausalPaths(inputs);
		const valueFlow = result.paths.find((path) => path.pathId === "value-flow-option-dyna-nom-prin");
		expect(valueFlow?.status).toBe("PARTIAL");
		expect(valueFlow?.gaps).toContain("producer expression input dependency status is UNRESOLVED");
		expect(result.status).toBe("PARTIAL");
	});
});
