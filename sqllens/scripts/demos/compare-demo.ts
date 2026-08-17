// sqllens 还原结果 vs 原始 SQL 原文 逐字对照 —— 用 npx tsx scripts/demos/compare-demo.ts 运行
// 目的: 验证 hops 文件里的"加工"行是否就是原始 SQL 的原样切片
import { readFileSync } from "node:fs";
import { SqlSession, lineageAt, Schema } from "../../src/index.ts";
import { partSpanOf } from "../../src/ir/part-span.js";

const sql = readFileSync(
	"e:/02_area/股衍数据-数据cookbook/titans-cognition/.evidence-cache/tasksql-118141-20260814.txt",
	"utf-8",
);
const s = SqlSession.create(sql, "databricks");
const cell = s.doc.statements[1]; // SELECT 语句
const text = cell.text;

const idx = text.indexOf("Curr_Prvs_Sales_Income");
const hop = lineageAt(cell.scopes, idx, new Schema({}));
const sp = partSpanOf(hop.expr.cst);
const raw = text.slice(sp.start, sp.end);

console.log(`=== 原始 SQL 原样切片（span ${sp.start}-${sp.end}，保留原始换行缩进）===`);
console.log(raw);

const normalized = raw.replace(/\s+/g, " ").trim();
console.log("\n=== 空白归一化后（与 hops 文件 L37 同规则）===");
console.log(normalized);

// 与 hops 文件 L37"加工"行自动比对
const hopsLines = readFileSync("output/118141/sqllens-118141-hops.txt", "utf-8").split("\n");
const extracted = hopsLines[36].replace(/^\s*加工: /, ""); // L37
console.log("\n=== 自动比对 ===");
console.log("hops L37 与原文切片(归一化)完全一致:", extracted === normalized);
if (extracted !== normalized) {
	for (let i = 0; i < Math.max(extracted.length, normalized.length); i++) {
		if (extracted[i] !== normalized[i]) {
			console.log(`首个差异位置: ${i}`);
			console.log("hops 侧:", JSON.stringify(extracted.slice(Math.max(0, i - 30), i + 30)));
			console.log("原文侧:", JSON.stringify(normalized.slice(Math.max(0, i - 30), i + 30)));
			break;
		}
	}
}
