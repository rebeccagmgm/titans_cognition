// golden 回归校验 —— npx tsx scripts/verification/verify-golden.ts (退出码 0=通过)
import { readFileSync } from "node:fs";
const gen = JSON.parse(readFileSync("output/118141/plan-facts-118141.json", "utf8"));
const gold = JSON.parse(readFileSync("golden/118141/plan-facts.json", "utf8"));
function comparable(doc: any): any {
	const copy = JSON.parse(JSON.stringify(doc));
	delete copy.plan?.meta?.generated_at;
	return copy;
}

console.log(
	"golden 一致性:",
	JSON.stringify(comparable(gen)) === JSON.stringify(comparable(gold))
		? "OK（忽略易变 generated_at）"
		: "FAIL 有结构差异",
);

const d = gen;
const P = d.plan, G = d.grain_inference;
const rels = P.relations;
let pass = 0, fail = 0;
const chk = (name: string, ok: boolean) => { ok ? pass++ : fail++; console.log(`${ok ? "OK" : "FAIL"} ${name}`); };
const j = (idEnd: string) => rels.find((r: any) => r.id.endsWith(idEnd)) as any;
const gi = (idEnd: string) => G.find((x: any) => x.node_id.endsWith(idEnd)) as any;

chk("47 个关系节点", rels.length === 47);
chk("9 张物理表", P.physical_inputs.length === 9);
chk("4 层嵌套 (root.project 存在)", rels.some((r: any) => r.id === "root.project"));
chk("join.1 inner/det", j("t.join.1") && j("t.join.1").join_type === "inner" && j("t.join.1").right.endsWith("read.det"));
chk("join.2..7 全部 left", ["2", "3", "4", "5", "6", "7"].every((n) => j("t.join." + n).join_type === "left"));
chk("4 个 expand", rels.filter((r: any) => r.type === "expand").length === 4);
chk("expand 全部 fanout 模型", rels.filter((r: any) => r.type === "expand").every((r: any) => {
	const g = gi(r.id);
	return g.cardinality === "unknown" && g.cardinality_effect === "fanout" && g.per_input_rows === "0..N" && g.grain_effect === "expanded";
}));
chk("actl.aggregate grain=[Contr_Id]", (() => {
	const g = G.find((x: any) => x.node_id.includes("actl.aggregate"));
	return JSON.stringify(g.grain_candidate) === '["Contr_Id"]' && g.cardinality === "non-increasing" && g.confidence === "high";
})());
chk("x.join.1 不扩行且 requires=[]", gi("x.join.1").cardinality === "non-increasing" && gi("x.join.1").confidence === "high" && gi("x.join.1").requires.length === 0);
chk("x.join.1 传播证据", gi("x.join.1").evidence.some((e: string) => e.includes("覆盖右表 grain key [Contr_Id]")));
chk("machine truth 无省略号", (() => {
	const bad: string[] = [];
	for (const r of rels) {
		if (r.type === "join" && r.condition_expr && r.condition_expr.includes("…")) bad.push(r.id);
		if (r.type === "filter" && r.predicate_expr.includes("…")) bad.push(r.id);
		if (r.type === "aggregate" && r.group_by_exprs.some((x: string) => x.includes("…"))) bad.push(r.id);
		if (r.type === "project") for (const e of r.expressions) if (e.expr_text.includes("…")) bad.push(r.id);
	}
	return bad.length === 0;
})());
chk("display 截断 20 处", (JSON.stringify(d).match(/…/g) || []).length === 20);
chk("meta 拆分", P.meta.contract_version === "1.1.0" && P.meta.adapter_version === "0.2.0" && P.meta.parser.engine === "sql-static-lineage" && P.meta.parser.version === "1.8.0");
chk("join.1 物理解析", (() => {
	const i = j("t.join.1").condition_columns.find((c: any) => c.qualifier === "info");
	const de = j("t.join.1").condition_columns.find((c: any) => c.qualifier === "det");
	return i && i.physical && i.physical[0].table === "PDATA_N.T98_OTC_DERI_COMP_SALE_INFO" && i.physical[0].column === "agt_id" && de && de.physical[0].table === "PDATA_N.T98_OTC_DERI_COMP_SALE_ADTNL_DET";
})());
chk("s_sp.CONTRACT_CODE 穿透别名", (() => {
	const c = j("t.join.2").condition_columns.find((c: any) => c.qualifier === "s_sp" && c.name === "CONTRACT_CODE");
	return c.physical && c.physical[0].column === "Inr_Comp_No";
})());
chk("End_Pric_Date 多源数组", (() => {
	const c = gi === null ? null : j("x.join.1").condition_columns.find((c: any) => c.qualifier === "t" && c.name === "End_Pric_Date");
	return c.physical && c.physical.length === 2;
})());
chk("unknowns=3 (lateral 盲区, star 已展开)", P.unknowns.length === 3);
chk("star 展开: info.project 92列", (() => {
	const p = rels.find((r: any) => r.id === "root.casttable.x.t.info.project");
	return p?.output_columns?.length === 92;
})());
chk("star 展开: m.project 60列", (() => {
	const p = rels.find((r: any) => r.id === "root.casttable.x.t.m.project");
	return p?.output_columns?.length === 60;
})());
chk("star 展开: x.project 76列 (T.*→子查询输出列)", (() => {
	const p = rels.find((r: any) => r.id === "root.casttable.x.project");
	return p?.output_columns?.length === 76;
})());
chk("ID 无重复", new Set(rels.map((r: any) => r.id)).size === rels.length);
chk("引用无悬空", rels.every((r: any) => {
	if (r.type === "join") return rels.some((x: any) => x.id === r.left) && rels.some((x: any) => x.id === r.right);
	if (["project", "filter", "aggregate", "expand"].includes(r.type)) return !r.source || rels.some((x: any) => x.id === r.source);
	return true;
}));
console.log(`--- 断言结果: ${pass} 通过, ${fail} 失败 ---`);
process.exit(fail ? 1 : 0);
