import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const root = resolve(import.meta.dirname, "../../..");
const output = resolve(root, "output/indicator-processing-graph-rgstcomp-mthend");

function readJson(name: string): any {
	return JSON.parse(readFileSync(resolve(output, name), "utf8"));
}

function readJsonl(name: string): any[] {
	const text = readFileSync(resolve(output, name), "utf8").trim();
	return text ? text.split(/\r?\n/).map((line) => JSON.parse(line)) : [];
}

let passed = 0;
let failed = 0;
function check(name: string, ok: boolean): void {
	if (ok) passed += 1;
	else failed += 1;
	console.log(`${ok ? "OK" : "FAIL"} ${name}`);
}

const manifest = readJson("manifest.json");
const sources = readJsonl("source_artifacts.jsonl");
const statements = readJsonl("statements.jsonl");
const relations = readJsonl("relation_nodes.jsonl");
const fields = readJsonl("field_expression_nodes.jsonl");
const edges = readJsonl("edges.jsonl");
const unknowns = readJsonl("unknowns.jsonl");

check("6 source SQL artifacts", sources.length === 6);
check("all 12 SQL statements retained", statements.length === 12);
check(
	"all source captures hash-verified",
	sources.every((x) => x.capture_status === "SUCCESS" && /^[a-f0-9]{64}$/.test(x.content_sha256)),
);
check("relation ids unique", new Set(relations.map((x) => x.node_id)).size === relations.length);
check("field expression ids unique", new Set(fields.map((x) => x.node_id)).size === fields.length);
check(
	"all relation expressions untruncated",
	relations.every((x) => !JSON.stringify(x.relation).includes("…")),
);
check(
	"all field expressions untruncated",
	fields.every((x) => !x.expression.expr_text.includes("…")),
);
check(
	"all direct field spans round-trip and star fields retain expansion provenance",
	fields.every((x) =>
		x.expression.star_expansion === true
			? x.span_roundtrip === "NOT_APPLICABLE_SCHEMA_EXPANSION" && x.expansion_provenance === "SZDATA_TABLE_DDL"
			: x.span_roundtrip === "PASS",
	),
);
check(
	"all plan unknowns retained",
	unknowns.filter((x) => x.unknown_type === "PLAN_UNKNOWN").length === manifest.counts.plan_unknowns,
);
check(
	"all syntax diagnostics retained",
	unknowns.filter((x) => x.unknown_type === "SYNTAX_DIAGNOSTIC").length === manifest.counts.syntax_diagnostics,
);
check(
	"source syntax counts reconcile",
	sources.reduce((sum, x) => sum + x.syntax_error_count, 0) === manifest.counts.syntax_diagnostics,
);
check(
	"statement syntax counts reconcile",
	statements.reduce((sum, x) => sum + x.syntax_error_count, 0) === manifest.counts.syntax_diagnostics,
);
check("syntax diagnostic gate is explicit", typeof manifest.gates.no_syntax_diagnostics === "boolean");
check("SZData schema evidence is attached", manifest.inputs.schema_evidence?.source === "SZDATA_TABLE_DDL");
check("all required star tables have schema", manifest.gates.all_required_star_tables_have_schema === true);
check("schema-fed star expansion is recorded", manifest.counts.schema_expanded_fields > 0);
check("no star expansion remains unresolved", manifest.gates.no_unresolved_star_expansion === true);
check(
	"non-query output notices do not masquerade as unknowns",
	unknowns
		.filter((x) => x.reason_code === "NON_QUERY_OUTPUT_NOT_APPLICABLE")
		.every((x) => x.unknown_type === "NOT_APPLICABLE"),
);
check("all relation references resolve", manifest.gates.relation_references_resolve === true);
check("T98 has four producer tasks", manifest.coverage.t98_producer_tasks.length === 4);
check(
	"indicator reads both T98 and T05",
	["pdata_n.t98_otc_deri_comp_sale_info", "pdata_n.t05_otc_comp_rgst_sac_evt"].every((table) =>
		manifest.coverage.indicator_inputs.includes(table),
	),
);
check(
	"162610 retains join/filter/aggregate/setop",
	["join", "filter", "aggregate", "setop"].every((type) =>
		relations.some((x) => x.task_id === "162610" && x.relation.type === type),
	),
);
check(
	"162610 anonymous runtime expression is retained as derived output",
	fields.some(
		(x) =>
			x.task_id === "162610" &&
			x.expression.output_name_status === "ANONYMOUS_EXPRESSION" &&
			x.expression.expr_text.includes("from_unixtime"),
	),
);
check(
	"162610 derived UNION dimension references are classified",
	(() => {
		const join = relations.find(
			(x) => x.node_id === "task:162610:statement:1:relation:root.join.1",
		);
		const refs = join?.relation.condition_columns ?? [];
		return ["grp_type_code", "grp_val"].every((name) =>
			refs.some((ref: any) => ref.qualifier === "index" && ref.name === name && ref.resolution === "DERIVED_OUTPUT"),
		);
	})(),
);
check(
	"T98 counterparty UNION fields retain physical origins",
	(() =>
		["86840", "86841", "220650"].every((taskId) => {
			const join = relations.find(
				(x) => x.task_id === taskId && x.relation.type === "join" && x.relation.condition_expr?.includes("cp.client_id"),
			);
			const ref = join?.relation.condition_columns?.find((item: any) => item.qualifier === "cp" && item.name === "client_id");
			return ref?.resolution === "PHYSICAL" && Array.isArray(ref.physical) && ref.physical.length > 0;
		})
	)(),
);
check(
	"four branch tasks expose dyna_nom_prin expressions",
	["86840", "86841", "86842", "220650"].every((taskId) =>
		fields.some((x) => x.task_id === taskId && x.output.toLowerCase() === "dyna_nom_prin"),
	),
);
check(
	"task/table read-write edges exist",
	edges.some((x) => x.edge_type === "TASK_WRITES_DATASET") && edges.some((x) => x.edge_type === "TASK_READS_DATASET"),
);
check(
	"manifest does not claim business acceptance",
	manifest.boundaries.business_logic_correctness === "NOT_EVALUATED",
);

console.log(`--- ${passed} passed, ${failed} failed ---`);
process.exit(failed ? 1 : 0);
