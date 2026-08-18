// sql-static-lineage × Spark (databricks 方言) 实测 —— 用 npx tsx spark-demo.ts 运行
// 模拟数仓宽表加工 SQL：INSERT OVERWRITE + CTE + 窗口函数 + 多表 JOIN
import {
	analyze,
	Schema,
	SqlSession,
	resolveDialect,
	parse,
	toScopes,
	qualify,
	lineage,
} from "../../src/index.ts";

console.log("=== 0. Spark 相关方言 ===");
console.log("spark ->", resolveDialect("spark"));
console.log("glue ->", resolveDialect("glue"));

// 模拟 TITANS 风格 OTC 衍生品场景：ods 交易流水 + 维度表
const schema = new Schema({
	ods_trade: {
		trade_no: "string",
		cust_no: "string",
		product_code: "string",
		notional_amount: "decimal",
		currency: "string",
		status: "string",
		trade_date: "date",
		update_time: "timestamp",
		dt: "string",
	},
	dim_customer: { cust_no: "string", cust_name: "string", cust_type: "string" },
	dim_product: { product_code: "string", product_name: "string" },
});

// 典型数仓 ETL：宽表加工
const sql = `
INSERT OVERWRITE TABLE dwd_otc_position_di
SELECT
	t.trade_no,
	t.cust_no,
	c.cust_name,
	t.product_code,
	p.product_name,
	t.notional_amount,
	t.currency,
	t.status,
	t.trade_date
FROM ods_trade t
JOIN dim_customer c ON t.cust_no = c.cust_no
JOIN dim_product p ON t.product_code = p.product_code
WHERE t.dt = '2026-08-15'
`;

console.log("\n=== 1. analyze: INSERT OVERWRITE + JOIN 诊断 ===");
const a = analyze(sql, "databricks", { schema });
console.log("语法诊断:", JSON.stringify(a.syntaxDiagnostics, null, 2));
console.log("语义诊断:", JSON.stringify(a.diagnostics, null, 2));
console.log("语句类型:", a.ast.statement);
console.log("输出列血缘:");
for (const col of a.lineage.all) {
	console.log(" ", col.output, "->", JSON.stringify(col.origins));
}

console.log("\n=== 2. 窗口函数 + CTE（更接近真实加工 SQL） ===");
const sql2 = `
WITH ranked AS (
	SELECT
		t.trade_no,
		t.cust_no,
		t.notional_amount,
		ROW_NUMBER() OVER (PARTITION BY t.trade_no ORDER BY t.update_time DESC) AS rn
	FROM ods_trade t
	WHERE t.dt = '2026-08-15'
)
SELECT r.trade_no, r.notional_amount
FROM ranked r
WHERE r.rn = 1
`;
const a2 = analyze(sql2, "databricks", { schema });
console.log("语法诊断:", JSON.stringify(a2.syntaxDiagnostics, null, 2));
console.log("语义诊断:", JSON.stringify(a2.diagnostics, null, 2));
console.log("血缘（穿透 CTE + 窗口函数）:");
for (const col of a2.lineage.all) {
	console.log(" ", col.output, "->", JSON.stringify(col.origins));
}

console.log("\n=== 3. 故意写错字段，验证语义诊断 ===");
const a3 = analyze("SELECT trade_no, bad_col FROM ods_trade WHERE dt = 'x'", "databricks", { schema });
console.log("诊断:", JSON.stringify(a3.diagnostics, null, 2));

console.log("\n=== 4. 编辑式会话 + 不完整 SQL（编辑器场景） ===");
let s = SqlSession.create("SELECT trade_no, cust", "databricks", { schema });
console.log("半截输入 diagnostics():", JSON.stringify(s.diagnostics(), null, 2));
s = s.withText("SELECT trade_no, cust_no FROM ods_trade WHERE dt = '2026-08-15'");
console.log("补全后 diagnostics():", JSON.stringify(s.diagnostics(), null, 2));
