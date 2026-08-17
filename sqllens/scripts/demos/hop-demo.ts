// sqllens 逐跳血缘 + 加工逻辑（无损层）实测 —— 用 npx tsx scripts/demos/hop-demo.ts 运行
// 每跳展示: 层 / 投影 / 加工表达式原文(逐字还原) / IR结构 / terminal / via
import { mkdirSync, readFileSync, createWriteStream } from "node:fs";
import { SqlSession, lineageAt, Schema } from "../../src/index.ts";
import { partSpanOf } from "../../src/ir/part-span.js";

const sql = readFileSync(
	"e:/02_area/股衍数据-数据cookbook/titans-cognition/.evidence-cache/tasksql-118141-20260814.txt",
	"utf-8",
);
const s = SqlSession.create(sql, "databricks");
const cell = s.doc.statements[1]; // SELECT 语句（cell-relative 坐标）
const text = cell.text;
// 同时写 UTF-8 文件，避免终端重定向的编码问题
mkdirSync("output/118141", { recursive: true });
const out = createWriteStream("output/118141/sqllens-118141-hops.txt", { encoding: "utf8" });
function log(s: string): void {
	console.log(s);
	out.write(s + "\n");
}

function scopeLabel(scope: any): string {
	const outs = Array.isArray(scope.outputs) ? scope.outputs.slice(0, 2).join(",") : "unknown";
	return `${scope.body.kind}[${outs}]`;
}

/** 从 CST span 逐字还原加工表达式原文（无损） */
function exprText(expr: any): string {
	const sp = partSpanOf(expr.cst);
	if (!sp) return "(无span)";
	return text.slice(sp.start, sp.end).replace(/\s+/g, " ").trim();
}

/** IR 结构摘要：加工逻辑的形态 */
function exprSummary(expr: any): string {
	switch (expr.kind) {
		case "case":
			return `case[${expr.whens.length}个when分支]`;
		case "function":
			return `function ${expr.name}${expr.window ? " [OVER窗口]" : ""}[${expr.args?.length ?? "?"}参]`;
		case "binary":
			return `binary ${expr.op}`;
		case "cast":
			return `cast→${expr.typeText}`;
		case "column":
			return `column ${(expr.parts ?? []).join(".")}`;
		case "literal":
			return `literal '${expr.text}'`;
		case "unary":
			return `unary ${expr.op}`;
		default:
			return expr.kind;
	}
}

function printHop(hop: any, depth: number): void {
	const pad = "  ".repeat(depth);
	const alias = hop.projection?.alias?.name ? `AS ${hop.projection.alias.name}` : "(无别名)";
	const term =
		hop.terminal === "unresolved"
			? "unresolved(诚实死路)"
			: hop.terminal?.map((o: any) => `${o.table.join(".")}.${o.column}`).join(", ") ?? "-";
	const via = hop.via?.map((v: any) => `${v.kind}@${scopeLabel(v.scope)}`).join(" → ") ?? "-";
	const dn = hop.downstream.length ? ` | 下游${hop.downstream.length}跳` : "";
	log(`${pad}● 层: ${scopeLabel(hop.scope)} | 投影: ${alias}${dn}`);
	log(`${pad}  加工: ${exprText(hop.expr)}`);
	log(`${pad}  IR : ${exprSummary(hop.expr)}`);
	log(`${pad}  来处: ${term}`);
	log(`${pad}  路径: ${via}`);
	for (const d of hop.downstream) printHop(d, depth + 1);
}

for (const colName of [
	"Main_Oper_Name",
	"Init_Nom_Prin_Main",
	"End_Pric_Date",
	"Actl_Days",
	"Curr_Prvs_Sales_Income",
]) {
	const idx = text.indexOf(colName);
	log(`\n===== 列 ${colName}（cell offset=${idx}）=====`);
	const hop = lineageAt(cell.scopes, idx, new Schema({}));
	if (!hop) {
		log("  无法定位该列");
		continue;
	}
	printHop(hop, 0);
}
