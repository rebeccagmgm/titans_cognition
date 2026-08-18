import { createHash } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { relative, resolve } from "node:path";

import { lineage, Schema, SqlSession } from "../../src/index.ts";
import { columnOrigins } from "../../src/lineage/lineage.ts";
import { resolveColumnRef } from "../../src/sema/resolve.ts";
import { buildPlanFacts } from "../plans/plan-adapter.ts";

type JsonRecord = Record<string, any>;

interface LearningStage {
	stage_no: number;
	stage_id: string;
	title: string;
}

interface LearningProfile {
	schema_version: string;
	case_id: string;
	task_id: string;
	task_role: string;
	target_field: string;
	dialect: string;
	source_sql: string;
	schema_evidence: string;
	graph_output: string;
	stages: LearningStage[];
	boundaries: string[];
}

const workspace = resolve(import.meta.dirname, "../../..");
const profilePath = resolve(workspace, process.argv[2] ?? "cases/case-learn-86840/learning-profile.json");
const outputDir = resolve(workspace, process.argv[3] ?? "output/case-learn-86840");
const profile = JSON.parse(readFileSync(profilePath, "utf8")) as LearningProfile;
const sourcePath = resolve(workspace, profile.source_sql);
const schemaEvidencePath = resolve(workspace, profile.schema_evidence);
const graphDir = resolve(workspace, profile.graph_output);

function requireFile(label: string, path: string): void {
	if (!existsSync(path)) {
		throw new Error(
			`Missing ${label}: ${relative(workspace, path).replace(/\\/g, "/")}. ` +
				"This learning case requires the referenced local evidence snapshot as a prerequisite.",
		);
	}
}

requireFile("source SQL snapshot", sourcePath);
requireFile("Schema evidence", schemaEvidencePath);

const sha256 = (value: string | Buffer): string => createHash("sha256").update(value).digest("hex");
const normalizeName = (value: string): string => value.replace(/[`"\[\]]/g, "").toLowerCase();
const json = (value: unknown): string => JSON.stringify(value, null, 2) + "\n";

function readJson(path: string): JsonRecord {
	return JSON.parse(readFileSync(path, "utf8")) as JsonRecord;
}

function readJsonl(path: string): JsonRecord[] {
	const text = readFileSync(path, "utf8").trim();
	return text ? text.split(/\r?\n/).map((line) => JSON.parse(line) as JsonRecord) : [];
}

function writeJson(name: string, value: JsonRecord): { file: string; bytes: number; sha256: string } {
	const text = json(value);
	const path = resolve(outputDir, name);
	writeFileSync(path, text, "utf8");
	return { file: name, bytes: Buffer.byteLength(text), sha256: sha256(text) };
}

function sourceLabel(source: JsonRecord): JsonRecord {
	const relation = source.source?.relation;
	return {
		kind: source.kind,
		relation: relation?.parts ?? null,
		name: source.name ?? null,
		output_columns: source.scope?.outputs ?? null,
	};
}

function scopeSummary(scope: JsonRecord, seen = new WeakSet<object>()): JsonRecord {
	if (seen.has(scope)) return { cycle: true };
	seen.add(scope);
	return {
		body_kind: scope.body?.kind ?? "unknown",
		dialect: scope.dialect,
		sources: (scope.sourceList ?? []).map((item: JsonRecord) => ({
			key: item.key,
			source: sourceLabel(item.source ?? {}),
		})),
		ctes: [...(scope.ctes ?? new Map()).entries()].map(([name, ref]: [string, JsonRecord]) => ({
			name,
			outputs: ref.scope?.outputs ?? "unknown",
		})),
		outputs: scope.outputs,
		children: (scope.children ?? []).map((child: JsonRecord) => scopeSummary(child, seen)),
	};
}

function relationOutline(relation: JsonRecord): JsonRecord {
	const expressions = relation.expressions ?? relation.measures ?? [];
	return {
		id: relation.id,
		type: relation.type,
		span: relation.span ?? null,
		output_columns: relation.output_columns ?? null,
		source: relation.source ?? null,
		left: relation.left ?? null,
		right: relation.right ?? null,
		branches: relation.branches ?? null,
		expression_count: expressions.length,
		expressions: expressions.map((expression: JsonRecord) => ({
			output: expression.output,
			expr_kind: expression.expr_kind,
			expr_text: expression.expr_text,
			star_expansion: expression.star_expansion ?? false,
			input_column_count: expression.input_columns?.length ?? 0,
		})),
		condition_expr: relation.condition_expr ?? null,
	};
}

function serializeIr(value: unknown, seen = new WeakSet<object>(), depth = 0): unknown {
	if (value === null || typeof value !== "object") return value;
	if (depth > 18) return { truncated: "IR_DEPTH_LIMIT" };
	if (seen.has(value)) return { cycle: true };
	seen.add(value);
	if (Array.isArray(value)) return value.map((item) => serializeIr(item, seen, depth + 1));
	const output: JsonRecord = {};
	for (const [key, item] of Object.entries(value)) {
		if (key === "cst" || key === "parent" || key === "analysis" || key.startsWith("_")) continue;
		output[key] = serializeIr(item, seen, depth + 1);
	}
	return output;
}

function expressionRows(plan: JsonRecord, statementIndex: number): JsonRecord[] {
	return (plan.relations ?? []).flatMap((relation: JsonRecord) => {
		const expressions = relation.expressions ?? relation.measures ?? [];
		return expressions.map((expression: JsonRecord, ordinal: number) => ({
			statement_index: statementIndex,
			relation_id: relation.id,
			relation_type: relation.type,
			ordinal,
			...expression,
		}));
	});
}

function bindingRows(targetExpressions: JsonRecord[], scopes: JsonRecord, schema: Schema): JsonRecord[] {
	return targetExpressions.flatMap((expression) =>
		((expression.input_columns ?? []) as JsonRecord[]).map((input) => ({
			...(function resolveInput(): JsonRecord {
				const parts = input.qualifier ? [input.qualifier, input.name] : [input.name];
				const resolved = resolveColumnRef(scopes, { parts, clause: input.clause } as any, schema as any);
				if (resolved.kind !== "bound") {
					return { resolution: resolved.kind, physical: [] };
				}
				return {
					resolution: "bound",
					bound_source_kind: resolved.source.kind,
					bound_column: resolved.column,
					physical: columnOrigins(resolved.source, resolved.column, schema, new Set()),
				};
			})(),
			expression_output: expression.output,
			expression: expression.expr_text,
			name: input.name,
			qualifier: input.qualifier ?? null,
			clause: input.clause ?? null,
		})),
	);
}

function readGraphSlice(): JsonRecord {
	const read = (name: string): JsonRecord[] => readJsonl(resolve(graphDir, name));
	const fields = read("field_expression_nodes.jsonl");
	const relations = read("relation_nodes.jsonl");
	const edges = read("edges.jsonl");
	const entities = read("entities.jsonl");
	const target = normalizeName(profile.target_field);
	const taskPrefix = `task:${profile.task_id}`;
	const targetFields = fields.filter(
		(item) => item.task_id === profile.task_id && normalizeName(String(item.output)) === target,
	);
	const relatedRelations = relations.filter((item) => item.task_id === profile.task_id);
	const relatedEdges = edges.filter(
		(item) =>
			item.task_id === profile.task_id ||
			String(item.from ?? "").startsWith(taskPrefix) ||
			String(item.to ?? "").startsWith(taskPrefix),
	);
	const relatedEntityIds = new Set<string>([
		...targetFields.map((item) => item.node_id),
		...relatedRelations.map((item) => item.node_id),
		...relatedEdges.flatMap((item) => [item.from, item.to].filter(Boolean)),
	]);
	const relatedEntities = entities.filter(
		(item) => relatedEntityIds.has(item.entity_id) || item.task_id === profile.task_id,
	);
	const pathsPath = resolve(graphDir, "minimal-causal-paths.json");
	const paths =
		readJson(pathsPath).paths?.filter((path: JsonRecord) => path.producerTaskId === profile.task_id) ?? [];
	return {
		status: "PARTIAL",
		reason: "只保存 86840 的图切片；消费者任务和完整指标因果路径仍在原 case 中",
		source_graph_dir: relative(workspace, graphDir).replace(/\\/g, "/"),
		counts: {
			entities: relatedEntities.length,
			relations: relatedRelations.length,
			field_expressions: targetFields.length,
			edges: relatedEdges.length,
			matching_causal_paths: paths.length,
		},
		entities: relatedEntities,
		relations: relatedRelations,
		field_expressions: targetFields,
		edges: relatedEdges,
		causal_path_references: paths.map((path: JsonRecord) => ({
			path_id: path.pathId,
			path_type: path.pathType,
			full_case_status: path.status,
			consumer_task_id: path.consumerTaskId,
			consumer_role: path.consumerRole,
			partition_resolution_status: path.partitionSlice?.resolutionStatus ?? null,
			warning: "此处只引用原 indicator case 的路径状态，未由单任务切片重新验收",
		})),
	};
}

mkdirSync(outputDir, { recursive: true });

const sourceBytes = readFileSync(sourcePath);
const sql = sourceBytes.toString("utf8");
const schemaEvidence = readJson(schemaEvidencePath);
const schemaRecords = (schemaEvidence.records ?? []).filter(
	(record: JsonRecord) => record.status === "SUCCESS" && Array.isArray(record.columns),
);
const schemaMapping = Object.fromEntries(
	schemaRecords.map((record: JsonRecord) => [
		record.qualified_name,
		Object.fromEntries(record.columns.map((column: JsonRecord) => [column.name, column.type ?? "unknown"])),
	]),
);
const schema = new Schema(schemaMapping);
const session = SqlSession.create(sql, profile.dialect as any, { schema });
const plans = session.doc.statements.map((cell, statementIndex) =>
	buildPlanFacts(cell, sql, {
		statement_index: statementIndex,
		dialect: profile.dialect,
		schema,
		include_expression_dependencies: true,
	}),
);
const targetExpressions = plans
	.flatMap((plan, statementIndex) => expressionRows(plan, statementIndex))
	.filter((expression) => normalizeName(String(expression.output ?? "")) === normalizeName(profile.target_field));
const lineageByStatement = session.doc.statements.map((cell, statementIndex) => {
	const all = lineage(cell.scopes, schema).all;
	return {
		statement_index: statementIndex,
		outputs: all.map((item) => ({
			output: item.output,
			origins: item.origins,
		})),
		target_outputs: all
			.filter((item) => normalizeName(item.output) === normalizeName(profile.target_field))
			.map((item) => ({ output: item.output, origins: item.origins })),
	};
});
const planUnknowns = plans.flatMap((plan) => plan.unknowns);
const actionablePlanUnknowns = planUnknowns.filter(
	(unknown) => !(unknown.field === "output_columns" && String(unknown.reason ?? "").includes("star/匿名投影")),
);
const planStatus = actionablePlanUnknowns.length > 0 ? "PARTIAL" : "SUCCESS_WITH_NOT_APPLICABLE";

const written: Array<{
	stage_no: number;
	stage_id: string;
	title: string;
	file: string;
	bytes: number;
	sha256: string;
	status: string;
}> = [];
function stage(stageNo: number, stageId: string, title: string, status: string, output: JsonRecord): void {
	const result = writeJson(`${String(stageNo).padStart(2, "0")}-${stageId}.json`, {
		schema_version: "case-learning-stage-v1",
		case_id: profile.case_id,
		stage_no: stageNo,
		stage_id: stageId,
		title,
		status,
		output,
	});
	written.push({ stage_no: stageNo, stage_id: stageId, title, ...result, status });
}

stage(1, "input", "输入与证据", "SUCCESS", {
	task_id: profile.task_id,
	task_role: profile.task_role,
	target_field: profile.target_field,
	source_sql: relative(workspace, sourcePath).replace(/\\/g, "/"),
	source_sha256: sha256(sourceBytes),
	byte_length: sourceBytes.length,
	schema_evidence: {
		path: relative(workspace, schemaEvidencePath).replace(/\\/g, "/"),
		sha256: sha256(readFileSync(schemaEvidencePath)),
		record_count: schemaRecords.length,
	},
	boundaries: profile.boundaries,
});

stage(2, "parse", "SQL 解析", session.doc.errors === 0 ? "SUCCESS" : "PARTIAL", {
	dialect: profile.dialect,
	statement_count: session.doc.statements.length,
	document_errors: session.doc.errors,
	document_diagnostics: session.doc.diagnostics,
	statements: session.doc.statements.map((cell, statementIndex) => ({
		statement_index: statementIndex,
		span: cell.span,
		text_length: cell.text.length,
		errors: cell.errors,
		diagnostics: cell.diagnostics,
	})),
});

stage(3, "ir", "IR / 关系结构", planStatus, {
	method: "sql-static-lineage QueryExpr IR plus plan-adapter relation outline",
	statements: plans.map((plan, statementIndex) => ({
		statement_index: statementIndex,
		parser_ir: serializeIr(session.doc.statements[statementIndex].ast),
		root_relations: plan.roots,
		physical_inputs: plan.physical_inputs,
		relation_count: plan.relations.length,
		relations: plan.relations.map(relationOutline),
		unknowns: plan.unknowns,
	})),
});

stage(4, "scope", "Scope 作用域", "SUCCESS", {
	statements: session.doc.statements.map((cell, statementIndex) => ({
		statement_index: statementIndex,
		scope: scopeSummary(cell.scopes.root),
	})),
});

stage(5, "binding", "Binding 列绑定", targetExpressions.length > 0 ? "SUCCESS" : "PARTIAL", {
	target_field: profile.target_field,
	expression_count: targetExpressions.length,
	expressions: targetExpressions.map((expression) => ({
		relation_id: expression.relation_id,
		relation_type: expression.relation_type,
		output: expression.output,
		expr_text: expression.expr_text,
		input_columns: bindingRows(
			[expression],
			session.doc.statements[expression.statement_index].scopes.root,
			schema,
		),
	})),
	interpretation: "resolution/physical 是静态解析结果；缺失或多源必须继续作为 Unknown/歧义处理",
});

stage(
	6,
	"lineage",
	"Lineage 字段血缘",
	lineageByStatement.some((item) => item.target_outputs.length > 0) ? "SUCCESS" : "PARTIAL",
	{
		target_field: profile.target_field,
		statements: lineageByStatement,
		interpretation: "origins 表示输出值依赖的基表字段，不表示行集过滤或业务正确性",
	},
);

stage(7, "plan-facts", "Logical Plan Facts", planStatus, {
	method: "buildPlanFacts",
	parser: plans[0]?.meta?.parser ?? null,
	contract: plans[0]?.meta ?? null,
	unknown_summary: {
		total: planUnknowns.length,
		actionable: actionablePlanUnknowns.length,
		not_applicable: planUnknowns.length - actionablePlanUnknowns.length,
	},
	plans,
});

let graphSlice: JsonRecord;
try {
	graphSlice = readGraphSlice();
} catch (error) {
	graphSlice = {
		status: "NOT_AVAILABLE",
		error: error instanceof Error ? error.message : String(error),
		message: "请先生成 indicator-processing-graph 输出，再重跑本学习 case",
	};
}
stage(8, "graph-slice", "Processing Graph 切片", graphSlice.status, graphSlice);

const guide =
	[
		"# case-learn-86840 学习入口",
		"",
		"按编号阅读 01 → 08；每一步先看 `output`，再回到对应 SQL/源码核对证据。",
		"",
		...written.map((item) => `${item.stage_no}. [${item.title}](./${item.file}) — ${item.status}`),
		"",
		"## 建议提问",
		"",
		"- 02：SQL 是否完整解析？哪里有诊断？",
		"- 03：关系树中 read/project/join/filter/aggregate 怎么连接？",
		"- 04：当前查询块能看到哪些表和别名？",
		"- 05：dyna_nom_prin 的每个输入字段绑定到哪张物理表？",
		"- 06：dyna_nom_prin 的 origins 是哪些基表列？",
		"- 07：plan facts 比 sql-static-lineage 原始结果多保存了哪些事实？",
		"- 08：86840 在跨任务图中留下了哪些边，哪些仍不完整？",
	].join("\n") + "\n";
writeFileSync(resolve(outputDir, "README.md"), guide, "utf8");

const manifest = {
	schema_version: "case-learning-manifest-v1",
	case_id: profile.case_id,
	status: written.some((item) => item.status === "NOT_AVAILABLE") ? "PARTIAL" : "SUCCESS_WITH_BOUNDARIES",
	profile: relative(workspace, profilePath).replace(/\\/g, "/"),
	profile_sha256: sha256(readFileSync(profilePath)),
	stage_count: written.length,
	stages: written,
	boundaries: profile.boundaries,
	not_claimed: ["complete_indicator_journey", "business_correctness", "runtime_execution", "business_acceptance"],
};
writeFileSync(resolve(outputDir, "learning-manifest.json"), json(manifest), "utf8");
console.log(
	JSON.stringify({ output: relative(workspace, outputDir), status: manifest.status, stages: written }, null, 2),
);
