// ============================================================================
// Model Fingerprint —— 从 plan-facts JSON 提炼"模型指纹" (用于跨 SQL 比较)
//
// 目的: 不追求静态分析完备性, 只提炼"两个模型是否同源/同构/同 grain"所需的
//       判别信号。结构化输出 + 人类可读版。
//
// 用法:
//   npx tsx scripts/plans/plan-fingerprint.ts <plan-facts.json> [--id 118141] [--human]
//   无参数默认: plan-facts-118141.json
// ============================================================================
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";

export interface ModelFingerprint {
	/** 模型标识 (任务号/别名)。 */
	id: string;
	meta: {
		dialect: string;
		contract_version: string;
		parser_version: string;
		generated_at: string;
	};
	/** 输入物理表 (去重, 短名)。 */
	inputs: string[];
	/** 主链路径: 从主表到最终输出的节点序列摘要 (join 带右表). */
	spine: string[];
	/** 关键变形统计。 */
	transformations: {
		expand_count: number;
		aggregates: string[];
		window_count: number;
		case_count: number;
		filter_count: number;
		project_count: number;
		/** 集合操作节点数 (union/except/intersect)。 */
		union_count: number;
	};
	/** 已知 grain (grain_inference 中非空候选). */
	known_grains: { node: string; grain: string[] }[];
	/** 主 grain: 最外层输出的传播 grain. null = unknown. */
	main_grain: string[] | null;
	main_grain_status: "known" | "unknown";
	/** 扩行风险 join (cardinality=unknown 的 join) —— 主 grain 待证明的根因。 */
	row_expansion_risks: { node: string; right: string }[];
	/** 关键 unknown (unknowns 条目 + 未解析条件列)。 */
	key_unknowns: { node: string; field: string; reason: string }[];
}

const SHORT = (t: string) => t.split(".").pop() ?? t;

function rightTables(rels: any[], nodeId: string): string[] {
	// 沿 right 子树的 source 链收集 read 表 (不含支线 join 的右表)
	const out: string[] = [];
	const seen = new Set<string>();
	const walk = (id: string): void => {
		if (seen.has(id)) return;
		seen.add(id);
		const r = rels.find((x) => x.id === id);
		if (!r) return;
		if (r.type === "read") { out.push(r.table); return; }
		if (r.type === "join") { walk(r.left); return; } // 主链走 left (左深链)
		if (r.source) walk(r.source);
	};
	walk(nodeId);
	return out;
}

function spineOf(facts: any): string[] {
	const rels = facts.relations;
	const lines: string[] = [];
	let cur: string | undefined = facts.roots[0];
	const seen = new Set<string>();
	let guard = 0;
	let projRun = 0; // 连续 PROJECT 折叠计数
	const flushProj = () => { if (projRun > 0) { lines.push(`PROJECT${projRun > 1 ? ` ×${projRun}` : ""}`); projRun = 0; } };
	while (cur && !seen.has(cur) && guard++ < 200) {
		seen.add(cur);
		const r = rels.find((x) => x.id === cur);
		if (!r) break;
		if (r.type === "read") {
			flushProj();
			lines.push(`READ ${SHORT(r.table)}`);
		} else if (r.type === "join") {
			flushProj();
			const right = rightTables(rels, r.right);
			const cond = r.condition_display ? ` on ${r.condition_display}` : "";
			lines.push(`${r.join_type.toUpperCase()} JOIN ${right.map(SHORT).join("+")}${cond}`);
			cur = r.left; // 主链走 left (左深链)
			continue;
		} else if (r.type === "filter") {
			flushProj();
			lines.push(`FILTER ${r.predicate_display}`);
		} else if (r.type === "aggregate") {
			flushProj();
			lines.push(`AGGREGATE GROUP BY [${r.group_by.map((c: any) => c.name).join(", ")}]`);
		} else if (r.type === "expand") {
			flushProj();
			lines.push(`EXPAND (lateral: ${r.produced_columns.join(", ")})`);
		} else if (r.type === "setop") {
			flushProj();
			lines.push(`${r.setop.toUpperCase()}${r.all ? " ALL" : ""} [${r.branches.length} 分支]`);
			cur = r.branches[0]; // 主链走第一条分支 (左折叠主路径)
			continue;
		} else if (r.type === "project") {
			projRun++; // 折叠: 多层透传投影合成一条
		} else {
			flushProj();
			lines.push(`${r.type.toUpperCase()}`);
		}
		cur = r.source ?? undefined;
	}
	flushProj();
	return lines;
}

export function buildFingerprint(planFacts: any, id: string): ModelFingerprint {
	const facts = planFacts.plan ?? planFacts;
	const grain = planFacts.grain_inference ?? [];
	const rels: any[] = facts.relations;

	const inputs = [...new Set(rels.filter((r: any) => r.type === "read").map((r: any) => SHORT(r.table)))];

	const aggregates = grain
		.filter((g: any) => g.grain_candidate && g.grain_candidate.length > 0)
		.map((g: any) => `${g.node_id}: [${g.grain_candidate.join(", ")}]`);
	const knownGrains = grain
		.filter((g: any) => g.grain_candidate !== null)
		.map((g: any) => ({ node: g.node_id, grain: g.grain_candidate }));

	// 主 grain: 根节点沿 source 传播的 grain (从 grain_inference 里找根节点对应条目)
	const rootId = facts.roots[0];
	const rootGrain = grain.find((g: any) => g.node_id === rootId);

	const riskJoins = grain
		.filter((g: any) => g.cardinality === "unknown" && g.node_id.includes(".join."))
		.map((g: any) => {
			const j = rels.find((r: any) => r.id === g.node_id);
			return { node: g.node_id, right: j ? rightTables(rels, j.right).map(SHORT).join("+") : "?" };
		});

	const windowCount = rels
		.filter((r: any) => r.type === "project")
		.reduce((n, r) => n + r.expressions.filter((e: any) => e.window).length, 0);
	const caseCount = rels
		.filter((r: any) => r.type === "project")
		.reduce((n, r) => n + r.expressions.filter((e: any) => e.expr_kind === "case").length, 0);

	const unknowns = [...facts.unknowns].map((u: any) => ({
		node: u.node_id,
		field: u.field,
		reason: u.reason,
	}));

	return {
		id,
		meta: {
			dialect: facts.meta.dialect,
			contract_version: facts.meta.contract_version,
			parser_version: facts.meta.parser.version,
			generated_at: facts.meta.generated_at,
		},
		inputs,
		spine: spineOf(facts),
		transformations: {
			expand_count: rels.filter((r: any) => r.type === "expand").length,
			aggregates,
			window_count: windowCount,
			case_count: caseCount,
			filter_count: rels.filter((r: any) => r.type === "filter").length,
			project_count: rels.filter((r: any) => r.type === "project").length,
			union_count: rels.filter((r: any) => r.type === "setop").length,
		},
		known_grains: knownGrains,
		main_grain: rootGrain?.grain_candidate ?? null,
		main_grain_status: rootGrain && rootGrain.grain_candidate !== null ? "known" : "unknown",
		row_expansion_risks: riskJoins,
		key_unknowns: unknowns,
	};
}

export function renderHuman(fp: ModelFingerprint): string {
	const L: string[] = [];
	L.push(`Model Fingerprint: ${fp.id}`);
	L.push(`  契约 ${fp.meta.contract_version} / parser ${fp.meta.parser_version} / ${fp.meta.dialect}`);
	L.push(`输入模型 (${fp.inputs.length} 张物理表)`);
	for (const t of fp.inputs) L.push(`  - ${t}`);
	L.push(`主体路径 (输入→输出)`);
	for (const s of [...fp.spine].reverse()) L.push(`  ${s}`);
	L.push(`关键变形`);
	L.push(`  ${fp.transformations.expand_count} × lateral fanout / ${fp.transformations.union_count} × setop`);
	for (const a of fp.transformations.aggregates) L.push(`  AGG: ${a}`);
	L.push(`  ${fp.transformations.window_count} × window / ${fp.transformations.case_count} × CASE / ${fp.transformations.filter_count} × filter`);
	L.push(`已知 grain`);
	for (const g of fp.known_grains) L.push(`  ${g.node} = [${g.grain.join(", ")}]`);
	L.push(`主 grain: ${fp.main_grain_status === "known" ? `[${(fp.main_grain ?? []).join(", ")}]` : "unknown / 待元数据证明"}`);
	L.push(`关键 unknown (${fp.key_unknowns.length})`);
	for (const u of fp.key_unknowns) L.push(`  ${u.node} ${u.field}: ${u.reason}`);
	L.push(`扩行风险 join (${fp.row_expansion_risks.length})`);
	for (const r of fp.row_expansion_risks) L.push(`  ${r.node} → ${r.right}`);
	return L.join("\n");
}

// ---- CLI (仅直接执行时运行, 被 import 时不触发) ----
const isMain = process.argv[1] && process.argv[1].replace(/\\/g, "/").endsWith("plan-fingerprint.ts");
if (isMain) {
	const args = process.argv.slice(2);
	const file = args.find((a) => !a.startsWith("--")) ?? "output/118141/plan-facts-118141.json";
	const idArg = args.find((a) => a.startsWith("--id"));
	const id = idArg ? idArg.split("=")[1] ?? "model" : file.replace(/\.json$/, "").replace(/^plan-facts-/, "");
	const facts = JSON.parse(readFileSync(file, "utf8"));
	const fp = buildFingerprint(facts, id);
	const human = renderHuman(fp);
	console.log(human);
	mkdirSync("output/118141", { recursive: true });
	writeFileSync(`output/118141/fingerprint-${id}.json`, JSON.stringify(fp, null, 2), "utf8");
	console.log(`\n[已保存] output/118141/fingerprint-${id}.json`);
}
