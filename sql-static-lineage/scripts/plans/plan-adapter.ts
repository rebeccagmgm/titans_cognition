// ============================================================================
// plan-adapter —— 薄 adapter: sql-static-lineage scope 树 → Logical Plan Facts (JSON)
//
// 不做任何解析: 原料全部来自 sql-static-lineage 已建模的 IR + scope:
//   - 每个 query scope → read*/join*/filter?/aggregate?/project 节点链
//   - 子查询源递归展开, 父节点引用子图根 (project) id
//   - unknown 显式标注: star 层 outputs、未建模 body、缺 schema 的列
//
// v1.1 (2026-08-15):
//   - 原文不截断: *_expr / expr_text 完整原文, *_display / display_text 截断预览
//   - ColumnRef.physical: 接 schema 后用 lineageAt 解析到基表 (数组, 多源可能)
//   - inferGrain + propagateGrain: aggregate 的 grain key 沿 plan 传播,
//     join 右表 key 被连接条件覆盖时可判定不扩行 (无需外部元数据)
//   - expand: fanout 模型 (cardinality_effect/per_input_rows/grain_effect),
//     不再用 non-decreasing
//
// 坐标系: cell 内 IR 的 cst 是 CELL-RELATIVE (见 document.ts nodeAt);
//          本文件所有 span/offset 平移 cellBase 后为 DOCUMENT 坐标。
// ============================================================================
import { readFileSync } from "node:fs";
import type { Scope, ScopeTree } from "../../src/scope/scope.js";
import { resolveColumnSource } from "../../src/sema/resolve.js";
import type { SchemaProvider } from "../../src/qualify/schema-provider.js";
import type {
	AggregateRelation,
	ColumnRef,
	ExpandRelation,
	ExpressionFacts,
	FilterRelation,
	GrainInference,
	JoinRelation,
	PlanFacts,
	PlanRelation,
	ProjectRelation,
	ReadRelation,
	SetopRelation,
	SourceSpan,
} from "./plan-contract.js";
import type { SelectExpr, Expr } from "../../src/ir/ir.js";
import { lineageAt } from "../../src/lineage/hops.js";

// ---------------------------------------------------------------------------
// helpers
// ---------------------------------------------------------------------------

/** IR 节点 (cell 坐标) → 文档坐标 SourceSpan。 */
function spanOf(
	cellBase: number,
	node: { start?: { start: number }; stop?: { stop: number } } | null | undefined,
): SourceSpan {
	if (!node?.start || !node?.stop) return { start: cellBase, end: cellBase };
	return { start: cellBase + node.start.start, end: cellBase + node.stop.stop + 1 };
}

const DISPLAY_MAX = 120;
/** 完整原文 (machine truth)。 */
function fullTextOf(
	sql: string,
	cellBase: number,
	node: { start?: { start: number }; stop?: { stop: number } } | null | undefined,
): string {
	const s = spanOf(cellBase, node);
	return sql.slice(s.start, s.end).replace(/\s+/g, " ").trim();
}
/** 截断预览 (人看)。 */
function displayTextOf(
	sql: string,
	cellBase: number,
	node: { start?: { start: number }; stop?: { stop: number } } | null | undefined,
): string {
	const t = fullTextOf(sql, cellBase, node);
	return t.length > DISPLAY_MAX ? t.slice(0, DISPLAY_MAX) + "…" : t;
}

/** 递归提取表达式树里的列引用 (IR Expr 遍历), 携带列名 token 的 cell 偏移供物理解析。 */
function collectColumns(e: Expr | null | undefined, clause: ColumnRef["clause"], out: ColumnRef[]): void {
	if (!e) return;
	switch (e.kind) {
		case "column":
			out.push({
				name: e.parts[e.parts.length - 1] ?? "?",
				qualifier: e.parts.length > 1 ? e.parts[0] : undefined,
				clause,
				physical: null, // 由 resolvePhysical 填充
				_cellOffset: e.partSpans?.[0]?.start, // 列名 token 起点 (cell 坐标)
			} as ColumnRef & { _cellOffset?: number });
			return;
		case "binary":
			collectColumns(e.left, clause, out);
			collectColumns(e.right, clause, out);
			return;
		case "unary":
			collectColumns(e.operand, clause, out);
			return;
		case "function":
			for (const a of e.args) collectColumns(a, clause, out);
			return;
		case "case":
			for (const w of e.whens) {
				collectColumns(w.when, clause, out);
				collectColumns(w.then, clause, out);
			}
			if (e.elseExpr) collectColumns(e.elseExpr, clause, out);
			return;
		case "cast":
			collectColumns(e.expr, clause, out);
			return;
		case "predicate":
			collectColumns(e.operand, clause, out);
			for (const a of e.args ?? []) collectColumns(a, clause, out);
			return;
		case "subscript":
			collectColumns(e.base, clause, out);
			if (e.index) collectColumns(e.index, clause, out);
			return;
		default:
			return;
	}
}

type RefWithOffset = ColumnRef & { _cellOffset?: number };

/**
 * Resolve a source table from SQL structure alone when the scope has exactly
 * one eligible physical table, or when a qualifier names one explicitly.
 * This is a candidate binding: without Schema Evidence the column's
 * existence is not verified.
 */
function sqlCandidateFor(ref: ColumnRef, scope: Scope): { table: string; column: string }[] | null {
	const qualified = ref.qualifier
		? [...scope.sources.entries()].find(([key]) => key.toLowerCase() === ref.qualifier!.toLowerCase())?.[1]
		: undefined;
	if (qualified?.kind === "table" && qualified.source?.relation?.fqn) {
		return [{ table: qualified.source.relation.fqn, column: ref.name }];
	}
	if (ref.qualifier) return null;
	const tables = [...scope.sources.values()]
		.filter((source: any) => source.kind === "table" && source.source?.relation?.fqn)
		.map((source: any) => String(source.source.relation.fqn));
	return tables.length === 1 ? [{ table: tables[0]!, column: ref.name }] : null;
}

function schemaContainsField(schema: unknown, table: string, column: string, dialect: string): boolean {
	const provider = schema as { columnsFor?: (parts: string[], dialect?: string) => Array<{ name?: string }> | undefined } | null;
	const columns = provider?.columnsFor?.(table.split("."), dialect);
	return Array.isArray(columns) && columns.some((candidate) => candidate.name?.toLowerCase() === column.toLowerCase());
}

type DerivedOutputResolution =
	{ kind: "PHYSICAL"; physical: { table: string; column: string }[] }
	| { kind: "SQL_CANDIDATE"; candidates: { table: string; column: string }[] }
	| { kind: "DERIVED_OUTPUT" }
	| null;

type DerivedOutputResolver = (scope: Scope, name: string) => DerivedOutputResolution;

/** Resolve one output column through a UNION/UNION ALL subquery boundary. */
function resolveSetopOutput(
	cell: { scopes: ScopeTree },
	schema: unknown,
	scope: Scope,
	name: string,
	resolveDerivedOutput?: DerivedOutputResolver,
): DerivedOutputResolution {
	if (scope.body.kind === "setop") {
		if (!scope.branches) return null;
		const branches = [scope.branches.left, scope.branches.right];
		const resolutions = branches.map((branch) =>
			resolveDerivedOutput?.(branch, name) ?? resolveSetopOutput(cell, schema, branch, name, resolveDerivedOutput),
		);
		if (resolutions.some((resolution) => resolution === null)) return null;
		const physical = resolutions.flatMap((resolution) =>
			resolution?.kind === "PHYSICAL" ? resolution.physical : [],
		);
		const candidates = resolutions.flatMap((resolution) =>
			resolution?.kind === "SQL_CANDIDATE" ? resolution.candidates : [],
		);
		if (physical.length > 0 && candidates.length > 0) {
			const seen = new Set<string>();
			return {
				kind: "SQL_CANDIDATE",
				candidates: [...physical, ...candidates].filter((item) => {
					const key = `${item.table}.${item.column}`.toLowerCase();
					if (seen.has(key)) return false;
					seen.add(key);
					return true;
				}),
			};
		}
		if (physical.length > 0) {
			const seen = new Set<string>();
			return {
				kind: "PHYSICAL",
				physical: physical.filter((item) => {
					const key = `${item.table}.${item.column}`.toLowerCase();
					if (seen.has(key)) return false;
					seen.add(key);
					return true;
				}),
			};
		}
		if (candidates.length > 0) {
			const seen = new Set<string>();
			return {
				kind: "SQL_CANDIDATE",
				candidates: candidates.filter((item) => {
					const key = `${item.table}.${item.column}`.toLowerCase();
					if (seen.has(key)) return false;
					seen.add(key);
					return true;
				}),
			};
		}
		return { kind: "DERIVED_OUTPUT" };
	}
	if (scope.body.kind !== "select" || !Array.isArray(scope.outputs)) return null;
	const ordinal = scope.outputs.findIndex((output) => output.toLowerCase() === name.toLowerCase());
	const projection = ordinal >= 0 ? scope.body.projections[ordinal] : undefined;
	if (!projection) return null;
	if (projection.expr.kind === "literal") return { kind: "DERIVED_OUTPUT" };
	if (projection.expr.kind !== "column" || projection.expr.partSpans?.[0]?.start == null) return null;
	const hop = lineageAt(cell.scopes, projection.expr.partSpans[0].start, schema as never);
	if (hop && hop.terminal !== "unresolved" && hop.terminal && hop.terminal.every((origin) =>
		schemaContainsField(schema, origin.table.join("."), origin.column, cell.scopes.root.dialect)
	)) {
		return {
			kind: "PHYSICAL",
			physical: hop.terminal.map((origin) => ({ table: origin.table.join("."), column: origin.column })),
		};
	}
	const parts = projection.expr.parts;
	const candidate = sqlCandidateFor({
		name: parts[parts.length - 1] ?? name,
		qualifier: parts.length > 1 ? parts[0] : undefined,
		clause: "projection",
		physical: null,
	}, scope);
	return candidate ? { kind: "SQL_CANDIDATE", candidates: candidate } : null;
}

/** 直接遍历 sql-static-lineage IR，保留连接/过滤/表达式判断所需的结构事实。 */
function expressionFacts(e: Expr | null | undefined): ExpressionFacts {
	const operators = new Set<string>();
	const literals = new Set<string>();
	const functions = new Set<string>();
	const predicates = new Map<string, { operator: string; negated: boolean }>();
	const comparisons: ExpressionFacts["comparisons"] = [];
	const collectLiterals = (node: Expr | null | undefined, out: string[]): void => {
		if (!node) return;
		if (node.kind === "literal") {
			out.push(node.text);
			return;
		}
		if (node.kind === "binary") {
			collectLiterals(node.left, out);
			collectLiterals(node.right, out);
		} else if (node.kind === "unary") collectLiterals(node.operand, out);
		else if (node.kind === "function") for (const arg of node.args) collectLiterals(arg, out);
		else if (node.kind === "case") {
			for (const branch of node.whens) {
				collectLiterals(branch.when, out);
				collectLiterals(branch.then, out);
			}
			collectLiterals(node.elseExpr, out);
		} else if (node.kind === "cast") collectLiterals(node.expr, out);
		else if (node.kind === "predicate") {
			collectLiterals(node.operand, out);
			for (const arg of node.args) collectLiterals(arg, out);
		}
	};
	const visit = (node: Expr | null | undefined): void => {
		if (!node) return;
		switch (node.kind) {
			case "literal":
				literals.add(node.text);
				return;
			case "binary":
				operators.add(node.op.toLowerCase());
				if (["=", "!=", "<>", "<", "<=", ">", ">="].includes(node.op.toLowerCase())) {
					const refs: ColumnRef[] = [];
					const comparisonLiterals: string[] = [];
					collectColumns(node, "where", refs);
					collectLiterals(node, comparisonLiterals);
					comparisons.push({
						operator: node.op.toLowerCase(),
						columns: [...new Set(refs.map((ref) => ref.name.toLowerCase()))],
						literals: [...new Set(comparisonLiterals)],
					});
				}
				visit(node.left);
				visit(node.right);
				return;
			case "unary":
				operators.add(node.op.toLowerCase());
				visit(node.operand);
				return;
			case "function":
				functions.add(node.name.toLowerCase());
				for (const arg of node.args) visit(arg);
				return;
			case "case":
				for (const branch of node.whens) {
					visit(branch.when);
					visit(branch.then);
				}
				visit(node.elseExpr);
				return;
			case "cast":
				visit(node.expr);
				return;
			case "predicate": {
				const operator = node.op.toLowerCase();
				predicates.set(`${operator}:${node.negated}`, { operator, negated: node.negated });
				visit(node.operand);
				for (const arg of node.args) visit(arg);
				return;
			}
			case "subscript":
				visit(node.base);
				visit(node.index);
				visit(node.end);
				visit(node.step);
				return;
			case "lambda":
				visit(node.body);
				return;
			default:
				return;
		}
	};
	visit(e);
	return {
		operators: [...operators],
		literals: [...literals],
		functions: [...functions],
		predicates: [...predicates.values()],
		comparisons,
	};
}

/** 物理解析: 用 sql-static-lineage lineageAt 把列引用追到基表 (喂 schema 后)。
 *  锚定用 IR partSpans[0] (列名 token 的 cell 坐标) —— nodeAt 是裸数值比较,
 *  必须精确落在列名 token 上, 否则会命中父表达式/别名 (错位解析)。
 *  注意: lineageAt 返回的 hop.terminal 可能为 undefined (followColumn 无来源),
 *  此时列保持 physical=null, 并由调用方记入 unknowns。 */
function resolvePhysical(
	cell: { scopes: ScopeTree },
	schema: unknown,
	scope: Scope,
	nodeId: string,
	refs: ColumnRef[],
	unknownSink: { node_id: string; field: string; reason: string; span?: SourceSpan }[],
	dialect: string,
	resolveDerivedOutput?: DerivedOutputResolver,
): void {
	const schemaHasColumn = (table: string[], column: string): boolean => {
		const provider = schema as { columnsFor?: (parts: string[], dialect?: string) => Array<{ name?: string }> | undefined };
		const columns = provider.columnsFor?.(table, dialect);
		return Array.isArray(columns) && columns.some((candidate) => candidate.name?.toLowerCase() === column.toLowerCase());
	};
	const sourceFor = (qualifier: string): any => {
		for (const [key, source] of scope.sources) {
			if (key.toLowerCase() === qualifier.toLowerCase()) return source;
		}
		return undefined;
	};
	for (const ref of refs) {
		const withOff = ref as RefWithOffset;
		if (withOff._cellOffset == null) continue;
		if (ref.qualifier) {
			const source = sourceFor(ref.qualifier);
			if (
				source?.kind === "lateral" &&
				Array.isArray(source.source?.columns) &&
				source.source.columns.some((column: string) => column.toLowerCase() === ref.name.toLowerCase())
			) {
				ref.resolution = "DERIVED_OUTPUT";
				ref.derived_from = `LATERAL_OUTPUT:${ref.qualifier}.${ref.name}`;
				delete withOff._cellOffset;
				continue;
			}
			// CTEs and parenthesized derived tables expose the same output
			// boundary. Keep both on the adapter path so CTE references do not
			// fall back to lineageAt and get misreported as a lateral blind spot.
			const sourceScope = source?.kind === "subquery"
				? source.scope
				: source?.kind === "cte" ? source.ref.scope : undefined;
			const sourceOutputs = sourceScope?.outputs;
			if (
				sourceScope &&
				sourceScope.body.kind !== "setop"
			) {
				const derived = resolveDerivedOutput?.(sourceScope, ref.name);
				if (derived?.kind === "PHYSICAL") {
					ref.physical = derived.physical;
					ref.resolution = "PHYSICAL";
					delete withOff._cellOffset;
					continue;
				}
				if (derived?.kind === "SQL_CANDIDATE") {
					ref.sql_candidate = derived.candidates;
					ref.resolution = "SQL_CANDIDATE";
					delete withOff._cellOffset;
					continue;
				}
				if (derived?.kind === "DERIVED_OUTPUT") {
					ref.resolution = "DERIVED_OUTPUT";
					ref.derived_from = `SUBQUERY_OUTPUT:${ref.qualifier}.${ref.name}`;
					delete withOff._cellOffset;
					continue;
				}
			}
			if (
				sourceScope?.body.kind === "setop" &&
				(Array.isArray(sourceOutputs) ? sourceOutputs.some((output: string) => output.toLowerCase() === ref.name.toLowerCase()) : true)
			) {
				const derived = resolveSetopOutput(cell, schema, sourceScope, ref.name, resolveDerivedOutput);
				if (derived?.kind === "PHYSICAL") {
					ref.physical = derived.physical;
					ref.resolution = "PHYSICAL";
					delete withOff._cellOffset;
					continue;
				}
				if (derived?.kind === "SQL_CANDIDATE") {
					ref.sql_candidate = derived.candidates;
					ref.resolution = "SQL_CANDIDATE";
					delete withOff._cellOffset;
					continue;
				}
				if (derived?.kind === "DERIVED_OUTPUT") {
					ref.resolution = "DERIVED_OUTPUT";
					ref.derived_from = `SETOP_OUTPUT:${ref.qualifier}.${ref.name}`;
					delete withOff._cellOffset;
					continue;
				}
			}
		}
		if (!ref.qualifier && scope.sources.size === 1) {
			const onlySource = [...scope.sources.values()][0];
			if (onlySource?.kind === "subquery" || onlySource?.kind === "cte") {
				const onlySourceScope = onlySource.kind === "subquery" ? onlySource.scope : onlySource.ref.scope;
				const derived = onlySourceScope.body.kind === "setop"
					? resolveSetopOutput(cell, schema, onlySourceScope, ref.name, resolveDerivedOutput)
					: resolveDerivedOutput?.(onlySourceScope, ref.name);
				if (derived?.kind === "PHYSICAL") {
					ref.physical = derived.physical;
					ref.resolution = "PHYSICAL";
					delete withOff._cellOffset;
					continue;
				}
				if (derived?.kind === "SQL_CANDIDATE") {
					ref.sql_candidate = derived.candidates;
					ref.resolution = "SQL_CANDIDATE";
					delete withOff._cellOffset;
					continue;
				}
				if (derived?.kind === "DERIVED_OUTPUT") {
					ref.resolution = "DERIVED_OUTPUT";
					ref.derived_from = `SUBQUERY_OUTPUT:${ref.name}`;
					delete withOff._cellOffset;
					continue;
				}
			}
		}
		if (!ref.qualifier) {
			const bound = resolveColumnSource(scope, [ref.name], schema as SchemaProvider);
			if (bound?.source.kind === "lateral") {
				ref.resolution = "DERIVED_OUTPUT";
				ref.derived_from = `LATERAL_OUTPUT:${bound.source.source.alias ?? ref.name}.${ref.name}`;
				delete withOff._cellOffset;
				continue;
			}
		}
		const hop = lineageAt(cell.scopes, withOff._cellOffset, schema as never);
		if (hop && hop.terminal !== "unresolved" && hop.terminal && hop.terminal.every((output) => schemaHasColumn(output.table, output.column))) {
			ref.physical = hop.terminal.map((o) => ({ table: o.table.join("."), column: o.column }));
			ref.resolution = "PHYSICAL";
		} else {
			const candidate = sqlCandidateFor(ref, scope);
			if (candidate) {
				ref.sql_candidate = candidate;
				ref.resolution = "SQL_CANDIDATE";
				delete withOff._cellOffset;
				continue;
			}
			const why = !hop
				? "锚定失败"
				: hop.terminal === "unresolved"
					? "sql-static-lineage 判定 unresolved (列不在 schema/绑定失败)"
					: Array.isArray(hop.terminal) && !hop.terminal.every((output) => schemaHasColumn(output.table, output.column))
						? "lineage 已找到候选基表，但当前 schema 快照缺少字段证据"
						: "followColumn 无来源 (sql-static-lineage 对 lateral 子查询别名列盲区)";
			ref.resolution = "UNRESOLVED";
			unknownSink.push({
				node_id: nodeId,
				field: "physical",
				reason: `${ref.qualifier ? ref.qualifier + "." : ""}${ref.name} 无法解析到基表: ${why}`,
			});
		}
		delete withOff._cellOffset; // 解析完清除中间值 (不进 JSON)
	}
}

// ---------------------------------------------------------------------------
// adapter 主体
// ---------------------------------------------------------------------------

export interface PlanAdapterOptions {
	statement_index?: number;
	adapter_version?: string;
	/** 可选 schema (sql-static-lineage Schema 实例), 提供后条件列 physical 解析启用。 */
	schema?: unknown;
	/** 方言 (用于 schema 列折叠), 默认 databricks。 */
	dialect?: string;
	/** 为指标因果路径生成结构化表达式依赖；默认关闭以保持既有产物稳定。 */
	include_expression_dependencies?: boolean;
}

const CONTRACT_VERSION = "1.1.2";
const ADAPTER_VERSION = "0.2.1";
const EXPRESSION_DEPENDENCY_CONTRACT_VERSION = "1.1.3";
export const EXPRESSION_DEPENDENCY_ADAPTER_VERSION = "0.2.10";

export function buildPlanFacts(
	cell: { scopes: ScopeTree; span: { start: number } },
	sql: string,
	opts?: PlanAdapterOptions,
): PlanFacts {
	const relations: PlanRelation[] = [];
	const unknowns: PlanFacts["unknowns"] = [];
	const physical = new Set<string>();
	const relationScopes = new Map<string, Scope>();
	const roots: string[] = [];
	const root = cell.scopes.root;
	const cellBase = cell.span.start ?? 0;
	const schema = opts?.schema;
	const dialect = opts?.dialect ?? "databricks";

	// 每个 scope 的根节点 id 缓存 (子查询源可能被多次引用, 如 join 右臂 + from 列表)
	const rootIds = new Map<Scope, string>();

	function buildScope(scope: Scope, path: string): string {
		if (rootIds.has(scope)) return rootIds.get(scope)!;
		const body = scope.body;
		const outCols = Array.isArray(scope.outputs) ? scope.outputs : null;

		// setop body (UNION/EXCEPT/INTERSECT) → setop 节点 + 分支子图
		//   分支取 scope.branches (嵌套 setop 递归保留), 不用 children (会混入 CTE 子块)
		if (body.kind === "setop") {
			const id = `${path}.setop`;
			const branchIds: string[] = [];
			const walkBranch = (sc: Scope) => {
				branchIds.push(buildScope(sc, `${path}.setop.b${branchIds.length}`));
			};
			if (scope.branches) {
				walkBranch(scope.branches.left);
				walkBranch(scope.branches.right);
			}
			const branchOutputs = branchIds.map(
				(branchId) => relations.find((relation) => relation.id === branchId)?.output_columns,
			);
			const inferredOutputs =
				branchOutputs.length > 0 &&
				branchOutputs.every((outputs): outputs is string[] => Array.isArray(outputs) && outputs.length > 0) &&
				branchOutputs.every((outputs) => outputs.length === branchOutputs[0]!.length)
					? branchOutputs[0]
					: null;
			const s: SetopRelation = {
				id,
				type: "setop",
				setop: (body as { op?: string }).op ?? "union",
				all: (body as { all?: boolean }).all ?? undefined,
				by_name: (body as { byName?: boolean }).byName ?? undefined,
				branches: branchIds,
				span: spanOf(cellBase, body.cst),
				provenance: branchIds.length > 0 ? "extracted" : "unknown",
				output_columns: outCols ?? inferredOutputs,
			};
			relations.push(s);
			if (branchIds.length === 0) {
				unknowns.push({ node_id: id, field: "branches", reason: "setop 无 branches (sql-static-lineage 未建模分支)" });
			}
			rootIds.set(scope, id);
			return id;
		}

		// 非 select/setop body (pipe/…) → other 节点显式保留
		if (body.kind !== "select") {
			const id = `${path}.other`;
			relations.push({
				id,
				type: "other",
				body_kind: body.kind,
				note: "v1 未建模 body, 显式保留",
				span: spanOf(cellBase, body.cst),
				provenance: "unknown",
				output_columns: outCols,
			} as PlanRelation);
			unknowns.push({ node_id: id, field: "body", reason: `body.kind=${body.kind} 未建模 (v1 范围: select)` });
			rootIds.set(scope, id);
			return id;
		}

		// ---- 1. read 节点: 每个 table/cte 源一个; lateral 源 → expand ----
		const nodeIds = new Map<string, string>(); // 绑定 key → 节点 id
		for (const [key, src] of scope.sources) {
			if (src.kind === "table" || src.kind === "cte") {
				const id = `${path}.read.${key}`;
				const rel = src.source.relation;
				if (rel?.fqn) physical.add(rel.fqn);
				const r: ReadRelation = {
					id,
					type: "read",
					table: rel?.fqn ?? key,
					binding: key,
					columns: null, // 列清单需 qualify 展开, v1 不填充
					is_cte: src.kind === "cte" ? true : undefined,
					span: spanOf(cellBase, src.source.cst),
					provenance: "extracted",
					output_columns: null,
				};
				relations.push(r);
				nodeIds.set(key, id);
			} else if (src.kind === "lateral") {
				const id = `${path}.expand.${key}`;
				const e: ExpandRelation = {
					id,
					type: "expand",
					expand_kind: "lateral",
					produced_columns: src.source.columns ?? [],
					span: spanOf(cellBase, src.source.cst),
					provenance: "extracted",
					output_columns: null,
				};
				relations.push(e);
				nodeIds.set(key, id);
			}
		}

		// 绑定 key → 节点 id (subquery 源递归建子图)
		function sourceNodeId(key: string, src: { kind: string; scope?: Scope }): string | null {
			if (src.kind === "subquery" && src.scope) return buildScope(src.scope, `${path}.${key}`);
			return nodeIds.get(key) ?? null;
		}

		// ---- 2. from 源 → 左深链: from[0] 起, 按序 join/expand 挂接 ----
		//   table/subquery 源: 第 1 个为链首, 后续生成 join (有 joins 记录用其 kind, 无则逗号 cross)
		//   lateral 源: 行扩展, 挂接当前链尾 (Spark LATERAL VIEW 语义), 不产生 join
		let chainTail: string | null = null;
		let first = true;
		const fromEntries = body.from ?? [];
		for (let fi = 0; fi < fromEntries.length; fi++) {
			const f = fromEntries[fi] as SelectExpr["from"][number];
			// 找绑定 key
			let boundKey: string | null = null;
			for (const [k, s] of scope.sources) {
				if (s.kind === "table" || s.kind === "cte") {
					if (f.kind === "table" && (s.source.relation?.name ?? "") === f.relation.name) {
						boundKey = k;
						break;
					}
				} else if (s.kind === "subquery" && s.source.alias === f.alias) {
					boundKey = k;
					break;
				} else if (s.kind === "lateral" && s.source.alias === f.alias) {
					boundKey = k;
					break;
				}
			}
			if (!boundKey) {
				// 兜底: 无别名表 → sources 里唯一的无别名 table
				for (const [k, s] of scope.sources) {
					if (s.kind === "table" && !s.source.alias) {
						boundKey = k;
						break;
					}
				}
			}
			const isLateral = scope.sources.get(boundKey ?? "")?.kind === "lateral";
			const nodeId = boundKey
				? sourceNodeId(boundKey, scope.sources.get(boundKey) as { kind: string; scope?: Scope })
				: null;
			if (!nodeId) continue;

			if (isLateral) {
				// 行扩展挂接链尾
				const e = relations.find((r) => r.id === nodeId) as ExpandRelation;
				if (e && chainTail) e.source = chainTail;
				chainTail = nodeId;
				continue;
			}

			if (first) {
				chainTail = nodeId;
				first = false;
				continue;
			}
			// join 节点 (左深链)
			const joinRec = (body.joins ?? [])[fi - 1];
			const id = `${path}.join.${fi}`;
			const joinCols: ColumnRef[] = [];
			if (joinRec?.on) collectColumns(joinRec.on, "join", joinCols);
			const j: JoinRelation = {
				id,
				type: "join",
				join_type: joinRec?.kind ?? "cross", // 无 join 记录 = 逗号隐式连接
				left: chainTail ?? "?",
				right: nodeId,
				condition_expr: joinRec
					? joinRec.on
						? fullTextOf(sql, cellBase, joinRec.on.cst)
						: joinRec.using
							? `USING (${joinRec.using.join(", ")})`
							: null
					: null,
				condition_display: joinRec
					? joinRec.on
						? displayTextOf(sql, cellBase, joinRec.on.cst)
						: joinRec.using
							? `USING (${joinRec.using.join(", ")})`
							: null
					: null,
				condition_columns: joinCols,
				condition_facts: opts?.include_expression_dependencies ? expressionFacts(joinRec?.on) : undefined,
				using: joinRec?.using ? true : undefined,
				span: joinRec ? spanOf(cellBase, joinRec.cst) : spanOf(cellBase, f.cst),
				provenance: "extracted",
				output_columns: null,
			};
			relations.push(j);
			relationScopes.set(id, scope);
			chainTail = id;
		}

		// ---- 3. filter 节点 ----
		if (body.where) {
			const id = `${path}.filter`;
			const whereCols: ColumnRef[] = [];
			collectColumns(body.where, "where", whereCols);
			const f: FilterRelation = {
				id,
				type: "filter",
				predicate_expr: fullTextOf(sql, cellBase, body.where.cst),
				predicate_display: displayTextOf(sql, cellBase, body.where.cst),
				predicate_columns: whereCols,
				predicate_facts: opts?.include_expression_dependencies ? expressionFacts(body.where) : undefined,
				span: spanOf(cellBase, body.where.cst),
				provenance: "extracted",
				output_columns: null,
				source: chainTail ?? undefined,
			};
			relations.push(f);
			relationScopes.set(id, scope);
			chainTail = id;
		}

		// ---- 4. aggregate 节点 ----
		const gbExprs = body.groupBy ?? [];
		if (body.aggregated) {
			const id = `${path}.aggregate`;
			const gbCols: ColumnRef[] = [];
			for (const e of gbExprs) collectColumns(e, "groupBy", gbCols);
			const a: AggregateRelation = {
				id,
				type: "aggregate",
				group_by: gbCols,
				group_by_exprs: gbExprs.map((e) => fullTextOf(sql, cellBase, e.cst)),
				group_by_exprs_display: gbExprs.map((e) => displayTextOf(sql, cellBase, e.cst)),
				measures: body.projections
					.filter((p) => p.expr.kind === "function" && (p.expr as { aggregate?: boolean }).aggregate)
					.map((p, ordinal) => {
						const inputColumns: ColumnRef[] = [];
						if (opts?.include_expression_dependencies) collectColumns(p.expr, "projection", inputColumns);
						return {
							output: p.name ?? `$expr_${ordinal}`,
							output_name_status: p.name ? ("EXPLICIT" as const) : ("ANONYMOUS_EXPRESSION" as const),
							expr_kind: p.expr.kind,
							aggregate: true,
							expr_text: fullTextOf(sql, cellBase, p.cst),
							display_text: displayTextOf(sql, cellBase, p.cst),
							span: spanOf(cellBase, p.cst),
							input_columns: inputColumns.length > 0 ? inputColumns : undefined,
							expression_facts: opts?.include_expression_dependencies
								? expressionFacts(p.expr)
								: undefined,
						};
					}),
				span: gbExprs.length > 0 ? spanOf(cellBase, gbExprs[0].cst) : spanOf(cellBase, body.cst),
				provenance: "extracted",
				output_columns: null,
				source: chainTail ?? undefined,
			};
			relations.push(a);
			relationScopes.set(id, scope);
			chainTail = id;
		}

		// ---- 5. project 节点 (每层必有) ----
		// star 展开: 限定 T.* → schema 列清单 / 子查询输出列传播; 裸 * → 各源列并集
		type ExpandedColumn = { name: string; input_columns?: ColumnRef[] };
		const expandStar = (p: { expr: { kind: string; qualifier?: string } }): ExpandedColumn[] | null => {
			if (p.expr.kind !== "star") return null;
			const qual = p.expr.qualifier;
			const qlast = Array.isArray(qual) ? qual[qual.length - 1] : qual; // qualifier 可能是分段数组 (db.tbl.*)
			const foldKey = (k: string) => k.toLowerCase(); // databricks 大小写不敏感, 绑定名与 qualifier 允许大小写差异
			const cols: ExpandedColumn[] = [];
			for (const [key, src] of scope.sources) {
				if (qlast && foldKey(key) !== foldKey(String(qlast))) continue; // 限定 star 只取匹配绑定
				if (src.kind === "table" || src.kind === "cte") {
					const fqn = src.source.relation?.fqn;
					if (!schema || !fqn) return null; // 缺 schema 无法枚举
					const c = (schema as any).columnsFor(fqn.split("."), dialect);
					if (!c) return null;
					cols.push(
						...c.map((x: any) => ({
							name: x.name,
							input_columns: opts?.include_expression_dependencies
								? [
										{
											name: x.name,
											qualifier: key,
											clause: "projection" as const,
											physical: [{ table: fqn, column: x.name }],
											resolution: "PHYSICAL" as const,
										},
									]
								: undefined,
						})),
					);
				} else if (src.kind === "subquery" && src.scope) {
					const subId = buildScope(src.scope, `${path}.${key}`);
					const sub = relations.find((r) => r.id === subId);
					const subOut = sub?.output_columns;
					if (!Array.isArray(subOut) || subOut.length === 0) return null;
					const projectExpressions = sub && Array.isArray((sub as Partial<ProjectRelation>).expressions)
						? (sub as ProjectRelation).expressions
						: [];
					cols.push(
						...(subOut as string[]).map((name) => ({
							name,
							input_columns: projectExpressions.find((expression) => expression.output === name)
								?.input_columns,
						})),
					);
				} else if (src.kind === "lateral") {
					cols.push(...(src.source.columns ?? []).map((name) => ({ name })));
				}
			}
			return cols.length > 0 ? cols : null;
		};

		const pid = `${path}.project`;
		const exprs: any[] = [];
		const outNames: string[] = [];
		let starFailed = false;
		for (const p of body.projections) {
			if (p.isStar) {
				const starCols = expandStar(p as { expr: { kind: string; qualifier?: string } });
				if (starCols) {
					for (const c of starCols) {
						exprs.push({
							output: c.name,
							output_name_status: "STAR_EXPANSION",
							expr_kind: "column",
							expr_text: c.name,
							display_text: c.name,
							span: spanOf(cellBase, p.cst),
							star_expansion: true,
							input_columns: c.input_columns,
						});
						outNames.push(c.name);
					}
				} else {
					const expr = p.expr as { kind: string };
					exprs.push({
						output: "*",
						expr_kind: expr.kind,
						expr_text: fullTextOf(sql, cellBase, p.cst),
						display_text: displayTextOf(sql, cellBase, p.cst),
						span: spanOf(cellBase, p.cst),
					});
					starFailed = true;
				}
			} else {
				const expr = p.expr as Expr & { window?: unknown; aggregate?: boolean };
				const anonymous = !p.name;
				const output = p.name ?? `$expr_${outNames.length}`;
				const inputColumns: ColumnRef[] = [];
				if (opts?.include_expression_dependencies) collectColumns(expr, "projection", inputColumns);
				exprs.push({
					output,
					output_name_status: anonymous ? "ANONYMOUS_EXPRESSION" : "EXPLICIT",
					expr_kind: expr.kind,
					window: expr.kind === "function" && expr.window ? true : undefined,
					aggregate: expr.kind === "function" && expr.aggregate ? true : undefined,
					expr_text: fullTextOf(sql, cellBase, p.cst),
					display_text: displayTextOf(sql, cellBase, p.cst),
					span: spanOf(cellBase, p.cst),
					input_columns: inputColumns.length > 0 ? inputColumns : undefined,
					expression_facts: opts?.include_expression_dependencies ? expressionFacts(expr) : undefined,
				});
				outNames.push(output);
			}
		}
		const computedOut = !starFailed && outNames.length > 0 ? outNames : null;
		const pr: ProjectRelation = {
			id: pid,
			type: "project",
			expressions: exprs,
			span: spanOf(cellBase, body.cst),
			provenance: computedOut ? "extracted" : "unknown",
			output_columns: computedOut ?? outCols,
			source: chainTail ?? undefined,
		};
		relations.push(pr);
		relationScopes.set(pid, scope);
		if (!computedOut) {
			unknowns.push({
				node_id: pid,
				field: "output_columns",
				reason: "star/匿名投影无法枚举: 缺该表 schema 或子查询输出列未知",
				span: spanOf(cellBase, body.cst),
			});
		}
		rootIds.set(scope, pid);

		// 表达式子查询 / CTE 子块
		for (const child of scope.children) {
			if (!rootIds.has(child)) buildScope(child, `${path}.(child)`);
		}
		return pid;
	}

	roots.push(buildScope(root, "root"));

	// Resolve ordinary derived-table outputs from the already-built child project
	// facts. This complements the SETOP-specific resolver above: a parent scope
	// referencing `deal.notional` must inherit the physical input recorded by
	// `deal`'s `SELECT *` project instead of asking lineageAt to cross an alias
	// boundary it does not own.
	const resolveDerivedOutput: DerivedOutputResolver = (scope, name) => {
		const rootId = rootIds.get(scope);
		const project = relations.find((relation) => relation.id === rootId && relation.type === "project") as ProjectRelation | undefined;
		const expression = project?.expressions.find((candidate) => candidate.output.toLowerCase() === name.toLowerCase());
		if (!expression) return null;
		const inputs = expression.input_columns ?? [];
		if (inputs.length === 0 && expression.output_name_status === "STAR_EXPANSION" && scope.sources.size === 1) {
			const source = [...scope.sources.values()][0];
			const sourceScope = source?.kind === "subquery"
				? source.scope
				: source?.kind === "cte" ? source.ref.scope : undefined;
			if (sourceScope?.body.kind === "setop") {
				const derived = resolveSetopOutput(cell, schema, sourceScope, name, resolveDerivedOutput);
				if (derived) return derived;
			}
		}
		const physical = inputs.flatMap((input) => input.resolution === "PHYSICAL" ? input.physical ?? [] : []);
		const candidates = inputs.flatMap((input) => input.resolution === "SQL_CANDIDATE" ? input.sql_candidate ?? [] : []);
		const unresolved = inputs.some((input) =>
			input.resolution !== "PHYSICAL" &&
			input.resolution !== "DERIVED_OUTPUT" &&
			input.resolution !== "SQL_CANDIDATE"
		);
		if (physical.length > 0 && candidates.length === 0 && !unresolved) {
			const seen = new Set<string>();
			return {
				kind: "PHYSICAL",
				physical: physical.filter((item) => {
					const key = `${item.table}.${item.column}`.toLowerCase();
					if (seen.has(key)) return false;
					seen.add(key);
					return true;
				}),
			};
		}
		if (physical.length === 0 && candidates.length > 0 && !unresolved) {
			const seen = new Set<string>();
			return {
				kind: "SQL_CANDIDATE",
				candidates: candidates.filter((item) => {
					const key = `${item.table}.${item.column}`.toLowerCase();
					if (seen.has(key)) return false;
					seen.add(key);
					return true;
				}),
			};
		}
		if (physical.length === 0 && candidates.length === 0 && inputs.length > 0 && inputs.every((input) => input.resolution === "DERIVED_OUTPUT")) {
			return { kind: "DERIVED_OUTPUT" };
		}
		// An expression with no column inputs is still a derived output when it
		// is a function, CASE, cast, or arithmetic expression rather than a
		// literal. Do not turn a computed constant/system value into a fake
		// physical-field Unknown at a derived-table or set-op boundary.
		if (physical.length === 0 && candidates.length === 0 && inputs.length === 0 && expression.expr_kind !== "column") {
			return { kind: "DERIVED_OUTPUT" };
		}
		return null;
	};

	// ---- 物理解析: 所有条件/谓词/分组列追到基表 ----
	if (schema) {
		// Resolve child scopes before their parent projects. buildScope appends a
		// derived scope's relations before its enclosing project, so preserve that
		// construction order when derived outputs inherit child project facts.
		for (const r of relations) {
			const scope = relationScopes.get(r.id);
			if (!scope) continue;
			if (r.type === "join") resolvePhysical(cell, schema, scope, r.id, r.condition_columns, unknowns, dialect, resolveDerivedOutput);
			else if (r.type === "filter") resolvePhysical(cell, schema, scope, r.id, r.predicate_columns, unknowns, dialect, resolveDerivedOutput);
			else if (r.type === "aggregate") {
				resolvePhysical(cell, schema, scope, r.id, r.group_by, unknowns, dialect, resolveDerivedOutput);
				for (const measure of r.measures) {
					if (measure.input_columns)
						resolvePhysical(cell, schema, scope, r.id, measure.input_columns, unknowns, dialect, resolveDerivedOutput);
				}
			} else if (r.type === "project") {
				for (const expression of r.expressions) {
					if (expression.input_columns)
						resolvePhysical(cell, schema, scope, r.id, expression.input_columns, unknowns, dialect, resolveDerivedOutput);
				}
			}
		}
	}

	// parser 版本 (sql-static-lineage package.json)
	let parserVersion = "unknown";
	try {
		const pkg = JSON.parse(readFileSync(new URL("../../package.json", import.meta.url), "utf8")) as {
			version?: string;
		};
		parserVersion = pkg.version ?? "unknown";
	} catch {
		// 非仓库内运行时 fallback
	}

	return {
		meta: {
			contract_version: opts?.include_expression_dependencies
				? EXPRESSION_DEPENDENCY_CONTRACT_VERSION
				: CONTRACT_VERSION,
			adapter_version:
				opts?.adapter_version ??
				(opts?.include_expression_dependencies ? EXPRESSION_DEPENDENCY_ADAPTER_VERSION : ADAPTER_VERSION),
			parser: { engine: "sql-static-lineage", version: parserVersion },
			dialect: root.dialect ?? "unknown",
			statement_index: opts?.statement_index ?? 0,
			generated_at: new Date().toISOString(),
		},
		relations,
		roots,
		physical_inputs: [...physical],
		unknowns,
	};
}

// ---------------------------------------------------------------------------
// Grain / Cardinality 推断层 v1.1
//   1. propagateGrain: aggregate 的 grain key 沿 plan 自底向上传播
//   2. inferGrain: 结合传播结果输出判定 (join 右表 key 覆盖 → 不扩行)
// ---------------------------------------------------------------------------

interface GrainState {
	/** grain key 列集; null = 未知; [] = 全局聚合 (至多 1 行, 任何键唯一)。 */
	grain: string[] | null;
	note: string;
}

/** 右表 binding: id 形如 ...{path}.project 或 ...{path}.read.{key} → 取倒数第二段 (read 取末段)。 */
function rightBindingOf(nodeId: string): string {
	const segs = nodeId.split(".");
	return segs[segs.length - 2] === "read" ? segs[segs.length - 1] : segs[segs.length - 2];
}

/** 沿 source 链传播 grain (relations 数组顺序 ≈ 拓扑序: 子图先于父节点)。 */
export function propagateGrain(facts: PlanFacts): Map<string, GrainState> {
	const st = new Map<string, GrainState>();
	for (const r of facts.relations) {
		switch (r.type) {
			case "read":
				st.set(r.id, { grain: null, note: "物理表, 无键信息" });
				break;
			case "expand":
				st.set(r.id, { grain: null, note: "行扩展改变粒度" });
				break;
			case "filter": {
				const src = r.source ? st.get(r.source) : null;
				st.set(r.id, src ? { ...src } : { grain: null, note: "上游未知" });
				break;
			}
			case "project": {
				const src = r.source ? st.get(r.source) : null;
				if (!src || src.grain === null) {
					st.set(r.id, { grain: null, note: "上游无 grain" });
					break;
				}
				const outs = r.output_columns ?? [];
				// 输出列需保留全部键列才可传播 (重命名/删除 → 保守 null)
				if (outs && src.grain.every((k) => outs.includes(k))) {
					st.set(r.id, { grain: [...src.grain], note: src.note });
				} else {
					st.set(r.id, { grain: null, note: "投影后键列不可见" });
				}
				break;
			}
			case "aggregate": {
				const keys = [...new Set(r.group_by.map((c) => c.name))];
				st.set(r.id, {
					grain: keys.length > 0 ? keys : [],
					note: keys.length > 0 ? `GROUP BY ${keys.join(", ")}` : "全局聚合 (至多 1 行)",
				});
				break;
			}
			case "join": {
				const rightSt = st.get(r.right) ?? { grain: null, note: "右表未知" };
				const leftSt = st.get(r.left) ?? { grain: null, note: "左表未知" };
				let out: GrainState;
				if (r.join_type === "cross") out = { grain: null, note: "笛卡尔积" };
				else if (r.join_type === "left" || r.join_type === "inner")
					out = { grain: leftSt.grain, note: leftSt.note };
				else out = { grain: rightSt.grain, note: rightSt.note }; // right/full: 输出由右表决定 (v1 保守)
				st.set(r.id, out);
				break;
			}
			case "other":
				st.set(r.id, { grain: null, note: "未建模" });
				break;
			case "setop":
				st.set(r.id, {
					grain: null,
					note: `${r.setop.toUpperCase()}${r.all ? " ALL" : ""}: 分支合并, 输出行数 = 各分支之和/去重, grain 键不保证`,
				});
				break;
		}
	}
	return st;
}

/** 右表 grain key 是否被连接条件覆盖 (右表每键至多 1 行 → 该 join 不因右表扩行)。 */
function joinRightKeyCovered(
	r: JoinRelation,
	states: Map<string, GrainState>,
): { covered: boolean; key: string[] | null; note: string } {
	const rightSt = states.get(r.right);
	if (!rightSt || rightSt.grain === null) return { covered: false, key: null, note: "右表无传播 grain" };
	const rightBinding = rightBindingOf(r.right);
	const rightCols = new Set(r.condition_columns.filter((c) => c.qualifier === rightBinding).map((c) => c.name));
	const key = rightSt.grain;
	const covered = key.length > 0 && key.every((k) => rightCols.has(k));
	return {
		covered,
		key,
		note: covered
			? `连接条件覆盖右表 grain key [${key.join(", ")}] (来自上游: ${rightSt.note})`
			: `右表 grain key [${key.join(", ")}] 未被连接条件完全覆盖 (右列: ${[...rightCols].join(", ") || "无"})`,
	};
}

export function inferGrain(facts: PlanFacts): GrainInference[] {
	const states = propagateGrain(facts);
	const out: GrainInference[] = [];
	for (const r of facts.relations) {
		switch (r.type) {
			case "aggregate": {
				const keys = [...new Set(r.group_by.map((c) => c.name))];
				if (keys.length > 0) {
					out.push({
						node_id: r.id,
						grain_candidate: keys,
						cardinality: "non-increasing", // 非严格: 输入本就每键一行则行数不变
						confidence: "high",
						evidence: [`GROUP BY ${keys.join(", ")} (聚合节点)`],
						requires: [],
					});
				} else {
					out.push({
						node_id: r.id,
						grain_candidate: [],
						cardinality: "non-increasing", // 全局聚合 → 至多 1 行
						confidence: "high",
						evidence: ["无 GROUP BY 的聚合 (全局聚合, 至多 1 行)"],
						requires: [],
					});
				}
				break;
			}
			case "join": {
				const rightSt = states.get(r.right) ?? { grain: null, note: "右表未知" };
				const outGrain = states.get(r.id)?.grain ?? null;
				const covered = joinRightKeyCovered(r, states);
				const cond = r.condition_display ?? "无";
				if (r.join_type === "cross") {
					out.push({
						node_id: r.id,
						grain_candidate: null,
						cardinality: "unknown", // 笛卡尔积: 行数 = 左×右, 非单调 (右表 0 行 → 0 行)
						confidence: "high",
						evidence: ["CROSS JOIN (笛卡尔积, 行数 = 左表行数 × 右表行数)"],
						requires: [],
					});
					break;
				}
				if (covered.covered) {
					const nonInc = r.join_type === "left" || r.join_type === "inner";
					out.push({
						node_id: r.id,
						grain_candidate: outGrain,
						cardinality: nonInc ? "non-increasing" : "unknown",
						confidence: "high",
						evidence: [
							`${r.join_type.toUpperCase()} JOIN (条件: ${cond})`,
							covered.note,
							nonInc
								? "右表每键至多 1 行 → 本 join 不因右表扩行"
								: "RIGHT/FULL JOIN 保留右表全部行, 行数仍可能变化",
						],
						requires: [],
					});
				} else {
					const allCols = [...new Set(r.condition_columns.map((c) => c.name))];
					const rightBinding = rightBindingOf(r.right);
					const rightCols = [
						...new Set(r.condition_columns.filter((c) => c.qualifier === rightBinding).map((c) => c.name)),
					];
					out.push({
						node_id: r.id,
						grain_candidate: outGrain,
						cardinality: "unknown", // 是否扩行取决于右表条件列唯一性
						confidence: "medium",
						evidence: [`${r.join_type.toUpperCase()} JOIN (条件: ${cond})`, covered.note],
						requires:
							rightCols.length > 0
								? [
										`右表 ${r.right} 的 ${rightCols.join("/")} 唯一性 (PK/UK/distinct 统计); 条件涉及列: ${allCols.join("/") || "无"}`,
									]
								: [
										`右表 ${r.right} 连接键唯一性; 条件涉及列: ${allCols.join("/") || "无"} (PK/UK/distinct 统计)`,
									],
					});
				}
				break;
			}
			case "expand": {
				out.push({
					node_id: r.id,
					grain_candidate: null,
					cardinality: "unknown", // explode: 空集合/NULL → 0 行, 非空 → N 行, 非单调
					confidence: "medium",
					evidence: [
						`${r.expand_kind} 行扩展 (产生列: ${r.produced_columns.join(", ") || "无"})`,
						"explode/posexplode 对空集合/NULL 不产生行 → 每行产出 0..N 行",
					],
					requires: [],
					cardinality_effect: "fanout",
					per_input_rows: "0..N",
					grain_effect: "expanded",
				});
				break;
			}
			case "setop": {
				out.push({
					node_id: r.id,
					grain_candidate: null,
					// UNION ALL: 行数 = 各分支之和 (非递减); UNION/EXCEPT/INTERSECT: 去重/集合语义, 未知
					cardinality: r.all ? "non-decreasing" : "unknown",
					confidence: "high",
					evidence: [
						`${r.setop.toUpperCase()}${r.all ? " ALL" : ""} (分支: ${r.branches.length} 个)`,
						r.all
							? "UNION ALL: 输出行数 = 各分支行数之和 (不减少)"
							: "UNION/EXCEPT/INTERSECT: 去重或集合语义, 行数需分支基数",
					],
					requires: r.all ? [] : ["各分支行数 + 去重语义 (UNION) 或集合基数 (EXCEPT/INTERSECT)"],
				});
				break;
			}
			case "read": {
				out.push({
					node_id: r.id,
					grain_candidate: null,
					cardinality: "unknown",
					confidence: "low",
					evidence: [`读取 ${r.table}`],
					requires: [`${r.table} 的 PK/UK 元数据`],
				});
				break;
			}
			default:
				// project/filter/other: 不改变行数与 grain (v1 保守)
				break;
		}
	}
	return out;
}
