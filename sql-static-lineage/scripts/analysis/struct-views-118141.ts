// 118141 全量结构视图 —— 递归 scope 树, 每层输出 clausesOf 清单
// 用 npx tsx struct-views-118141.ts 运行 → 输出 struct-views-118141.txt
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { SqlSession } from "../../src/index.ts";

const sql = readFileSync(
	"e:/02_area/股衍数据-数据cookbook/titans-cognition/.evidence-cache/tasksql-118141-20260814.txt",
	"utf-8",
);
const s = SqlSession.create(sql, "databricks");
const cell = s.doc.statements[1];
const root = cell.scopes.root;

const out: string[] = [];
const log = (x: string) => out.push(x);

const seen = new WeakSet<any>();
function dump(scope: any, tag: string, depth: number): void {
	if (seen.has(scope)) return;
	seen.add(scope);
	const pad = "  ".repeat(depth);
	const body = scope.body as any;
	const outs = Array.isArray(scope.outputs)
		? `${scope.outputs.length}列(${scope.outputs.slice(0, 4).join(",")}${scope.outputs.length > 4 ? ",..." : ""})`
		: String(scope.outputs);
	log(`${pad}■ ${tag} body=${body?.kind} out=${outs}`);
	const clauses = s.doc.clausesOf(scope);
	if (clauses.length === 0) {
		log(`${pad}  clauses: (无)`);
	} else {
		for (const c of clauses) {
			const anchor = sql.slice(c.anchorSpan.start, c.anchorSpan.end);
			const full = sql.slice(c.span.start, c.span.end).replace(/\s+/g, " ").slice(0, 90);
			log(`${pad}  [${c.kind}] 锚点"${anchor}" : ${full}${full.length >= 90 ? "..." : ""}`);
		}
	}
	// 递归子查询源
	for (const [k, v] of scope.sources ?? []) {
		if (v.kind === "subquery" && v.scope) dump(v.scope, `└─ 子查询 "${k}"`, depth + 1);
	}
	// 递归其他子 scope（CTE / 表达式子查询等）
	for (const c of scope.children ?? []) {
		const isSrc = [...(scope.sources?.values() ?? [])].some((v: any) => v.scope === c);
		if (!isSrc && !seen.has(c)) dump(c, "└─ (其他子块)", depth + 1);
	}
}

log("118141 全量结构视图（clausesOf 递归 scope 树）\n");
dump(root, "主查询", 0);

mkdirSync("output/118141", { recursive: true });
writeFileSync("output/118141/struct-views-118141.txt", out.join("\n"), "utf8");
console.log(out.join("\n"));
console.log("\n[已保存] struct-views-118141.txt");
