// sqllens 实测真实调度任务 SQL（118141: OTC_SALE_DAILY_RPT 收入日报）
// 用 npx tsx scripts/demos/real-sql-demo.ts 运行
import { readFileSync } from "node:fs";
import { parse, SqlSession, toScopes, qualify, lineage, Schema, analyze } from "../../src/index.ts";

const sql = readFileSync(
	"e:/02_area/股衍数据-数据cookbook/titans-cognition/.evidence-cache/tasksql-118141-20260814.txt",
	"utf-8",
);

console.log("SQL 长度:", sql.length, "字符");

console.log("\n=== 1. parse: 语法错误统计（databricks 方言） ===");
const p = parse(sql, "databricks");
console.log("语法错误数:", p.errors);
console.log("token 数:", p.tokens.length);

console.log("\n=== 2. SqlSession: 语句切分与逐句语法诊断 ===");
const s = SqlSession.create(sql, "databricks");
console.log("会话 statements 数:", s.doc.statements.length);
s.doc.statements.forEach((st, i) => {
	const len = st.span.end - st.span.start;
	console.log(
		`  语句[${i}] 起始偏移=${st.span.start} 长度=${len} 类别=${st.category} 语法错误=${st.errors}`,
	);
});

console.log("\n=== 3. 语义诊断（无 schema，纯名称解析） ===");
const diags = s.doc.diagnostics;
console.log("诊断总数:", diags.length);
diags.slice(0, 15).forEach((d) => {
	console.log(`  [${d.kind}] L${d.line}:${d.column} ${d.message}`);
});
if (diags.length > 15) console.log(`  ... 其余 ${diags.length - 15} 条略过`);

console.log("\n=== 4. 血缘: 输出列 → 源表列（无 schema，表名原样保留） ===");
try {
	// 取第二条 SELECT 语句的 scopes（CREATE TABLE 无输出列）
	const selStmt = s.doc.statements[1];
	console.log("SELECT 语句类别:", selStmt.category);
	const scopes = selStmt.scopes;
	const lin = lineage(scopes, new Schema({}));
	console.log("血缘输出列数:", lin.all.length);
	// 全量输出（92 列）
	for (const c of lin.all) {
		const origins = c.origins.map((o) => `${o.table.join(".")}.${o.column}`).join(" + ");
		console.log(`  ${c.output} <- ${origins || "(无基表来源: 字面量/表达式)"}`);
	}
} catch (e) {
	console.log("血缘计算失败:", (e as Error).message);
}
