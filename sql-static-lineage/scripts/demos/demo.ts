// sql-static-lineage 快速上手演示 —— 用 npx tsx scripts/demos/demo.ts 运行
// 展示: analyze / Schema / diagnostics / lineage / SqlSession / resolveDialect
import {
	analyze,
	Schema,
	SqlSession,
	resolveDialect,
	parse,
	toScopes,
	qualify,
	lineage,
	deriveSymbols,
} from "../../src/index.ts";

console.log("=== 0. 方言解析 ===");
console.log("athena ->", resolveDialect("athena")); // trino
console.log("mariadb ->", resolveDialect("mariadb")); // mysql
console.log("spark ->", resolveDialect("spark")); // databricks

// 模拟一个交易系统 schema（类似你们的 TITANS 元数据视角）
const schema = new Schema({
	t_customer: { id: "int", cust_name: "string", cust_type: "string" },
	t_order: { id: "int", cust_id: "int", amount: "decimal", status: "string", trade_date: "date" },
});

console.log("\n=== 1. analyze 一次性分析（整条流水线） ===");
const sql = `
	SELECT c.cust_name, o.amount, o.status
	FROM t_customer c
	JOIN t_order o ON c.id = o.cust_id
	WHERE o.amount > 1000 AND o.status = 'FILLED'
`;
const a = analyze(sql, "postgres", { schema });

console.log("语法/语义诊断:", JSON.stringify(a.diagnostics, null, 2));
console.log("\n输出列血缘 originsOf('cust_name'):", JSON.stringify(a.lineage.originsOf("cust_name"), null, 2));
console.log("输出列血缘 originsOf('amount'):", JSON.stringify(a.lineage.originsOf("amount"), null, 2));
console.log("\nsymbols（大纲模型）:", JSON.stringify(a.symbols.slice(0, 6).map(({ kind, modifiers, name, frame, type, origins }) => ({ kind, modifiers, name, frame, type, origins })), null, 2));

console.log("\n=== 2. 故意写错，看 Never-wrong 行为 ===");
const bad = analyze("SELECT a, b FROM t", "postgres", { schema });
console.log("诊断:", JSON.stringify(bad.diagnostics, null, 2));

console.log("\n=== 3. 分阶段使用（parse -> scopes -> qualify -> lineage） ===");
const { ast, errors } = parse("SELECT a, b FROM t", "snowflake");
console.log("parse errors:", errors, "| ast 语句类型:", ast.statement);
const scopes = toScopes(ast);
qualify(scopes, schema);
const lin = lineage(scopes, schema);
console.log("分阶段 lineage:", JSON.stringify(lin.all.map(({ output, origins }) => ({ output, origins })), null, 2));
const syms = deriveSymbols(scopes);
console.log("分阶段 symbols 数量:", syms.length);

console.log("\n=== 4. SqlSession（编辑器式会话，编辑复用缓存） ===");
let s = SqlSession.create("SELECT amount, status FROM t_order", "postgres", { schema });
console.log("tokens 数:", s.tokens.length);
console.log("diagnostics():", JSON.stringify(s.diagnostics(), null, 2));
console.log("lineage():", JSON.stringify(s.lineage().all.map(({ output, origins }) => ({ output, origins })), null, 2));
// 编辑产生新会话，缓存复用
s = s.withText("SELECT amount, id FROM t_order");
console.log("编辑后 diagnostics():", JSON.stringify(s.diagnostics(), null, 2));
