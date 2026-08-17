// 118141 → Logical Plan Facts + Grain Inference
// 用 npx tsx scripts/plans/plan-118141.ts 运行 → 输出 output/118141/plan-facts-118141.json
// v1.1: 传入真实 schema (info/det/m), 条件列 physical 解析启用;
//       grain 传播 + fanout 模型 + 原文不截断
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { SqlSession } from "../../src/index.ts";
import { buildPlanFacts, inferGrain } from "./plan-adapter.ts";
import { schema118141 } from "./schema-118141.ts";

const sql = readFileSync(
	"e:/02_area/股衍数据-数据cookbook/titans-cognition/.evidence-cache/tasksql-118141-20260814.txt",
	"utf-8",
);
const s = SqlSession.create(sql, "databricks");
const cell = s.doc.statements[1];

const facts = buildPlanFacts(cell, sql, { statement_index: 1, schema: schema118141, dialect: "databricks" });
const grain = inferGrain(facts);

const doc = { plan: facts, grain_inference: grain };
mkdirSync("output/118141", { recursive: true });
writeFileSync("output/118141/plan-facts-118141.json", JSON.stringify(doc, null, 2), "utf8");

// ---- 摘要 ----
console.log(`节点总数: ${facts.relations.length}`);
console.log(`物理表 (${facts.physical_inputs.length}):`);
for (const t of facts.physical_inputs) console.log(`  - ${t}`);
console.log("\n节点清单:");
for (const r of facts.relations) {
	const src = r.source ? ` ← ${r.source}` : "";
	const extra =
		r.type === "read" ? ` (${(r as any).binding})` :
		r.type === "join" ? ` ${(r as any).join_type} ← ${(r as any).left} ⋈ ${(r as any).right}` :
		r.type === "filter" ? ` "${(r as any).predicate_display}"` :
		r.type === "aggregate" ? ` GROUP BY [${(r as any).group_by.map((c: any) => c.name).join(", ")}]` :
		r.type === "project" ? ` ${(r as any).output_columns ? `${(r as any).output_columns.length}列` : "star(unknown)"}` :
		r.type === "expand" ? ` ${(r as any).expand_kind}` : "";
	console.log(`  ${r.id} [${r.type}]${extra}${src}`);
}
console.log(`\nunknowns (${facts.unknowns.length}):`);
for (const u of facts.unknowns) console.log(`  - ${u.node_id} ${u.field}: ${u.reason}`);
console.log(`\ngrain_inference (${grain.length}):`);
for (const g of grain) {
	console.log(`  ${g.node_id}: grain=${JSON.stringify(g.grain_candidate)} cardinality=${g.cardinality} conf=${g.confidence}`);
	if (g.requires.length) console.log(`       requires: ${g.requires.join("; ")}`);
}
console.log("\n[已保存] plan-facts-118141.json");
