import { describe, expect, it } from "vitest";
import { Schema, SqlSession } from "../src/index.js";
import { buildPlanFacts } from "../scripts/plans/plan-adapter.ts";

describe("plan adapter star expansion", () => {
	it("preserves native physical origins through a nested scalar subquery", () => {
		const sql =
			"SELECT x.y AS result FROM (SELECT (SELECT l.value FROM demo.lookup l WHERE l.id = t.id) AS y FROM demo.base t) x";
		const schema = new Schema({
			"demo.base": { id: "int" },
			"demo.lookup": { id: "int", value: "int" },
		});
		const session = SqlSession.create(sql, "databricks", { schema });

		const plan = buildPlanFacts(session.doc.statements[0]!, sql, {
			dialect: "databricks",
			schema,
			include_expression_dependencies: true,
		});

		const rootProject = plan.relations.find(
			(relation) => relation.id === "root.project" && relation.type === "project",
		);
		if (rootProject?.type !== "project") throw new Error("root project relation missing");
		expect(rootProject.expressions[0]?.input_columns).toEqual(
			expect.arrayContaining([
				expect.objectContaining({
					resolution: "PHYSICAL",
					physical: [{ table: "demo.lookup", column: "value" }],
				}),
			]),
		);
	});

	it("keeps native origins from a scalar subquery inside a mixed expression", () => {
		const sql =
			"SELECT CASE WHEN t.flag = 1 THEN (SELECT l.value FROM demo.lookup l WHERE l.id = t.id) ELSE t.fallback END AS result FROM demo.base t";
		const schema = new Schema({
			"demo.base": { id: "int", flag: "int", fallback: "int" },
			"demo.lookup": { id: "int", value: "int" },
		});
		const session = SqlSession.create(sql, "databricks", { schema });

		const plan = buildPlanFacts(session.doc.statements[0]!, sql, {
			dialect: "databricks",
			schema,
			include_expression_dependencies: true,
		});

		const rootProject = plan.relations.find(
			(relation) => relation.id === "root.project" && relation.type === "project",
		);
		if (rootProject?.type !== "project") throw new Error("root project relation missing");
		const physical = rootProject.expressions[0]?.input_columns?.flatMap((input) => input.physical ?? []) ?? [];
		expect(physical).toEqual(
			expect.arrayContaining([
				{ table: "demo.base", column: "flag" },
				{ table: "demo.base", column: "fallback" },
				{ table: "demo.lookup", column: "value" },
			]),
		);
	});

	it("preserves native window partition and order origins", () => {
		const sql = "SELECT ROW_NUMBER() OVER (PARTITION BY t.k ORDER BY t.ts) AS rn FROM demo.events t";
		const schema = new Schema({
			"demo.events": { k: "int", ts: "timestamp" },
		});
		const session = SqlSession.create(sql, "databricks", { schema });

		const plan = buildPlanFacts(session.doc.statements[0]!, sql, {
			dialect: "databricks",
			schema,
			include_expression_dependencies: true,
		});

		const rootProject = plan.relations.find((relation) => relation.id === "root.project" && relation.type === "project");
		if (rootProject?.type !== "project") throw new Error("root project relation missing");
		const physical = rootProject.expressions[0]?.input_columns?.flatMap((input) => input.physical ?? []) ?? [];
		expect(physical).toEqual(
			expect.arrayContaining([
				{ table: "demo.events", column: "k" },
				{ table: "demo.events", column: "ts" },
			]),
		);
	});

	it("surfaces native lineage failures as plan unknowns", () => {
		const sql = "SELECT (SELECT l.value FROM demo.lookup l) AS result";
		let failNextSchemaLookup = true;
		const schema = {
			columnsFor: (parts: string[]) => {
				if (failNextSchemaLookup) {
					failNextSchemaLookup = false;
					throw new Error("synthetic native lineage failure");
				}
				return parts.join(".").toLowerCase() === "demo.lookup" ? [{ name: "value" }] : undefined;
			},
		};
		const session = SqlSession.create(sql, "databricks");

		const plan = buildPlanFacts(session.doc.statements[0]!, sql, {
			dialect: "databricks",
			schema,
			include_expression_dependencies: true,
		});

		expect(plan.unknowns).toEqual(
			expect.arrayContaining([
				expect.objectContaining({
					field: "native_lineage",
					reason: expect.stringContaining("synthetic native lineage failure"),
				}),
			]),
		);
	});

	it("keeps a set-operation subquery star unresolved instead of crashing", () => {
		const sql = "SELECT * FROM (SELECT 1 AS a UNION ALL SELECT 2 AS a) x";
		const session = SqlSession.create(sql, "databricks");

		const plan = buildPlanFacts(session.doc.statements[0]!, sql, {
			statement_index: 0,
			dialect: "databricks",
		});

		expect(plan.relations.length).toBeGreaterThan(0);
		const rootProject = plan.relations.find((relation) => relation.id === "root.project");
		expect(rootProject?.type).toBe("project");
		if (rootProject?.type !== "project") throw new Error("root project relation missing");
		expect(rootProject.expressions[0]?.output_name_status).toBe("STAR_EXPANSION");
		expect(rootProject.expressions[0]?.input_columns).toBeUndefined();
	});

	it("preserves lateral output columns as derived outputs", () => {
		const sql = "SELECT y.pos FROM demo.base t LATERAL VIEW posexplode(array(1)) y AS pos, val";
		const session = SqlSession.create(sql, "databricks");
		const plan = buildPlanFacts(session.doc.statements[0]!, sql, {
			dialect: "databricks",
			schema: {
				columnsFor: (parts: string[]) =>
					parts.join(".").toLowerCase() === "demo.base" ? [{ name: "id" }] : undefined,
			},
			include_expression_dependencies: true,
		});

		expect(plan.unknowns).toEqual([]);
		const rootProject = plan.relations.find(
			(relation) => relation.id === "root.project" && relation.type === "project",
		);
		if (rootProject?.type !== "project") throw new Error("root project relation missing");
		expect(rootProject.expressions[0]?.input_columns?.[0]).toMatchObject({
			name: "pos",
			qualifier: "y",
			resolution: "DERIVED_OUTPUT",
		});
	});

	it("propagates physical inputs through a lateral-derived subquery output", () => {
		const sql =
			"SELECT x.busi_date FROM (SELECT date_add(t.dt, y.pos) AS busi_date FROM demo.base t LATERAL VIEW posexplode(array(1)) y AS pos, val) x";
		const session = SqlSession.create(sql, "databricks");
		const plan = buildPlanFacts(session.doc.statements[0]!, sql, {
			dialect: "databricks",
			schema: {
				columnsFor: (parts: string[]) =>
					parts.join(".").toLowerCase() === "demo.base" ? [{ name: "dt" }] : undefined,
			},
			include_expression_dependencies: true,
		});

		expect(plan.unknowns).toEqual([]);
		const rootProject = plan.relations.find(
			(relation) => relation.id === "root.project" && relation.type === "project",
		);
		if (rootProject?.type !== "project") throw new Error("root project relation missing");
		expect(rootProject.expressions[0]?.input_columns).toMatchObject([
			{
				name: "busi_date",
				qualifier: "x",
				resolution: "PHYSICAL",
				physical: [{ table: "demo.base", column: "dt" }],
			},
		]);
	});

	it("propagates physical inputs through a computed lateral-derived output", () => {
		const sql =
			"SELECT c_sp.busi_date FROM (SELECT date_add(strt_date, pos) AS busi_date FROM (SELECT start_date AS strt_date FROM demo.source) x LATERAL VIEW posexplode(array(1)) y AS pos, val) c_sp";
		const session = SqlSession.create(sql, "databricks");
		const plan = buildPlanFacts(session.doc.statements[0]!, sql, {
			dialect: "databricks",
			schema: {
				columnsFor: (parts: string[]) =>
					parts.join(".").toLowerCase() === "demo.source" ? [{ name: "start_date" }] : undefined,
			},
			include_expression_dependencies: true,
		});

		const rootProject = plan.relations.find(
			(relation) => relation.id === "root.project" && relation.type === "project",
		);
		if (rootProject?.type !== "project") throw new Error("root project relation missing");
		expect(plan.unknowns).toEqual([]);
		expect(rootProject.expressions[0]?.input_columns).toMatchObject([
			{
				name: "busi_date",
				qualifier: "c_sp",
				resolution: "PHYSICAL",
				physical: [{ table: "demo.source", column: "start_date" }],
			},
		]);
	});

	it("does not promote a computed lateral-derived output without base schema evidence", () => {
		const sql =
			"SELECT c_sp.busi_date FROM (SELECT date_add(strt_date, pos) AS busi_date FROM (SELECT start_date AS strt_date FROM demo.source) x LATERAL VIEW posexplode(array(1)) y AS pos, val) c_sp";
		const session = SqlSession.create(sql, "databricks");
		const plan = buildPlanFacts(session.doc.statements[0]!, sql, {
			dialect: "databricks",
			schema: { columnsFor: () => undefined },
			include_expression_dependencies: true,
		});

		const rootProject = plan.relations.find(
			(relation) => relation.id === "root.project" && relation.type === "project",
		);
		if (rootProject?.type !== "project") throw new Error("root project relation missing");
		expect(rootProject.expressions[0]?.input_columns?.[0]?.resolution).not.toBe("PHYSICAL");
	});

	it("resolves unqualified outputs from a set-operation derived table", () => {
		const sql =
			"SELECT rec_id FROM (SELECT concat('a', id) AS rec_id FROM demo.a UNION ALL SELECT concat('b', id) AS rec_id FROM demo.b) casttable";
		const session = SqlSession.create(sql, "databricks");
		const schema = {
			columnsFor: (parts: string[]) => {
				const table = parts.join(".").toLowerCase();
				return table === "demo.a" || table === "demo.b" ? [{ name: "id" }] : undefined;
			},
		};
		const plan = buildPlanFacts(session.doc.statements[0]!, sql, {
			dialect: "databricks",
			schema,
			include_expression_dependencies: true,
		});

		expect(plan.unknowns).toEqual([]);
		const rootProject = plan.relations.find(
			(relation) => relation.id === "root.project" && relation.type === "project",
		);
		if (rootProject?.type !== "project") throw new Error("root project relation missing");
		expect(rootProject.expressions[0]?.input_columns?.[0]).toMatchObject({
			name: "rec_id",
			resolution: "PHYSICAL",
			physical: [
				{ table: "demo.a", column: "id" },
				{ table: "demo.b", column: "id" },
			],
		});
	});

	it("keeps simple-case inputs and inputless computed outputs across set operations", () => {
		const sql =
			"SELECT label, generated FROM (SELECT CASE kind WHEN 'a' THEN 'A' ELSE 'B' END AS label, from_unixtime(unix_timestamp()) AS generated FROM demo.a UNION ALL SELECT CASE kind WHEN 'b' THEN 'B' ELSE 'A' END AS label, from_unixtime(unix_timestamp()) AS generated FROM demo.b) x";
		const session = SqlSession.create(sql, "databricks");
		const schema = {
			columnsFor: (parts: string[]) => {
				const table = parts.join(".").toLowerCase();
				return table === "demo.a" || table === "demo.b" ? [{ name: "kind" }] : undefined;
			},
		};
		const plan = buildPlanFacts(session.doc.statements[0]!, sql, {
			dialect: "databricks",
			schema,
			include_expression_dependencies: true,
		});

		expect(plan.unknowns).toEqual([]);
		const rootProject = plan.relations.find(
			(relation) => relation.id === "root.project" && relation.type === "project",
		);
		if (rootProject?.type !== "project") throw new Error("root project relation missing");
		expect(rootProject.expressions[0]?.input_columns).toMatchObject([
			{
				name: "label",
				resolution: "PHYSICAL",
				physical: [
					{ table: "demo.a", column: "kind" },
					{ table: "demo.b", column: "kind" },
				],
			},
		]);
		expect(rootProject.expressions[1]?.input_columns).toMatchObject([
			{ name: "generated", resolution: "DERIVED_OUTPUT" },
		]);
	});

	it("propagates physical inputs through a CTE output boundary", () => {
		const sql = "WITH base AS (SELECT id AS record_id FROM demo.base) SELECT record_id FROM base";
		const session = SqlSession.create(sql, "databricks");
		const plan = buildPlanFacts(session.doc.statements[0]!, sql, {
			dialect: "databricks",
			schema: {
				columnsFor: (parts: string[]) =>
					parts.join(".").toLowerCase() === "demo.base" ? [{ name: "id" }] : undefined,
			},
			include_expression_dependencies: true,
		});

		expect(plan.unknowns).toEqual([]);
		const rootProject = plan.relations.find(
			(relation) => relation.id === "root.project" && relation.type === "project",
		);
		if (rootProject?.type !== "project") throw new Error("root project relation missing");
		expect(rootProject.expressions[0]?.input_columns).toMatchObject([
			{ name: "record_id", resolution: "PHYSICAL", physical: [{ table: "demo.base", column: "id" }] },
		]);
	});

	it("keeps mixed physical and SQL-candidate branches across a set operation", () => {
		const sql = "SELECT book FROM (SELECT book FROM demo.physical UNION ALL SELECT book FROM demo.unverified) x";
		const session = SqlSession.create(sql, "databricks");
		const plan = buildPlanFacts(session.doc.statements[0]!, sql, {
			dialect: "databricks",
			schema: {
				columnsFor: (parts: string[]) =>
					parts.join(".").toLowerCase() === "demo.physical" ? [{ name: "book" }] : undefined,
			},
			include_expression_dependencies: true,
		});

		expect(plan.unknowns).toEqual([]);
		const rootProject = plan.relations.find(
			(relation) => relation.id === "root.project" && relation.type === "project",
		);
		if (rootProject?.type !== "project") throw new Error("root project relation missing");
		expect(rootProject.expressions[0]?.input_columns?.[0]).toMatchObject({
			name: "book",
			resolution: "SQL_CANDIDATE",
			sql_candidate: [
				{ table: "demo.physical", column: "book" },
				{ table: "demo.unverified", column: "book" },
			],
		});
	});

	it("propagates star outputs through a nested set-operation subquery", () => {
		const sql = "SELECT id FROM (SELECT * FROM (SELECT id FROM demo.a UNION ALL SELECT id FROM demo.b) x) y";
		const session = SqlSession.create(sql, "databricks");
		const schema = {
			columnsFor: (parts: string[]) => {
				const table = parts.join(".").toLowerCase();
				return table === "demo.a" || table === "demo.b" ? [{ name: "id" }] : undefined;
			},
		};
		const plan = buildPlanFacts(session.doc.statements[0]!, sql, {
			dialect: "databricks",
			schema,
			include_expression_dependencies: true,
		});

		expect(plan.unknowns).toEqual([]);
		const rootProject = plan.relations.find(
			(relation) => relation.id === "root.project" && relation.type === "project",
		);
		if (rootProject?.type !== "project") throw new Error("root project relation missing");
		expect(rootProject.expressions[0]?.input_columns?.[0]).toMatchObject({
			name: "id",
			resolution: "PHYSICAL",
			physical: [
				{ table: "demo.a", column: "id" },
				{ table: "demo.b", column: "id" },
			],
		});
	});
});
