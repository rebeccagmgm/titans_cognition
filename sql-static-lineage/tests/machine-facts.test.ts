import { mkdtempSync, readFileSync, renameSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, relative, resolve } from "node:path";
import { afterEach, describe, expect, it } from "vitest";

import { canonicalJson, datasetId, fieldId, sha256, safeSegment, stripVolatile } from "../scripts/machine-facts/machine-facts-contract.ts";
import { inputDependencyStatus, mergeSchemaEvidence, processProfile, rebuildIndex, relationNeedsMissingSchema } from "../scripts/machine-facts/machine-facts.ts";

const workspace = resolve(import.meta.dirname, "../..");
const roots: string[] = [];

afterEach(() => {
	for (const root of roots.splice(0)) rmSync(root, { recursive: true, force: true });
});

function fixture(): { root: string; profile: string; output: string; sql: string } {
	const root = mkdtempSync(join(tmpdir(), "titans-machine-facts-"));
	roots.push(root);
	const sql = join(root, "task.sql");
	const schema = join(root, "schema.json");
	const profile = join(root, "profile.json");
	writeFileSync(sql, "SELECT id FROM demo.source;\nINSERT OVERWRITE TABLE demo.target SELECT s.id FROM (SELECT id FROM demo.source) s WHERE s.id > 0;\n", "utf8");
	writeFileSync(schema, JSON.stringify({ records: [{ qualified_name: "demo.source", db: "demo", table: "source", status: "SUCCESS", guid: "guid-source", source: "SZDATA_TABLE_DDL", metadata_qualified_name: "DEMO.SOURCE", ddl_sha256: "ddl-source", required_for_star: true, table_status: "ONLINE", columns: [{ name: "id", partition: false }, { name: "dt", partition: true }] }, { qualified_name: "demo.target", db: "demo", table: "target", status: "SUCCESS", columns: [{ name: "id", partition: false }] }], captured_at: "volatile" }), "utf8");
	writeFileSync(profile, JSON.stringify({ schema_version: "test", dialect: "databricks", schema_evidence: relative(workspace, schema).replace(/\\/g, "/"), tasks: [{ task_id: "test-task", sql_snapshot: relative(workspace, sql).replace(/\\/g, "/"), writes: "demo.target" }] }), "utf8");
	return { root, profile: relative(workspace, profile).replace(/\\/g, "/"), output: relative(workspace, join(root, "machine-facts")).replace(/\\/g, "/"), sql };
}

describe("machine facts contract", () => {
	it("canonicalizes keys while preserving array order and removes volatile schema fields", () => {
		const left = canonicalJson({ b: 2, a: 1, items: ["z", "a"] });
		const right = canonicalJson({ items: ["z", "a"], a: 1, b: 2 });
		expect(left).toBe(right);
		expect(stripVolatile({ captured_at: "now", nested: { source_path: "x", keep: true } })).toEqual({ nested: { keep: true } });
		expect(sha256(left)).toHaveLength(64);
		expect(() => safeSegment("../bad", "task_id")).toThrow();
		expect(() => safeSegment("CON", "task_id")).toThrow();
		expect(() => safeSegment("name.", "task_id")).toThrow();
		expect(datasetId("source-a", "Demo.Source")).not.toBe(datasetId("source-b", "Demo.Source"));
	});

	it("merges persisted schema evidence deterministically without task-specific rules", () => {
		const merged = mergeSchemaEvidence([
			{ records: [
				{ qualified_name: "demo.source", status: "SUCCESS", columns: [{ name: "id" }] },
				{ qualified_name: "demo.missing", status: "NOT_EVALUABLE", columns: [] },
			] },
			{ records: [
				{ qualified_name: "DEMO.SOURCE", status: "SUCCESS", columns: [{ name: "id" }, { name: "dt" }], ddl: "CREATE TABLE demo.source" },
				{ qualified_name: "demo.extra", status: "SUCCESS", columns: [{ name: "key" }] },
			] },
		], "test-source");

		expect(merged.logical_source_id).toBe("test-source");
		expect(merged.records).toHaveLength(3);
		expect(merged.records.find((record: { qualified_name?: string }) => record.qualified_name?.toLowerCase() === "demo.source")).toMatchObject({
		status: "SUCCESS",
		columns: [{ name: "id" }, { name: "dt" }],
		});
	});

	it("creates one current bundle, reuses it, and replaces it when SQL changes", () => {
		const f = fixture();
		const first = processProfile(f.profile, f.output, "test-source");
		expect(first.tasks).toHaveLength(1);
		expect(first.tasks[0]?.status).toBe("CREATED");
		expect(first.index.count).toBe(1);
		const relation = readFileSync(join(f.root, "machine-facts", "registry", "tasks", "test-task", "bundle", "relation-nodes.jsonl"), "utf8");
		expect(relation).not.toContain("statement:sql:");
		const schemaRefs = readFileSync(join(f.root, "machine-facts", "registry", "tasks", "test-task", "bundle", "schema-refs.jsonl"), "utf8")
			.trim().split(/\r?\n/).map((line) => JSON.parse(line));
		const sourceRef = schemaRefs.find((record: { qualified_name?: string }) => record.qualified_name === "demo.source");
		expect(sourceRef).toMatchObject({ required_for_star: true, ddl_sha256: "ddl-source", source: "SZDATA_TABLE_DDL", metadata_qualified_name: "DEMO.SOURCE", partition_columns: ["dt"] });
		const manifestPath = join(f.root, "machine-facts", "registry", "tasks", "test-task", "bundle", "manifest.json");
		const firstManifest = JSON.parse(readFileSync(manifestPath, "utf8"));

		const replay = processProfile(f.profile, f.output, "test-source");
		expect(replay.tasks[0]?.status).toBe("REUSED");

		writeFileSync(f.sql, "INSERT OVERWRITE TABLE demo.target SELECT id + 1 AS id FROM demo.source;\n", "utf8");
		const replaced = processProfile(f.profile, f.output, "test-source");
		expect(replaced.tasks[0]?.status).toBe("REPLACED");
		const secondManifest = JSON.parse(readFileSync(manifestPath, "utf8"));
		expect(secondManifest.inputs.sql_sha256).not.toBe(firstManifest.inputs.sql_sha256);
		expect(rebuildIndex(join(f.root, "machine-facts")).count).toBe(1);
	});

	it("binds root SELECT expressions to an explicit INSERT target by target schema order", () => {
		const f = fixture();
		processProfile(f.profile, f.output, "test-source");
		const bundle = join(f.root, "machine-facts", "registry", "tasks", "test-task", "bundle");
		const bindings = readFileSync(join(bundle, "output-field-bindings.jsonl"), "utf8")
			.trim()
			.split(/\r?\n/)
			.filter(Boolean)
			.map((line) => JSON.parse(line));
		const manifest = JSON.parse(readFileSync(join(bundle, "manifest.json"), "utf8"));

		expect(bindings).toHaveLength(1);
		expect(bindings[0]).toMatchObject({
			task_id: "test-task",
			statement_id: "task:test-task:statement:1",
			target_dataset_id: datasetId("test-source", "demo.target"),
			target_field_id: fieldId("test-source", "demo.target", "id"),
			target_dataset: "demo.target",
			target_field: "id",
			source_ordinal: 0,
			target_ordinal: 0,
			binding_method: "TARGET_SCHEMA_POSITIONAL",
			binding_status: "RESOLVED",
			target_schema_status: "MATCH",
		});
		expect(manifest.counts.output_field_bindings).toBe(1);
		expect(manifest.outputs.some((output: { path?: string }) => output.path === "output-field-bindings.jsonl")).toBe(true);
	});

	it("uses a matching task-local CREATE schema while preserving physical target schema drift", () => {
		const f = fixture();
		const schemaPath = join(f.root, "schema.json");
		const schema = JSON.parse(readFileSync(schemaPath, "utf8"));
		const target = schema.records.find((record: { qualified_name?: string }) => record.qualified_name === "demo.target");
		target.columns.push({ name: "new_tail", partition: false });
		writeFileSync(schemaPath, JSON.stringify(schema), "utf8");
		writeFileSync(
			f.sql,
			"CREATE TABLE IF NOT EXISTS demo.target (id STRING);\nINSERT OVERWRITE TABLE demo.target SELECT id FROM demo.source;\n",
			"utf8",
		);

		processProfile(f.profile, f.output, "test-source");
		const bundle = join(f.root, "machine-facts", "registry", "tasks", "test-task", "bundle");
		const bindings = readFileSync(join(bundle, "output-field-bindings.jsonl"), "utf8")
			.trim()
			.split(/\r?\n/)
			.filter(Boolean)
			.map((line) => JSON.parse(line));
		const unknowns = readFileSync(join(bundle, "unknowns.jsonl"), "utf8")
			.trim()
			.split(/\r?\n/)
			.filter(Boolean)
			.map((line) => JSON.parse(line));

		expect(bindings).toHaveLength(1);
		expect(bindings[0]).toMatchObject({
			target_field: "id",
			binding_method: "SQL_CREATE_POSITIONAL",
			binding_status: "RESOLVED",
			target_schema_status: "DRIFT_EXTRA_TARGET_COLUMNS",
		});
		expect(unknowns).toContainEqual(
			expect.objectContaining({
				outcome_class: "UNKNOWN",
				reason_code: "TARGET_SCHEMA_DRIFT",
			}),
		);
	});

	it("does not guess positional output bindings when target schema and SELECT counts differ", () => {
		const f = fixture();
		const schemaPath = join(f.root, "schema.json");
		const schema = JSON.parse(readFileSync(schemaPath, "utf8"));
		const target = schema.records.find((record: { qualified_name?: string }) => record.qualified_name === "demo.target");
		target.columns.push({ name: "required_tail", partition: false });
		writeFileSync(schemaPath, JSON.stringify(schema), "utf8");
		writeFileSync(f.sql, "INSERT OVERWRITE TABLE demo.target SELECT id FROM demo.source;\n", "utf8");

		processProfile(f.profile, f.output, "test-source");
		const bundle = join(f.root, "machine-facts", "registry", "tasks", "test-task", "bundle");
		const bindingText = readFileSync(join(bundle, "output-field-bindings.jsonl"), "utf8").trim();
		const unknowns = readFileSync(join(bundle, "unknowns.jsonl"), "utf8")
			.trim()
			.split(/\r?\n/)
			.filter(Boolean)
			.map((line) => JSON.parse(line));

		expect(bindingText).toBe("");
		expect(unknowns).toContainEqual(
			expect.objectContaining({
				outcome_class: "NOT_EVALUABLE",
				reason_code: "OUTPUT_BINDING_NOT_PROVABLE",
			}),
		);
	});

	it("honors an explicit INSERT target column list instead of physical schema position", () => {
		const f = fixture();
		const schemaPath = join(f.root, "schema.json");
		const schema = JSON.parse(readFileSync(schemaPath, "utf8"));
		const source = schema.records.find((record: { qualified_name?: string }) => record.qualified_name === "demo.source");
		const target = schema.records.find((record: { qualified_name?: string }) => record.qualified_name === "demo.target");
		source.columns.unshift({ name: "amount", partition: false });
		target.columns = [
			{ name: "id", partition: false },
			{ name: "amount", partition: false },
			{ name: "unused_tail", partition: false },
		];
		writeFileSync(schemaPath, JSON.stringify(schema), "utf8");
		writeFileSync(
			f.sql,
			"INSERT OVERWRITE TABLE demo.target (amount, id) SELECT amount, id FROM demo.source;\n",
			"utf8",
		);

		processProfile(f.profile, f.output, "test-source");
		const bundle = join(f.root, "machine-facts", "registry", "tasks", "test-task", "bundle");
		const bindings = readFileSync(join(bundle, "output-field-bindings.jsonl"), "utf8")
			.trim()
			.split(/\r?\n/)
			.filter(Boolean)
			.map((line) => JSON.parse(line));

		expect(bindings).toHaveLength(2);
		expect(bindings.map((binding) => ({
			target: binding.target_field,
			sourceOrdinal: binding.source_ordinal,
			targetOrdinal: binding.target_ordinal,
			method: binding.binding_method,
			schema: binding.target_schema_status,
		}))).toEqual([
			{ target: "amount", sourceOrdinal: 0, targetOrdinal: 1, method: "EXPLICIT_TARGET_COLUMN_LIST", schema: "MATCH" },
			{ target: "id", sourceOrdinal: 1, targetOrdinal: 0, method: "EXPLICIT_TARGET_COLUMN_LIST", schema: "MATCH" },
		]);
	});

	it("keeps dynamic partition output mapping unresolved", () => {
		const f = fixture();
		const schemaPath = join(f.root, "schema.json");
		const schema = JSON.parse(readFileSync(schemaPath, "utf8"));
		const target = schema.records.find((record: { qualified_name?: string }) => record.qualified_name === "demo.target");
		target.columns.push({ name: "dt", partition: true });
		writeFileSync(schemaPath, JSON.stringify(schema), "utf8");
		writeFileSync(
			f.sql,
			"INSERT OVERWRITE TABLE demo.target PARTITION (dt) SELECT id, '2026-08-18' AS dt FROM demo.source;\n",
			"utf8",
		);

		processProfile(f.profile, f.output, "test-source");
		const bundle = join(f.root, "machine-facts", "registry", "tasks", "test-task", "bundle");
		expect(readFileSync(join(bundle, "output-field-bindings.jsonl"), "utf8").trim()).toBe("");
		const unknowns = readFileSync(join(bundle, "unknowns.jsonl"), "utf8")
			.trim()
			.split(/\r?\n/)
			.filter(Boolean)
			.map((line) => JSON.parse(line));
		expect(unknowns).toContainEqual(
			expect.objectContaining({
				outcome_class: "NOT_EVALUABLE",
				reason_code: "DYNAMIC_PARTITION_BINDING_NOT_PROVABLE",
			}),
		);
	});

	it("excludes failed status and corrupted current bundles from the index", () => {
		const f = fixture();
		processProfile(f.profile, f.output, "test-source");
		const taskRoot = join(f.root, "machine-facts", "registry", "tasks", "test-task");
		const statusPath = join(taskRoot, "analysis-status.json");
		const status = JSON.parse(readFileSync(statusPath, "utf8"));
		status.state = "FAILED";
		status.failure = { outcome_class: "FAILURE", reason_code: "TEST_FAILURE", message: "test" };
		writeFileSync(statusPath, JSON.stringify(status), "utf8");
		expect(rebuildIndex(join(f.root, "machine-facts")).count).toBe(0);

		processProfile(f.profile, f.output, "test-source");
		const statements = join(taskRoot, "bundle", "statements.jsonl");
		writeFileSync(statements, `${readFileSync(statements, "utf8")}corrupt\n`, "utf8");
		const result = rebuildIndex(join(f.root, "machine-facts"));
		expect(result.count).toBe(0);
		expect(result.failures.join(" ")).toContain("hash mismatch");
	});

	it("requires a logical source and rejects same-context output drift", () => {
		const f = fixture();
		const profileWithoutSource = JSON.parse(readFileSync(join(f.root, "profile.json"), "utf8"));
		const profilePath = join(f.root, "profile-without-source.json");
		writeFileSync(profilePath, JSON.stringify({ ...profileWithoutSource, logical_source_id: undefined }), "utf8");
		expect(() => processProfile(relative(workspace, profilePath).replace(/\\/g, "/"), f.output)).toThrow("logical_source_id is required");

		processProfile(f.profile, f.output, "test-source");
		const manifestPath = join(f.root, "machine-facts", "registry", "tasks", "test-task", "bundle", "manifest.json");
		const manifest = JSON.parse(readFileSync(manifestPath, "utf8"));
		manifest.counts.unknowns += 1;
		writeFileSync(manifestPath, JSON.stringify(manifest), "utf8");
		const result = processProfile(f.profile, f.output, "test-source");
		expect(result.tasks[0]?.status).toBe("FAILED");
		expect(result.tasks[0]?.failures[0]?.reason_code).toBe("NON_DETERMINISTIC_OUTPUT");
	});

	it("restores a valid recovery bundle before replay", () => {
		const f = fixture();
		processProfile(f.profile, f.output, "test-source");
		const taskRoot = join(f.root, "machine-facts", "registry", "tasks", "test-task");
		renameSync(join(taskRoot, "bundle"), join(taskRoot, ".recovery"));
		const result = processProfile(f.profile, f.output, "test-source");
		expect(result.tasks[0]?.status).toBe("REUSED");
	});

	it("excludes unsafe snapshots and mismatched status identities", () => {
		const f = fixture();
		processProfile(f.profile, f.output, "test-source");
		const taskRoot = join(f.root, "machine-facts", "registry", "tasks", "test-task");
		const manifestPath = join(taskRoot, "bundle", "manifest.json");
		const manifest = JSON.parse(readFileSync(manifestPath, "utf8"));
		manifest.inputs.sql_snapshot = "../../outside.sql";
		writeFileSync(manifestPath, JSON.stringify(manifest), "utf8");
		let result = rebuildIndex(join(f.root, "machine-facts"));
		expect(result.count).toBe(0);
		expect(result.failures.join(" ")).toContain("unsafe");

		processProfile(f.profile, f.output, "test-source");
		const statusPath = join(taskRoot, "analysis-status.json");
		const status = JSON.parse(readFileSync(statusPath, "utf8"));
		status.logical_source_id = "other-source";
		writeFileSync(statusPath, JSON.stringify(status), "utf8");
		result = rebuildIndex(join(f.root, "machine-facts"));
		expect(result.count).toBe(0);
		expect(result.failures.join(" ")).toContain("identity");
	});

	it("turns a corrupt status file into a typed recovery failure", () => {
		const f = fixture();
		processProfile(f.profile, f.output, "test-source");
		const statusPath = join(f.root, "machine-facts", "registry", "tasks", "test-task", "analysis-status.json");
		writeFileSync(statusPath, "{not-json", "utf8");
		const result = processProfile(f.profile, f.output, "test-source");
		expect(result.tasks[0]?.failures[0]?.reason_code).toBe("RECOVERY_REQUIRED");
		expect(JSON.parse(readFileSync(statusPath, "utf8")).state).toBe("FAILED");
	});

	it("isolates malformed status and manifest during index rebuild", () => {
		const f = fixture();
		processProfile(f.profile, f.output, "test-source");
		const taskRoot = join(f.root, "machine-facts", "registry", "tasks", "test-task");
		writeFileSync(join(taskRoot, "analysis-status.json"), "{broken", "utf8");
		let result = rebuildIndex(join(f.root, "machine-facts"));
		expect(result.count).toBe(0);
		expect(result.failures.join(" ")).toContain("invalid analysis-status");

		const f2 = fixture();
		processProfile(f2.profile, f2.output, "test-source");
		const taskRoot2 = join(f2.root, "machine-facts", "registry", "tasks", "test-task");
		writeFileSync(join(taskRoot2, "bundle", "manifest.json"), JSON.stringify({ outputs: "not-an-array" }), "utf8");
		result = rebuildIndex(join(f2.root, "machine-facts"));
		expect(result.count).toBe(0);
		expect(result.failures.join(" ")).toContain("structural");
	});

	it("rejects duplicate task identities before writing", () => {
		const f = fixture();
		const profile = JSON.parse(readFileSync(join(f.root, "profile.json"), "utf8"));
		profile.tasks.push(profile.tasks[0]);
		const duplicatePath = join(f.root, "duplicate-profile.json");
		writeFileSync(duplicatePath, JSON.stringify(profile), "utf8");
		expect(() => processProfile(relative(workspace, duplicatePath).replace(/\\/g, "/"), f.output, "test-source")).toThrow("task_id values must be unique");
	});

	it("preserves plan unknown classes without manufacturing field-binding unknowns", () => {
		const f = fixture();
		writeFileSync(
			f.sql,
			"CREATE TABLE IF NOT EXISTS demo.target (id STRING);\nINSERT OVERWRITE TABLE demo.target SELECT s.id, id AS ambiguous_id, from_unixtime(unix_timestamp()) AS loaded_at FROM demo.source s JOIN demo.target t ON s.id = t.id;\n",
			"utf8",
		);

		processProfile(f.profile, f.output, "test-source");
		const bundle = join(f.root, "machine-facts", "registry", "tasks", "test-task", "bundle");
		const unknowns = readFileSync(join(bundle, "unknowns.jsonl"), "utf8")
			.trim()
			.split(/\r?\n/)
			.filter(Boolean)
			.map((line) => JSON.parse(line));
		const expressions = readFileSync(join(bundle, "field-expression-nodes.jsonl"), "utf8")
			.trim()
			.split(/\r?\n/)
			.filter(Boolean)
			.map((line) => JSON.parse(line));
		const manifest = JSON.parse(readFileSync(join(bundle, "manifest.json"), "utf8"));

		expect(unknowns.some((item) => item.outcome_class === "NOT_APPLICABLE" && item.reason_code === "NON_QUERY_OUTPUT_NOT_APPLICABLE")).toBe(true);
		expect(unknowns.some((item) => item.reason_code === "PHYSICAL_FIELD_BINDING_UNRESOLVED")).toBe(false);
		expect(expressions.some((item) => item.input_dependency_status === "NO_PHYSICAL_INPUT")).toBe(true);
		expect(expressions.some((item) => item.input_dependency_status === "UNRESOLVED")).toBe(true);
		expect(manifest.method.adapter.name).toBe("machine-facts-writer");
		expect(manifest.method.plan_adapter.name).toBe("plan-adapter");
		expect(manifest.counts.unknowns_by_outcome.NOT_APPLICABLE).toBe(1);
		expect(Object.values(manifest.counts.unknowns_by_outcome as Record<string, number>).reduce((sum, value) => sum + value, 0)).toBe(manifest.counts.unknowns);
	});

	it("keeps mixed physical and unresolved dependencies explicitly partial", () => {
		expect(inputDependencyStatus({ input_columns: [
			{ name: "known_id", resolution: "PHYSICAL", physical: [{ table: "demo.source", column: "known_id" }] },
			{ name: "missing_id", resolution: "UNRESOLVED", physical: null },
		] })).toBe("PARTIAL");
		expect(inputDependencyStatus({ input_columns: [
			{ name: "known_id", resolution: "PHYSICAL", physical: [{ table: "demo.source", column: "known_id" }] },
			{ name: "derived_id", resolution: "DERIVED_OUTPUT", derived_from: "cte.id" },
		] })).toBe("PARTIAL");
	});

	it("detects missing schema evidence through relation inputs", () => {
		const relations = [
			{ id: "source", type: "read", table: "demo.source" },
			{ id: "missing", type: "read", table: "demo.missing" },
			{ id: "join", type: "join", left: "source", right: "missing" },
		];
		expect(relationNeedsMissingSchema("join", relations, new Set(["demo.source"]))).toBe(true);
		expect(relationNeedsMissingSchema("join", relations, new Set(["demo.source", "demo.missing"]))).toBe(false);
	});

	it("keeps qualified missing-schema columns as candidates", () => {
		const f = fixture();
		writeFileSync(f.sql, "INSERT OVERWRITE TABLE demo.target SELECT s.id FROM demo.source s JOIN demo.missing m ON s.id = m.id;\n", "utf8");
		processProfile(f.profile, f.output, "test-source");
		const bundle = join(f.root, "machine-facts", "registry", "tasks", "test-task", "bundle");
		const unknowns = readFileSync(join(bundle, "unknowns.jsonl"), "utf8")
			.trim()
			.split(/\r?\n/)
			.filter(Boolean)
			.map((line) => JSON.parse(line));
		expect(unknowns.some((item) => item.reason_code === "SCHEMA_BINDING_NOT_EVALUABLE")).toBe(false);
	});

	it("does not relabel followColumn parser unknowns as missing schema", () => {
		const f = fixture();
		writeFileSync(f.sql, "CREATE TABLE demo.target AS SELECT A.*, B.* FROM (SELECT id FROM demo.source) A FULL OUTER JOIN (SELECT id FROM demo.missing) B ON A.id = B.id;", "utf8");
		processProfile(f.profile, f.output, "test-source");
		const bundle = join(f.root, "machine-facts", "registry", "tasks", "test-task", "bundle");
		const unknowns = readFileSync(join(bundle, "unknowns.jsonl"), "utf8")
			.trim().split(/\r?\n/).filter(Boolean).map((line) => JSON.parse(line));

		expect(unknowns.filter((item) => item.reason_code === "SCHEMA_BINDING_NOT_EVALUABLE" && item.message.includes("followColumn 无来源"))).toHaveLength(0);
		expect(unknowns.filter((item) => item.reason_code === "PHYSICAL_FIELD_UNRESOLVED" && item.message.includes("followColumn 无来源"))).toHaveLength(0);
		expect(unknowns.some((item) => item.reason_code === "SCHEMA_BINDING_NOT_EVALUABLE" && item.message.includes("demo.missing"))).toBe(true);
	});

	it("passes nested schema namespaces to derived-table star resolution", () => {
		const f = fixture();
		writeFileSync(f.sql, "CREATE TABLE demo.target AS SELECT A.id FROM (SELECT id FROM demo.source) A;", "utf8");
		processProfile(f.profile, f.output, "test-source");
		const bundle = join(f.root, "machine-facts", "registry", "tasks", "test-task", "bundle");
		const unknowns = readFileSync(join(bundle, "unknowns.jsonl"), "utf8")
			.trim().split(/\r?\n/).filter(Boolean).map((line) => JSON.parse(line));

		expect(unknowns.filter((item) => item.reason_code === "PHYSICAL_FIELD_UNRESOLVED")).toHaveLength(0);
		expect(unknowns.filter((item) => item.reason_code === "PLAN_FACT_UNRESOLVED")).toHaveLength(0);
	});

	it("does not mark a non-query-only unknown as a partial parse", () => {
		const f = fixture();
		writeFileSync(f.sql, "CREATE TABLE demo.target (id STRING);", "utf8");
		processProfile(f.profile, f.output, "test-source");
		const bundle = join(f.root, "machine-facts", "registry", "tasks", "test-task", "bundle");
		const statements = readFileSync(join(bundle, "statements.jsonl"), "utf8")
			.trim().split(/\r?\n/).filter(Boolean).map((line) => JSON.parse(line));
		const unknowns = readFileSync(join(bundle, "unknowns.jsonl"), "utf8")
			.trim().split(/\r?\n/).filter(Boolean).map((line) => JSON.parse(line));

		expect(statements).toHaveLength(1);
		expect(statements[0].parse_status).toBe("SUCCESS");
		expect(unknowns).toHaveLength(1);
		expect(unknowns[0]).toMatchObject({ outcome_class: "NOT_APPLICABLE", reason_code: "NON_QUERY_OUTPUT_NOT_APPLICABLE" });
	});

	it("records syntax-only candidates when a single source schema is absent", () => {
		const f = fixture();
		const schemaPath = join(f.root, "schema.json");
		const schema = JSON.parse(readFileSync(schemaPath, "utf8"));
		schema.records = schema.records.filter((record: { qualified_name?: string }) => record.qualified_name !== "demo.source");
		writeFileSync(schemaPath, JSON.stringify(schema), "utf8");

		processProfile(f.profile, f.output, "test-source");
		const bundle = join(f.root, "machine-facts", "registry", "tasks", "test-task", "bundle");
		const expressions = readFileSync(join(bundle, "field-expression-nodes.jsonl"), "utf8")
			.trim()
			.split(/\r?\n/)
			.filter(Boolean)
			.map((line) => JSON.parse(line));
		const lineage = readFileSync(join(bundle, "column-lineage-edges.jsonl"), "utf8")
			.trim()
			.split(/\r?\n/)
			.filter(Boolean)
			.map((line) => JSON.parse(line));

		expect(expressions.some((item) => item.input_dependency_status === "SQL_CANDIDATE")).toBe(true);
		expect(expressions.some((item) => item.candidate_input_fields?.some((field: { binding_status?: string }) => field.binding_status === "UNVERIFIED_SCHEMA"))).toBe(true);
		expect(lineage.some((item) => item.resolution_status === "UNVERIFIED_SCHEMA" && item.method === "SQL_SINGLE_SOURCE_BINDING")).toBe(true);
		const unknowns = readFileSync(join(bundle, "unknowns.jsonl"), "utf8")
			.trim().split(/\r?\n/).filter(Boolean).map((line) => JSON.parse(line));
		expect(unknowns.some((item) => item.reason_code === "SCHEMA_BINDING_NOT_EVALUABLE")).toBe(false);
	});

	it("keeps missing-schema facts unevaluable for star expansion", () => {
		const f = fixture();
		const schemaPath = join(f.root, "schema.json");
		const schema = JSON.parse(readFileSync(schemaPath, "utf8"));
		schema.records = schema.records.filter((record: { qualified_name?: string }) => record.qualified_name !== "demo.source");
		writeFileSync(schemaPath, JSON.stringify(schema), "utf8");
		writeFileSync(f.sql, "INSERT OVERWRITE TABLE demo.target SELECT * FROM demo.source;\n", "utf8");

		processProfile(f.profile, f.output, "test-source");
		const bundle = join(f.root, "machine-facts", "registry", "tasks", "test-task", "bundle");
		const unknowns = readFileSync(join(bundle, "unknowns.jsonl"), "utf8")
			.trim().split(/\r?\n/).filter(Boolean).map((line) => JSON.parse(line));
		expect(unknowns.some((item) => item.outcome_class === "NOT_EVALUABLE" && item.reason_code === "SCHEMA_BINDING_NOT_EVALUABLE")).toBe(true);
	});

	it("treats scheduler date placeholders as reversible parser values", () => {
		const f = fixture();
		writeFileSync(
			f.sql,
			"SELECT '${yyyy-MM-dd}' AS busi_date, id FROM demo.trd_${yyyyMM}_h UNION ALL SELECT '${yyyy-MM-dd}' AS busi_date, id FROM demo.trd_${yyyyMM,-1M}_h;\n",
			"utf8",
		);

		processProfile(f.profile, f.output, "test-source");
		const bundle = join(f.root, "machine-facts", "registry", "tasks", "test-task", "bundle");
		const statements = readFileSync(join(bundle, "statements.jsonl"), "utf8")
			.trim().split(/\r?\n/).filter(Boolean).map((line) => JSON.parse(line));
		const relations = readFileSync(join(bundle, "relation-nodes.jsonl"), "utf8")
			.trim().split(/\r?\n/).filter(Boolean).map((line) => JSON.parse(line));
		const unknowns = readFileSync(join(bundle, "unknowns.jsonl"), "utf8")
			.trim().split(/\r?\n/).filter(Boolean).map((line) => JSON.parse(line));

		const nonEmptyStatements = statements.filter((item) => String(item.raw_sql).trim().length > 0);
		expect(nonEmptyStatements.length).toBeGreaterThan(0);
		expect(nonEmptyStatements.every((item) => item.parse_status === "SUCCESS")).toBe(true);
		expect(statements.map((item) => item.raw_sql).join("\n")).toContain("${yyyyMM,-1M}");
		expect(relations.some((item) => item.relation?.table === "demo.trd_${yyyyMM}_h")).toBe(true);
		expect(relations.some((item) => item.relation?.table === "demo.trd_${yyyyMM,-1M}_h")).toBe(true);
		expect(relations.some((item) => item.relation?.binding === "trd_${yyyyMM}_h")).toBe(true);
		expect(relations.some((item) => item.relation?.binding === "trd_${yyyyMM,-1M}_h")).toBe(true);
		expect(unknowns.some((item) => item.reason_code === "SYNTAX_DIAGNOSTIC")).toBe(false);
	});

	it("reuses the materialized 118141 Schema Evidence for star expansion", () => {
		const root = mkdtempSync(join(tmpdir(), "titans-machine-facts-118141-"));
		roots.push(root);
		const output = join(root, "machine-facts");
		const result = processProfile("sql-static-lineage/fixtures/machine-facts-independent-profile.json", output, "gfhive-test");
		expect(result.tasks[0]?.state).toBe("SUCCESS");
		const bundle = join(output, "registry", "tasks", "118141", "bundle");
		const manifest = JSON.parse(readFileSync(join(bundle, "manifest.json"), "utf8"));
		const expressions = readFileSync(join(bundle, "field-expression-nodes.jsonl"), "utf8")
			.trim()
			.split(/\r?\n/)
			.filter(Boolean)
			.map((line) => JSON.parse(line));

		expect(manifest.counts.schema_refs).toBe(3);
		expect(manifest.counts.column_lineage_edges).toBeGreaterThan(2);
		expect(expressions.some((item) => item.output_name_status === "STAR_EXPANSION" && item.input_dependency_status === "PHYSICAL")).toBe(true);
	});

	it("binds ordinary subquery outputs for the 86840 notional expressions", () => {
		const root = mkdtempSync(join(tmpdir(), "titans-machine-facts-86840-"));
		roots.push(root);
		const output = join(root, "machine-facts");
		processProfile("cases/indicator-journey-rgstcomp-mthend/processing-graph-profile.json", output, "gfhive-test");
		const bundle = join(output, "registry", "tasks", "86840", "bundle");
		const expressions = readFileSync(join(bundle, "field-expression-nodes.jsonl"), "utf8")
			.trim()
			.split(/\r?\n/)
			.filter(Boolean)
			.map((line) => JSON.parse(line));
		const targets = expressions.filter((item) => ["Init_Nom_Prin", "Dyna_Nom_Prin", "Absl_Nom_Prin"].includes(item.output_name));
		const outputBindings = readFileSync(join(bundle, "output-field-bindings.jsonl"), "utf8")
			.trim()
			.split(/\r?\n/)
			.filter(Boolean)
			.map((line) => JSON.parse(line));
		const unknowns = readFileSync(join(bundle, "unknowns.jsonl"), "utf8")
			.trim()
			.split(/\r?\n/)
			.filter(Boolean)
			.map((line) => JSON.parse(line));

		expect(targets).toHaveLength(3);
		for (const target of targets) {
			expect(target.input_dependency_status, target.output_name).toBe("PHYSICAL");
			expect(target.input_fields.length, target.output_name).toBeGreaterThan(0);
			expect(target.unresolved_input_columns, target.output_name).toHaveLength(0);
		}
		expect(outputBindings).toHaveLength(89);
		expect(outputBindings).toContainEqual(
			expect.objectContaining({
				expression_id: targets.find((target) => target.output_name === "Dyna_Nom_Prin")?.expression_id,
				target_dataset: "pdata_n.t98_otc_deri_comp_sale_info",
				target_field: "dyna_nom_prin",
				source_ordinal: 26,
				target_ordinal: 26,
				binding_method: "SQL_CREATE_POSITIONAL",
				binding_status: "RESOLVED",
				target_schema_status: "DRIFT_EXTRA_TARGET_COLUMNS",
			}),
		);
		expect(unknowns).toContainEqual(
			expect.objectContaining({ outcome_class: "UNKNOWN", reason_code: "TARGET_SCHEMA_DRIFT" }),
		);
	});
});
