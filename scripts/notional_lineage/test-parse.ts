// 测试 sqllens 解析数综加工 SQL(insert into ... select + ${}模板变量)
// 用法: npx tsx scripts/notional_lineage/test-parse.ts
import { readFileSync } from "node:fs";
import { SqlSession, lineage } from "../../sqllens/src/index.ts";

const sql = readFileSync(
	"e:/02_area/股衍数据-数据cookbook/titans-cognition/output/titans-collection-20260815/data/downstream-tasks-sql/tasksql-103943-20260816114217.txt",
	"utf-8",
);
// 模板变量替换
const cleaned = sql.split("$" + "{").join("ZZ").replace(/ZZ[^}]*}/g, "'2026-01-01'");
const s = SqlSession.create(cleaned, "databricks");
console.log(`语句数: ${s.doc.statements.length}`);
s.doc.statements.forEach((cell, i) => {
	const text = cell.text.slice(0, 200).replace(/\s+/g, " ");
	console.log(`\n[${i}] ${text}...`);
});
// 对包含 SELECT 的语句尝试血缘
for (const cell of s.doc.statements) {
	const text = cell.text;
	if (!/select/i.test(text)) continue;
	const lin = lineage(cell.scopes, undefined);
	console.log(`\n=== 语句血缘(输出列=${lin.all.length}) ===");
	for (const c of lin.all.slice(0, 15)) {
		const srcs = c.origins.map((o: any) => o.table.join(".") + "." + o.column);
		console.log(`  ${c.output} <- ${srcs.length ? srcs.join(", ") : "(无来源)"}`);
	}
}
