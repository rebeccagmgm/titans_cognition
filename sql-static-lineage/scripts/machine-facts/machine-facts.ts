import { mkdirSync, readFileSync, readdirSync, renameSync, rmSync, statSync, writeFileSync, existsSync } from "node:fs";
import { basename, dirname, join, relative, resolve } from "node:path";

import { Schema, SqlSession, type SchemaMapping } from "../../src/index.ts";
import { buildPlanFacts, EXPRESSION_DEPENDENCY_ADAPTER_VERSION } from "../plans/plan-adapter.ts";
import type { PlanFacts } from "../plans/plan-contract.ts";
import {
	MACHINE_FACTS_ADAPTER_VERSION,
	MACHINE_FACTS_CONTRACT_VERSION,
	MACHINE_FACTS_STATUS_VERSION,
	canonicalJson,
	canonicalJsonl,
	datasetId,
	fieldId,
	normalizeName,
	safeSegment,
	sha256,
	stableRecords,
	stripVolatile,
	type AnalysisStatus,
	type FailureOutcome,
	type GenericAnalysisProfile,
	type GenericTaskProfile,
	type MachineFactsManifest,
	type OutcomeClass,
	type StatementRecord,
	type SchemaReferenceRecord,
	type DatasetIoRecord,
	type RelationNodeRecord,
	type RelationEdgeRecord,
	type FieldExpressionRecord,
	type InputDependencyStatus,
	type ColumnLineageRecord,
	type UnknownOutcomeRecord,
	type SourceArtifactRecord,
	type TaskFactIndexRecord,
} from "./machine-facts-contract.ts";

type JsonRecord = Record<string, any>;
type SourceSpan = { start: number; end: number };
type SchemaAvailability = ReadonlySet<string> | Pick<Schema, "columnsFor">;

function hasSchemaTable(table: string, available: SchemaAvailability, dialect: string): boolean {
	const provider = available as Partial<Pick<Schema, "columnsFor">>;
	if (typeof provider.columnsFor === "function") {
		const columns = provider.columnsFor.call(available, normalizeName(table).split("."), dialect);
		return Array.isArray(columns) && columns.length > 0;
	}
	return (available as ReadonlySet<string>).has(normalizeName(table));
}

export interface TaskRunResult {
	task_id: string;
	state: "SUCCESS" | "FAILED";
	status: "CREATED" | "REUSED" | "REPLACED" | "FAILED";
	manifest_sha256?: string;
	failures: FailureOutcome[];
}

export interface ProfileRunResult {
	output_root: string;
	tasks: TaskRunResult[];
	index: { path: string; count: number; failures: string[] };
}

const REQUIRED_DATASETS = [
	"statements.jsonl",
	"schema-refs.jsonl",
	"dataset-io.jsonl",
	"relation-nodes.jsonl",
	"relation-edges.jsonl",
	"field-expression-nodes.jsonl",
	"column-lineage-edges.jsonl",
	"unknowns.jsonl",
] as const;

const workspace = resolve(import.meta.dirname, "../../..");

type ParserSqlInput = {
	sql: string;
	restore: <T>(value: T) => T;
};

function parserToken(length: number, index: number): string {
	if (length < 3) throw new Error(`parser placeholder is too short to sanitize safely: ${length}`);
	const payloadLength = length - 2;
	const payload = index.toString(36).toUpperCase().padStart(payloadLength, "0").slice(-payloadLength);
	return `_P${payload}`;
}

function sanitizeSqlForParser(sql: string): ParserSqlInput {
	const rawToToken = new Map<string, string>();
	const tokenToRaw = new Map<string, string>();
	let tokenIndex = 0;
	const register = (raw: string): string => {
		const existing = rawToToken.get(raw);
		if (existing) return existing;
		let token = parserToken(raw.length, tokenIndex++);
		while (sql.includes(token) || tokenToRaw.has(token)) token = parserToken(raw.length, tokenIndex++);
		rawToToken.set(raw, token);
		tokenToRaw.set(token, raw);
		return token;
	};

	// Scheduler placeholders are lexical values, even when they occur inside
	// a table identifier. Keep replacement length identical so every parser
	// span remains a valid span in the original SQL.
	let sanitized = sql.replace(/\$\{[^{}\r\n]*\}/g, (raw) => register(raw));

	// Some source systems also expose legacy bare identifiers containing '$'.
	// Sanitize those only outside quoted strings/comments; quoted identifiers
	// already have an unambiguous SQL representation.
	let output = "";
	let quote: "'" | '"' | "`" | null = null;
	let lineComment = false;
	let blockComment = false;
	const isIdentifierStart = (char: string): boolean => /[A-Za-z_]/.test(char);
	const isIdentifierPart = (char: string): boolean => /[A-Za-z0-9_$]/.test(char);
	for (let index = 0; index < sanitized.length;) {
		const char = sanitized[index]!;
		const next = sanitized[index + 1] ?? "";
		if (lineComment) {
			output += char;
			index++;
			if (char === "\n") lineComment = false;
			continue;
		}
		if (blockComment) {
			output += char;
			index++;
			if (char === "*" && next === "/") {
				output += next;
				index++;
				blockComment = false;
			}
			continue;
		}
		if (quote) {
			output += char;
			index++;
			if (char === quote) {
				if (next === quote) {
					output += next;
					index++;
				} else {
					quote = null;
				}
			}
			continue;
		}
		if (char === "-" && next === "-") {
			output += "--";
			index += 2;
			lineComment = true;
			continue;
		}
		if (char === "/" && next === "*") {
			output += "/*";
			index += 2;
			blockComment = true;
			continue;
		}
		if (char === "'" || char === '"' || char === "`") {
			output += char;
			index++;
			quote = char;
			continue;
		}
		if (isIdentifierStart(char)) {
			let end = index + 1;
			while (end < sanitized.length && isIdentifierPart(sanitized[end]!)) end++;
			const identifier = sanitized.slice(index, end);
			output += identifier.includes("$") ? register(identifier) : identifier;
			index = end;
			continue;
		}
		output += char;
		index++;
	}
	sanitized = output;

	const replacements = [...tokenToRaw.entries()].sort(([left], [right]) => right.length - left.length);
	const restoreString = (value: string): string => replacements.reduce((current, [token, raw]) => {
		const escaped = token.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
		return current.replace(new RegExp(escaped, "gi"), () => raw);
	}, value);
	const restore = <T>(value: T): T => {
		const visit = (item: unknown): unknown => {
			if (typeof item === "string") return restoreString(item);
			if (Array.isArray(item)) return item.map(visit);
			if (item && typeof item === "object") {
				for (const [key, child] of Object.entries(item as JsonRecord)) (item as JsonRecord)[key] = visit(child);
			}
			return item;
		};
		return visit(value) as T;
	};
	return { sql: sanitized, restore };
}

function json<T>(path: string): T {
	return JSON.parse(readFileSync(path, "utf8")) as T;
}

function writeCanonical(path: string, value: unknown): void {
	mkdirSync(dirname(path), { recursive: true });
	writeFileSync(path, canonicalJson(value), "utf8");
}

function writeJsonl(path: string, records: readonly unknown[]): { row_count: number; content_sha256: string } {
	const bytes = canonicalJsonl(records);
	writeFileSync(path, bytes, "utf8");
	return { row_count: records.length, content_sha256: sha256(bytes) };
}

function fileHash(path: string): string {
	return sha256(readFileSync(path));
}

function rootForBundle(bundleDir: string): string {
	return resolve(bundleDir, "../../../..");
}

function relativeRoot(root: string, path: string): string {
	return relative(root, path).replace(/\\/g, "/");
}

function safeTask(task: GenericTaskProfile): void {
	safeSegment(task.task_id, "task_id");
	if (!task.sql_snapshot || typeof task.sql_snapshot !== "string") throw new Error(`task ${task.task_id} has no SQL snapshot`);
}

function normalizeWrites(task: GenericTaskProfile): string[] {
	if (!task.writes) return [];
	return (Array.isArray(task.writes) ? [...task.writes] : [task.writes]).filter(Boolean).map(normalizeName);
}

function classifyStatement(text: string): string {
	const normalized = text.trimStart().toUpperCase();
	if (normalized.startsWith("CREATE TABLE")) return "CREATE_TABLE";
	if (normalized.startsWith("INSERT OVERWRITE")) return "INSERT_OVERWRITE";
	if (normalized.startsWith("INSERT INTO")) return "INSERT_INTO";
	if (normalized.startsWith("MERGE INTO")) return "MERGE_INTO";
	if (normalized.startsWith("WITH")) return "WITH_QUERY";
	if (normalized.startsWith("SELECT")) return "SELECT";
	return "OTHER";
}

function parseSqlWrite(text: string): string | null {
	const match = text.match(
	/^\s*(?:CREATE\s+(?:OR\s+REPLACE\s+)?TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?|INSERT\s+(?:OVERWRITE|INTO)\s+(?:TABLE\s+)?|MERGE\s+INTO\s+)([A-Za-z0-9_`".\-]+)/i,
	);
	return match?.[1] ? normalizeName(match[1]) : null;
}

function spanValid(span: unknown, text: string): span is SourceSpan {
	return (
		typeof span === "object" && span !== null &&
		Number.isInteger((span as SourceSpan).start) && Number.isInteger((span as SourceSpan).end) &&
		(span as SourceSpan).start >= 0 && (span as SourceSpan).end >= (span as SourceSpan).start &&
		(span as SourceSpan).end <= text.length
	);
}

function globalRelationId(taskId: string, statementIndex: number, localId: string): string {
	const relationMarker = ":relation:";
	const markerIndex = localId.indexOf(relationMarker);
	const normalizedLocalId = markerIndex >= 0 && (localId.startsWith("sql:") || localId.includes(":statement:sql:")) ? localId.slice(markerIndex + relationMarker.length) : localId;
	return `task:${taskId}:statement:${statementIndex}:relation:${normalizedLocalId}`;
}

function globalizeRelation(taskId: string, statementIndex: number, relation: JsonRecord): JsonRecord {
	const mapId = (id: string): string => globalRelationId(taskId, statementIndex, id);
	const converted = stripVolatile(relation) as JsonRecord;
	converted.id = mapId(relation.id);
	if (relation.source) converted.source = mapId(relation.source);
	if (relation.left) converted.left = mapId(relation.left);
	if (relation.right) converted.right = mapId(relation.right);
	if (relation.branches) converted.branches = relation.branches.map(mapId);
	return converted;
}


function schemaRecordQuality(record: JsonRecord): [number, number, number, string] {
	return [
		record.status === "SUCCESS" ? 1 : 0,
		Array.isArray(record.columns) ? record.columns.length : 0,
		typeof record.ddl === "string" && record.ddl.length > 0 ? 1 : 0,
		canonicalJson(record),
	];
}

function isBetterSchemaRecord(candidate: JsonRecord, current: JsonRecord | undefined): boolean {
	if (!current) return true;
	const left = schemaRecordQuality(candidate);
	const right = schemaRecordQuality(current);
	for (let i = 0; i < left.length - 1; i++) {
		if (left[i] !== right[i]) return left[i] > right[i];
	}
	return left[left.length - 1] < right[right.length - 1];
}

export function mergeSchemaEvidence(raws: readonly JsonRecord[], logicalSourceId: string): JsonRecord {
	const byQualifiedName = new Map<string, JsonRecord>();
	for (const raw of raws) {
		const records = Array.isArray(raw.records) ? raw.records : [];
		for (const record of records) {
			if (!record || typeof record !== "object") continue;
			const candidate = stripVolatile(record) as JsonRecord;
			const qualifiedName = String(candidate.qualified_name ?? `${candidate.db ?? ""}.${candidate.table ?? ""}`).trim();
			if (!qualifiedName || qualifiedName === ".") continue;
			const key = normalizeName(qualifiedName);
			if (isBetterSchemaRecord(candidate, byQualifiedName.get(key))) byQualifiedName.set(key, candidate);
		}
	}
	return {
		schema_version: "machine-facts-schema-bundle-v1",
		logical_source_id: logicalSourceId,
		records: stableRecords([...byQualifiedName.values()], (record) => normalizeName(String(record.qualified_name ?? `${record.db ?? ""}.${record.table ?? ""}`))),
	};
}

function schemaProjection(raw: JsonRecord, logicalSourceId: string): JsonRecord {
	return mergeSchemaEvidence([raw], logicalSourceId);
}

function schemaProvider(schemaBundle: JsonRecord): Schema {
	const mapping: SchemaMapping = {};
	for (const record of schemaBundle.records as JsonRecord[]) {
		if (record.status !== "SUCCESS" || !Array.isArray(record.columns) || !record.qualified_name) continue;
		const table: SchemaMapping = Object.fromEntries(
			record.columns.map((column: JsonRecord) => [String(column.name), "unknown"]),
		);
		const parts = String(record.qualified_name).split(".").filter(Boolean);
		if (parts.length === 0) continue;
		let namespace = mapping;
		for (const part of parts.slice(0, -1)) {
			const current = namespace[part];
			if (typeof current !== "object" || current === null || "nullable" in current) {
				namespace[part] = {};
			}
			namespace = namespace[part] as SchemaMapping;
		}
		namespace[parts[parts.length - 1]!] = table;
	}
	return new Schema(mapping);
}

function outputColumns(relation: JsonRecord): JsonRecord[] {
	if (relation.type === "project") return Array.isArray(relation.expressions) ? relation.expressions : [];
	if (relation.type === "aggregate") return Array.isArray(relation.measures) ? relation.measures : [];
	return [];
}

export function inputDependencyStatus(expression: JsonRecord): InputDependencyStatus {
	const inputs = Array.isArray(expression.input_columns) ? expression.input_columns as JsonRecord[] : [];
	const hasPhysical = inputs.some((input) => input.resolution === "PHYSICAL" && Array.isArray(input.physical) && input.physical.length > 0);
	const hasDerived = inputs.some((input) => input.resolution === "DERIVED_OUTPUT");
	const hasSqlCandidate = inputs.some((input) => input.resolution === "SQL_CANDIDATE" && Array.isArray(input.sql_candidate) && input.sql_candidate.length > 0);
	const hasUnresolved = inputs.some((input) => input.resolution !== "PHYSICAL" && input.resolution !== "DERIVED_OUTPUT" && input.resolution !== "SQL_CANDIDATE");
	if (hasPhysical && (hasUnresolved || hasDerived || hasSqlCandidate)) return "PARTIAL";
	if (hasPhysical) return "PHYSICAL";
	if (hasSqlCandidate && !hasUnresolved && !hasDerived) return "SQL_CANDIDATE";
	if (hasSqlCandidate) return "PARTIAL";
	if (hasDerived && hasUnresolved) return "PARTIAL";
	if (hasDerived) return "DERIVED_OUTPUT";
	if (inputs.length > 0) return "UNRESOLVED";
	return "NO_PHYSICAL_INPUT";
}

function physicalTablesIn(value: unknown, result = new Set<string>()): Set<string> {
	if (Array.isArray(value)) {
		for (const item of value) physicalTablesIn(item, result);
		return result;
	}
	if (!value || typeof value !== "object") return result;
	const object = value as JsonRecord;
	if (Array.isArray(object.physical)) {
		for (const physical of object.physical as JsonRecord[]) {
			if (physical && typeof physical.table === "string") result.add(normalizeName(physical.table));
		}
	}
	if (object.type === "read" && typeof object.table === "string") result.add(normalizeName(object.table));
	for (const [key, child] of Object.entries(object)) if (key !== "physical") physicalTablesIn(child, result);
	return result;
}

function unresolvedInputColumns(expression: JsonRecord): JsonRecord[] {
	const inputs = Array.isArray(expression.input_columns) ? expression.input_columns as JsonRecord[] : [];
	return inputs
		.filter((input) => input.resolution !== "PHYSICAL" && input.resolution !== "DERIVED_OUTPUT" && input.resolution !== "SQL_CANDIDATE")
		.map((input) => ({
			name: input.name ?? null,
			qualifier: input.qualifier ?? null,
			resolution: input.resolution ?? "UNRESOLVED",
		}));
}

export function relationNeedsMissingSchema(
	nodeId: string,
	relations: readonly JsonRecord[],
	availableSchemaNames: SchemaAvailability,
	visiting = new Set<string>(),
	dialect = "databricks",
): boolean {
	if (visiting.has(nodeId)) return true;
	const relation = relations.find((candidate) => candidate.id === nodeId);
	if (!relation) return true;
	if (relation.type === "read") {
		if (relation.is_cte) return false;
		return !hasSchemaTable(String(relation.table ?? ""), availableSchemaNames, dialect);
	}
	const nextVisiting = new Set(visiting).add(nodeId);
	const inputs = [relation.source, relation.left, relation.right, ...(Array.isArray(relation.branches) ? relation.branches : [])].filter(Boolean) as string[];
	return inputs.some((input) => relationNeedsMissingSchema(input, relations, availableSchemaNames, nextVisiting, dialect));
}

function classifyPlanUnknown(
	item: JsonRecord,
	relation: JsonRecord | undefined,
	statementType: string,
	availableSchemaNames: SchemaAvailability,
	relations: readonly JsonRecord[],
	dialect: string,
): { outcome_class: OutcomeClass; reason_code: string } {
	const expressions = outputColumns(relation ?? {});
	const schemaAvailable = relation ? !relationNeedsMissingSchema(String(relation.id), relations, availableSchemaNames, new Set<string>(), dialect) : false;
	if (item.field === "physical") {
		if (String(item.reason ?? "").includes("schema 快照缺少字段证据")) {
			return { outcome_class: "NOT_EVALUABLE", reason_code: "SCHEMA_BINDING_NOT_EVALUABLE" };
		}
		if (String(item.reason ?? "").includes("followColumn 无来源")) {
			return { outcome_class: "UNKNOWN", reason_code: "PHYSICAL_FIELD_UNRESOLVED" };
		}
		return schemaAvailable
			? { outcome_class: "UNKNOWN", reason_code: "PHYSICAL_FIELD_UNRESOLVED" }
			: { outcome_class: "NOT_EVALUABLE", reason_code: "SCHEMA_BINDING_NOT_EVALUABLE" };
	}
	if (item.field === "output_columns") {
		if (statementType === "CREATE_TABLE" && expressions.length === 0) {
			return { outcome_class: "NOT_APPLICABLE", reason_code: "NON_QUERY_OUTPUT_NOT_APPLICABLE" };
		}
		if (!schemaAvailable) {
			return { outcome_class: "NOT_EVALUABLE", reason_code: "SCHEMA_BINDING_NOT_EVALUABLE" };
		}
		if (expressions.some((expression) => expression.output === "*" || expression.output_name_status === "STAR_EXPANSION")) {
			return { outcome_class: "UNKNOWN", reason_code: "STAR_EXPANSION_UNRESOLVED" };
		}
		if (expressions.some((expression) => expression.output === "?" || expression.output_name_status === "ANONYMOUS_EXPRESSION")) {
			return { outcome_class: "UNKNOWN", reason_code: "ANONYMOUS_OUTPUT_NAME_UNRESOLVED" };
		}
	}
	return { outcome_class: "UNKNOWN", reason_code: "PLAN_FACT_UNRESOLVED" };
}

const SQL_CANDIDATE_SAFE_RESOLUTIONS = new Set(["PHYSICAL", "SQL_CANDIDATE", "DERIVED_OUTPUT"]);

/**
 * A missing table schema does not by itself make a SQL dependency unevaluable.
 * If every column-bearing part of the plan is already bound physically or by
 * an unambiguous SQL candidate, the writer can preserve the dependency as
 * UNVERIFIED_SCHEMA. Keep the schema gap as NOT_EVALUABLE when a star or an
 * unresolved predicate/condition prevents that representation.
 */
function canRepresentMissingSchemaAsSqlCandidate(
	missingTables: readonly string[],
	relations: readonly JsonRecord[],
): boolean {
	const missing = new Set(missingTables.map((table) => normalizeName(table)));
	const candidateTables = new Set<string>();
	let safe = true;

	const visit = (value: unknown): void => {
		if (!safe || value === null || value === undefined) return;
		if (Array.isArray(value)) {
			for (const item of value) visit(item);
			return;
		}
		if (typeof value !== "object") return;
		const object = value as JsonRecord;
		if (object.output === "*" || object.output_name_status === "STAR_EXPANSION") safe = false;
		if (typeof object.resolution === "string") {
			if (!SQL_CANDIDATE_SAFE_RESOLUTIONS.has(object.resolution)) safe = false;
			if (object.resolution === "SQL_CANDIDATE" && Array.isArray(object.sql_candidate)) {
				for (const candidate of object.sql_candidate as JsonRecord[]) {
					if (typeof candidate.table === "string") candidateTables.add(normalizeName(candidate.table));
				}
			}
		}
		for (const child of Object.values(object)) visit(child);
	};

	for (const relation of relations) visit(relation);
	return safe && missing.size > 0 && [...missing].every((table) => candidateTables.has(table));
}

function makeFailure(outcome_class: OutcomeClass, reason_code: string, message: string, subject?: string): FailureOutcome {
	return { outcome_class, reason_code, message, ...(subject ? { subject } : {}) };
}

function contextHash(task: GenericTaskProfile, profile: GenericAnalysisProfile, logicalSourceId: string): string {
	return sha256(canonicalJson({
		contract_version: MACHINE_FACTS_CONTRACT_VERSION,
		adapter_version: MACHINE_FACTS_ADAPTER_VERSION,
		plan_adapter_version: EXPRESSION_DEPENDENCY_ADAPTER_VERSION,
		logical_source_id: logicalSourceId,
		dialect: profile.dialect,
		declared_outputs: normalizeWrites(task),
		include_expression_dependencies: true,
	}));
}

function writeStatus(taskRoot: string, status: AnalysisStatus): void {
	const path = join(taskRoot, "analysis-status.json");
	const temp = `${path}.tmp`;
	const backup = `${path}.bak`;
	if (existsSync(backup)) throw new Error("RECOVERY_REQUIRED: stale analysis-status backup exists");
	writeCanonical(temp, status);
	try {
		if (existsSync(path)) renameSync(path, backup);
		renameSync(temp, path);
		if (existsSync(backup)) rmSync(backup, { force: true });
	} catch (error) {
		if (!existsSync(path) && existsSync(backup)) renameSync(backup, path);
		if (existsSync(temp)) rmSync(temp, { force: true });
		throw error;
	}
}

function readStatus(taskRoot: string): AnalysisStatus | null {
	const path = join(taskRoot, "analysis-status.json");
	return existsSync(path) ? json<AnalysisStatus>(path) : null;
}

function readCurrentManifestHash(taskRoot: string): string | null {
	try {
		return readStatus(taskRoot)?.current_manifest_sha256 ?? null;
	} catch {
		return null;
	}
}

function recoverTaskState(taskRoot: string): void {
	const statusBackup = join(taskRoot, "analysis-status.json.bak");
	if (existsSync(statusBackup)) {
		if (existsSync(join(taskRoot, "analysis-status.json"))) throw new Error("RECOVERY_REQUIRED: status and status backup both exist");
		renameSync(statusBackup, join(taskRoot, "analysis-status.json"));
	}
	const recovery = join(taskRoot, ".recovery");
	const staging = readdirSync(taskRoot, { withFileTypes: true })
		.filter((entry) => entry.isDirectory() && entry.name.startsWith(".staging-"))
		.map((entry) => join(taskRoot, entry.name));
	for (const stagingPath of staging) {
		if (validateBundle(stagingPath).length === 0) throw new Error("RECOVERY_REQUIRED: valid staging directory requires inspection");
		rmSync(stagingPath, { recursive: true, force: true });
	}
	if (existsSync(recovery)) {
		const recoveryErrors = validateBundle(recovery);
		const bundle = join(taskRoot, "bundle");
		if (existsSync(bundle) || recoveryErrors.length > 0) throw new Error(`RECOVERY_REQUIRED: recovery directory requires inspection (${recoveryErrors.join("; ")})`);
		renameSync(recovery, bundle);
	}
	let status: AnalysisStatus | null;
	try {
		status = readStatus(taskRoot);
	} catch (error) {
		throw new Error(`RECOVERY_REQUIRED: analysis-status.json is invalid (${error instanceof Error ? error.message : String(error)})`);
	}
	if (status?.state === "ANALYZING") throw new Error("RECOVERY_REQUIRED: previous analysis was interrupted");
}

function snapshot(root: string, kind: "sql" | "schema", hash: string, bytes: Buffer): string {
	const path = join(root, "snapshots", kind, `${hash}.${kind === "sql" ? "sql" : "json"}`);
	mkdirSync(dirname(path), { recursive: true });
	if (existsSync(path)) {
		if (fileHash(path) !== hash) throw new Error(`snapshot hash collision: ${relativeRoot(root, path)}`);
	} else {
		writeFileSync(path, bytes);
	}
	return relativeRoot(root, path);
}

function planRecords(
	task: GenericTaskProfile,
	logicalSourceId: string,
	sql: string,
	plan: PlanFacts,
	statementId: string,
	statementIndex: number,
	statementType: string,
	availableSchemaNames: SchemaAvailability,
	dialect: string,
	artifactId: string,
): {
	relations: RelationNodeRecord[];
	relationEdges: RelationEdgeRecord[];
	fields: FieldExpressionRecord[];
	lineage: ColumnLineageRecord[];
	unknowns: UnknownOutcomeRecord[];
	reads: DatasetIoRecord[];
} {
	const relations: JsonRecord[] = [];
	const relationEdges: JsonRecord[] = [];
	const fields: JsonRecord[] = [];
	const lineage: JsonRecord[] = [];
	const unknowns: JsonRecord[] = [];
	const reads: JsonRecord[] = [];
	const planRelations = plan.relations as JsonRecord[];
	const relationIds = new Set(plan.relations.map((relation) => globalRelationId(task.task_id, statementIndex, relation.id)));

	for (const table of plan.physical_inputs) {
		reads.push({
			task_id: task.task_id,
			statement_id: statementId,
			direction: "READ",
			dataset_id: datasetId(logicalSourceId, table),
			physical_dataset: normalizeName(table),
			provenance: "SQL_PLAN",
			resolution_status: "RESOLVED",
		});
	}

	for (const item of plan.unknowns) {
		const relation = planRelations.find((candidate) => candidate.id === item.node_id);
		const classification = classifyPlanUnknown(item as JsonRecord, relation, statementType, availableSchemaNames, planRelations, dialect);
		unknowns.push({
			unknown_id: `unknown:${task.task_id}:${statementIndex}:${unknowns.length}`,
			task_id: task.task_id,
			statement_id: statementId,
			subject: item.node_id,
			outcome_class: classification.outcome_class,
			reason_code: classification.reason_code,
			message: item.reason,
			source_locator: item.span ?? null,
			artifact_id: artifactId,
		});
	}

	const explicitPhysicalUnknowns = new Set(
		(plan.unknowns as JsonRecord[])
			.filter((item) => item.field === "physical")
			.map((item) => String(item.node_id)),
	);
	for (const relation of planRelations) {
		const missingTables = [...physicalTablesIn(relation)].filter((table) => !hasSchemaTable(table, availableSchemaNames, dialect));
		const explicitPhysicalUnknown = explicitPhysicalUnknowns.has(String(relation.id));
		const candidateBinding = missingTables.length > 0 && !explicitPhysicalUnknown && canRepresentMissingSchemaAsSqlCandidate(missingTables, planRelations);
		if (missingTables.length > 0 && !candidateBinding && !explicitPhysicalUnknown) {
			unknowns.push({
				unknown_id: `unknown:${task.task_id}:${statementIndex}:${unknowns.length}`,
				task_id: task.task_id,
				statement_id: statementId,
				subject: relation.id,
				outcome_class: "NOT_EVALUABLE",
				reason_code: "SCHEMA_BINDING_NOT_EVALUABLE",
				message: `physical references lack schema evidence: ${missingTables.join(", ")}`,
				source_locator: relation.span ?? null,
				artifact_id: artifactId,
			});
		}
	}

	for (const localRelation of plan.relations as JsonRecord[]) {
		const relation = globalizeRelation(task.task_id, statementIndex, localRelation);
		const relationId = relation.id as string;
		const sourceSpan = relation.span as SourceSpan;
		const node: JsonRecord = {
			relation_id: relationId,
			task_id: task.task_id,
			statement_id: statementId,
			relation_type: relation.type,
			source_span: sourceSpan,
			source_text: spanValid(sourceSpan, sql) ? sql.slice(sourceSpan.start, sourceSpan.end) : null,
			provenance: relation.provenance === "extracted" ? "SQL_PLAN" : "PARTIAL_SQL_PLAN",
			relation,
		};
		relations.push(node);
		const refs = [relation.source, relation.left, relation.right, ...(relation.branches ?? [])].filter(Boolean) as string[];
		for (const ref of refs) {
			relationEdges.push({
				edge_id: `relation-edge:${ref}:${relationId}`,
				task_id: task.task_id,
				statement_id: statementId,
				from_relation_id: ref,
				to_relation_id: relationId,
				edge_type: "RELATION_INPUT",
				provenance: "SQL_PLAN",
				source_span: relation.span,
			});
			if (!relationIds.has(ref)) {
				unknowns.push(makeFailure("FAILURE", "RELATION_ENDPOINT_MISSING", `relation endpoint ${ref} is missing`, relationId));
			}
		}

		for (const [role, expressions] of [["PROJECT_EXPRESSION", relation.type === "project" ? outputColumns(relation) : []], ["AGGREGATE_MEASURE", relation.type === "aggregate" ? outputColumns(relation) : []]] as const) {
			for (const [ordinal, expression] of expressions.entries()) {
				const expressionId = `${relationId}:expression:${role.toLowerCase()}:${ordinal}`;
				const expressionSpan = expression.span as SourceSpan;
				const physicalInputs: JsonRecord[] = [];
				const candidateInputs: JsonRecord[] = [];
				for (const input of expression.input_columns ?? []) {
					for (const physical of input.physical ?? []) {
						if (input.resolution !== "PHYSICAL") continue;
						physicalInputs.push({
							field_id: fieldId(logicalSourceId, physical.table, physical.column),
							table: normalizeName(physical.table),
							column: normalizeName(physical.column),
						});
					}
					for (const candidate of input.sql_candidate ?? []) {
						candidateInputs.push({
							field_id: fieldId(logicalSourceId, candidate.table, candidate.column),
							table: normalizeName(candidate.table),
							column: normalizeName(candidate.column),
							binding_status: "UNVERIFIED_SCHEMA",
						});
					}
				}
				const uniqueInputs = [...new Map(physicalInputs.map((item) => [item.field_id, item])).values()];
				const uniqueCandidates = [...new Map(candidateInputs.map((item) => [item.field_id, item])).values()];
				fields.push({
					expression_id: expressionId,
					task_id: task.task_id,
					statement_id: statementId,
					relation_id: relationId,
					role,
					ordinal,
					output_name: expression.output,
					output_name_status: expression.output_name_status ?? "UNKNOWN",
						expression_text: expression.expr_text,
						source_span: expressionSpan,
						input_fields: uniqueInputs,
						candidate_input_fields: uniqueCandidates,
						unresolved_input_columns: unresolvedInputColumns(expression),
						input_dependency_status: inputDependencyStatus(expression),
						artifact_id: artifactId,
				});
				for (const input of uniqueInputs) {
					lineage.push({
						edge_id: `lineage:${input.field_id}:${expressionId}`,
						task_id: task.task_id,
						statement_id: statementId,
						from_field_id: input.field_id,
						to_expression_id: expressionId,
						method: "SQL_PLAN_LINEAGE",
						resolution_provenance: "SCHEMA_BOUND",
					});
				}
				for (const input of uniqueCandidates) {
					lineage.push({
						edge_id: `lineage-candidate:${input.field_id}:${expressionId}`,
						task_id: task.task_id,
						statement_id: statementId,
						from_field_id: input.field_id,
						to_expression_id: expressionId,
						method: "SQL_SINGLE_SOURCE_BINDING",
						resolution_provenance: "SQL_SYNTAX_NO_SCHEMA",
						resolution_status: "UNVERIFIED_SCHEMA",
					});
				}
			}
		}
	}
	return {
		relations: relations as RelationNodeRecord[],
		relationEdges: relationEdges as RelationEdgeRecord[],
		fields: fields as FieldExpressionRecord[],
		lineage: lineage as ColumnLineageRecord[],
		unknowns: unknowns as UnknownOutcomeRecord[],
		reads: reads as DatasetIoRecord[],
	};
}

function validateJsonSchema(value: unknown, schema: JsonRecord, path = "$", errors: string[] = []): string[] {
	const type = schema.type as string | undefined;
	const actual = Array.isArray(value) ? "array" : value === null ? "null" : typeof value;
	if (type && actual !== type) {
		errors.push(`${path}: expected ${type}, got ${actual}`);
		return errors;
	}
	if (schema.const !== undefined && value !== schema.const) errors.push(`${path}: expected const ${String(schema.const)}`);
	if (schema.pattern && typeof value === "string" && !(new RegExp(String(schema.pattern))).test(value)) errors.push(`${path}: pattern mismatch`);
	if (Array.isArray(value)) {
		if (schema.items) value.forEach((item, index) => validateJsonSchema(item, schema.items as JsonRecord, `${path}[${index}]`, errors));
		return errors;
	}
	if (actual !== "object" || value === null) return errors;
	const object = value as JsonRecord;
	for (const required of (schema.required ?? []) as string[]) if (!(required in object)) errors.push(`${path}: missing required property ${required}`);
	const properties = (schema.properties ?? {}) as JsonRecord;
	for (const [key, childSchema] of Object.entries(properties)) if (key in object) validateJsonSchema(object[key], childSchema as JsonRecord, `${path}.${key}`, errors);
	return errors;
}

function manifestContext(manifest: MachineFactsManifest): JsonRecord {
	return { schema_version: manifest.schema_version, task_id: manifest.task_id, logical_source_id: manifest.logical_source_id, inputs: manifest.inputs, method: manifest.method };
}

function outputPath(bundleDir: string, path: string): string | null {
	const resolved = resolve(bundleDir, path);
	const relativePath = relative(bundleDir, resolved).replace(/\\/g, "/");
	return relativePath === path && !path.startsWith("/") && !path.includes("..") ? resolved : null;
}

function snapshotReference(root: string, reference: string, kind: "sql" | "schema", hash: string): string | null {
	const extension = kind === "sql" ? "sql" : "json";
	const expected = `snapshots/${kind}/${hash}.${extension}`;
	if (reference !== expected || !/^[a-f0-9]{64}$/.test(hash)) return null;
	const resolved = resolve(root, reference);
	return relative(root, resolved).replace(/\\/g, "/") === reference ? resolved : null;
}

export function validateBundle(bundleDir: string): string[] {
	const errors: string[] = [];
	const manifestPath = join(bundleDir, "manifest.json");
	if (!existsSync(manifestPath)) return ["manifest.json is missing"];
	let manifest: MachineFactsManifest;
	try {
		manifest = json<MachineFactsManifest>(manifestPath);
	} catch (error) {
		return [`manifest.json is invalid: ${error instanceof Error ? error.message : String(error)}`];
	}
	if (!manifest.inputs || typeof manifest.inputs !== "object" || !manifest.method || typeof manifest.method !== "object" || !Array.isArray(manifest.outputs)) {
		errors.push("manifest structural fields are invalid");
		return [...new Set(errors)];
	}
	try {
		const schemaPath = join(workspace, "sql-static-lineage", "schemas", "machine-facts.schema.json");
		const schemaErrors = validateJsonSchema(manifest, json<JsonRecord>(schemaPath));
		for (const error of schemaErrors) errors.push(`manifest schema: ${error}`);
	} catch (error) {
		errors.push(`manifest schema validation failed: ${error instanceof Error ? error.message : String(error)}`);
	}
	let recordSchemas: JsonRecord = {};
	try {
		recordSchemas = (json<JsonRecord>(join(workspace, "sql-static-lineage", "schemas", "machine-facts-records.schema.json")).properties ?? {}) as JsonRecord;
	} catch (error) {
		errors.push(`record schema validation failed: ${error instanceof Error ? error.message : String(error)}`);
	}
	if (manifest.schema_version !== MACHINE_FACTS_CONTRACT_VERSION) errors.push("unsupported manifest schema_version");
	if (manifest.status !== "SUCCESS") errors.push("manifest status is not SUCCESS");
	for (const output of manifest.outputs ?? []) {
		if (!output || typeof output !== "object" || typeof output.path !== "string" || typeof output.content_sha256 !== "string" || !Number.isInteger(output.row_count)) {
			errors.push("manifest output record is structurally invalid");
			continue;
		}
		const path = outputPath(bundleDir, output.path);
		if (!path) {
			errors.push(`unsafe output path ${output.path}`);
			continue;
		}
		if (!existsSync(path)) {
			errors.push(`missing output ${output.path}`);
			continue;
		}
		if (fileHash(path) !== output.content_sha256) errors.push(`hash mismatch ${output.path}`);
		try {
			const rows = readJsonl(path);
			if (rows.length !== output.row_count) errors.push(`row count mismatch ${output.path}`);
			const recordSchema = recordSchemas[output.path] as JsonRecord | undefined;
			if (!recordSchema) errors.push(`record schema missing ${output.path}`);
			else rows.forEach((row, index) => validateJsonSchema(row, recordSchema, `${output.path}[${index}]`, errors));
		} catch (error) {
			errors.push(`invalid JSONL ${output.path}: ${error instanceof Error ? error.message : String(error)}`);
		}
	}
	for (const required of REQUIRED_DATASETS) {
		if (!(manifest.outputs ?? []).some((output) => output && typeof output === "object" && output.path === required)) errors.push(`required output not declared ${required}`);
	}
	const root = rootForBundle(bundleDir);
	const sqlPath = snapshotReference(root, manifest.inputs.sql_snapshot, "sql", manifest.inputs.sql_sha256);
	if (!sqlPath || !existsSync(sqlPath) || fileHash(sqlPath) !== manifest.inputs.sql_sha256) errors.push("SQL snapshot is missing, unsafe, or hash-mismatched");
	const schemaPath = snapshotReference(root, manifest.inputs.schema_snapshot, "schema", manifest.inputs.schema_bundle_sha256);
	if (!schemaPath || !existsSync(schemaPath) || fileHash(schemaPath) !== manifest.inputs.schema_bundle_sha256) errors.push("Schema snapshot is missing, unsafe, or hash-mismatched");
	const sourceArtifactPath = join(bundleDir, "source-artifact.json");
	if (!existsSync(sourceArtifactPath)) errors.push("source-artifact.json is missing");
	else {
		try {
			const sourceArtifact = json<JsonRecord>(sourceArtifactPath);
			const sourceSchema = recordSchemas["source-artifact.json"] as JsonRecord | undefined;
			if (sourceSchema) for (const error of validateJsonSchema(sourceArtifact, sourceSchema, "source-artifact.json")) errors.push(error);
			if (sourceArtifact.task_id !== manifest.task_id || sourceArtifact.logical_source_id !== manifest.logical_source_id || sourceArtifact.sql_sha256 !== manifest.inputs.sql_sha256 || sourceArtifact.sql_snapshot !== manifest.inputs.sql_snapshot) errors.push("source-artifact does not match manifest");
		} catch (error) {
			errors.push(`source-artifact.json is invalid: ${error instanceof Error ? error.message : String(error)}`);
		}
	}
	const sql = sqlPath && existsSync(sqlPath) ? readFileSync(sqlPath, "utf8") : "";
	const statements = readJsonlForValidation(join(bundleDir, "statements.jsonl"), errors);
	for (const statement of statements) {
		if (!spanValid(statement.span, sql) || sql.slice(statement.span.start, statement.span.end) !== statement.raw_sql) {
			errors.push(`statement span roundtrip failed ${statement.statement_id}`);
		}
	}
	const relationNodes = readJsonlForValidation(join(bundleDir, "relation-nodes.jsonl"), errors);
	const relationIds = new Set(relationNodes.map((node) => node.relation_id));
	for (const edge of readJsonlForValidation(join(bundleDir, "relation-edges.jsonl"), errors)) {
		if (!relationIds.has(edge.from_relation_id) || !relationIds.has(edge.to_relation_id)) errors.push(`relation endpoint missing ${edge.edge_id}`);
	}
	const expressions = readJsonlForValidation(join(bundleDir, "field-expression-nodes.jsonl"), errors);
	const expressionIds = new Set(expressions.map((node) => node.expression_id));
	for (const expression of expressions) if (!relationIds.has(expression.relation_id)) errors.push(`expression owner missing ${expression.expression_id}`);
	for (const edge of readJsonlForValidation(join(bundleDir, "column-lineage-edges.jsonl"), errors)) {
		if (!expressionIds.has(edge.to_expression_id)) errors.push(`lineage expression endpoint missing ${edge.edge_id}`);
	}
	return [...new Set(errors)];
}

function readJsonl(path: string): JsonRecord[] {
	if (!existsSync(path)) return [];
	const text = readFileSync(path, "utf8").trim();
	return text ? text.split(/\r?\n/).map((line) => JSON.parse(line) as JsonRecord) : [];
}

function readJsonlForValidation(path: string, errors: string[]): JsonRecord[] {
	try {
		return readJsonl(path);
	} catch (error) {
		errors.push(`invalid JSONL ${basename(path)}: ${error instanceof Error ? error.message : String(error)}`);
		return [];
	}
}

function publishBundle(taskRoot: string, staging: string, manifest: MachineFactsManifest): { status: "CREATED" | "REUSED" | "REPLACED"; manifest_sha256: string } {
	const bundle = join(taskRoot, "bundle");
	const manifestBytes = canonicalJson(manifest);
	const manifestHash = sha256(manifestBytes);
	const hadExisting = existsSync(bundle);
	if (existsSync(bundle)) {
		const existing = json<MachineFactsManifest>(join(bundle, "manifest.json"));
		const existingErrors = validateBundle(bundle);
		const sameCanonicalManifest = sha256(canonicalJson(existing)) === sha256(manifestBytes);
		if (sameCanonicalManifest && existingErrors.length === 0) {
			rmSync(staging, { recursive: true, force: true });
			return { status: "REUSED", manifest_sha256: sha256(canonicalJson(existing)) };
		}
		if (existingErrors.length === 0 && sha256(canonicalJson(manifestContext(existing))) === sha256(canonicalJson(manifestContext(manifest)))) {
			rmSync(staging, { recursive: true, force: true });
			throw new Error("NON_DETERMINISTIC_OUTPUT: same analysis context produced different Bundle content");
		}
	}
	const recovery = join(taskRoot, ".recovery");
	if (existsSync(recovery)) throw new Error("RECOVERY_REQUIRED: recovery directory exists");
	try {
		if (existsSync(bundle)) renameSync(bundle, recovery);
		renameSync(staging, bundle);
		const errors = validateBundle(bundle);
		if (errors.length) throw new Error(`published Bundle failed validation: ${errors.join("; ")}`);
		if (existsSync(recovery)) rmSync(recovery, { recursive: true, force: true });
		return { status: hadExisting ? "REPLACED" : "CREATED", manifest_sha256: manifestHash };
	} catch (error) {
		if (existsSync(bundle)) rmSync(bundle, { recursive: true, force: true });
		if (existsSync(recovery)) renameSync(recovery, bundle);
		throw error;
	}
}

function buildTaskBundle(
	task: GenericTaskProfile,
	profile: GenericAnalysisProfile,
	logicalSourceId: string,
	root: string,
	schemaBundle: JsonRecord,
	schemaBundleHash: string,
): { staging: string; manifest: MachineFactsManifest } {
	safeTask(task);
	const sqlPath = resolve(workspace, task.sql_snapshot);
	const sqlBytes = readFileSync(sqlPath);
	const sql = sqlBytes.toString("utf8");
	const sqlHash = sha256(sqlBytes);
	const sqlSnapshot = snapshot(root, "sql", sqlHash, sqlBytes);
	const schemaBytes = Buffer.from(canonicalJson(schemaBundle), "utf8");
	const schemaSnapshot = snapshot(root, "schema", schemaBundleHash, schemaBytes);
	const staging = join(root, "registry", "tasks", task.task_id, `.staging-${process.pid}-${Date.now()}`);
	mkdirSync(staging, { recursive: true });
	const schema = schemaProvider(schemaBundle);
	const sourceArtifact: SourceArtifactRecord = {
		schema_version: "machine-facts-source-artifact-v1",
		task_id: task.task_id,
		logical_source_id: logicalSourceId,
		sql_snapshot: sqlSnapshot,
		sql_sha256: sqlHash,
		byte_length: sqlBytes.length,
		encoding: "UTF-8",
	};
	writeCanonical(join(staging, "source-artifact.json"), sourceArtifact);

	const statements: StatementRecord[] = [];
	const datasetIo: DatasetIoRecord[] = [];
	const relations: RelationNodeRecord[] = [];
	const relationEdges: RelationEdgeRecord[] = [];
	const expressions: FieldExpressionRecord[] = [];
	const lineage: ColumnLineageRecord[] = [];
	const unknowns: UnknownOutcomeRecord[] = [];
	const schemaRefs: SchemaReferenceRecord[] = (schemaBundle.records as JsonRecord[]).map((record, index) => ({
		schema_ref_id: `schema-ref:${logicalSourceId}:${index}`,
		logical_source_id: logicalSourceId,
		qualified_name: record.qualified_name ?? null,
		guid: record.guid ?? null,
		status: record.status ?? "UNKNOWN",
		source: record.source ?? null,
		metadata_qualified_name: record.metadata_qualified_name ?? null,
		ddl_sha256: record.ddl_sha256 ?? null,
		table_status: record.table_status ?? null,
		required_for_star: record.required_for_star === true,
		physical_columns: Array.isArray(record.columns) ? record.columns.map((column: JsonRecord) => column.name).filter(Boolean) : [],
		partition_columns: Array.isArray(record.columns)
			? record.columns.filter((column: JsonRecord) => column.partition === true).map((column: JsonRecord) => String(column.name)).filter(Boolean)
			: [],
	}));
	let parserVersion = "unknown";
	let planAdapterVersion = "unknown";
	const parserSql = sanitizeSqlForParser(sql);
	const session = SqlSession.create(parserSql.sql, profile.dialect as any, { schema });
	for (const [statementIndex, cell] of session.doc.statements.entries()) {
		const statementId = `task:${task.task_id}:statement:${statementIndex}`;
		const span = { start: cell.span.start, end: cell.span.end };
		const rawSql = sql.slice(span.start, span.end);
		const parsedWrite = parseSqlWrite(rawSql);
		const statementType = classifyStatement(rawSql);
		if (parsedWrite) {
			datasetIo.push({ task_id: task.task_id, statement_id: statementId, direction: "WRITE", dataset_id: datasetId(logicalSourceId, parsedWrite), physical_dataset: parsedWrite, provenance: "SQL_PARSE", resolution_status: "RESOLVED" });
		}
		const plan: PlanFacts = parserSql.restore(buildPlanFacts(cell, sql, {
			statement_index: statementIndex,
			dialect: profile.dialect,
			schema,
			include_expression_dependencies: true,
		}));
		const hasActionableUnknown = plan.unknowns.some((item) => {
			const relation = (plan.relations as JsonRecord[]).find((candidate) => candidate.id === item.node_id);
			return classifyPlanUnknown(item as JsonRecord, relation, statementType, schema, plan.relations as JsonRecord[], profile.dialect).outcome_class !== "NOT_APPLICABLE";
		});
		parserVersion = plan.meta.parser.version;
		planAdapterVersion = plan.meta.adapter_version;
		statements.push({
			statement_id: statementId,
			task_id: task.task_id,
			statement_index: statementIndex,
			statement_type: statementType,
			span,
			raw_sql: rawSql,
			parse_status: cell.errors > 0 || hasActionableUnknown ? "PARTIAL" : "SUCCESS",
			diagnostic: cell.diagnostics,
		});
		const records = planRecords(task, logicalSourceId, sql, plan, statementId, statementIndex, statementType, schema, profile.dialect, `sql:${task.task_id}:${sqlHash}`);
		relations.push(...records.relations);
		relationEdges.push(...records.relationEdges);
		expressions.push(...records.fields);
		lineage.push(...records.lineage);
		unknowns.push(...records.unknowns);
		datasetIo.push(...records.reads);
		if (cell.errors > 0) {
			for (const diagnostic of cell.diagnostics) {
				unknowns.push({ task_id: task.task_id, statement_id: statementId, outcome_class: "UNKNOWN", reason_code: "SYNTAX_DIAGNOSTIC", message: diagnostic.message, source_locator: { start: diagnostic.offset ?? span.start, end: (diagnostic.offset ?? span.start) + diagnostic.length } });
			}
		}
	}
	const dedupedUnknowns = new Set<string>();
	const retainedUnknowns = unknowns.filter((item) => {
		if (item.reason_code !== "SCHEMA_BINDING_NOT_EVALUABLE" || !item.message.startsWith("physical references lack schema evidence:")) return true;
		const key = `${item.task_id}|${item.statement_id ?? ""}|${item.message}`;
		if (dedupedUnknowns.has(key)) return false;
		dedupedUnknowns.add(key);
		return true;
	});
	unknowns.splice(0, unknowns.length, ...retainedUnknowns);
	for (const write of normalizeWrites(task)) {
		datasetIo.push({ task_id: task.task_id, direction: "WRITE", dataset_id: datasetId(logicalSourceId, write), physical_dataset: write, provenance: "PROFILE_DECLARED", resolution_status: "DECLARED" });
	}
	if (normalizeWrites(task).length > 0 && !datasetIo.some((item) => item.provenance === "SQL_PARSE" && item.direction === "WRITE")) {
		unknowns.push({ task_id: task.task_id, outcome_class: "NOT_EVALUABLE", reason_code: "OUTPUT_BINDING_NOT_PROVABLE", message: "Profile declared output has no unambiguous SQL output field binding" });
	}
	const unknownsByOutcome = Object.fromEntries(
		(["UNKNOWN", "NOT_EVALUABLE", "NOT_APPLICABLE", "FAILURE"] as const).map((outcome) => [outcome, unknowns.filter((item) => item.outcome_class === outcome).length]),
	) as Record<OutcomeClass, number>;
	const files: Array<{ path: string; schema_version: string; row_count: number; content_sha256: string }> = [];
	for (const [name, records, schemaVersion] of [
		["statements.jsonl", statements, "machine-facts-statements-v1"],
		["schema-refs.jsonl", schemaRefs, "machine-facts-schema-refs-v1"],
		["dataset-io.jsonl", stableRecords(datasetIo, (record) => JSON.stringify(record)), "machine-facts-dataset-io-v1"],
		["relation-nodes.jsonl", relations, "machine-facts-relation-nodes-v1"],
		["relation-edges.jsonl", relationEdges, "machine-facts-relation-edges-v1"],
		["field-expression-nodes.jsonl", expressions, "machine-facts-field-expressions-v1"],
		["column-lineage-edges.jsonl", lineage, "machine-facts-column-lineage-v1"],
		["unknowns.jsonl", unknowns, "machine-facts-unknowns-v1"],
	] as const) {
		const result = writeJsonl(join(staging, name), records);
		files.push({ path: name, schema_version: schemaVersion, ...result });
	}
	const manifest: MachineFactsManifest = {
		schema_version: MACHINE_FACTS_CONTRACT_VERSION,
		task_id: task.task_id,
		logical_source_id: logicalSourceId,
		status: "SUCCESS",
		inputs: {
			sql_sha256: sqlHash,
			sql_snapshot: sqlSnapshot,
			schema_bundle_sha256: schemaBundleHash,
			schema_snapshot: schemaSnapshot,
			analysis_config_sha256: contextHash(task, profile, logicalSourceId),
		},
		method: {
			dialect: profile.dialect,
			parser: { engine: "sql-static-lineage", version: parserVersion },
			adapter: { name: "machine-facts-writer", version: MACHINE_FACTS_ADAPTER_VERSION },
			plan_adapter: { name: "plan-adapter", version: planAdapterVersion },
		},
		outputs: files,
		counts: {
			statements: statements.length,
			schema_refs: schemaRefs.length,
			dataset_io: datasetIo.length,
			relation_nodes: relations.length,
			relation_edges: relationEdges.length,
			field_expression_nodes: expressions.length,
			column_lineage_edges: lineage.length,
			unknowns: unknowns.length,
			unknowns_by_outcome: unknownsByOutcome,
		},
		gates: { required_files: true, hash_integrity: true, span_roundtrip: true, relation_endpoints: true, lineage_endpoints: true },
		boundaries: { business_logic_correctness: "NOT_EVALUATED", runtime_execution: "NOT_EVALUATED", business_rows_read: false, external_model_calls: 0, cross_task_field_stitching: "NOT_GENERATED" },
	};
	writeCanonical(join(staging, "manifest.json"), manifest);
	return { staging, manifest };
}

export function runTask(
	task: GenericTaskProfile,
	profile: GenericAnalysisProfile,
	logicalSourceId: string,
	root: string,
	schemaBundle: JsonRecord,
	schemaBundleHash: string,
): TaskRunResult {
	safeTask(task);
	const taskRoot = join(root, "registry", "tasks", task.task_id);
	mkdirSync(taskRoot, { recursive: true });
	let sqlHash = "";
	try {
		sqlHash = sha256(readFileSync(resolve(workspace, task.sql_snapshot)));
	} catch {
		// The typed task failure below retains an empty hash when the source itself is unavailable.
	}
	try {
		recoverTaskState(taskRoot);
	} catch (error) {
		const failure = makeFailure("FAILURE", "RECOVERY_REQUIRED", error instanceof Error ? error.message : String(error));
		writeStatus(taskRoot, { schema_version: MACHINE_FACTS_STATUS_VERSION, task_id: task.task_id, logical_source_id: logicalSourceId, state: "FAILED", requested: { sql_sha256: sqlHash, schema_bundle_sha256: schemaBundleHash, analysis_config_sha256: contextHash(task, profile, logicalSourceId), dialect: profile.dialect }, current_manifest_sha256: readCurrentManifestHash(taskRoot), failure });
		return { task_id: task.task_id, state: "FAILED", status: "FAILED", failures: [failure] };
	}
	const requested = { sql_sha256: sqlHash, schema_bundle_sha256: schemaBundleHash, analysis_config_sha256: contextHash(task, profile, logicalSourceId), dialect: profile.dialect };
	writeStatus(taskRoot, { schema_version: MACHINE_FACTS_STATUS_VERSION, task_id: task.task_id, logical_source_id: logicalSourceId, state: "ANALYZING", requested, current_manifest_sha256: readStatus(taskRoot)?.current_manifest_sha256 ?? null });
	let staging: string | null = null;
	try {
		const built = buildTaskBundle(task, profile, logicalSourceId, root, schemaBundle, schemaBundleHash);
		staging = built.staging;
		const errors = validateBundle(staging);
		if (errors.length) throw new Error(errors.join("; "));
		const published = publishBundle(taskRoot, staging, built.manifest);
		staging = null;
		writeStatus(taskRoot, { schema_version: MACHINE_FACTS_STATUS_VERSION, task_id: task.task_id, logical_source_id: logicalSourceId, state: "SUCCESS", requested, current_manifest_sha256: published.manifest_sha256 });
		return { task_id: task.task_id, state: "SUCCESS", status: published.status, manifest_sha256: published.manifest_sha256, failures: [] };
	} catch (error) {
		if (staging && existsSync(staging)) rmSync(staging, { recursive: true, force: true });
		const message = error instanceof Error ? error.message : String(error);
		const reasonCode = message.includes("NON_DETERMINISTIC_OUTPUT") ? "NON_DETERMINISTIC_OUTPUT" : message.includes("RECOVERY") ? "RECOVERY_REQUIRED" : "TASK_ANALYSIS_FAILED";
		const failure = makeFailure("FAILURE", reasonCode, message);
		writeStatus(taskRoot, { schema_version: MACHINE_FACTS_STATUS_VERSION, task_id: task.task_id, logical_source_id: logicalSourceId, state: "FAILED", requested, current_manifest_sha256: readCurrentManifestHash(taskRoot), failure });
		return { task_id: task.task_id, state: "FAILED", status: "FAILED", failures: [failure] };
	}
}

export function rebuildIndex(root: string): ProfileRunResult["index"] {
	const indexDir = join(root, "indexes");
	mkdirSync(indexDir, { recursive: true });
	const records: JsonRecord[] = [];
	const failures: string[] = [];
	let indexSchema: JsonRecord | null = null;
	try {
		indexSchema = (json<JsonRecord>(join(workspace, "sql-static-lineage", "schemas", "machine-facts-records.schema.json")).properties as JsonRecord)["task-fact-index.jsonl"] as JsonRecord;
	} catch (error) {
		failures.push(`task-fact-index schema unavailable: ${error instanceof Error ? error.message : String(error)}`);
	}
	const tasksRoot = join(root, "registry", "tasks");
	if (existsSync(tasksRoot)) {
		for (const taskId of readdirSync(tasksRoot)) {
			const taskRoot = join(tasksRoot, taskId);
			if (!statSync(taskRoot).isDirectory()) continue;
			let status: AnalysisStatus | null;
			try {
				status = readStatus(taskRoot);
			} catch (error) {
				failures.push(`${taskId}: invalid analysis-status.json (${error instanceof Error ? error.message : String(error)})`);
				continue;
			}
			if (!status || status.state !== "SUCCESS") {
				if (status?.state === "FAILED") failures.push(`${taskId}: ${status.failure?.reason_code ?? "FAILED"}`);
				continue;
			}
			const bundle = join(taskRoot, "bundle");
			const errors = validateBundle(bundle);
			const manifestPath = join(bundle, "manifest.json");
			if (!existsSync(manifestPath) || errors.length) {
				failures.push(`${taskId}: ${errors.join("; ") || "manifest missing"}`);
				continue;
			}
			const manifest = json<MachineFactsManifest>(manifestPath);
			const requestedStatus = status.requested as AnalysisStatus["requested"] | undefined;
			const statusMatchesManifest = typeof status.task_id === "string" && typeof status.logical_source_id === "string" && requestedStatus !== undefined &&
				status.task_id === taskId && status.task_id === manifest.task_id && status.logical_source_id === manifest.logical_source_id &&
				requestedStatus.sql_sha256 === manifest.inputs.sql_sha256 && requestedStatus.schema_bundle_sha256 === manifest.inputs.schema_bundle_sha256 &&
				requestedStatus.analysis_config_sha256 === manifest.inputs.analysis_config_sha256 && requestedStatus.dialect === manifest.method.dialect;
			if (!statusMatchesManifest || sha256(canonicalJson(manifest)) !== status.current_manifest_sha256) {
				failures.push(`${taskId}: status/manifest identity or hash mismatch`);
				continue;
			}
			const candidate: TaskFactIndexRecord = { task_id: taskId, logical_source_id: manifest.logical_source_id, sql_sha256: manifest.inputs.sql_sha256, manifest_sha256: status.current_manifest_sha256, bundle_path: relativeRoot(root, bundle), status: "SUCCESS" };
			const indexErrors = indexSchema ? validateJsonSchema(candidate, indexSchema, `task-fact-index.jsonl[${records.length}]`) : ["task-fact-index schema unavailable"];
			if (indexErrors.length) {
				failures.push(`${taskId}: ${indexErrors.join("; ")}`);
				continue;
			}
			records.push(candidate);
		}
	}
	const path = join(indexDir, "task-fact-index.jsonl");
	writeFileSync(path, canonicalJsonl(stableRecords(records, (record) => String(record.task_id))), "utf8");
	return { path, count: records.length, failures };
}

export function processProfile(profilePath: string, outputRoot: string, sourceIdOverride?: string): ProfileRunResult {
	const profile = json<GenericAnalysisProfile>(resolve(workspace, profilePath));
	if (!profile.dialect || !Array.isArray(profile.tasks) || profile.tasks.length === 0) throw new Error("profile must contain dialect and tasks");
	if (!sourceIdOverride && !profile.logical_source_id) throw new Error("logical_source_id is required");
	const logicalSourceId = safeSegment(sourceIdOverride ?? profile.logical_source_id!, "logical_source_id");
	const taskIds = profile.tasks.map((task) => task.task_id);
	if (new Set(taskIds).size !== taskIds.length) throw new Error("profile task_id values must be unique");
	const root = resolve(workspace, outputRoot);
	mkdirSync(root, { recursive: true });
	const configuredEvidence = Array.isArray(profile.schema_evidence)
		? [...profile.schema_evidence]
		: profile.schema_evidence ? [profile.schema_evidence] : [];
	const evidencePaths = configuredEvidence.map((path) => resolve(workspace, path));
	if (evidencePaths.length === 0 || evidencePaths.some((path) => !existsSync(path))) throw new Error("schema_evidence is required and must exist");
	const schemaBundle = mergeSchemaEvidence(evidencePaths.map((path) => json<JsonRecord>(path)), logicalSourceId);
	const schemaBytes = Buffer.from(canonicalJson(schemaBundle), "utf8");
	const schemaBundleHash = sha256(schemaBytes);
	snapshot(root, "schema", schemaBundleHash, schemaBytes);
	const tasks = profile.tasks.map((task) => runTask(task, profile, logicalSourceId, root, schemaBundle, schemaBundleHash));
	return { output_root: root, tasks, index: rebuildIndex(root) };
}

function parseArgs(args: string[]): { profile: string; output: string; sourceId?: string } {
	const value = (name: string, fallback: string): string => {
		const index = args.indexOf(name);
		return index >= 0 && args[index + 1] ? args[index + 1] : fallback;
	};
	return { profile: value("--profile", "cases/indicator-journey-rgstcomp-mthend/processing-graph-profile.json"), output: value("--output", "machine-facts"), sourceId: args.includes("--source-id") ? value("--source-id", "") : undefined };
}

if (process.argv[1] && basename(process.argv[1]).startsWith("machine-facts")) {
	const args = parseArgs(process.argv.slice(2));
	const result = processProfile(args.profile, args.output, args.sourceId);
	console.log(JSON.stringify({ output: result.output_root, tasks: result.tasks, index: result.index }, null, 2));
}
