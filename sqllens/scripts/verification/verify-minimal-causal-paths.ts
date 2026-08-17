import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import {
	assembleMinimalCausalPaths,
	loadGraphInputs,
	type GraphInputs,
	type MinimalCausalPathsResult,
} from "../analysis/minimal-causal-path-assembler.ts";

type JsonRecord = Record<string, any>;

interface GoldenPath {
	pathId: string;
	pathType: "VALUE_FLOW" | "ROWSET_CONTROL";
	producerRole: string;
	consumerRole: string;
	stepTypes: string[];
	edgeTypes: string[];
	partition?: { field: string; literal: string; resolutionStatus: string };
}

interface Golden {
	schemaVersion: string;
	caseId: string;
	expectedStatus: string;
	paths: GoldenPath[];
}

const workspace = resolve(import.meta.dirname, "../../..");
const profilePath = resolve(workspace, "cases/indicator-journey-rgstcomp-mthend/processing-graph-profile.json");
const outputDir = resolve(workspace, "output/indicator-processing-graph-rgstcomp-mthend");
const generatedPath = resolve(outputDir, "minimal-causal-paths.json");
const goldenPath = resolve(workspace, "cases/indicator-journey-rgstcomp-mthend/minimal-causal-paths-golden.json");
const assemblerPath = resolve(workspace, "sqllens/scripts/analysis/minimal-causal-path-assembler.ts");

const inputs = loadGraphInputs(profilePath, outputDir);
const assembled = assembleMinimalCausalPaths(inputs);
const generated = JSON.parse(readFileSync(generatedPath, "utf8")) as MinimalCausalPathsResult;
const golden = JSON.parse(readFileSync(goldenPath, "utf8")) as Golden;
const assemblerSource = readFileSync(assemblerPath, "utf8");

let passed = 0;
let failed = 0;

function check(name: string, condition: boolean): void {
	if (condition) {
		passed += 1;
		console.log(`  OK  ${name}`);
	} else {
		failed += 1;
		console.error(`  FAIL ${name}`);
	}
}

function cloneInputs(value: GraphInputs): GraphInputs {
	return structuredClone(value);
}

function pathByType(result: MinimalCausalPathsResult, pathType: string): JsonRecord | undefined {
	return result.paths.find((path) => path.pathType === pathType) as JsonRecord | undefined;
}

function assertDegrades(name: string, mutate: (copy: GraphInputs) => void, expectedGap: string): void {
	const copy = cloneInputs(inputs);
	mutate(copy);
	const result = assembleMinimalCausalPaths(copy);
	check(`${name}: overall status degrades`, result.status !== "PASS");
	check(
		`${name}: affected path records a gap`,
		result.paths.some((path) => path.status === "PARTIAL" && path.gaps.some((gap) => gap.includes(expectedGap))),
	);
}

console.log("=== Minimal Causal Paths Verification ===\n");

console.log("--- Fresh Assembly ---");
check("fresh assembly matches written output", JSON.stringify(assembled) === JSON.stringify(generated));
check("overall status is PASS", assembled.status === "PASS");
check("configured paths are all assembled", assembled.validation.configuredPathCount === assembled.paths.length);
check("both paths are complete", assembled.validation.completePathCount === 2);
check("no gaps remain", assembled.validation.gapCount === 0);

console.log("\n--- Golden Contract ---");
check("schema version matches golden", assembled.schemaVersion === golden.schemaVersion);
check("case ID matches golden", assembled.caseId === golden.caseId);
check("status matches golden", assembled.status === golden.expectedStatus);
check("path count matches golden", assembled.paths.length === golden.paths.length);
for (const expected of golden.paths) {
	const actual = assembled.paths.find((path) => path.pathId === expected.pathId);
	check(`${expected.pathId}: exists`, Boolean(actual));
	check(`${expected.pathId}: type`, actual?.pathType === expected.pathType);
	check(`${expected.pathId}: producer role`, actual?.producerRole === expected.producerRole);
	check(`${expected.pathId}: consumer role`, actual?.consumerRole === expected.consumerRole);
	check(
		`${expected.pathId}: ordered steps`,
		JSON.stringify(actual?.steps.map((step) => step.stepType)) === JSON.stringify(expected.stepTypes),
	);
	check(
		`${expected.pathId}: ordered edges`,
		JSON.stringify(actual?.edges.map((edge) => edge.edgeType)) === JSON.stringify(expected.edgeTypes),
	);
	if (expected.partition) {
		check(`${expected.pathId}: partition field`, actual?.partitionSlice?.field === expected.partition.field);
		check(`${expected.pathId}: partition literal`, actual?.partitionSlice?.literal === expected.partition.literal);
		check(
			`${expected.pathId}: partition boundary is explicit`,
			actual?.partitionSlice?.resolutionStatus === expected.partition.resolutionStatus,
		);
	}
}

console.log("\n--- Structured Evidence ---");
const valueFlow = pathByType(assembled, "VALUE_FLOW");
const rowsetControl = pathByType(assembled, "ROWSET_CONTROL");
check(
	"base graph has structured read-field edges",
	inputs.edges.some((edge) => edge.edge_type === "READ_RELATION_READS_FIELD_AS_EXPRESSION"),
);
check(
	"base graph has structured expression-feed edges",
	inputs.edges.some((edge) => edge.edge_type === "FIELD_EXPRESSION_FEEDS_EXPRESSION"),
);
check(
	"aggregate has structured input columns",
	inputs.fieldExpressions.some(
		(item) => item.role === "AGGREGATE_MEASURE" && item.expression?.input_columns?.length > 0,
	),
);
check(
	"filters have structured literal/operator facts",
	inputs.relations.some(
		(item) =>
			item.relation?.type === "filter" &&
			item.relation?.predicate_facts?.operators?.length > 0 &&
			item.relation?.predicate_facts?.literals?.length > 0,
	),
);
check(
	"IS NULL is a structured predicate fact",
	inputs.relations.some((item) =>
		item.relation?.predicate_facts?.predicates?.some(
			(predicate: JsonRecord) => predicate.operator === "null" && predicate.negated === false,
		),
	),
);
check(
	"every path edge has evidence",
	assembled.paths.every((path) => path.edges.every((edge) => edge.evidenceRefs?.length > 0)),
);
check(
	"every SQL/derived step has evidence",
	assembled.paths.every((path) =>
		path.steps.every((step) => step.provenance === "PROFILE_DECLARED" || step.evidenceRefs?.length > 0),
	),
);
check("ROWSET_CONTROL is not presented as VALUE_FLOW", rowsetControl?.pathType === "ROWSET_CONTROL");
check(
	"partition slice is not overstated as SQL-verified",
	valueFlow?.partitionSlice?.resolutionStatus === "PROFILE_DECLARED_NOT_SQL_IR_VERIFIED",
);

console.log("\n--- No Case Logic In Assembler ---");
for (const task of inputs.profile.tasks) {
	check(`assembler does not contain task id ${task.task_id}`, !assemblerSource.includes(task.task_id));
}
check(
	"assembler does not contain case table names",
	!assemblerSource.toLowerCase().includes("t98_otc_deri_comp_sale_info"),
);
check("assembler does not contain control literal", !assemblerSource.includes("SKIP_REPORT"));
check("assembler does not use RegExp", !assemblerSource.includes("new RegExp"));
check("assembler does not read raw_sql", !assemblerSource.includes("raw_sql"));

console.log("\n--- Evidence Deletion Degradation ---");
const valueEdges = valueFlow?.edges as JsonRecord[];
const rowsetEdges = rowsetControl?.edges as JsonRecord[];
const valueWrite = valueEdges.find((edge) => edge.edgeType === "FIELD_EXPRESSION_WRITES_FIELD");
const valueFlowEdge = valueEdges.find((edge) => edge.edgeType === "TASK_DATASET_FLOW");
const valueRead = valueEdges.find((edge) => edge.edgeType === "READ_RELATION_READS_FIELD_AS_EXPRESSION");
const valueFeed = valueEdges.find((edge) => edge.edgeType === "FIELD_EXPRESSION_FEEDS_EXPRESSION");
const rowsetFlow = rowsetEdges.find((edge) => edge.edgeType === "TASK_DATASET_FLOW");
const rowsetRead = rowsetEdges.find((edge) => edge.edgeType === "READ_RELATION_READS_FIELD_AS_EXPRESSION");

assertDegrades(
	"delete producer write",
	(copy) => {
		copy.edges = copy.edges.filter(
			(edge) =>
				!(edge.edge_type === valueWrite.edgeType && edge.from === valueWrite.from && edge.to === valueWrite.to),
		);
	},
	"producer FIELD_EXPRESSION_WRITES_FIELD",
);
assertDegrades(
	"delete value-flow task bridge",
	(copy) => {
		copy.edges = copy.edges.filter(
			(edge) =>
				!(
					edge.edge_type === valueFlowEdge.edgeType &&
					edge.from === valueFlowEdge.from &&
					edge.to === valueFlowEdge.to
				),
		);
	},
	"TASK_DATASET_FLOW",
);
assertDegrades(
	"delete value-flow read binding",
	(copy) => {
		copy.edges = copy.edges.filter(
			(edge) =>
				!(edge.edge_type === valueRead.edgeType && edge.from === valueRead.from && edge.to === valueRead.to),
		);
	},
	"READ_RELATION_READS_FIELD_AS_EXPRESSION",
);
assertDegrades(
	"delete expression feed",
	(copy) => {
		copy.edges = copy.edges.filter(
			(edge) =>
				!(edge.edge_type === valueFeed.edgeType && edge.from === valueFeed.from && edge.to === valueFeed.to),
		);
	},
	"FIELD_EXPRESSION_FEEDS_EXPRESSION",
);
assertDegrades(
	"delete rowset task bridge",
	(copy) => {
		copy.edges = copy.edges.filter(
			(edge) =>
				!(edge.edge_type === rowsetFlow.edgeType && edge.from === rowsetFlow.from && edge.to === rowsetFlow.to),
		);
	},
	"TASK_DATASET_FLOW",
);
assertDegrades(
	"delete rowset read binding",
	(copy) => {
		copy.edges = copy.edges.filter(
			(edge) =>
				!(edge.edge_type === rowsetRead.edgeType && edge.from === rowsetRead.from && edge.to === rowsetRead.to),
		);
	},
	"structured READS_AS",
);

const controlFilterId = rowsetControl?.steps.find(
	(step: JsonRecord) => step.stepType === "CONTROL_VALUE_FILTER",
)?.filterRelationNodeId;
assertDegrades(
	"delete control literal fact",
	(copy) => {
		const relation = copy.relations.find((item) => item.node_id === controlFilterId)?.relation;
		if (relation?.predicate_facts) relation.predicate_facts.comparisons = [];
	},
	"control-literal filter",
);
const nullFilterId = rowsetControl?.steps.find(
	(step: JsonRecord) => step.stepType === "IS_NULL_FILTER",
)?.filterRelationNodeId;
assertDegrades(
	"delete IS NULL predicate fact",
	(copy) => {
		const relation = copy.relations.find((item) => item.node_id === nullFilterId)?.relation;
		if (relation?.predicate_facts) relation.predicate_facts.predicates = [];
	},
	"IS NULL filter",
);

const noEdges = cloneInputs(inputs);
noEdges.edges = [];
const noEdgesResult = assembleMinimalCausalPaths(noEdges);
check("empty evidence cannot PASS", noEdgesResult.status !== "PASS");
check(
	"empty evidence keeps both paths PARTIAL",
	noEdgesResult.paths.every((path) => path.status === "PARTIAL"),
);

console.log(`\n--- ${passed} passed, ${failed} failed ---`);
if (failed > 0) process.exit(1);
