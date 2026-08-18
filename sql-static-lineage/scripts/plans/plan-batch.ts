// ============================================================================
// 横向样本批量跑批 —— Model Fingerprint 跨 SQL 比较
//
// 样本: .evidence-cache 中 szdata task-sql 拉取的任务 SQL (无 schema 模式:
//       结构事实 + grain 推断照常, physical 解析降级为 unknown)
// 用法: npx tsx scripts/plans/plan-batch.ts
// 输出: output/horizon/plan-facts-<id>.json + output/horizon/fingerprint-<id>.json + 对比表
// ============================================================================
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { SqlSession } from "../../src/index.ts";
import { buildPlanFacts, inferGrain } from "./plan-adapter.ts";
import type { PlanFacts } from "./plan-contract.ts";
import { buildFingerprint, renderHuman, type ModelFingerprint } from "./plan-fingerprint.ts";

const EVIDENCE = "e:/02_area/股衍数据-数据cookbook/titans-cognition/.evidence-cache";
const OUT = "output/horizon";
mkdirSync(OUT, { recursive: true });

// 样本清单: id + 缓存文件 + 形态备注
const SAMPLES: { id: string; file: string; note: string }[] = [
	{ id: "71698", file: "tasksql-71698-20260815003408.txt", note: "SELECT 单表 (Oracle 采集)" },
	{ id: "146685", file: "tasksql-146685-20260815010447.txt", note: "SELECT 单表 ref_book" },
	{ id: "78477", file: "tasksql-78477-20260815010451.txt", note: "SELECT 单表 40+列" },
	{ id: "245220", file: "tasksql-245220-20260815014315.txt", note: "SELECT UNION ALL 双表 (模板表名)" },
	{ id: "144141", file: "tasksql-144141-20260815010452.txt", note: "INSERT OVERWRITE 简单" },
	{ id: "62517", file: "tasksql-62517-20260815014313.txt", note: "INSERT OVERWRITE" },
	{ id: "71734", file: "tasksql-71734-20260815010506.txt", note: "INSERT OVERWRITE 拷贝" },
	{ id: "144167", file: "tasksql-144167-20260815010509.txt", note: "INSERT OVERWRITE 38列" },
	{ id: "160423", file: "tasksql-160423-20260815010504.txt", note: "INSERT OVERWRITE 40列" },
	{ id: "71703", file: "tasksql-71703-20260815010501.txt", note: "INSERT OVERWRITE UNION 复杂" },
	{ id: "244357", file: "tasksql-244357-20260815014314.txt", note: "CREATE+INSERT+UNION 16KB" },
];

const DIALECTS = ["databricks", "trino", "mysql", "postgres"];

interface RunResult {
	id: string;
	note: string;
	ok: boolean;
	dialect?: string;
	error?: string;
	fp?: ModelFingerprint;
}

/**
 * 等长模板渲染: Horae 模板变量 ${yyyyMM} / ${yyyyMM,-1M} 等折叠为下划线形式。
 * 长度保持不变 → statement span 不错位; 同时规避 sql-static-lineage 对模板表名静默丢 union 的缺陷。
 * 例: trd_deal_${yyyyMM}_h → trd_deal___yyyyMM__h (仍可辨认为模板位)。
 */
function renderTemplateKeepSpan(sql: string): string {
	return sql.replace(/\$\{([^}]*)\}/g, (_m, inner: string) => {
		const body = inner.replace(/[^A-Za-z0-9_]/g, "_");
		return `__${body}_`;
	});
}

function runSample(s: { id: string; file: string; note: string }): RunResult {
	const raw = readFileSync(`${EVIDENCE}/${s.file}`, "utf-8");
	const sql = renderTemplateKeepSpan(raw);
	for (const d of DIALECTS) {
		let sess: SqlSession;
		try {
			sess = SqlSession.create(sql, d);
		} catch {
			continue;
		}
		const n = sess.doc.statements.length;
		// 选"实质节点最多"的 statement (read/project/filter/join/aggregate/expand/setop),
		// 排除 other 兜底节点 (pipe 等未建模 body 不算数); 从后往前, 同分取靠后
		let best: { i: number; facts: PlanFacts; score: number } | null = null;
		for (let i = n - 1; i >= 0; i--) {
			try {
				const facts = buildPlanFacts(sess.doc.statements[i], sql, { statement_index: i });
				const score = facts.relations.filter((r) => r.type !== "other").length;
				if (score === 0) continue;
				if (!best || score >= best.score) best = { i, facts, score };
			} catch {
				// 尝试其他 statement
			}
		}
		if (!best) continue;
		const { facts } = best;
		const grain = inferGrain(facts);
		const doc = { plan: facts, grain_inference: grain };
		writeFileSync(`${OUT}/plan-facts-${s.id}.json`, JSON.stringify(doc, null, 2), "utf8");
		const fp = buildFingerprint(doc, s.id);
		writeFileSync(`${OUT}/fingerprint-${s.id}.json`, JSON.stringify(fp, null, 2), "utf8");
		return { id: s.id, note: s.note, ok: true, dialect: d, fp };
	}
	return { id: s.id, note: s.note, ok: false, error: "所有方言/statement 均失败" };
}

const results = SAMPLES.map(runSample);

// ---- 对比表 ----
console.log("=".repeat(120));
console.log("Model Fingerprint 横向对比 (无 schema 模式, physical 解析降级为 unknown)");
console.log("=".repeat(120));
const H = (t: string, w: number) => t.padEnd(w);
console.log(
	H("id", 10) + H("形态", 34) + H("dialect", 10) + H("节点", 5) + H("表", 5) +
	H("expand", 7) + H("agg", 6) + H("window", 7) + H("case", 5) + H("union", 6) +
	H("主grain", 16) + H("knownGrain", 12) + H("unknown", 7) + "spine 摘要",
);
console.log("-".repeat(120));
for (const r of results) {
	if (!r.ok || !r.fp) {
		console.log(H(r.id, 10) + H(r.note, 34) + "FAIL: " + r.error);
		continue;
	}
	const f = r.fp;
	const spineShort = f.spine.slice(-6).map((x) => x.replace(/ on .*/, "")).join(" → ");
	console.log(
		H(r.id, 10) + H(r.note.slice(0, 32), 34) + H(r.dialect ?? "", 10) +
		H(String(f.spine.length), 5) +
		H(String(f.inputs.length), 5) +
		H(String(f.transformations.expand_count), 7) +
		H(String(f.transformations.aggregates.length), 6) +
		H(String(f.transformations.window_count), 7) +
		H(String(f.transformations.case_count), 5) +
		H(String(f.transformations.union_count), 6) +
		H(f.main_grain_status === "known" ? `[${f.main_grain?.join(",")}]` : "unknown", 16) +
		H(String(f.known_grains.length), 12) +
		H(String(f.key_unknowns.length), 7) +
		spineShort,
	);
}
console.log("=".repeat(120));

// ---- 详细 human 版 ----
for (const r of results) {
	if (!r.ok || !r.fp) {
		console.log(`\n### ${r.id} FAILED: ${r.error}`);
		continue;
	}
	console.log(`\n### ${r.id} (${r.note})`);
	console.log(renderHuman(r.fp));
}
