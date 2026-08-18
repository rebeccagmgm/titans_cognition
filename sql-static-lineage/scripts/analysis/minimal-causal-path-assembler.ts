import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { relative, resolve } from "node:path";
import { pathToFileURL } from "node:url";

type JsonRecord = Record<string, any>;
type PathType = "VALUE_FLOW" | "ROWSET_CONTROL";

interface TaskProfile {
	task_id: string;
	role: string;
	writes: string;
	sql_snapshot?: string;
	focus_outputs?: string[];
}

interface MinimalPathSpec {
	path_id: string;
	path_type: PathType;
	producer_role: string;
	producer_field: string;
	consumer_role: string;
	target_field: string;
	partition_assertion?: { field: string; literal: string };
	control_literal?: string;
}

export interface ProcessingProfile {
	case_id: string;
	indicator_id: string;
	target_field: string;
	tasks: TaskProfile[];
	minimal_causal_paths: MinimalPathSpec[];
}

export interface GraphInputs {
	profile: ProcessingProfile;
	entities: JsonRecord[];
	edges: JsonRecord[];
	fieldExpressions: JsonRecord[];
	relations: JsonRecord[];
}

interface CausalPath {
	pathId: string;
	pathType: PathType;
	description: string;
	status: "COMPLETE" | "PARTIAL";
	producerTaskId?: string;
	producerRole: string;
	consumerTaskId?: string;
	consumerRole: string;
	partitionSlice?: JsonRecord;
	steps: JsonRecord[];
	edges: JsonRecord[];
	gaps: string[];
	controlFlowNote?: string;
}

export interface MinimalCausalPathsResult {
	schemaVersion: "minimal-causal-paths-v1";
	caseId: string;
	status: "PASS" | "PARTIAL" | "FAIL";
	paths: CausalPath[];
	validation: JsonRecord;
	boundaries: { notClaimed: string[] };
}

const normalizeName = (value: string): string => value.replace(/[`"\[\]]/g, "").toLowerCase();
const fieldEntityId = (dataset: string, field: string): string =>
	`field:${normalizeName(dataset)}:${normalizeName(field)}`;

function readJson<T>(path: string): T {
	return JSON.parse(readFileSync(path, "utf8")) as T;
}

function readJsonl(path: string): JsonRecord[] {
	const text = readFileSync(path, "utf8").trim();
	return text ? text.split(/\r?\n/).map((line) => JSON.parse(line) as JsonRecord) : [];
}

export function loadGraphInputs(profilePath: string, outputDir: string): GraphInputs {
	return {
		profile: readJson<ProcessingProfile>(profilePath),
		entities: readJsonl(resolve(outputDir, "entities.jsonl")),
		edges: readJsonl(resolve(outputDir, "edges.jsonl")),
		fieldExpressions: readJsonl(resolve(outputDir, "field_expression_nodes.jsonl")),
		relations: readJsonl(resolve(outputDir, "relation_nodes.jsonl")),
	};
}

function uniqueTask(profile: ProcessingProfile, role: string, gaps: string[]): TaskProfile | undefined {
	const matches = profile.tasks.filter((task) => task.role === role);
	if (matches.length !== 1) gaps.push(`role ${role} expected one task, found ${matches.length}`);
	return matches.length === 1 ? matches[0] : undefined;
}

function expressionById(inputs: GraphInputs, nodeId: string | undefined): JsonRecord | undefined {
	return nodeId ? inputs.fieldExpressions.find((item) => item.node_id === nodeId) : undefined;
}

function relationById(inputs: GraphInputs, nodeId: string | undefined): JsonRecord | undefined {
	return nodeId ? inputs.relations.find((item) => item.node_id === nodeId) : undefined;
}

function relationInputs(relationRecord: JsonRecord | undefined): string[] {
	const relation = relationRecord?.relation as JsonRecord | undefined;
	if (!relation) return [];
	return [relation.source, relation.left, relation.right, ...(relation.branches ?? [])].filter(Boolean);
}

function relationAncestors(inputs: GraphInputs, startId: string | undefined): Set<string> {
	const ancestors = new Set<string>();
	const queue = startId ? [startId] : [];
	while (queue.length > 0) {
		const current = queue.shift()!;
		if (ancestors.has(current)) continue;
		ancestors.add(current);
		queue.push(...relationInputs(relationById(inputs, current)));
	}
	return ancestors;
}

function physicalColumnMatches(ref: JsonRecord, dataset: string, field: string): boolean {
	return ((ref.physical ?? []) as JsonRecord[]).some(
		(item) =>
			normalizeName(item.table) === normalizeName(dataset) && normalizeName(item.column) === normalizeName(field),
	);
}

function relationReferencesField(relation: JsonRecord, key: string, dataset: string, field: string): boolean {
	return ((relation[key] ?? []) as JsonRecord[]).some((ref) => physicalColumnMatches(ref, dataset, field));
}

function structuredLiteralEquals(value: string, expected: string): boolean {
	const trimmed = value.trim();
	const unquoted =
		(trimmed.startsWith("'") && trimmed.endsWith("'")) || (trimmed.startsWith('"') && trimmed.endsWith('"'))
			? trimmed.slice(1, -1)
			: trimmed;
	return unquoted === expected;
}

function artifactRefs(...items: Array<JsonRecord | undefined>): string[] {
	return [...new Set(items.map((item) => item?.artifact_id).filter((value): value is string => Boolean(value)))];
}

function inputResolutionStatus(expression: JsonRecord | undefined): "RESOLVED" | "PARTIAL" | "UNRESOLVED" | "DERIVED_OUTPUT" | "NO_PHYSICAL_INPUT" {
	const status = expression?.input_dependency_status ?? expression?.expression?.input_dependency_status;
	if (status === "PHYSICAL") return "RESOLVED";
	if (status === "PARTIAL") return "PARTIAL";
	if (status === "DERIVED_OUTPUT") return "DERIVED_OUTPUT";
	if (status === "NO_PHYSICAL_INPUT") return "NO_PHYSICAL_INPUT";
	if (status === undefined) {
		const refs = (expression?.expression?.input_columns ?? []) as JsonRecord[];
		const physicalRefs = refs.filter((ref) => Array.isArray(ref.physical) && ref.physical.length > 0);
		if (refs.length > 0 && physicalRefs.length === refs.length) return "RESOLVED";
		if (physicalRefs.length > 0) return "PARTIAL";
	}
	return "UNRESOLVED";
}

function resolutionGap(expression: JsonRecord | undefined, label: string): string | undefined {
	const status = inputResolutionStatus(expression);
	return status === "PARTIAL" || status === "UNRESOLVED" ? `${label} input dependency status is ${status}` : undefined;
}

function sourceEdge(edge: JsonRecord, index: number): JsonRecord {
	return {
		edgeId: `SOURCE-${index + 1}`,
		edgeType: edge.edge_type,
		from: edge.from,
		to: edge.to,
		dataset: edge.dataset,
		field: edge.field,
		provenance: edge.provenance,
		evidenceRefs: [...new Set([...(edge.evidenceRefs ?? []), ...(edge.artifact_id ? [edge.artifact_id] : [])])],
	};
}

function findWriteEdge(
	inputs: GraphInputs,
	taskId: string | undefined,
	dataset: string | undefined,
	field: string,
): JsonRecord | undefined {
	if (!taskId || !dataset) return undefined;
	const target = fieldEntityId(dataset, field);
	return inputs.edges.find(
		(edge) =>
			edge.edge_type === "FIELD_EXPRESSION_WRITES_FIELD" &&
			edge.to === target &&
			String(edge.from).startsWith(`task:${taskId}:`),
	);
}

function findDatasetFlow(
	inputs: GraphInputs,
	producerTaskId: string | undefined,
	consumerTaskId: string | undefined,
	dataset: string | undefined,
): JsonRecord | undefined {
	if (!producerTaskId || !consumerTaskId || !dataset) return undefined;
	return inputs.edges.find(
		(edge) =>
			edge.edge_type === "TASK_DATASET_FLOW" &&
			edge.from === `task:${producerTaskId}` &&
			edge.to === `task:${consumerTaskId}` &&
			normalizeName(edge.dataset) === normalizeName(dataset),
	);
}

function targetAggregate(
	inputs: GraphInputs,
	consumerTaskId: string | undefined,
	targetDataset: string | undefined,
	targetField: string,
): { expression?: JsonRecord; writeEdge?: JsonRecord } {
	if (!consumerTaskId || !targetDataset) return {};
	const target = fieldEntityId(targetDataset, targetField);
	const writeEdges = inputs.edges
		.filter(
			(edge) =>
				edge.edge_type === "FIELD_EXPRESSION_WRITES_FIELD" &&
				edge.to === target &&
				String(edge.from).startsWith(`task:${consumerTaskId}:`),
		)
		.sort((left, right) => String(left.from).localeCompare(String(right.from)));
	for (const writeEdge of writeEdges) {
		const expression = expressionById(inputs, writeEdge.from);
		if (expression?.role === "AGGREGATE_MEASURE") return { expression, writeEdge };
	}
	return {};
}

function assembleValueFlow(inputs: GraphInputs, spec: MinimalPathSpec): CausalPath {
	const gaps: string[] = [];
	const producer = uniqueTask(inputs.profile, spec.producer_role, gaps);
	const consumer = uniqueTask(inputs.profile, spec.consumer_role, gaps);
	const producerDataset = producer?.writes;
	const targetDataset = consumer?.writes;
	const producerWrite = findWriteEdge(inputs, producer?.task_id, producerDataset, spec.producer_field);
	if (!producerWrite) gaps.push("missing producer FIELD_EXPRESSION_WRITES_FIELD edge");
	const producerExpression = expressionById(inputs, producerWrite?.from);
	if (!producerExpression) gaps.push("missing producer field expression");
	const producerResolutionGap = resolutionGap(producerExpression, "producer expression");
	if (producerResolutionGap) gaps.push(producerResolutionGap);
	const datasetFlow = findDatasetFlow(inputs, producer?.task_id, consumer?.task_id, producerDataset);
	if (!datasetFlow) gaps.push("missing TASK_DATASET_FLOW edge");
	const aggregate = targetAggregate(inputs, consumer?.task_id, targetDataset, spec.target_field);
	if (!aggregate.expression || !aggregate.writeEdge) gaps.push("missing target aggregate write edge");
	const feedEdge = inputs.edges.find(
		(edge) =>
			edge.edge_type === "FIELD_EXPRESSION_FEEDS_EXPRESSION" &&
			edge.to === aggregate.expression?.node_id &&
			normalizeName(edge.dataset ?? "") === normalizeName(producerDataset ?? "") &&
			normalizeName(edge.field ?? "") === normalizeName(spec.producer_field),
	);
	if (!feedEdge) gaps.push("missing FIELD_EXPRESSION_FEEDS_EXPRESSION edge");
	const consumerExpression = expressionById(inputs, feedEdge?.from);
	const consumerResolutionGap = resolutionGap(consumerExpression, "consumer expression");
	if (consumerResolutionGap) gaps.push(consumerResolutionGap);
	if (!consumerExpression) gaps.push("missing consumer read expression");
	const readEdge = inputs.edges.find(
		(edge) =>
			edge.edge_type === "READ_RELATION_READS_FIELD_AS_EXPRESSION" &&
			edge.to === consumerExpression?.node_id &&
			normalizeName(edge.dataset ?? "") === normalizeName(producerDataset ?? "") &&
			normalizeName(edge.field ?? "") === normalizeName(spec.producer_field),
	);
	if (!readEdge) gaps.push("missing READ_RELATION_READS_FIELD_AS_EXPRESSION edge");
	const readRelation = relationById(inputs, readEdge?.from);
	const sourceRef = ((aggregate.expression?.expression as JsonRecord | undefined)?.input_columns ?? []).find(
		(ref: JsonRecord) => physicalColumnMatches(ref, producerDataset ?? "", spec.producer_field),
	) as JsonRecord | undefined;
	const aggregateFacts = (aggregate.expression?.expression as JsonRecord | undefined)?.expression_facts as
		JsonRecord | undefined;
	if (!aggregateFacts?.functions?.length) gaps.push("aggregate expression has no structured function fact");

	const steps: JsonRecord[] = [];
	if (producerExpression)
		steps.push({
			stepType: "TASK_OUTPUT_EXPRESSION",
			taskId: producer?.task_id,
			fieldNodeId: producerExpression.node_id,
			outputField: spec.producer_field,
			expression: producerExpression.expression?.expr_text,
			provenance: "SQL_IR_EXTRACTED",
			evidenceRefs: artifactRefs(producerExpression),
		});
	if (producerWrite)
		steps.push({
			stepType: "MATERIALIZES_AS",
			taskId: producer?.task_id,
			targetDataset: normalizeName(producerDataset!),
			targetField: normalizeName(spec.producer_field),
			provenance: producerWrite.provenance,
			evidenceRefs: artifactRefs(producerWrite, producerExpression),
		});
	if (readEdge && consumerExpression && readRelation)
		steps.push({
			stepType: "READS_AS",
			taskId: consumer?.task_id,
			readRelationNodeId: readRelation.node_id,
			fieldNodeId: consumerExpression.node_id,
			physicalBinding: {
				table: normalizeName(producerDataset!),
				field: normalizeName(spec.producer_field),
				viaAlias: sourceRef?.qualifier ?? null,
			},
			resolutionStatus: inputResolutionStatus(consumerExpression),
			provenance: readEdge.provenance,
			evidenceRefs: artifactRefs(readEdge, consumerExpression, readRelation),
		});
	if (feedEdge && aggregate.expression)
		steps.push({
			stepType: "AGGREGATES_TO",
			taskId: consumer?.task_id,
			sourceFieldNodeId: feedEdge.from,
			aggregateFieldNodeId: aggregate.expression.node_id,
			aggregateFunctions: aggregateFacts?.functions ?? [],
			outputField: spec.target_field,
			provenance: feedEdge.provenance,
			evidenceRefs: artifactRefs(feedEdge, aggregate.expression),
		});
	if (aggregate.writeEdge && aggregate.expression)
		steps.push({
			stepType: "MATERIALIZES_AS",
			taskId: consumer?.task_id,
			targetDataset: normalizeName(targetDataset!),
			targetField: normalizeName(spec.target_field),
			provenance: aggregate.writeEdge.provenance,
			evidenceRefs: artifactRefs(aggregate.writeEdge, aggregate.expression),
		});

	const sourceEdges = [producerWrite, datasetFlow, readEdge, feedEdge, aggregate.writeEdge].filter(
		(edge): edge is JsonRecord => Boolean(edge),
	);
	return {
		pathId: spec.path_id,
		pathType: "VALUE_FLOW",
		description: `${spec.producer_field} -> ${spec.target_field}`,
		status: gaps.length === 0 ? "COMPLETE" : "PARTIAL",
		producerTaskId: producer?.task_id,
		producerRole: spec.producer_role,
		consumerTaskId: consumer?.task_id,
		consumerRole: spec.consumer_role,
		partitionSlice: spec.partition_assertion
			? {
					dataset: producerDataset ? normalizeName(producerDataset) : null,
					field: spec.partition_assertion.field,
					literal: spec.partition_assertion.literal,
					resolutionStatus: "PROFILE_DECLARED_NOT_SQL_IR_VERIFIED",
					provenance: "PROFILE_DECLARED",
				}
			: undefined,
		steps,
		edges: sourceEdges.map(sourceEdge),
		gaps,
	};
}

function assembleRowsetControl(inputs: GraphInputs, spec: MinimalPathSpec): CausalPath {
	const gaps: string[] = [];
	const producer = uniqueTask(inputs.profile, spec.producer_role, gaps);
	const consumer = uniqueTask(inputs.profile, spec.consumer_role, gaps);
	const producerDataset = producer?.writes;
	const targetDataset = consumer?.writes;
	const producerWrite = findWriteEdge(inputs, producer?.task_id, producerDataset, spec.producer_field);
	if (!producerWrite) gaps.push("missing producer FIELD_EXPRESSION_WRITES_FIELD edge");
	const producerExpression = expressionById(inputs, producerWrite?.from);
	if (!producerExpression) gaps.push("missing producer field expression");
	const producerResolutionGap = resolutionGap(producerExpression, "producer expression");
	if (producerResolutionGap) gaps.push(producerResolutionGap);
	const datasetFlow = findDatasetFlow(inputs, producer?.task_id, consumer?.task_id, producerDataset);
	if (!datasetFlow) gaps.push("missing TASK_DATASET_FLOW edge");
	const aggregate = targetAggregate(inputs, consumer?.task_id, targetDataset, spec.target_field);
	if (!aggregate.expression || !aggregate.writeEdge) gaps.push("missing target aggregate write edge");
	const aggregateAncestors = relationAncestors(inputs, aggregate.expression?.relation_node_id);
	const readEdge = inputs.edges.find((edge) => {
		if (
			edge.edge_type !== "READ_RELATION_READS_FIELD_AS_EXPRESSION" ||
			normalizeName(edge.dataset ?? "") !== normalizeName(producerDataset ?? "") ||
			normalizeName(edge.field ?? "") !== normalizeName(spec.producer_field)
		)
			return false;
		const expression = expressionById(inputs, edge.to);
		return expression?.task_id === consumer?.task_id && aggregateAncestors.has(expression?.relation_node_id);
	});
	if (!readEdge) gaps.push("missing structured READS_AS edge for control field");
	const readExpression = expressionById(inputs, readEdge?.to);
	const readResolutionGap = resolutionGap(readExpression, "control expression");
	if (readResolutionGap) gaps.push(readResolutionGap);
	const readRelation = relationById(inputs, readEdge?.from);
	const controlFilter = inputs.relations.find((item) => {
		const relation = item.relation as JsonRecord;
		const facts = relation.predicate_facts as JsonRecord | undefined;
		return (
			item.task_id === consumer?.task_id &&
			relation.type === "filter" &&
			aggregateAncestors.has(item.node_id) &&
			relationReferencesField(relation, "predicate_columns", producerDataset ?? "", spec.producer_field) &&
			facts?.comparisons?.some(
				(comparison: JsonRecord) =>
					comparison.operator === "=" &&
					comparison.columns?.some(
						(column: string) => normalizeName(column) === normalizeName(spec.producer_field),
					) &&
					comparison.literals?.some((literal: string) =>
						structuredLiteralEquals(literal, spec.control_literal ?? ""),
					),
			)
		);
	});
	if (!controlFilter) gaps.push("missing structured control-literal filter");
	const controlFilterId = controlFilter?.node_id as string | undefined;
	const leftJoin = inputs.relations.find((item) => {
		const relation = item.relation as JsonRecord;
		return (
			item.task_id === consumer?.task_id &&
			relation.type === "join" &&
			relation.join_type === "left" &&
			aggregateAncestors.has(item.node_id) &&
			relationAncestors(inputs, relation.right).has(controlFilterId ?? "")
		);
	});
	if (!leftJoin) gaps.push("missing LEFT JOIN whose right input contains control filter");
	const joinRelation = leftJoin?.relation as JsonRecord | undefined;
	const rightJoinRef = ((joinRelation?.condition_columns ?? []) as JsonRecord[]).find((ref) =>
		((ref.physical ?? []) as JsonRecord[]).some(
			(item) => normalizeName(item.table) === normalizeName(producerDataset ?? ""),
		),
	);
	const rightJoinPhysical = (rightJoinRef?.physical as JsonRecord[] | undefined)?.find(
		(item) => normalizeName(item.table) === normalizeName(producerDataset ?? ""),
	);
	if (!rightJoinPhysical) gaps.push("LEFT JOIN has no structured right-side physical key");
	const rightKey = rightJoinPhysical?.column as string | undefined;
	const nullFilter = inputs.relations.find((item) => {
		const relation = item.relation as JsonRecord;
		const facts = relation.predicate_facts as JsonRecord | undefined;
		return (
			item.task_id === consumer?.task_id &&
			relation.type === "filter" &&
			aggregateAncestors.has(item.node_id) &&
			relationAncestors(inputs, item.node_id).has(leftJoin?.node_id ?? "") &&
			Boolean(rightKey) &&
			relationReferencesField(relation, "predicate_columns", producerDataset ?? "", rightKey ?? "") &&
			facts?.predicates?.some(
				(predicate: JsonRecord) => predicate.operator === "null" && predicate.negated === false,
			)
		);
	});
	if (!nullFilter) gaps.push("missing structured IS NULL filter on right join key");

	const steps: JsonRecord[] = [];
	if (producerExpression)
		steps.push({
			stepType: "TASK_OUTPUT_EXPRESSION",
			taskId: producer?.task_id,
			fieldNodeId: producerExpression.node_id,
			outputField: spec.producer_field,
			expression: producerExpression.expression?.expr_text,
			provenance: "SQL_IR_EXTRACTED",
			evidenceRefs: artifactRefs(producerExpression),
		});
	if (producerWrite)
		steps.push({
			stepType: "MATERIALIZES_AS",
			taskId: producer?.task_id,
			targetDataset: normalizeName(producerDataset!),
			targetField: normalizeName(spec.producer_field),
			provenance: producerWrite.provenance,
			evidenceRefs: artifactRefs(producerWrite, producerExpression),
		});
	if (readEdge && readExpression && readRelation)
		steps.push({
			stepType: "READS_AS",
			taskId: consumer?.task_id,
			readRelationNodeId: readRelation.node_id,
			fieldNodeId: readExpression.node_id,
			physicalBinding: { table: normalizeName(producerDataset!), field: normalizeName(spec.producer_field) },
			resolutionStatus: inputResolutionStatus(readExpression),
			provenance: readEdge.provenance,
			evidenceRefs: artifactRefs(readEdge, readExpression, readRelation),
		});
	if (controlFilter)
		steps.push({
			stepType: "CONTROL_VALUE_FILTER",
			taskId: consumer?.task_id,
			filterRelationNodeId: controlFilter.node_id,
			controlLiteral: spec.control_literal,
			predicateFacts: controlFilter.relation.predicate_facts,
			provenance: "SQL_IR_EXTRACTED",
			evidenceRefs: artifactRefs(controlFilter),
		});
	if (leftJoin && rightJoinPhysical)
		steps.push({
			stepType: "LEFT_JOIN_FORMATION",
			taskId: consumer?.task_id,
			joinRelationNodeId: leftJoin.node_id,
			joinType: "left",
			rightPhysicalKey: {
				table: normalizeName(rightJoinPhysical.table),
				field: normalizeName(rightJoinPhysical.column),
			},
			conditionColumns: joinRelation?.condition_columns,
			provenance: "SQL_IR_EXTRACTED",
			evidenceRefs: artifactRefs(leftJoin),
		});
	if (nullFilter)
		steps.push({
			stepType: "IS_NULL_FILTER",
			taskId: consumer?.task_id,
			filterRelationNodeId: nullFilter.node_id,
			filterField: normalizeName(rightKey!),
			predicateFacts: nullFilter.relation.predicate_facts,
			provenance: "SQL_IR_EXTRACTED",
			evidenceRefs: artifactRefs(nullFilter),
		});
	if (aggregate.expression)
		steps.push({
			stepType: "ROWSET_CONTROL",
			taskId: consumer?.task_id,
			controlledAggregateNodeId: aggregate.expression.relation_node_id,
			controlledOutputField: spec.target_field,
			controlMechanism: "LEFT_JOIN_PLUS_IS_NULL",
			provenance: "DERIVED_FROM_STRUCTURED_IR",
			evidenceRefs: artifactRefs(controlFilter, leftJoin, nullFilter, aggregate.expression),
		});

	const sourceEdges = [producerWrite, datasetFlow, readEdge].filter((edge): edge is JsonRecord => Boolean(edge));
	const pathEdges = sourceEdges.map(sourceEdge);
	if (controlFilter && leftJoin && nullFilter && aggregate.expression)
		pathEdges.push({
			edgeId: `DERIVED-${pathEdges.length + 1}`,
			edgeType: "ROWSET_CONTROL",
			from: controlFilter.node_id,
			to: aggregate.expression.node_id,
			joinRelationNodeId: leftJoin.node_id,
			nullFilterRelationNodeId: nullFilter.node_id,
			provenance: "DERIVED_FROM_STRUCTURED_IR",
			evidenceRefs: artifactRefs(controlFilter, leftJoin, nullFilter, aggregate.expression),
		});

	return {
		pathId: spec.path_id,
		pathType: "ROWSET_CONTROL",
		description: `${spec.producer_field} controls rows entering ${spec.target_field}`,
		status: gaps.length === 0 ? "COMPLETE" : "PARTIAL",
		producerTaskId: producer?.task_id,
		producerRole: spec.producer_role,
		consumerTaskId: consumer?.task_id,
		consumerRole: spec.consumer_role,
		steps,
		edges: pathEdges,
		gaps,
		controlFlowNote: "ROWSET_CONTROL changes the aggregate input row set; it is not a value-flow edge.",
	};
}

export function assembleMinimalCausalPaths(inputs: GraphInputs): MinimalCausalPathsResult {
	const specs = inputs.profile.minimal_causal_paths ?? [];
	const paths = specs.map((spec) =>
		spec.path_type === "VALUE_FLOW" ? assembleValueFlow(inputs, spec) : assembleRowsetControl(inputs, spec),
	);
	const completePathCount = paths.filter((path) => path.status === "COMPLETE").length;
	const status: MinimalCausalPathsResult["status"] =
		specs.length > 0 && paths.length === specs.length && completePathCount === specs.length
			? "PASS"
			: paths.some((path) => path.steps.length > 0)
				? "PARTIAL"
				: "FAIL";
	return {
		schemaVersion: "minimal-causal-paths-v1",
		caseId: inputs.profile.case_id,
		status,
		paths,
		validation: {
			configuredPathCount: specs.length,
			assembledPathCount: paths.length,
			completePathCount,
			gapCount: paths.reduce((count, path) => count + path.gaps.length, 0),
			usesStructuredExpressionDependencies: true,
			partitionAssertionsAreProfileDeclarations: true,
		},
		boundaries: {
			notClaimed: [
				"complete_indicator_journey",
				"all_task_coverage",
				"business_correctness",
				"cross_indicator_algorithm",
			],
		},
	};
}

function runCli(): void {
	const workspace = resolve(import.meta.dirname, "../../..");
	const profilePath = resolve(
		workspace,
		process.argv[2] ?? "cases/indicator-journey-rgstcomp-mthend/processing-graph-profile.json",
	);
	const outputDir = resolve(workspace, process.argv[3] ?? "output/indicator-processing-graph-rgstcomp-mthend");
	const resultPath = resolve(outputDir, process.argv[4] ?? "minimal-causal-paths.json");
	const result = assembleMinimalCausalPaths(loadGraphInputs(profilePath, outputDir));
	mkdirSync(outputDir, { recursive: true });
	writeFileSync(resultPath, JSON.stringify(result, null, 2) + "\n", "utf8");
	console.log(
		JSON.stringify(
			{
				output: relative(workspace, resultPath),
				status: result.status,
				paths: result.paths.map((path) => ({
					pathId: path.pathId,
					pathType: path.pathType,
					status: path.status,
					gaps: path.gaps,
				})),
			},
			null,
			2,
		),
	);
	if (result.status !== "PASS") process.exitCode = 1;
}

const invokedModule = process.argv[1] ? pathToFileURL(resolve(process.argv[1])).href : "";
if (import.meta.url === invokedModule) runCli();
