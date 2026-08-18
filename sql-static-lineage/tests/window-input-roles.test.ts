import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, relative, resolve } from "node:path";
import { afterEach, describe, expect, it } from "vitest";

import { Schema, SqlSession } from "../src/index.js";
import { processProfile } from "../scripts/machine-facts/machine-facts.js";
import { buildPlanFacts } from "../scripts/plans/plan-adapter.js";

const workspace = resolve(import.meta.dirname, "../..");
const roots: string[] = [];

afterEach(() => {
	for (const root of roots.splice(0)) rmSync(root, { recursive: true, force: true });
});

const schema = new Schema({
	"demo.events": {
		key_instrument_id: "int",
		calc_date: "date",
		amount: "double",
		fallback_amount: "double",
	},
});

function expressionOf(sql: string, inputSchema = schema): any {
	const session = SqlSession.create(sql, "databricks", { schema: inputSchema });
	const plan = buildPlanFacts(session.doc.statements[0]!, sql, {
		dialect: "databricks",
		schema: inputSchema,
		include_expression_dependencies: true,
	});
	const project = plan.relations.find((relation) => relation.id === "root.project");
	if (!project || project.type !== "project") throw new Error("root project relation missing");
	return { expression: project.expressions[0], plan };
}

function bindingsOf(expression: any): any[] {
	return expression.window_spec?.input_bindings ?? [];
}

describe("window input roles", () => {
	it("retains row_number partition and order roles with physical origins", () => {
		const { expression } = expressionOf(
			"SELECT row_number() OVER (PARTITION BY key_instrument_id ORDER BY calc_date DESC NULLS LAST) AS rn FROM demo.events",
		);
		expect(bindingsOf(expression)).toEqual([
			expect.objectContaining({ role: "WINDOW_PARTITION", ordinal: 0, expression_text: "key_instrument_id" }),
			expect.objectContaining({
				role: "WINDOW_ORDER",
				ordinal: 0,
				expression_text: "calc_date",
				direction: "DESC",
				nulls: "LAST",
			}),
		]);
		expect(bindingsOf(expression)[0].input_columns).toEqual(
			expect.arrayContaining([
				expect.objectContaining({ resolution: "PHYSICAL", physical: [{ table: "demo.events", column: "key_instrument_id" }] }),
			]),
		);
		expect(expression.input_columns).toEqual(
			expect.arrayContaining([
				expect.objectContaining({ resolution: "PHYSICAL", physical: [{ table: "demo.events", column: "key_instrument_id" }] }),
				expect.objectContaining({ resolution: "PHYSICAL", physical: [{ table: "demo.events", column: "calc_date" }] }),
			]),
		);
	});

	it("separates a SUM value input from window inputs", () => {
		const { expression } = expressionOf(
			"SELECT sum(amount) OVER (PARTITION BY key_instrument_id ORDER BY calc_date DESC) AS total FROM demo.events",
		);
		expect(bindingsOf(expression).map((binding) => binding.role)).toEqual([
			"VALUE",
			"WINDOW_PARTITION",
			"WINDOW_ORDER",
		]);
		expect(bindingsOf(expression)[0]).toMatchObject({
			role: "VALUE",
			ordinal: 0,
			expression_text: "amount",
		});
		expect(bindingsOf(expression)[0].input_columns).toEqual(
			expect.arrayContaining([
				expect.objectContaining({ resolution: "PHYSICAL", physical: [{ table: "demo.events", column: "amount" }] }),
			]),
		);
	});

	it("allows one physical field to carry multiple window roles", () => {
		const { expression } = expressionOf(
			"SELECT sum(amount) OVER (PARTITION BY amount ORDER BY amount DESC) AS total FROM demo.events",
		);
		const amountBindings = bindingsOf(expression).filter((binding) =>
			binding.input_columns.some((input: any) =>
				input.physical?.some((origin: any) => origin.table === "demo.events" && origin.column === "amount"),
			),
		);
		expect(amountBindings.map((binding) => [binding.role, binding.ordinal])).toEqual([
			["VALUE", 0],
			["WINDOW_PARTITION", 0],
			["WINDOW_ORDER", 0],
		]);
	});

	it("preserves complex partition/order expressions and their resolved inputs", () => {
		const { expression } = expressionOf(
			"SELECT row_number() OVER (PARTITION BY coalesce(key_instrument_id, amount) ORDER BY coalesce(calc_date, fallback_amount) DESC NULLS FIRST) AS rn FROM demo.events",
		);
		const bindings = bindingsOf(expression);
		expect(bindings[0]).toMatchObject({
			role: "WINDOW_PARTITION",
			expression_text: "coalesce(key_instrument_id, amount)",
		});
		expect(bindings[0].input_columns.flatMap((input: any) => input.physical ?? []).map((field: any) => field.column)).toEqual([
			"key_instrument_id",
			"amount",
		]);
		expect(bindings[1]).toMatchObject({
			role: "WINDOW_ORDER",
			expression_text: "coalesce(calc_date, fallback_amount)",
			direction: "DESC",
			nulls: "FIRST",
		});
		expect(bindings[1].input_columns.flatMap((input: any) => input.physical ?? []).map((field: any) => field.column)).toEqual([
			"calc_date",
			"fallback_amount",
		]);
		expect(bindings[1].span.end).toBeGreaterThan(bindings[1].span.start);
	});

	it("retains ASC/DESC and distinguishes explicit NULLS from UNSPECIFIED", () => {
		const { expression } = expressionOf(
			"SELECT row_number() OVER (ORDER BY calc_date ASC NULLS FIRST, amount DESC) AS rn FROM demo.events",
		);
		expect(bindingsOf(expression).map((binding) => ({ direction: binding.direction, nulls: binding.nulls }))).toEqual([
			{ direction: "ASC", nulls: "FIRST" },
			{ direction: "DESC", nulls: "UNSPECIFIED" },
		]);
	});

	it("keeps an empty OVER() as an expression-level window spec", () => {
		const { expression } = expressionOf("SELECT row_number() OVER () AS rn FROM demo.events");
		expect(expression.window).toBe(true);
		expect(expression.window_spec).toMatchObject({ input_bindings: [] });
		expect(expression.window_spec.source_span.end).toBeGreaterThan(expression.window_spec.source_span.start);
	});

	it("keeps unresolved window fields as Unknown instead of dropping them", () => {
		const { expression, plan } = expressionOf(
			"SELECT row_number() OVER (PARTITION BY missing_key ORDER BY calc_date) AS rn FROM demo.events e JOIN demo.other o ON e.key_instrument_id = o.key_instrument_id",
			new Schema({
				"demo.events": { key_instrument_id: "int", calc_date: "date" },
				"demo.other": { key_instrument_id: "int", calc_date: "date" },
			}),
		);
		const partition = bindingsOf(expression).find((binding) => binding.role === "WINDOW_PARTITION");
		expect(partition.input_columns).toEqual([
			expect.objectContaining({ name: "missing_key", resolution: "UNRESOLVED" }),
		]);
		expect(plan.unknowns).toEqual(
			expect.arrayContaining([
				expect.objectContaining({ node_id: "root.project", field: "physical", reason: expect.stringContaining("missing_key") }),
			]),
		);
	});

	it("publishes window roles in Machine Facts without changing input_fields", () => {
		const root = mkdtempSync(join(tmpdir(), "titans-window-facts-"));
		roots.push(root);
		const sqlPath = join(root, "task.sql");
		const schemaPath = join(root, "schema.json");
		const profilePath = join(root, "profile.json");
		writeFileSync(
			sqlPath,
			"SELECT sum(amount) OVER (PARTITION BY key_instrument_id ORDER BY calc_date DESC NULLS LAST) AS total FROM demo.events;\n",
			"utf8",
		);
		writeFileSync(
			schemaPath,
			JSON.stringify({
				records: [{
					qualified_name: "demo.events",
					status: "SUCCESS",
					columns: [
						{ name: "key_instrument_id", partition: false },
						{ name: "calc_date", partition: false },
						{ name: "amount", partition: false },
					],
				}],
			}),
			"utf8",
		);
		writeFileSync(
			profilePath,
			JSON.stringify({
				schema_version: "test",
				dialect: "databricks",
				schema_evidence: relative(workspace, schemaPath).replace(/\\/g, "/"),
				tasks: [{ task_id: "window-task", sql_snapshot: relative(workspace, sqlPath).replace(/\\/g, "/") }],
			}),
			"utf8",
		);

		const output = relative(workspace, join(root, "facts")).replace(/\\/g, "/");
		const result = processProfile(relative(workspace, profilePath).replace(/\\/g, "/"), output, "window-source");
		expect(result.tasks[0]?.state).toBe("SUCCESS");
		const bundle = join(root, "facts", "registry", "tasks", "window-task", "bundle");
		const field = JSON.parse(readFileSync(join(bundle, "field-expression-nodes.jsonl"), "utf8").trim());
		expect(field.input_fields.map((item: any) => item.column)).toEqual(["amount", "key_instrument_id", "calc_date"]);
		expect(field.window_spec.input_bindings).toEqual(
			expect.arrayContaining([
				expect.objectContaining({ role: "VALUE", ordinal: 0 }),
				expect.objectContaining({ role: "WINDOW_PARTITION", ordinal: 0 }),
				expect.objectContaining({ role: "WINDOW_ORDER", ordinal: 0, direction: "DESC", nulls: "LAST" }),
			]),
		);
	});
});
