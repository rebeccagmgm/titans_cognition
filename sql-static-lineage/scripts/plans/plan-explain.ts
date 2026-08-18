// ============================================================================
// plan-explain —— 把 plan-facts JSON 渲染成 EXPLAIN 式缩进树
//
// 用法:
//   npx tsx scripts/plans/plan-explain.ts <plan-facts.json> [--full] [--grain]
//   --full  展开所有 project 表达式 (默认只显示前 3 个)
//   --nograin 不标注 grain/cardinality
// 输出: 控制台树 + <同名>.explain.txt
// ============================================================================
import { readFileSync, writeFileSync } from "node:fs";

const args = process.argv.slice(2);
const file = args.find((a) => !a.startsWith("--")) ?? "output/118141/plan-facts-118141.json";
const FULL = args.includes("--full");
const SHOW_GRAIN = !args.includes("--nograin");

const doc = JSON.parse(readFileSync(file, "utf8"));
const facts = doc.plan ?? doc;
const grainList: any[] = doc.grain_inference ?? [];

const byId = new Map(facts.relations.map((r: any) => [r.id, r]));
const grainMap = new Map(grainList.map((g: any) => [g.node_id, g]));
const unknownMap = new Map(facts.unknowns.map((u: any) => [`${u.node_id}.${u.field}`, u]));

const SHORT = (t: string) => t.split(".").pop() ?? t;
const cut = (s: string, n = 90) => (s.length > n ? s.slice(0, n) + "…" : s);

/** 收集某节点子树内的 unknown 标注 (供父级汇总) */
function childUnknowns(id: string, out: string[] = [], seen = new Set<string>()): string[] {
	if (seen.has(id)) return out;
	seen.add(id);
	for (const u of facts.unknowns ?? []) {
		if (u.node_id === id) out.push(`  ⚠ ${u.field}: ${cut(u.reason, 70)}`);
	}
	const r = byId.get(id);
	if (!r) return out;
	if (r.type === "join") {
		childUnknowns(r.left, out, seen);
		childUnknowns(r.right, out, seen);
	} else if (r.source) {
		childUnknowns(r.source, out, seen);
	}
	return out;
}

function grainTag(id: string): string {
	if (!SHOW_GRAIN) return "";
	const g = grainMap.get(id);
	if (!g) return "";
	const parts: string[] = [];
	if (g.grain_candidate !== null) {
		parts.push(`grain=[${(g.grain_candidate as string[]).join(",")}]`);
	} else if (g.grain_candidate === null) {
		parts.push(`grain=null(全局)`);
	} else {
		parts.push("grain=?");
	}
	parts.push(`card=${g.cardinality}`);
	if (g.confidence !== undefined && g.confidence !== "unknown") parts.push(`conf=${g.confidence}`);
	if (g.cardinality_effect) parts.push(`effect=${g.cardinality_effect}`);
	if (g.requires && g.requires.length) parts.push(`requires=[${g.requires.join("; ")}]`);
	return parts.length ? `  ⏺ ${parts.join(" ")}` : "";
}

function exprSummary(r: any): string {
	const exprs = r.expressions ?? [];
	if (exprs.length === 0) return "PROJECT (0)";
	const show = FULL ? exprs : exprs.slice(0, 3);
	const parts = show.map((e: any) => {
		const nm = e.name ? ` ${e.name}` : "";
		const kind = e.expr_kind && e.expr_kind !== "column" ? ` [${e.expr_kind}]` : "";
		const w = e.window ? " [window]" : "";
		return cut((e.expr_text ?? e.column_name ?? "?").replace(/\s+/g, " "), 60) + (nm !== " ?" ? `→${nm}` : "") + kind + w;
	});
	const more = exprs.length > show.length ? ` …(+${exprs.length - show.length})` : "";
	return `PROJECT (${exprs.length}) ${parts.join(" | ")}${more}`;
}

const LINES: string[] = [];
function render(id: string, prefix: string, isLast: boolean, root = false) {
	const r = byId.get(id);
	if (!r) return;
	const conn = root ? "" : isLast ? "└─ " : "├─ ";
	let head = `${conn}[${r.type}]`;
	switch (r.type) {
		case "read":
			head += ` ${SHORT(r.table)}${r.binding ? ` AS ${r.binding}` : ""}`;
			break;
		case "filter":
			head += ` WHERE ${cut(r.predicate_display ?? r.predicate_expr, 100)}`;
			break;
		case "join":
			head += ` ${(r.join_type ?? "?").toUpperCase()} (${r.condition_display ?? r.condition_expr ?? ""})`;
			break;
		case "aggregate":
			head += ` GROUP BY [${(r.group_by ?? []).map((c: any) => c.name).join(", ")}]`;
			break;
		case "expand":
			head += ` lateral → ${(r.produced_columns ?? []).join(", ")}`;
			break;
		case "project":
			head += ` ${exprSummary(r)}`;
			break;
		default:
			head += ` (${JSON.stringify(r).slice(0, 80)})`;
	}
	LINES.push(`${prefix}${head}${grainTag(id)}`);

	// 该节点自己的 unknown
	for (const u of facts.unknowns ?? []) {
		if (u.node_id === id) LINES.push(`${prefix}${isLast ? "   " : "│  "} ⚠ ${u.field}: ${cut(u.reason, 80)}`);
	}

	const childPrefix = prefix + (root || isLast ? "   " : "│  ");
	if (r.type === "join") {
		// 主线 (left) 先画, 支线 (right) 最后 —— 从上往下即"主链 → 支线"
		render(r.left, childPrefix, false);
		render(r.right, childPrefix, true);
	} else if (r.source) {
		render(r.source, childPrefix, true);
	}
}

// ---- 头部 ----
LINES.push(`# Logical Plan Facts — ${file}`);
LINES.push(`meta: contract=${facts.meta.contract_version} adapter=${facts.meta.adapter_version} parser=${facts.meta.parser.engine}@${facts.meta.parser.version} dialect=${facts.meta.dialect} stmt=${facts.meta.statement_index}`);
LINES.push(`统计: ${facts.relations.length} 节点, ${new Set(facts.relations.filter((r: any) => r.type === "read").map((r: any) => r.table)).size} 物理表, ${(facts.unknowns ?? []).length} unknown`);
LINES.push("");

for (const rootId of facts.roots ?? []) {
	render(rootId, "", true, true);
}
LINES.push("");

// ---- unknown 汇总 ----
const uk = facts.unknowns ?? [];
if (uk.length) {
	LINES.push(`## 关键 unknown (${uk.length})`);
	for (const u of uk) {
		LINES.push(`- ${u.node_id} · ${u.field}: ${u.reason}`);
	}
	LINES.push("");
}

// ---- grain 汇总 ----
if (SHOW_GRAIN) {
	const known = grainList.filter((g: any) => g.grain_candidate !== null);
	const rootG = grainMap.get((facts.roots ?? [])[0]);
	LINES.push(`## grain 推断 (${grainList.length} 节点)`);
	LINES.push(`主 grain: ${rootG?.grain_candidate ? `[${rootG.grain_candidate.join(", ")}]` : "unknown / 待元数据证明"}`);
	for (const g of known) LINES.push(`- ${g.node_id}: [${g.grain_candidate.join(", ")}]`);
	LINES.push("");
}

const out = LINES.join("\n");
console.log(out);
writeFileSync(file.replace(/\.json$/, ".explain.txt"), out, "utf8");
console.log(`\n[已保存] ${file.replace(/\.json$/, ".explain.txt")}`);
