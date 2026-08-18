// IR 之上的结构化视图 demo —— 用 npx tsx struct-views-demo.ts 运行
// 展示 clausesOf / frameAt / nodeAt / setOpArmsOf 的实际输出
import { readFileSync } from "node:fs";
import { SqlSession, frameAt, nodeAt, setOpArmsOf } from "../../src/index.ts";

const sql = readFileSync(
	"e:/02_area/股衍数据-数据cookbook/titans-cognition/.evidence-cache/tasksql-118141-20260814.txt",
	"utf-8",
);
const s = SqlSession.create(sql, "databricks");
const cell = s.doc.statements[1]; // 主查询
const root = cell.scopes.root;
const text = cell.text;

// ---------- 1. clausesOf: 一个查询块的所有子句（kind + 位置） ----------
// 注意: 用 doc.clausesOf(scope) 实例方法（自动平移坐标系到 doc 坐标）;
// 自由函数 clausesOf(scope, tokens) 要求 tokens 与 scope.cst 同坐标系（仅单语句 doc 成立）
console.log("=== 1. clausesOf(主查询 scope, doc 坐标 span) ===");
const cl = s.doc.clausesOf(root);
for (const c of cl) {
	const spanText = sql.slice(c.span.start, c.span.end).replace(/\s+/g, " ").slice(0, 70);
	console.log(`  [${c.kind}] span=${c.span.start}-${c.span.end} : ${spanText}`);
}

// ---------- 2. frameAt: 某位置属于哪个查询块 ----------
console.log("\n=== 2. frameAt(13分支case里 Ddct_Ptrn 的位置) ===");
const idx = text.indexOf("Ddct_Ptrn");
const fr = frameAt(cell.scopes, idx);
console.log(`  frame: ${fr?.frame} | scope.outputs: ${fr?.scope.outputs?.slice(0, 3).join(",")}`);
// 再对比: 主查询开头的位置
const fr2 = frameAt(cell.scopes, text.indexOf("Curr_Prvs_Sales_Income"));
console.log(`  Curr_Prvs_Sales_Income 位置 frame: ${fr2?.frame} | outputs: ${fr2?.scope.outputs?.slice(0, 3).join(",")}`);

// ---------- 3. nodeAt: 某位置的最小表达式 ----------
console.log("\n=== 3. nodeAt(同上位置) ===");
const hit = nodeAt(cell.scopes, idx);
const sp = hit?.expr.cst ? (hit.expr.cst as any).start : undefined;
console.log(`  expr.kind: ${hit?.expr.kind} | 原文: "${sp ? text.slice(sp.start, sp.stop + 1) : "?"}"`);

// ---------- 4. setOpArmsOf: union 查询的臂 ----------
console.log("\n=== 4. setOpArmsOf(union 示例) ===");
const s2 = SqlSession.create("SELECT a FROM t1 UNION ALL SELECT b FROM t2 UNION SELECT c FROM t3", "databricks");
const c2 = s2.doc.statements[0];
const arms = setOpArmsOf(c2.scopes.root);
console.log(`  arms: ${arms?.arms.length} 个分支`);
for (const a of arms?.arms ?? []) {
	const t = c2.text.slice(a.span.start, a.span.end).replace(/\s+/g, " ").trim();
	console.log(`    - ${t}`);
}
