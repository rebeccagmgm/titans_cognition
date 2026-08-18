import { describe, expect, it } from "vitest";
import { Schema, SqlSession } from "../src/index.js";
import { originsOf } from "../src/lineage/lineage.js";
import type { Expr, SelectExpr } from "../src/ir/ir.js";
import type { ColumnRef, PlanFacts, PlanRelation } from "../scripts/plans/plan-contract.js";
import { buildPlanFacts } from "../scripts/plans/plan-adapter.js";

const SCHEMA = new Schema({
	"demo.orders": { id: "int", customer_id: "int", amount: "int" },
	"demo.items": { order_id: "int", status: "string", value: "int", amount: "int" },
	"demo.customers": { id: "int" },
	"demo.customer_alias": { customer_id: "int" },
	"demo.source": { k: "int" },
});

function physicalKeys(refs: ColumnRef[]): Set<string> {
	return new Set(
		refs.flatMap((ref) => (ref.physical ?? []).map((origin) => `${origin.table}.${origin.column}`.toLowerCase())),
	);
}

function relationOf(plan: PlanFacts, id: string): PlanRelation {
	const relation = plan.relations.find((candidate) => candidate.id === id);
	if (!relation) throw new Error(`missing relation ${id}`);
	return relation;
}

function refsOf(relation: PlanRelation): ColumnRef[] {
	if (relation.type === "filter") return relation.predicate_columns;
	if (relation.type === "join") return relation.condition_columns;
	if (relation.type === "aggregate") return relation.group_by;
	throw new Error(`relation ${relation.id} is not a clause relation`);
}

function runParityCase(
	sql: string,
	relationId: string,
	expression: (body: SelectExpr) => Expr,
): { plan: PlanFacts; refs: ColumnRef[]; native: Set<string> } {
	const session = SqlSession.create(sql, "databricks", { schema: SCHEMA });
	const statement = session.doc.statements[0]!;
	const root = statement.scopes.root;
	if (root.body.kind !== "select") throw new Error("expected a SELECT root");

	const plan = buildPlanFacts(statement, sql, {
		dialect: "databricks",
		schema: SCHEMA,
		include_expression_dependencies: true,
	});
	const refs = refsOf(relationOf(plan, relationId));
	const native = new Set(
		originsOf(expression(root.body), root, SCHEMA).map((origin) =>
			`${origin.table.join(".")}.${origin.column}`.toLowerCase(),
		),
	);
	for (const origin of native)
		expect(physicalKeys(refs), `${relationId} missing native origin ${origin}`).toContain(origin);
	return { plan, refs, native };
}

describe("plan adapter native lineage parity for clause inputs", () => {
	it("includes native origins for a correlated WHERE EXISTS output", () => {
		const { plan, refs, native } = runParityCase(
			"SELECT t.id FROM demo.orders t WHERE EXISTS (SELECT i.value FROM demo.items i WHERE i.order_id = t.id AND i.status = 'A')",
			"root.filter",
			(body) => body.where!,
		);

		expect(native).toEqual(new Set(["demo.items.value"]));
		expect(refs.map((ref) => ref.name)).toEqual(["value"]);
		const childFilter = refsOf(relationOf(plan, "root.(child).filter"));
		expect(childFilter.map((ref) => ref.name)).toEqual(expect.arrayContaining(["order_id", "id", "status"]));
	});

	it("includes native origins for a correlated WHERE scalar subquery", () => {
		const { refs, native } = runParityCase(
			"SELECT t.id FROM demo.orders t WHERE t.amount > (SELECT max(i.amount) FROM demo.items i WHERE i.order_id = t.id)",
			"root.filter",
			(body) => body.where!,
		);

		expect(native).toEqual(new Set(["demo.orders.amount", "demo.items.amount"]));
		expect(refs).toEqual(expect.arrayContaining([expect.objectContaining({ name: "amount", qualifier: "t" })]));
	});

	it("includes native origins for a nested scalar subquery in JOIN ON", () => {
		const { refs, native } = runParityCase(
			"SELECT o.id FROM demo.orders o JOIN demo.customers c ON o.customer_id = (SELECT max(x.customer_id) FROM demo.customer_alias x WHERE x.customer_id = c.id)",
			"root.join.1",
			(body) => body.joins![0]!.on!,
		);

		expect(native).toEqual(new Set(["demo.orders.customer_id", "demo.customer_alias.customer_id"]));
		expect(refs).toEqual(
			expect.arrayContaining([expect.objectContaining({ name: "customer_id", qualifier: "o" })]),
		);
	});

	it("keeps native origins for a GROUP BY expression across a derived scope", () => {
		const { refs, native } = runParityCase(
			"SELECT coalesce(x.k, 0) AS bucket, count(*) AS n FROM (SELECT t.k FROM demo.source t) x GROUP BY coalesce(x.k, 0)",
			"root.aggregate",
			(body) => body.groupBy![0]!,
		);

		expect(native).toEqual(new Set(["demo.source.k"]));
		expect(refs).toEqual(expect.arrayContaining([expect.objectContaining({ name: "k", qualifier: "x" })]));
	});

	it("records a clause-scoped Unknown when native lineage fails", () => {
		let failNextLookup = true;
		const schema = {
			columnsFor: (parts: string[]) => {
				if (failNextLookup) {
					failNextLookup = false;
					throw new Error("synthetic clause native lineage failure");
				}
				return parts.join(".").toLowerCase() === "demo.items" ? [{ name: "value" }] : undefined;
			},
		};
		const sql = "SELECT t.id FROM demo.orders t WHERE EXISTS (SELECT i.value FROM demo.items i)";
		const session = SqlSession.create(sql, "databricks");
		const plan = buildPlanFacts(session.doc.statements[0]!, sql, {
			dialect: "databricks",
			schema,
			include_expression_dependencies: true,
		});

		expect(plan.unknowns).toEqual(
			expect.arrayContaining([
				expect.objectContaining({
					node_id: "root.filter",
					field: "native_lineage",
					reason: expect.stringContaining("synthetic clause native lineage failure"),
				}),
			]),
		);
	});
});
