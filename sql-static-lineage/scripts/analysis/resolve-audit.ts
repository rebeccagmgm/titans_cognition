// 诊断: 13分支 case 表达式中每个列引用的解析状态 —— 用 npx tsx scripts/analysis/resolve-audit.ts 运行
// 目的: 验证 Ddct_Ptrn / Init_Marg_Prop / Base_Marg_Rate 是否为 needs-schema(缺schema) 而非算法漏
import { readFileSync } from "node:fs";
import { SqlSession, lineageAt, Schema } from "../../src/index.ts";
import { resolveColumnRef } from "../../src/sema/resolve.js";
import { partSpanOf } from "../../src/ir/part-span.js";

const sql = readFileSync(
	"e:/02_area/股衍数据-数据cookbook/titans-cognition/.evidence-cache/tasksql-118141-20260814.txt",
	"utf-8",
);
const s = SqlSession.create(sql, "databricks");
const cell = s.doc.statements[1];
const text = cell.text;

// 定位外层 hop（Curr_Prvs_Sales_Income 输出列）
const idx = text.indexOf("Curr_Prvs_Sales_Income");
const outerHop = lineageAt(cell.scopes, idx, new Schema({}));

// 递归收集 hop 树中所有 case 表达式 hop
const caseHops: any[] = [];
function collectCaseHops(hop: any): void {
	if (!hop) return;
	if (hop.expr?.kind === "case") caseHops.push(hop);
	for (const d of hop.downstream ?? []) collectCaseHops(d);
}
collectCaseHops(outerHop);
console.log(`收集到 case 表达式 hop 数: ${caseHops.length}（应=2: 外层2分支 + 内层13分支）`);

// 选 whens 最多的那个（13 分支内层 case）
const inner = caseHops.sort((a, b) => (b.expr.whens?.length ?? 0) - (a.expr.whens?.length ?? 0))[0];
if (!inner) {
	console.log("未找到 case 表达式");
	process.exit(1);
}
console.log(`审计目标: case[${inner.expr.whens.length}个when分支] @ scope=${inner.scope.body.kind}\n`);

// 收集表达式内所有列引用（任意深度递归，含 whens/args 等无 kind 结构）
const cols: Array<{ parts: string[]; text: string; status: string; detail: string }> = [];
const seen = new Set<string>();
const visited = new WeakSet<object>();
function walkExpr(expr: any): void {
	if (!expr || typeof expr !== "object" || visited.has(expr)) return;
	visited.add(expr);
	if (expr.kind === "column" && Array.isArray(expr.parts)) {
		const sp = partSpanOf(expr.cst);
		const key = sp ? `${sp.start}-${sp.end}` : expr.parts.join(".");
		if (!seen.has(key)) {
			seen.add(key);
			cols.push({ parts: expr.parts, text: sp ? text.slice(sp.start, sp.end) : "-", status: "?", detail: "" });
		}
		return;
	}
	for (const k of Object.keys(expr)) {
		if (k === "cst") continue; // ANTLR 树，跳过（列引用用 parts 就够了）
		const v = expr[k];
		if (Array.isArray(v)) {
			for (const e of v) walkExpr(e);
		} else if (v && typeof v === "object") {
			walkExpr(v);
		}
	}
}
walkExpr(inner.expr);

// 逐个解析状态检查（无 schema 模式，用 case 所在 scope）
const emptySchema = new Schema({});
let badCount = 0;
let boundCount = 0;
for (const c of cols) {
	const parts = c.parts.length ? c.parts : [c.text.split(".").pop() ?? ""];
	const r = resolveColumnRef(inner.scope, { parts, clause: undefined }, emptySchema as any);
	if (r.kind !== "bound") {
		c.status = r.kind;
		c.detail =
			r.kind === "needs-schema"
				? "基表列集未知 → needs-schema（有 schema 即可绑定）"
				: r.kind === "ambiguous"
					? `歧义候选: ${r.candidates?.map((x: any) => x.source?.relation?.parts?.join(".") ?? x.kind).join(", ") ?? "?"}`
					: r.kind;
		badCount++;
	} else {
		c.status = "bound";
		c.detail = `${r.source.source?.relation?.parts?.join(".") ?? "?"}.${r.column}`;
		boundCount++;
	}
}

console.log(`=== 13分支 case 列引用审计（共 ${cols.length} 个唯一引用）===`);
for (const c of cols) console.log(`${c.status === "bound" ? "✅" : "❌"} [${c.status}] ${c.text} → ${c.detail}`);
console.log(`\nbound=${boundCount}  未绑定=${badCount}（needs-schema=缺schema可修, unresolved=真未定义, ambiguous=真歧义）`);

// 聚焦三个漏源字段
console.log("\n=== 漏源字段专项 ===");
for (const name of ["Ddct_Ptrn", "Init_Marg_Prop", "Base_Marg_Rate"]) {
	for (const h of cols.filter((c) => c.text.split(".").pop() === name))
		console.log(`${h.status} ${h.text} → ${h.detail}`);
}
