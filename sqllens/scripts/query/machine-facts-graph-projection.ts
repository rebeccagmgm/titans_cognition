import { createHash } from "node:crypto";
import { existsSync, readFileSync } from "node:fs";
import { isAbsolute, join, relative, resolve, sep } from "node:path";

import type { GraphInputs, ProcessingProfile } from "./minimal-causal-paths-from-machine-facts.ts";
import { validateBundle } from "../machine-facts/machine-facts.ts";

type JsonRecord = Record<string, any>;

const workspace = resolve(import.meta.dirname, "../../..");

function sha256(value: string | Buffer): string {
	return createHash("sha256").update(value).digest("hex");
}

function readJson<T>(path: string): T {
	return JSON.parse(readFileSync(path, "utf8")) as T;
}

function readJsonl(path: string): JsonRecord[] {
	if (!existsSync(path)) return [];
	const text = readFileSync(path, "utf8").trim();
	return text ? text.split(/\r?\n/).map((line) => JSON.parse(line) as JsonRecord) : [];
}

function normalizeName(value: unknown): string {
	return String(value ?? "")
		.replace(/[`"\[\]]/g, "")
		.replace(/\s+/g, "")
		.toLowerCase();
}

function fieldEntityId(dataset: string, field: string): string {
	return `field:${normalizeName(dataset)}:${normalizeName(field)}`;
}

function artifactForStatement(statements: JsonRecord[], statementId: string): string | undefined {
	return statements.find((statement) => statement.statement_id === statementId)?.artifact_id as string | undefined;
}

function relationInputs(relation: JsonRecord): string[] {
	return [relation.source, relation.left, relation.right, ...(relation.branches ?? [])].filter(Boolean) as string[];
}

function relationAncestors(relations: Map<string, JsonRecord>, startId: string | undefined): Set<string> {
	const ancestors = new Set<string>();
	const queue = startId ? [startId] : [];
	while (queue.length > 0) {
		const current = queue.shift()!;
		if (ancestors.has(current)) continue;
		ancestors.add(current);
		const relation = relations.get(current)?.relation as JsonRecord | undefined;
		if (relation) queue.push(...relationInputs(relation));
	}
	return ancestors;
}

function physicalInputs(expression: JsonRecord): Array<{ table: string; column: string }> {
	const refs = (expression.input_columns ?? []) as JsonRecord[];
	const unique = new Map<string, { table: string; column: string }>();
	for (const ref of refs) {
		if (ref.resolution !== "PHYSICAL") continue;
		for (const physical of (ref.physical ?? []) as JsonRecord[]) {
			if (!physical.table || !physical.column) continue;
			const value = { table: normalizeName(physical.table), column: normalizeName(physical.column) };
			unique.set(`${value.table}.${value.column}`, value);
		}
	}
	return [...unique.values()];
}

function expressionFactsFromRelation(relation: JsonRecord, field: JsonRecord): JsonRecord {
	const groups = field.role === "AGGREGATE_MEASURE" ? relation.measures : relation.expressions;
	const candidate = Array.isArray(groups)
		? (groups.find(
				(expression: JsonRecord) =>
					expression.output === field.output_name && expression.span?.start === field.source_span?.start,
			) ?? groups[field.ordinal])
		: undefined;
	const expression = candidate
		? { ...candidate }
		: {
				output: field.output_name,
				expr_text: field.expression_text,
				span: field.source_span,
			};
	const resolvedInputs = (field.input_fields ?? []).map((input: JsonRecord) => ({
		name: input.column,
		physical: [{ table: input.table, column: input.column }],
		resolution: "PHYSICAL",
	}));
	const unresolvedInputs = (field.unresolved_input_columns ?? []).map((input: JsonRecord) => ({
		name: input.name,
		qualifier: input.qualifier ?? undefined,
		physical: null,
		resolution: input.resolution ?? "UNRESOLVED",
	}));
	return { ...expression, input_columns: [...resolvedInputs, ...unresolvedInputs] };
}

function addEntity(entities: Map<string, JsonRecord>, entity: JsonRecord): void {
	if (entity.entity_id) entities.set(entity.entity_id, entity);
}

function addEdge(edges: Map<string, JsonRecord>, edge: JsonRecord): void {
	const key = JSON.stringify([edge.edge_type, edge.from, edge.to, edge.dataset ?? null, edge.field ?? null]);
	edges.set(key, edge);
}

function taskDatasetReads(datasetIo: JsonRecord[], taskId: string): Set<string> {
	return new Set(
		datasetIo
			.filter((record) => record.task_id === taskId && record.direction === "READ")
			.map((record) => normalizeName(record.physical_dataset)),
	);
}

function bundlePath(factsRoot: string, taskId: string, file: string): string {
	return join(factsRoot, "registry", "tasks", taskId, "bundle", file);
}

function profileSqlHash(taskId: string, snapshot: string): string {
	const sqlPath = resolve(workspace, snapshot);
	const relativePath = relative(workspace, sqlPath);
	if (!snapshot || isAbsolute(relativePath) || relativePath === ".." || relativePath.startsWith(`..${sep}`)) {
		throw new Error(`unsafe SQL snapshot for task ${taskId}: ${snapshot}`);
	}
	if (!existsSync(sqlPath)) throw new Error(`missing SQL snapshot for task ${taskId}: ${snapshot}`);
	return sha256(readFileSync(sqlPath));
}

function assertValidatedBundle(factsRoot: string, taskId: string, expectedSqlHash: string): JsonRecord {
	const bundleDir = join(factsRoot, "registry", "tasks", taskId, "bundle");
	const errors = validateBundle(bundleDir);
	if (errors.length > 0) throw new Error(`invalid Machine Facts Bundle ${taskId}: ${errors.join("; ")}`);
	const manifestPath = join(bundleDir, "manifest.json");
	const statusPath = join(factsRoot, "registry", "tasks", taskId, "analysis-status.json");
	if (!existsSync(statusPath)) throw new Error(`missing analysis status for task ${taskId}`);
	const manifest = readJson<JsonRecord>(manifestPath);
	const status = readJson<JsonRecord>(statusPath);
	const manifestHash = sha256(readFileSync(manifestPath));
	if (status.state !== "SUCCESS" || status.current_manifest_sha256 !== manifestHash || status.task_id !== taskId) {
		throw new Error(`analysis status does not attest current SUCCESS Bundle for task ${taskId}`);
	}
	if (manifest.inputs?.sql_sha256 !== expectedSqlHash) {
		throw new Error(
			`SQL snapshot hash mismatch for task ${taskId}: profile=${expectedSqlHash}, bundle=${manifest.inputs?.sql_sha256 ?? "missing"}`,
		);
	}
	return manifest;
}

/**
 * Projects canonical Machine Facts into the legacy GraphInputs contract used by
 * the minimal causal path assembler. The projection is derived and case/profile
 * scoped; it is not written back into the canonical task bundle.
 */
export function loadMachineFactsGraphInputs(profilePath: string, factsRoot: string): GraphInputs {
	const profile = readJson<ProcessingProfile>(profilePath);
	const profileHash = sha256(readFileSync(profilePath));
	const entities = new Map<string, JsonRecord>();
	const edges = new Map<string, JsonRecord>();
	const fieldExpressions: JsonRecord[] = [];
	const relations: JsonRecord[] = [];
	const allDatasetIo: JsonRecord[] = [];
	const datasetIoByTask = new Map<string, JsonRecord[]>();

	for (const task of profile.tasks) {
		if (!task.sql_snapshot) throw new Error(`profile task ${task.task_id} has no sql_snapshot`);
		assertValidatedBundle(factsRoot, task.task_id, profileSqlHash(task.task_id, task.sql_snapshot));
		const statements = readJsonl(bundlePath(factsRoot, task.task_id, "statements.jsonl"));
		const taskRelations = readJsonl(bundlePath(factsRoot, task.task_id, "relation-nodes.jsonl"));
		const taskFields = readJsonl(bundlePath(factsRoot, task.task_id, "field-expression-nodes.jsonl"));
		const datasetIo = readJsonl(bundlePath(factsRoot, task.task_id, "dataset-io.jsonl"));
		allDatasetIo.push(...datasetIo);
		datasetIoByTask.set(task.task_id, datasetIo);
		const relationMap = new Map(taskRelations.map((record) => [record.relation_id as string, record]));

		addEntity(entities, {
			entity_id: `task:${task.task_id}`,
			entity_type: "TASK",
			task_id: task.task_id,
			role: task.role,
		});
		addEntity(entities, {
			entity_id: `dataset:${normalizeName(task.writes)}`,
			entity_type: "DATASET",
			name: normalizeName(task.writes),
		});

		for (const relationRecord of taskRelations) {
			relations.push({
				node_id: relationRecord.relation_id,
				node_type: "RELATION",
				task_id: task.task_id,
				statement_id: relationRecord.statement_id,
				artifact_id: artifactForStatement(statements, relationRecord.statement_id),
				relation: relationRecord.relation,
			});
		}

		for (const field of taskFields) {
			const relationRecord = relationMap.get(field.relation_id);
			const relation = relationRecord?.relation as JsonRecord | undefined;
			const expression = expressionFactsFromRelation(relation ?? {}, field);
			const projected = {
				node_id: field.expression_id,
				node_type: "FIELD_EXPRESSION",
				task_id: task.task_id,
				statement_id: field.statement_id,
				artifact_id: field.artifact_id,
				relation_node_id: field.relation_id,
				role: field.role,
				ordinal: field.ordinal,
				output: field.output_name,
				expression,
				input_dependency_status: field.input_dependency_status,
				unresolved_input_columns: field.unresolved_input_columns ?? [],
				raw_sql: field.expression_text,
				span_roundtrip: "NOT_EVALUATED_BY_PROJECTION",
			};
			fieldExpressions.push(projected);
			for (const input of physicalInputs(expression)) {
				const fieldId = fieldEntityId(input.table, input.column);
				addEntity(entities, {
					entity_id: fieldId,
					entity_type: "DATASET_FIELD",
					dataset: input.table,
					field: input.column,
				});
				addEdge(edges, {
					edge_type: "DATASET_FIELD_FLOWS_TO_EXPRESSION",
					from: fieldId,
					to: field.expression_id,
					dataset: input.table,
					field: input.column,
					provenance: "MACHINE_FACTS_FIELD_INPUT",
					artifact_id: field.artifact_id,
				});
				for (const relationId of relationAncestors(relationMap, field.relation_id)) {
					const ancestor = relationMap.get(relationId)?.relation as JsonRecord | undefined;
					if (ancestor?.type !== "read" || normalizeName(ancestor.table) !== input.table) continue;
					addEdge(edges, {
						edge_type: "READ_RELATION_READS_FIELD_AS_EXPRESSION",
						from: relationId,
						to: field.expression_id,
						dataset: input.table,
						field: input.column,
						provenance: "MACHINE_FACTS_RELATION_TO_FIELD",
						artifact_id: field.artifact_id,
					});
				}
			}
		}

		for (const focusOutput of task.focus_outputs ?? []) {
			const fieldId = fieldEntityId(task.writes, focusOutput);
			addEntity(entities, {
				entity_id: fieldId,
				entity_type: "DATASET_FIELD",
				dataset: normalizeName(task.writes),
				field: normalizeName(focusOutput),
			});
			for (const expression of fieldExpressions.filter(
				(item) => item.task_id === task.task_id && normalizeName(item.output) === normalizeName(focusOutput),
			)) {
				addEdge(edges, {
					edge_type: "FIELD_EXPRESSION_WRITES_FIELD",
					from: expression.node_id,
					to: fieldId,
					provenance: "PROFILE_TARGET_PLUS_MACHINE_FACTS_EXPRESSION",
					artifact_id: expression.artifact_id,
					profile_sha256: profileHash,
					evidenceRefs: [`profile:${profileHash}`],
				});
			}
		}
	}

	for (const producer of profile.tasks) {
		const produced = normalizeName(producer.writes);
		const producerWrites = (datasetIoByTask.get(producer.task_id) ?? []).filter(
			(record) => record.direction === "WRITE" && normalizeName(record.physical_dataset) === produced,
		);
		for (const consumer of profile.tasks) {
			if (
				producer.task_id === consumer.task_id ||
				producerWrites.length === 0 ||
				!taskDatasetReads(allDatasetIo, consumer.task_id).has(produced)
			)
				continue;
			const evidenceRefs = producerWrites
				.map((record) =>
					artifactForStatement(
						readJsonl(bundlePath(factsRoot, producer.task_id, "statements.jsonl")),
						record.statement_id,
					),
				)
				.filter((value): value is string => Boolean(value));
			addEdge(edges, {
				edge_type: "TASK_DATASET_FLOW",
				from: `task:${producer.task_id}`,
				to: `task:${consumer.task_id}`,
				dataset: produced,
				provenance: "PROFILE_DECLARED_OUTPUT_PLUS_MACHINE_FACTS_READ",
				evidenceRefs: [`profile:${profileHash}`, ...evidenceRefs],
				profile_sha256: profileHash,
			});
		}
	}

	const relationsById = new Map(relations.map((record) => [record.node_id as string, record]));
	for (const aggregate of fieldExpressions.filter((item) => item.role === "AGGREGATE_MEASURE")) {
		const aggregateInputs = physicalInputs(aggregate.expression);
		const ancestors = relationAncestors(relationsById, aggregate.relation_node_id);
		for (const input of aggregateInputs) {
			const source = fieldExpressions
				.filter(
					(item) =>
						item.task_id === aggregate.task_id &&
						item.role === "PROJECT_EXPRESSION" &&
						ancestors.has(item.relation_node_id) &&
						physicalInputs(item.expression).some(
							(candidate) => candidate.table === input.table && candidate.column === input.column,
						),
				)
				.sort(
					(left, right) =>
						(ancestors.has(left.relation_node_id) ? 0 : 1) -
						(ancestors.has(right.relation_node_id) ? 0 : 1),
				)[0];
			if (!source) continue;
			addEdge(edges, {
				edge_type: "FIELD_EXPRESSION_FEEDS_EXPRESSION",
				from: source.node_id,
				to: aggregate.node_id,
				dataset: input.table,
				field: input.column,
				provenance: "MACHINE_FACTS_EXPRESSION_TO_AGGREGATE",
				artifact_id: aggregate.artifact_id,
			});
		}
	}

	return { profile, entities: [...entities.values()], edges: [...edges.values()], fieldExpressions, relations };
}

export function resolveWorkspacePath(path: string): string {
	return resolve(workspace, path);
}
