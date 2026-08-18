// 名义本金贴源->模型 加工路径血缘分析 v3（sql-static-lineage databricks 方言）
// 用法: 在 sql-static-lineage/ 目录 npx tsx scripts/analysis/analyze-notional.ts
// 输入: ../output/notional-lineage-20260816/model-sql-hits.json
// 输出: ../output/notional-lineage-20260816/model-notional-lineage.json
// v3 策略（v2 基础上）:
//  1) projection.cst 精确锚定（避免 CREATE TABLE 列清单误匹配）
//  2) 无别名/别名冲突子查询: 递归穿透到子查询 scope 找同名输出列再解析
//  3) 子查询内部解析失败（sourceList 空/star）: 从子查询文本正则提取 FROM 表做启发式绑定
//  4) 计算表达式列: 表达式内每个限定列引用逐位置 lineageAt
//  5) lineage() 语句级抛错时文本回退
import { readFileSync, writeFileSync } from "node:fs";
import { SqlSession, lineage, lineageAt } from "../../src/index.ts";
import { partSpanOf } from "../../src/ir/part-span.js";
import { nodeAt } from "../../src/document/node-at.js";

const OUT_DIR = "e:/02_area/股衍数据-数据cookbook/titans-cognition/output/notional-lineage-20260816";
const SQL_DIR =
	"e:/02_area/股衍数据-数据cookbook/titans-cognition/output/titans-collection-20260815/data/downstream-tasks-sql";

const hits = JSON.parse(
	readFileSync(`${OUT_DIR}/model-sql-hits.json`, "utf-8"),
) as Array<{
	sql_file: string;
	task_id: string;
	target_table: string;
	ods_refs: string;
	notional_keyword_count: number;
}>;

const KW = /NOTIONAL|PRINCIPAL|本金|NOM_|PRIN_|MXQSBJ|_NOTL_|CLEAR_PRINCIPAL/i;

// 贴源表 -> KW 列名清单（来自 01 阶段 notional-fields-with-ods 映射）
const fieldsWithOds = JSON.parse(
	readFileSync(`${OUT_DIR}/notional-fields-with-ods.json`, "utf-8"),
) as Array<{ ods_table?: string; column_name?: string }>;
const odsCols = new Map<string, Set<string>>();
for (const f of fieldsWithOds) {
	const t = (f.ods_table ?? "").toLowerCase();
	if (!t) continue;
	if (!odsCols.has(t)) odsCols.set(t, new Set());
	odsCols.get(t)!.add((f.column_name ?? "").toLowerCase());
}

interface HopInfo {
	expr: string;
	ir: string;
	terminal: string;
	downstream: HopInfo[];
}

function spanText(cell: any, cst: any): string | undefined {
	const sp = partSpanOf(cst);
	if (!sp) return undefined;
	return cell.text.slice(sp.start, sp.end).replace(/\s+/g, " ").trim();
}

function exprText(cell: any, expr: any): string {
	return spanText(cell, expr?.cst) ?? "(无span)";
}
function exprSummary(expr: any): string {
	if (!expr) return "?";
	switch (expr.kind) {
		case "case": return `case[${expr.whens.length}个when]`;
		case "function": return `function ${expr.name}${expr.window ? "[OVER]" : ""}[${expr.args?.length ?? "?"}参]`;
		case "binary": return `binary ${expr.op}`;
		case "column": return `column ${(expr.parts ?? []).join(".")}`;
		case "literal": return `literal`;
		case "cast": return "cast";
		default: return expr.kind;
	}
}
function printHop(cell: any, hop: any, depth = 0): HopInfo {
	const term = hop.terminal === "unresolved" ? "unresolved"
		: hop.terminal?.map((o: any) => `${o.table.join(".")}.${o.column}`).join(", ") ?? "-";
	const node: HopInfo = {
		expr: exprText(cell, hop.expr),
		ir: exprSummary(hop.expr),
		terminal: term,
		downstream: [],
	};
	for (const d of hop.downstream ?? []) node.downstream.push(printHop(cell, d, depth + 1));
	return node;
}

// ---- 穿透 + 文本启发式 ----
function childScopeOf(src: any): any | undefined {
	if (src.kind === "cte") return src.ref.scope;
	if (src.kind === "subquery") return src.scope;
	if (src.kind === "relation") return src.scope;
	return undefined;
}

function producerIn(child: any, colName: string): any | undefined {
	if (child.body.kind !== "select") return undefined;
	const projs = child.body.projections ?? [];
	const lc = colName.toLowerCase();
	return projs.find((p: any) => !p.isStar && p.name !== undefined && p.name.toLowerCase() === lc);
}

// 子查询文本的 FROM 表提取（小写、去重）
function tablesFromText(subText: string): string[] {
	const out: string[] = [];
	for (const m of subText.matchAll(/\bfrom\s+([a-zA-Z0-9_$.]+)/gi)) {
		const t = m[1].toLowerCase();
		if (t.startsWith("(")) continue;
		if (!out.includes(t)) out.push(t);
	}
	return out;
}

interface Fallback {
	heuristic: boolean;
	heuristic_note?: string;
	candidate_tables?: string[];
	hop?: any;
	path?: string[];
}

// 子查询 scope 解析失败时的文本启发式: 单表绑定列, 多表列候选
function textFallback(cell: any, child: any, colName: string): Fallback | undefined {
	const sp = partSpanOf(child.body?.cst);
	if (!sp) return undefined;
	const subText = cell.text.slice(sp.start, sp.end);
	const tables = tablesFromText(subText);
	if (tables.length === 1) {
		const t = tables[0];
		return {
			heuristic: true,
			heuristic_note: `子查询内部无法绑定(${subText.slice(0, 50).replace(/\s+/g, " ")}), 文本提取单表 ${t} 绑定列 ${colName}`,
			hop: {
				terminal: [{ table: t.split("."), column: colName }],
				expr: { kind: "column", parts: [...t.split("."), colName], cst: undefined },
				downstream: [],
			},
			path: [`文本回退→${t}.${colName}`],
		};
	}
	if (tables.length > 1) {
		return {
			heuristic: true,
			heuristic_note: `子查询含多表(${tables.join(", ")}), 列 ${colName} 具体来源无法确定`,
			candidate_tables: tables,
			path: [`多表候选: ${tables.join(", ")}`],
		};
	}
	return undefined;
}

// 启发式绑定: 基于任务 ods_refs（贴源表清单）+ 贴源表列清单
// preferCols: 投影表达式中的源列名, 优先于输出列名做强匹配
function textFallbackV2(h: any, colName: string, preferCols?: string[]): Fallback | undefined {
	const odsRefs = (h.ods_refs ?? "").split(";").map((s: string) => s.trim().toLowerCase()).filter(Boolean);
	const want = colName.toLowerCase();
	const mkHop = (t: string, cn: string) => ({
		terminal: [{ table: t.split("."), column: cn }],
		expr: { kind: "column", parts: [...t.split("."), cn], cst: undefined },
		downstream: [],
	});
	// 0) 投影源列名优先: 强匹配唯一贴源表
	for (const pc of preferCols ?? []) {
		const strong: string[] = [];
		const w = pc.toLowerCase();
		for (const t of odsRefs) if (odsCols.get(t)?.has(w)) strong.push(t);
		if (strong.length === 1) {
			return { heuristic: true, heuristic_note: `投影列名 ${pc} 命中贴源表 ${strong[0]} 字段清单`, hop: mkHop(strong[0], pc), path: [`投影列名匹配→${strong[0]}.${pc}`] };
		}
		if (strong.length > 1) {
			return { heuristic: true, heuristic_note: `投影列名 ${pc} 出现在多张贴源表清单(${strong.join(",")}), 无法唯一确定`, candidate_tables: strong };
		}
	}
	// 1) 输出列名强匹配: 列名在某贴源表字段清单中
	const strong: string[] = [];
	for (const t of odsRefs) if (odsCols.get(t)?.has(want)) strong.push(t);
	if (strong.length === 1) {
		return { heuristic: true, heuristic_note: `列名命中贴源表 ${strong[0]} 字段清单`, hop: mkHop(strong[0], colName), path: [`贴源列清单匹配→${strong[0]}.${colName}`] };
	}
	if (strong.length > 1) {
		return { heuristic: true, heuristic_note: `列名出现在多张贴源表清单(${strong.join(",")}), 无法唯一确定`, candidate_tables: strong };
	}
	// 2) 弱匹配: 唯一贴源表按同名绑定
	if (odsRefs.length === 1) {
		const cn = (preferCols?.length === 1 ? preferCols[0] : colName);
		return { heuristic: true, heuristic_note: `唯一贴源表 ${odsRefs[0]}, 按同名列绑定`, hop: mkHop(odsRefs[0], cn), path: [`唯一贴源表→${odsRefs[0]}.${cn}`] };
	}
	// 3) 多表候选
	if (odsRefs.length > 1) {
		return { heuristic: true, heuristic_note: `多贴源表(${odsRefs.join(",")}), 列 ${colName} 来源不确定`, candidate_tables: odsRefs };
	}
	return undefined;
}

interface DrillResult {
	hop: any;
	depth: number;
	path: string[];
	heuristic?: boolean;
	heuristic_note?: string;
	candidate_tables?: string[];
}

function drillDown(cell: any, scopes: any, offset: number, colName: string, depth = 0): DrillResult {
	const path: string[] = [];
	const hop = lineageAt(scopes, offset, undefined);
	if (!hop) return { hop: undefined, depth, path };
	path.push(exprText(cell, hop.expr));
	if (hop.terminal !== "unresolved" || depth >= 5) return { hop, depth, path };
	const hit = nodeAt(scopes, offset);
	if (!hit) return { hop, depth, path };
	const want = colName.toLowerCase();
	for (const entry of hit.scope.sourceList ?? []) {
		const child = childScopeOf(entry.source);
		if (!child) continue;
		const proj = producerIn(child, want);
		if (proj) {
			const sp = partSpanOf(proj.cst);
			if (!sp) continue;
			const sub = drillDown(cell, scopes, sp.start, colName, depth + 1);
			const ok = sub.hop && sub.hop.terminal !== "unresolved";
			if (ok && !sub.heuristic) return { hop: sub.hop, depth: sub.depth, path: [...path, ...sub.path] };
			if (ok) return { hop: sub.hop, depth: sub.depth, path: [...path, ...sub.path], heuristic: true, heuristic_note: sub.heuristic_note };
			const fb = textFallback(cell, child, colName);
			if (fb?.hop) return { hop: fb.hop, depth: depth + 1, path: [...path, ...(fb.path ?? [])], heuristic: true, heuristic_note: fb.heuristic_note };
			if (fb) return { hop: undefined, depth: depth + 1, path: [...path, ...(fb.path ?? [])], heuristic: true, heuristic_note: fb.heuristic_note, candidate_tables: fb.candidate_tables };
		}
		const fb = textFallback(cell, child, colName);
		if (fb?.hop) return { hop: fb.hop, depth: depth + 1, path: [...path, ...(fb.path ?? [])], heuristic: true, heuristic_note: fb.heuristic_note };
		if (fb) return { hop: undefined, depth: depth + 1, path: [...path, ...(fb.path ?? [])], heuristic: true, heuristic_note: fb.heuristic_note, candidate_tables: fb.candidate_tables };
	}
	return { hop, depth, path };
}

function termOf(hop: any): string {
	if (!hop) return "(无hop)";
	if (hop.terminal === "unresolved") return "unresolved";
	return hop.terminal?.map((o: any) => `${o.table.join(".")}.${o.column}`).join(", ") ?? "-";
}

// 计算表达式: 逐限定列引用锚定解析
function exprRefsResolve(cell: any, scopes: any, sp: any, projExpr: string): any[] {
	const out: any[] = [];
	for (const m of projExpr.matchAll(/([a-z_][a-z0-9_]*)\s*\.\s*([A-Za-z_][A-Za-z0-9_]*)/g)) {
		const rel = sp.start + (m.index ?? 0) + m[0].indexOf(m[1]);
		const hop = lineageAt(scopes, rel, undefined);
		const ref: any = { ref: `${m[1]}.${m[2]}`, terminal: termOf(hop) };
		if (hop && hop.terminal !== "unresolved") ref.hops = [printHop(cell, hop)];
		out.push(ref);
	}
	return out;
}

// 对一条命中列做完整解析
function analyzeColumn(cell: any, scopes: any, c: any, h: any): any {
	const proj = c.projection;
	const sp = proj?.cst ? partSpanOf(proj.cst) : undefined;
	const offset = sp ? sp.start : (cell.text.indexOf(c.output) as number);
	const projExpr = sp ? cell.text.slice(sp.start, sp.end).replace(/\s+/g, " ").trim() : "(无projection)";
	const base = {
		output: c.output,
		origins: (c.origins ?? []).map((o: any) => `${o.table.join(".")}.${o.column}`),
		proj_expr: projExpr,
		anchor: sp ? "projection.cst" : "indexOf",
	};
	// 计算表达式: 投影不是裸列引用
	if (sp && proj && proj.expr?.kind !== "column") {
		const refs = exprRefsResolve(cell, scopes, sp, projExpr);
		const okRefs = refs.filter((r) => r.terminal !== "(无hop)" && r.terminal !== "unresolved");
		if (okRefs.length > 0) {
			// 计算表达式内引用全部原生解析: 视为原生计算列
			return { ...base, native: true, computed: true, terminal: okRefs.map((r) => r.terminal).join("; "), expr_refs: refs };
		}
		// 计算表达式引用无法绑定 -> 贴源启发式
		const fb = textFallbackV2(h, c.output);
		if (fb?.hop) {
			return { ...base, native: false, computed: true, heuristic: true, heuristic_note: fb.heuristic_note, terminal: termOf(fb.hop), hops: [printHop(cell, fb.hop)], expr_refs: refs };
		}
		return { ...base, native: false, computed: true, terminal: "unresolved(计算表达式, 引用无法绑定)", expr_refs: refs, heuristic: true, heuristic_note: fb?.heuristic_note, candidate_tables: fb?.candidate_tables };
	}
	const d = drillDown(cell, scopes, offset, c.output);
	const hop = d.hop;
	if (hop && hop.terminal !== "unresolved") {
		return { ...base, native: true, drill_depth: d.depth, drill_path: d.path, terminal: termOf(hop), hops: [printHop(cell, hop)], heuristic: d.heuristic ?? false, heuristic_note: d.heuristic_note };
	}
	// drill 未解 -> 贴源启发式
	const fb = textFallbackV2(h, c.output);
	if (fb?.hop) {
		return { ...base, native: false, drill_depth: d.depth, drill_path: d.path, heuristic: true, heuristic_note: fb.heuristic_note, terminal: termOf(fb.hop), hops: [printHop(cell, fb.hop)] };
	}
	return { ...base, native: false, drill_depth: d.depth, drill_path: d.path, heuristic: true, heuristic_note: fb?.heuristic_note ?? "无贴源启发式", candidate_tables: fb?.candidate_tables, terminal: termOf(hop), hops: hop ? [printHop(cell, hop)] : [] };
}

// 文本级回退: lineage() 抛错时正则提取 KW 投影列并尽力锚定
function fallbackTextColumns(cell: any, scopes: any): any[] {
	const text = cell.text;
	const out: any[] = [];
	const m = text.match(/select\s+([\s\S]*?)\s+from\s+\(/i);
	const body = m ? m[1] : text;
	const re = /(?:^|,)\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*(?:as\s+)?([a-zA-Z_][a-zA-Z0-9_]*)?/g;
	let mm: RegExpExecArray | null;
	while ((mm = re.exec(body))) {
		const name = (mm[2] ?? mm[1]).trim();
		if (!KW.test(name)) continue;
		const idx = text.indexOf(name);
		let hopInfo: any = undefined;
		if (idx >= 0) {
			try {
				const hop = lineageAt(scopes, idx, undefined);
				if (hop) hopInfo = printHop(cell, hop);
			} catch { /* total */ }
		}
		out.push({
			output: name,
			origins: [],
			proj_expr: mm[1].trim(),
			anchor: "fallback-regex",
			native: hopInfo ? hopInfo.terminal !== "unresolved" : false,
			terminal: hopInfo?.terminal ?? "(无法解析)",
			hops: hopInfo ? [hopInfo] : [],
			fallback: true,
		});
	}
	return out;
}

// 文本级投影提取: 对 INSERT WITH 前缀等 lineage 覆盖不全的结构, 从语句文本提取 KW 投影
function textKwProjections(text: string): Array<{ output: string; proj_expr: string; offset: number }> {
	const out: Array<{ output: string; proj_expr: string; offset: number }> = [];
	const seen = new Set<string>();
	// 1) X AS Y 形式(列引用改名)
	const asRe = /(?:^|,)\s*([A-Za-z_][A-Za-z0-9_.]*)\s+AS\s+([A-Za-z_][A-Za-z0-9_]*)/g;
	let m: RegExpExecArray | null;
	while ((m = asRe.exec(text))) {
		const expr = m[1];
		const alias = m[2];
		if (!KW.test(expr) && !KW.test(alias)) continue;
		if (seen.has(alias.toLowerCase())) continue;
		seen.add(alias.toLowerCase());
		out.push({ output: alias, proj_expr: expr, offset: m.index + m[0].indexOf(expr) });
	}
	// 2) 裸列名(逗号/行首后无 AS)
	const bareRe = /(?:^|,)\s*([A-Za-z_][A-Za-z0-9_]*)\s*(?:--[^\n]*)?(?=,|\n|$)/g;
	while ((m = bareRe.exec(text))) {
		const name = m[1];
		if (!KW.test(name)) continue;
		if (seen.has(name.toLowerCase())) continue;
		seen.add(name.toLowerCase());
		out.push({ output: name, proj_expr: name, offset: m.index + m[0].indexOf(name) });
	}
	return out;
}

// 文本投影列的解析: 先尝试 lineageAt 锚定, 失败后走贴源启发式
function analyzeTextColumn(cell: any, scopes: any, p: { output: string; proj_expr: string; offset: number }, h: any): any {
	const base = { output: p.output, origins: [], proj_expr: p.proj_expr, anchor: "text-regex" };
	try {
		const hop = lineageAt(scopes, p.offset, undefined);
		if (hop && hop.terminal !== "unresolved") {
			return { ...base, native: true, terminal: termOf(hop), hops: [printHop(cell, hop)] };
		}
	} catch { /* 忽略锚定异常 */ }
	const exprCols = p.proj_expr.match(/[A-Za-z_][A-Za-z0-9_]*/g) ?? [];
	const fb = textFallbackV2(h, p.output, exprCols);
	if (fb?.hop) {
		return { ...base, native: false, heuristic: true, heuristic_note: fb.heuristic_note, terminal: termOf(fb.hop), hops: [printHop(cell, fb.hop)] };
	}
	return { ...base, native: false, heuristic: true, heuristic_note: fb?.heuristic_note ?? "无贴源启发式", candidate_tables: fb?.candidate_tables, terminal: "(无法解析)" };
}

// 目标表列清单: 从 CREATE TABLE 列区提取(用于过滤表达式内部引用误捕获)
function targetColumnsOf(sql: string): Set<string> | undefined {
	const m = sql.match(/CREATE\s+TABLE(?:\s+IF\s+NOT\s+EXISTS)?\s+[A-Za-z0-9_.]+\s*\(([\s\S]*?)\)\s*(?:;|COMMENT|PARTITIONED|WITH|INSERT|$)/i);
	if (!m) return undefined;
	const cols = new Set<string>();
	for (const cm of m[1].matchAll(/^\s*,?\s*([A-Za-z_][A-Za-z0-9_]*)\s+(?:string|int|bigint|double|decimal|timestamp|date|boolean|float|smallint|tinyint)\b/gim)) {
		cols.add(cm[1].toLowerCase());
	}
	return cols.size > 0 ? cols : undefined;
}

const results: any[] = [];
for (const h of hits) {
	// p3 命中但 SQL 正文无名义本金关键词: 贴源引用仅为关联键/分区筛选等用途
	if (!h.notional_keyword_count) {
		results.push({
			sql_file: h.sql_file,
			task_id: h.task_id,
			target_table: h.target_table,
			ods_refs: h.ods_refs,
			skip: "SQL正文无名义本金关键词(notional_keyword_count=0), 贴源表引用仅作关联键/分区筛选等用途",
		});
		continue;
	}
	const sql = readFileSync(`${SQL_DIR}/${h.sql_file}`, "utf-8");
	const cleaned = sql.split("$" + "{").join("ZZ").replace(/ZZ[^}]*}/g, "'2026-01-01'");
	const targetCols = targetColumnsOf(cleaned);
	let session: any;
	try {
		session = SqlSession.create(cleaned, "databricks");
	} catch (e: any) {
		results.push({ sql_file: h.sql_file, task_id: h.task_id, target_table: h.target_table, error: String(e?.message ?? e) });
		continue;
	}
	let stmtErrors: string[] = [];
	for (let si = 0; si < session.doc.statements.length; si++) {
		const cell = session.doc.statements[si];
		const text = cell.text;
		if (!/select/i.test(text)) continue;
		let lin: any;
		try {
			lin = lineage(cell.scopes, undefined);
		} catch (e: any) {
			stmtErrors.push(`stmt${si}: ${String((e as any)?.message ?? e).slice(0, 100)}`);
			const fb = fallbackTextColumns(cell, cell.scopes);
			if (fb.length > 0) {
				results.push({
					sql_file: h.sql_file,
					task_id: h.task_id,
					target_table: h.target_table,
					ods_refs: h.ods_refs,
					stmt_index: si,
					stmt_head: text.slice(0, 80).replace(/\s+/g, " "),
					matched_columns: fb,
					lineage_error: String((e as any)?.message ?? e).slice(0, 200),
				});
			}
			continue;
		}
		const matched: any[] = [];
		for (const c of lin.all ?? []) {
			const srcNames = (c.origins ?? []).map((o: any) => `${o.table.join(".")}.${o.column}`);
			const hitKw = KW.test(c.output) || srcNames.some((s: string) => KW.test(s));
			if (!hitKw) continue;
			matched.push(analyzeColumn(cell, cell.scopes, c, h));
		}
		// 文本投影补充: INSERT WITH 前缀等结构 lineage 覆盖不全时补漏去重
		for (const p of textKwProjections(text)) {
			if (matched.some((x) => (x.output ?? "").toLowerCase() === p.output.toLowerCase())) continue;
			// 非目标表列的 KW 引用(表达式内部别名等)剔除
			if (targetCols && !targetCols.has(p.output.toLowerCase())) continue;
			matched.push(analyzeTextColumn(cell, cell.scopes, p, h));
		}
		if (matched.length > 0) {
			results.push({
				sql_file: h.sql_file,
				task_id: h.task_id,
				target_table: h.target_table,
				ods_refs: h.ods_refs,
				stmt_index: si,
				stmt_head: text.slice(0, 80).replace(/\s+/g, " "),
				matched_columns: matched,
			});
		}
	}
	if (stmtErrors.length > 0) {
		const last = results.filter((r) => r.sql_file === h.sql_file);
		if (last.length === 0) {
			results.push({ sql_file: h.sql_file, task_id: h.task_id, target_table: h.target_table, error: stmtErrors.join("; ") });
		} else {
			last[last.length - 1].partial_errors = stmtErrors;
		}
	}
}

writeFileSync(`${OUT_DIR}/model-notional-lineage.json`, JSON.stringify(results, null, 2), "utf-8");

// 控制台摘要
let colTotal = 0, nativeCols = 0, heuristicCols = 0, unresolvedCols = 0;
for (const r of results) {
	if (r.matched_columns) {
		colTotal += r.matched_columns.length;
		for (const m of r.matched_columns) {
			if (m.native) nativeCols++;
			else if (m.heuristic || m.candidate_tables || m.computed) heuristicCols++;
			else unresolvedCols++;
		}
		const bad = r.matched_columns.filter((m: any) => !m.native);
		console.log(`◆ ${r.target_table} (${r.sql_file}) 命中${r.matched_columns.length}列${bad.length ? `, 未原生解${bad.length}: [${bad.map((b: any) => b.output).join(", ")}]` : ""}`);
	} else if (r.skip) {
		console.log(`- ${r.sql_file}: skip(无名义本金关键词) -> ${r.target_table}`);
	} else {
		console.log(`✗ ${r.sql_file}: ${r.error}`);
	}
}
const skipped = results.filter((r) => r.skip).length;
console.log(`\n总计: ${results.filter((r) => r.matched_columns).length} 个任务, ${colTotal} 列 | 原生 ${nativeCols} | 启发式/计算 ${heuristicCols} | 未解 ${unresolvedCols} | skip ${skipped}`);
console.log(`[已保存] ${OUT_DIR}/model-notional-lineage.json`);
