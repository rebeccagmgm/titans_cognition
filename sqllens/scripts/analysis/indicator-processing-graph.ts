import { createHash } from "node:crypto";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { basename, relative, resolve } from "node:path";

import { Schema, SqlSession } from "../../src/index.ts";
import { buildPlanFacts } from "../plans/plan-adapter.ts";

interface TaskProfile {
	task_id: string;
	role: string;
	sql_snapshot: string;
	writes: string;
	focus_outputs: string[];
}

interface ProcessingProfile {
	schema_version: string;
	case_id: string;
	indicator_id: string;
	dialect: string;
	target_field: string;
	schema_evidence: string;
	tasks: TaskProfile[];
}

type JsonRecord = Record<string, any>;

const workspace = resolve(import.meta.dirname, "../../..");
const profilePath = resolve(
	workspace,
	process.argv[2] ?? "cases/indicator-journey-rgstcomp-mthend/processing-graph-profile.json",
);
const outputDir = resolve(workspace, process.argv[3] ?? "output/indicator-processing-graph-rgstcomp-mthend");
const profile = JSON.parse(readFileSync(profilePath, "utf8")) as ProcessingProfile;
const schemaEvidencePath = resolve(workspace, profile.schema_evidence);
const schemaEvidenceBytes = readFileSync(schemaEvidencePath);
const schemaEvidence = JSON.parse(schemaEvidenceBytes.toString("utf8")) as JsonRecord;
const successfulSchemaRecords = (schemaEvidence.records as JsonRecord[]).filter(
	(record) => record.status === "SUCCESS" && Array.isArray(record.columns) && record.columns.length > 0,
);
const schemaMapping = Object.fromEntries(
	successfulSchemaRecords.map((record) => [
		record.qualified_name,
		Object.fromEntries(record.columns.map((column: JsonRecord) => [column.name, "unknown"])),
	]),
);
const schema = new Schema(schemaMapping);

const sourceDir = resolve(outputDir, "source-sql");
mkdirSync(sourceDir, { recursive: true });

const sha256 = (value: string | Buffer): string => createHash("sha256").update(value).digest("hex");
const normalizeName = (value: string): string => value.replace(/[`"\[\]]/g, "").toLowerCase();
const normalizeWhitespace = (value: string): string => value.replace(/\s+/g, " ").trim();
const safeToken = (value: string): string => value.replace(/[^A-Za-z0-9_.:-]+/g, "_");

function stripDisplayFields(value: any): any {
	if (Array.isArray(value)) return value.map(stripDisplayFields);
	if (!value || typeof value !== "object") return value;
	return Object.fromEntries(
		Object.entries(value)
			.filter(([key]) => key !== "display_text" && !key.endsWith("_display"))
			.map(([key, item]) => [key, stripDisplayFields(item)]),
	);
}

function classifyStatement(text: string): string {
	const normalized = text.trimStart().toUpperCase();
	if (normalized.startsWith("CREATE TABLE")) return "CREATE_TABLE";
	if (normalized.startsWith("INSERT OVERWRITE")) return "INSERT_OVERWRITE";
	if (normalized.startsWith("INSERT INTO")) return "INSERT_INTO";
	if (normalized.startsWith("WITH")) return "WITH_QUERY";
	if (normalized.startsWith("SELECT")) return "SELECT";
	return "OTHER";
}

function globalRelationId(taskId: string, statementIndex: number, localId: string): string {
	return `task:${taskId}:statement:${statementIndex}:relation:${localId}`;
}

function globalizeRelation(taskId: string, statementIndex: number, relation: JsonRecord): JsonRecord {
	const converted = stripDisplayFields(relation);
	const mapId = (id: string): string => globalRelationId(taskId, statementIndex, id);
	converted.id = mapId(relation.id);
	if (relation.source) converted.source = mapId(relation.source);
	if (relation.left) converted.left = mapId(relation.left);
	if (relation.right) converted.right = mapId(relation.right);
	if (relation.branches) converted.branches = relation.branches.map(mapId);
	return converted;
}

function writeJsonl(name: string, records: JsonRecord[]): { path: string; count: number; hash: string } {
	const text = records.map((record) => JSON.stringify(record)).join("\n") + (records.length ? "\n" : "");
	const path = resolve(outputDir, name);
	writeFileSync(path, text, "utf8");
	return { path, count: records.length, hash: sha256(text) };
}

const sources: JsonRecord[] = [];
const statements: JsonRecord[] = [];
const relations: JsonRecord[] = [];
const fieldExpressions: JsonRecord[] = [];
const entities = new Map<string, JsonRecord>();
const edges = new Map<string, JsonRecord>();
const unknowns: JsonRecord[] = [];
const taskInputs = new Map<string, Set<string>>();

function addEntity(entity: JsonRecord): void {
	entities.set(entity.entity_id, entity);
}

function addEdge(edge: JsonRecord): void {
	const key = JSON.stringify([
		edge.edge_type,
		edge.from,
		edge.to,
		edge.role ?? null,
		edge.dataset ?? null,
		edge.field ?? null,
	]);
	edges.set(key, edge);
}

for (const task of profile.tasks) {
	const sqlPath = resolve(workspace, task.sql_snapshot);
	const sqlBytes = readFileSync(sqlPath);
	const sql = sqlBytes.toString("utf8");
	const contentHash = sha256(sqlBytes);
	const artifactId = `sql:${task.task_id}:${contentHash.slice(0, 16)}`;
	const copiedName = `task-${task.task_id}-${contentHash.slice(0, 12)}.sql`;
	const copiedPath = resolve(sourceDir, copiedName);
	writeFileSync(copiedPath, sqlBytes);

	addEntity({
		entity_id: `task:${task.task_id}`,
		entity_type: "TASK",
		task_id: task.task_id,
		role: task.role,
	});
	const writeDatasetId = `dataset:${normalizeName(task.writes)}`;
	addEntity({ entity_id: writeDatasetId, entity_type: "DATASET", name: normalizeName(task.writes) });
	addEdge({
		edge_type: "TASK_WRITES_DATASET",
		from: `task:${task.task_id}`,
		to: writeDatasetId,
		provenance: "PROFILE_DECLARED",
	});

	let session: ReturnType<typeof SqlSession.create>;
	try {
		session = SqlSession.create(sql, profile.dialect as any);
	} catch (error) {
		sources.push({
			artifact_id: artifactId,
			task_id: task.task_id,
			source_path: relative(workspace, sqlPath).replace(/\\/g, "/"),
			captured_path: relative(outputDir, copiedPath).replace(/\\/g, "/"),
			content_sha256: contentHash,
			byte_length: sqlBytes.length,
			char_length: sql.length,
			capture_status: "SUCCESS",
			parse_status: "FAILED",
			statement_count: 0,
		});
		unknowns.push({
			unknown_id: `unknown:${task.task_id}:document-parse`,
			unknown_type: "PARSER_FAILURE",
			task_id: task.task_id,
			artifact_id: artifactId,
			reason: error instanceof Error ? error.message : String(error),
		});
		continue;
	}

	sources.push({
		artifact_id: artifactId,
		task_id: task.task_id,
		source_path: relative(workspace, sqlPath).replace(/\\/g, "/"),
		captured_path: relative(outputDir, copiedPath).replace(/\\/g, "/"),
		content_sha256: contentHash,
		byte_length: sqlBytes.length,
		char_length: sql.length,
		encoding: "UTF-8",
		dialect: profile.dialect,
		capture_status: "SUCCESS",
		parse_status: session.doc.errors > 0 ? "PARTIAL" : "SUCCESS",
		statement_count: session.doc.statements.length,
		syntax_error_count: session.doc.errors,
		syntax_diagnostics: session.doc.diagnostics,
	});

	const inputs = new Set<string>();
	taskInputs.set(task.task_id, inputs);

	for (const [statementIndex, cell] of session.doc.statements.entries()) {
		const statementId = `task:${task.task_id}:statement:${statementIndex}`;
		const statementSpan = { start: cell.span.start, end: cell.span.end };
		const statementRaw = sql.slice(statementSpan.start, statementSpan.end);
		for (const [diagnosticIndex, diagnostic] of cell.diagnostics.entries()) {
			const diagnosticSpan =
				diagnostic.offset === undefined
					? null
					: {
							start: diagnostic.offset,
							end: Math.min(sql.length, diagnostic.offset + diagnostic.length),
						};
			unknowns.push({
				unknown_id: `unknown:${task.task_id}:statement:${statementIndex}:syntax:${diagnosticIndex}`,
				unknown_type: "SYNTAX_DIAGNOSTIC",
				task_id: task.task_id,
				statement_id: statementId,
				artifact_id: artifactId,
				message: diagnostic.message,
				line: diagnostic.line,
				column: diagnostic.column,
				offset: diagnostic.offset ?? null,
				length: diagnostic.length,
				span: diagnosticSpan,
				raw_sql: diagnosticSpan ? sql.slice(diagnosticSpan.start, diagnosticSpan.end) : null,
			});
		}
		let plan: ReturnType<typeof buildPlanFacts> | null = null;
		let planError: string | null = null;
		try {
			plan = buildPlanFacts(cell, sql, {
				statement_index: statementIndex,
				dialect: profile.dialect,
				schema,
				include_expression_dependencies: true,
			});
		} catch (error) {
			planError = error instanceof Error ? error.message : String(error);
			unknowns.push({
				unknown_id: `unknown:${task.task_id}:statement:${statementIndex}:plan`,
				unknown_type: "PLAN_BUILD_FAILURE",
				task_id: task.task_id,
				statement_id: statementId,
				artifact_id: artifactId,
				span: statementSpan,
				raw_sql: statementRaw,
				reason: planError,
			});
		}

		statements.push({
			statement_id: statementId,
			task_id: task.task_id,
			artifact_id: artifactId,
			statement_index: statementIndex,
			statement_type: classifyStatement(statementRaw),
			span: statementSpan,
			raw_sql: statementRaw,
			parse_status: !plan ? "FAILED" : cell.errors > 0 || plan.unknowns.length ? "PARTIAL" : "SUCCESS",
			syntax_error_count: cell.errors,
			syntax_diagnostics: cell.diagnostics,
			plan_error: planError,
		});
		addEdge({
			edge_type: "TASK_HAS_STATEMENT",
			from: `task:${task.task_id}`,
			to: statementId,
			provenance: "EXTRACTED",
		});

		if (!plan) continue;
		for (const table of plan.physical_inputs) {
			const normalizedTable = normalizeName(table);
			inputs.add(normalizedTable);
			const datasetId = `dataset:${normalizedTable}`;
			addEntity({ entity_id: datasetId, entity_type: "DATASET", name: normalizedTable });
			addEdge({
				edge_type: "TASK_READS_DATASET",
				from: `task:${task.task_id}`,
				to: datasetId,
				provenance: "SQL_PLAN",
			});
		}

		for (const item of plan.unknowns) {
			const localRelation = (plan.relations as JsonRecord[]).find((relation) => relation.id === item.node_id);
			const expressions = localRelation?.type === "project" ? (localRelation.expressions ?? []) : [];
			const reasonCode =
				item.field === "physical"
					? "PHYSICAL_COLUMN_LINEAGE_UNRESOLVED"
					: expressions.some((expression: JsonRecord) => expression.output === "*")
						? "STAR_EXPANSION_UNRESOLVED"
						: expressions.some((expression: JsonRecord) => expression.output === "?")
							? "ANONYMOUS_OUTPUT_NAME_UNRESOLVED"
							: classifyStatement(statementRaw) === "CREATE_TABLE" && expressions.length === 0
								? "NON_QUERY_OUTPUT_NOT_APPLICABLE"
								: "PLAN_OUTPUT_UNRESOLVED";
			const unknownType = reasonCode === "NON_QUERY_OUTPUT_NOT_APPLICABLE" ? "NOT_APPLICABLE" : "PLAN_UNKNOWN";
			unknowns.push({
				unknown_id: `unknown:${task.task_id}:${statementIndex}:plan:${unknowns.length + 1}`,
				unknown_type: unknownType,
				task_id: task.task_id,
				statement_id: statementId,
				node_id: globalRelationId(task.task_id, statementIndex, item.node_id),
				field: item.field,
				reason_code: reasonCode,
				reason: item.reason,
				span: item.span ?? null,
			});
		}

		for (const localRelation of plan.relations as JsonRecord[]) {
			const relation = globalizeRelation(task.task_id, statementIndex, localRelation);
			const span = relation.span as { start: number; end: number };
			const validSpan =
				Number.isInteger(span?.start) &&
				Number.isInteger(span?.end) &&
				span.start >= 0 &&
				span.end >= span.start &&
				span.end <= sql.length;
			const rawSql = validSpan ? sql.slice(span.start, span.end) : "";
			const relationRecord = {
				node_id: relation.id,
				node_type: "RELATION",
				task_id: task.task_id,
				statement_id: statementId,
				artifact_id: artifactId,
				relation,
				raw_sql: rawSql,
				span_status: validSpan && rawSql.length > 0 ? "PASS" : "PARTIAL",
			};
			relations.push(relationRecord);
			addEdge({
				edge_type: "STATEMENT_HAS_RELATION",
				from: statementId,
				to: relation.id,
				provenance: "SQL_PLAN",
			});

			const relationInputs: string[] = [];
			if (relation.source) relationInputs.push(relation.source);
			if (relation.left) relationInputs.push(relation.left);
			if (relation.right) relationInputs.push(relation.right);
			if (relation.branches) relationInputs.push(...relation.branches);
			for (const input of relationInputs) {
				addEdge({
					edge_type: "RELATION_INPUT",
					from: input,
					to: relation.id,
					provenance: "SQL_PLAN",
				});
			}

			if (!validSpan || rawSql.length === 0) {
				unknowns.push({
					unknown_id: `unknown:${task.task_id}:${statementIndex}:span:${safeToken(localRelation.id)}`,
					unknown_type: "RELATION_SPAN_INVALID_OR_EMPTY",
					task_id: task.task_id,
					statement_id: statementId,
					node_id: relation.id,
					span: relation.span ?? null,
				});
			}

			const expressionGroups: Array<{ role: string; items: JsonRecord[] }> = [];
			if (localRelation.type === "project") {
				expressionGroups.push({ role: "PROJECT_EXPRESSION", items: localRelation.expressions ?? [] });
			}
			if (localRelation.type === "aggregate") {
				expressionGroups.push({ role: "AGGREGATE_MEASURE", items: localRelation.measures ?? [] });
			}
			for (const group of expressionGroups) {
				for (const [ordinal, expression] of group.items.entries()) {
					const schemaExpansion = expression.star_expansion === true;
					const fieldNodeId = `${relation.id}:field:${group.role.toLowerCase()}:${ordinal}:${safeToken(expression.output)}`;
					const exprSpan = expression.span as { start: number; end: number };
					const exprSpanValid =
						Number.isInteger(exprSpan?.start) &&
						Number.isInteger(exprSpan?.end) &&
						exprSpan.start >= 0 &&
						exprSpan.end >= exprSpan.start &&
						exprSpan.end <= sql.length;
					const exactRaw = exprSpanValid ? sql.slice(exprSpan.start, exprSpan.end) : "";
					const roundtrip =
						exprSpanValid &&
						exactRaw.length > 0 &&
						normalizeWhitespace(exactRaw) === normalizeWhitespace(expression.expr_text);
					fieldExpressions.push({
						node_id: fieldNodeId,
						node_type: "FIELD_EXPRESSION",
						task_id: task.task_id,
						statement_id: statementId,
						artifact_id: artifactId,
						relation_node_id: relation.id,
						role: group.role,
						ordinal,
						output: expression.output,
						expression: stripDisplayFields(expression),
						raw_sql: exactRaw,
						span_roundtrip: schemaExpansion
							? "NOT_APPLICABLE_SCHEMA_EXPANSION"
							: roundtrip
								? "PASS"
								: "FAIL",
						expansion_provenance: schemaExpansion ? "SZDATA_TABLE_DDL" : null,
					});
					addEdge({
						edge_type: "RELATION_EMITS_FIELD_EXPRESSION",
						from: relation.id,
						to: fieldNodeId,
						provenance: "SQL_PLAN",
					});
					if (!schemaExpansion && !roundtrip) {
						unknowns.push({
							unknown_id: `unknown:${task.task_id}:${statementIndex}:field-span:${fieldExpressions.length}`,
							unknown_type: "FIELD_EXPRESSION_SPAN_ROUNDTRIP_FAILED",
							task_id: task.task_id,
							statement_id: statementId,
							node_id: fieldNodeId,
							span: exprSpan ?? null,
							expected_normalized: expression.expr_text,
							actual_raw: exactRaw,
						});
					}
				}
			}
		}
	}

	for (const focusOutput of task.focus_outputs) {
		const fieldId = `field:${normalizeName(task.writes)}:${focusOutput.toLowerCase()}`;
		addEntity({
			entity_id: fieldId,
			entity_type: "DATASET_FIELD",
			dataset: normalizeName(task.writes),
			field: focusOutput.toLowerCase(),
		});
		const matches = fieldExpressions.filter(
			(item) => item.task_id === task.task_id && item.output.toLowerCase() === focusOutput.toLowerCase(),
		);
		if (matches.length === 0) {
			unknowns.push({
				unknown_id: `unknown:${task.task_id}:focus-output:${focusOutput.toLowerCase()}`,
				unknown_type: "FOCUS_OUTPUT_NOT_FOUND",
				task_id: task.task_id,
				field: focusOutput,
			});
		}
		for (const match of matches) {
			addEdge({
				edge_type: "FIELD_EXPRESSION_WRITES_FIELD",
				from: match.node_id,
				to: fieldId,
				provenance: "PROFILE_TARGET_PLUS_SQL_EXPRESSION",
				artifact_id: match.artifact_id,
			});
		}
	}
}

// Expression dependencies are emitted only from structured IR column facts and
// relation topology. No SQL text or field-name heuristic participates here.
const relationById = new Map(relations.map((item) => [item.node_id as string, item]));

function relationAncestors(startId: string): Map<string, number> {
	const distances = new Map<string, number>();
	const queue: Array<{ id: string; distance: number }> = [{ id: startId, distance: 0 }];
	while (queue.length > 0) {
		const current = queue.shift()!;
		if (distances.has(current.id)) continue;
		distances.set(current.id, current.distance);
		const relation = relationById.get(current.id)?.relation as JsonRecord | undefined;
		if (!relation) continue;
		const inputs = [relation.source, relation.left, relation.right, ...(relation.branches ?? [])].filter(Boolean);
		for (const input of inputs) queue.push({ id: input, distance: current.distance + 1 });
	}
	return distances;
}

function physicalInputs(fieldExpression: JsonRecord): Array<{ table: string; column: string }> {
	const inputs = ((fieldExpression.expression as JsonRecord)?.input_columns ?? []) as JsonRecord[];
	const unique = new Map<string, { table: string; column: string }>();
	for (const input of inputs) {
		for (const physical of (input.physical ?? []) as JsonRecord[]) {
			const value = { table: normalizeName(physical.table), column: normalizeName(physical.column) };
			unique.set(`${value.table}.${value.column}`, value);
		}
	}
	return [...unique.values()];
}

for (const fieldExpression of fieldExpressions) {
	const inputs = physicalInputs(fieldExpression);
	const ancestors = relationAncestors(fieldExpression.relation_node_id as string);
	for (const input of inputs) {
		const fieldId = `field:${input.table}:${input.column}`;
		addEntity({
			entity_id: fieldId,
			entity_type: "DATASET_FIELD",
			dataset: input.table,
			field: input.column,
		});
		addEdge({
			edge_type: "DATASET_FIELD_FLOWS_TO_EXPRESSION",
			from: fieldId,
			to: fieldExpression.node_id,
			dataset: input.table,
			field: input.column,
			task_id: fieldExpression.task_id,
			provenance: "SQL_IR_COLUMN_REF",
			artifact_id: fieldExpression.artifact_id,
		});

		for (const relationId of ancestors.keys()) {
			const relationRecord = relationById.get(relationId);
			const relation = relationRecord?.relation as JsonRecord | undefined;
			if (relation?.type !== "read" || normalizeName(relation.table) !== input.table) continue;
			addEdge({
				edge_type: "READ_RELATION_READS_FIELD_AS_EXPRESSION",
				from: relationId,
				to: fieldExpression.node_id,
				dataset: input.table,
				field: input.column,
				task_id: fieldExpression.task_id,
				provenance: "SQL_IR_COLUMN_REF_PLUS_RELATION_TOPOLOGY",
				artifact_id: fieldExpression.artifact_id,
			});
		}
	}
}

for (const aggregateExpression of fieldExpressions.filter((item) => item.role === "AGGREGATE_MEASURE")) {
	const aggregateInputs = physicalInputs(aggregateExpression);
	const ancestors = relationAncestors(aggregateExpression.relation_node_id as string);
	for (const input of aggregateInputs) {
		const candidates = fieldExpressions
			.filter(
				(item) =>
					item.task_id === aggregateExpression.task_id &&
					item.role === "PROJECT_EXPRESSION" &&
					ancestors.has(item.relation_node_id as string) &&
					physicalInputs(item).some(
						(candidate) => candidate.table === input.table && candidate.column === input.column,
					),
			)
			.sort(
				(left, right) =>
					(ancestors.get(left.relation_node_id as string) ?? Number.MAX_SAFE_INTEGER) -
					(ancestors.get(right.relation_node_id as string) ?? Number.MAX_SAFE_INTEGER),
			);
		const sourceExpression = candidates[0];
		if (!sourceExpression) continue;
		addEdge({
			edge_type: "FIELD_EXPRESSION_FEEDS_EXPRESSION",
			from: sourceExpression.node_id,
			to: aggregateExpression.node_id,
			dataset: input.table,
			field: input.column,
			task_id: aggregateExpression.task_id,
			provenance: "SQL_IR_COLUMN_REF_PLUS_RELATION_TOPOLOGY",
			artifact_id: aggregateExpression.artifact_id,
		});
	}
}

for (const producer of profile.tasks) {
	const produced = normalizeName(producer.writes);
	for (const consumer of profile.tasks) {
		if (producer.task_id === consumer.task_id) continue;
		if (!taskInputs.get(consumer.task_id)?.has(produced)) continue;
		addEdge({
			edge_type: "TASK_DATASET_FLOW",
			from: `task:${producer.task_id}`,
			to: `task:${consumer.task_id}`,
			dataset: produced,
			provenance: "PROFILE_TARGET_MATCHES_SQL_INPUT",
			artifact_id: sources.find((source) => source.task_id === consumer.task_id)?.artifact_id,
		});
	}
}

const relationIds = new Set(relations.map((item) => item.node_id));
const relationReferencesResolve = relations.every((item) => {
	const relation = item.relation;
	const refs = [relation.source, relation.left, relation.right, ...(relation.branches ?? [])].filter(Boolean);
	return refs.every((ref: string) => relationIds.has(ref));
});
const planUnknownCount = unknowns.filter((item) => item.unknown_type === "PLAN_UNKNOWN").length;
const notApplicableCount = unknowns.filter((item) => item.unknown_type === "NOT_APPLICABLE").length;
const unresolvedStarCount = unknowns.filter((item) => item.reason_code === "STAR_EXPANSION_UNRESOLVED").length;
const syntaxDiagnosticCount = unknowns.filter((item) => item.unknown_type === "SYNTAX_DIAGNOSTIC").length;
const parserFailureCount = unknowns.filter((item) =>
	["PARSER_FAILURE", "PLAN_BUILD_FAILURE"].includes(item.unknown_type),
).length;
const spanFailureCount = unknowns.filter((item) => item.unknown_type.includes("SPAN_")).length;
const schemaExpandedFieldCount = fieldExpressions.filter((item) => item.expression.star_expansion === true).length;
const starSchemaRecords = (schemaEvidence.records as JsonRecord[]).filter(
	(record) => record.required_for_star === true,
);

mkdirSync(outputDir, { recursive: true });
const outputFiles = [
	writeJsonl("source_artifacts.jsonl", sources),
	writeJsonl("entities.jsonl", [...entities.values()]),
	writeJsonl("statements.jsonl", statements),
	writeJsonl("relation_nodes.jsonl", relations),
	writeJsonl("field_expression_nodes.jsonl", fieldExpressions),
	writeJsonl("edges.jsonl", [...edges.values()]),
	writeJsonl("unknowns.jsonl", unknowns),
];

const sourceBundleHash = sha256(
	sources
		.map((item) => item.content_sha256)
		.sort()
		.join("\n"),
);
const indicatorInputs = [...(taskInputs.get("162610") ?? new Set<string>())].sort();
const t98ProducerTasks = profile.tasks
	.filter((task) => normalizeName(task.writes) === "pdata_n.t98_otc_deri_comp_sale_info")
	.map((task) => task.task_id)
	.sort();
const actionableUnknownCount = unknowns.length - notApplicableCount;
const runStatus = parserFailureCount > 0 ? "FAILED" : actionableUnknownCount > 0 ? "PARTIAL" : "SUCCESS";
const manifest = {
	schema_version: "indicator-processing-graph-manifest-v1",
	run_id: `indicator-processing-graph-${sourceBundleHash.slice(0, 16)}`,
	case_id: profile.case_id,
	indicator_id: profile.indicator_id,
	target_field: profile.target_field,
	status: runStatus,
	method: {
		parser: "sqllens",
		parser_version: "1.8.0",
		adapter: "plan-adapter",
		adapter_version: "0.2.2",
		contract_version: "1.1.3",
		dialect: profile.dialect,
	},
	inputs: {
		profile: relative(workspace, profilePath).replace(/\\/g, "/"),
		profile_sha256: sha256(readFileSync(profilePath)),
		source_bundle_sha256: sourceBundleHash,
		schema_evidence: {
			path: relative(workspace, schemaEvidencePath).replace(/\\/g, "/"),
			sha256: sha256(schemaEvidenceBytes),
			source: schemaEvidence.source,
			required_table_count: schemaEvidence.required_table_count,
			success_count: schemaEvidence.success_count,
			unresolved_count: schemaEvidence.unresolved_count,
		},
	},
	counts: {
		tasks: profile.tasks.length,
		source_artifacts: sources.length,
		statements: statements.length,
		relation_nodes: relations.length,
		field_expression_nodes: fieldExpressions.length,
		entities: entities.size,
		edges: edges.size,
		unknowns: unknowns.length,
		plan_unknowns: planUnknownCount,
		not_applicable: notApplicableCount,
		unresolved_star_expansions: unresolvedStarCount,
		syntax_diagnostics: syntaxDiagnosticCount,
		parser_failures: parserFailureCount,
		span_failures: spanFailureCount,
		schema_expanded_fields: schemaExpandedFieldCount,
	},
	coverage: {
		t98_producer_tasks: t98ProducerTasks,
		indicator_inputs: indicatorInputs,
	},
	gates: {
		source_artifacts_complete: sources.length === profile.tasks.length,
		all_statements_retained: statements.length === sources.reduce((sum, item) => sum + item.statement_count, 0),
		relation_references_resolve: relationReferencesResolve,
		no_parser_failure: parserFailureCount === 0,
		no_syntax_diagnostics: syntaxDiagnosticCount === 0,
		all_required_star_tables_have_schema:
			starSchemaRecords.length === schemaEvidence.required_star_table_count &&
			starSchemaRecords.every((record) => record.status === "SUCCESS"),
		no_unresolved_star_expansion: unresolvedStarCount === 0,
		all_field_spans_roundtrip: fieldExpressions.every((item) =>
			item.expression.star_expansion === true
				? item.span_roundtrip === "NOT_APPLICABLE_SCHEMA_EXPANSION"
				: item.span_roundtrip === "PASS",
		),
		no_silent_loss_claimed: false,
	},
	boundaries: {
		business_logic_correctness: "NOT_EVALUATED",
		runtime_execution: "NOT_EVALUATED",
		business_rows_read: false,
		external_model_calls: 0,
		cross_task_field_stitching: "PARTIAL_DATASET_LEVEL_ONLY",
	},
	outputs: outputFiles.map((item) => ({
		path: relative(outputDir, item.path).replace(/\\/g, "/"),
		row_count: item.count,
		content_sha256: item.hash,
	})),
};
writeFileSync(resolve(outputDir, "manifest.json"), JSON.stringify(manifest, null, 2) + "\n", "utf8");

console.log(
	JSON.stringify({ output: outputDir, status: runStatus, counts: manifest.counts, gates: manifest.gates }, null, 2),
);
