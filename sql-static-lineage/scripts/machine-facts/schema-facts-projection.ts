import { fileURLToPath } from "node:url";
import {
	existsSync,
	mkdirSync,
	readFileSync,
	readdirSync,
	rmSync,
	writeFileSync,
} from "node:fs";
import { dirname, isAbsolute, join, resolve } from "node:path";

import { canonicalJson, canonicalJsonl, datasetId, fieldId, sha256 } from "./machine-facts-contract.ts";

export const SCHEMA_FACTS_SCHEMA_VERSION = "machine-facts-schema-facts-v1";

export type EvidenceStatus = "OBSERVED" | "ABSENT" | "UNAVAILABLE";
export type ProjectionStatus = "SUCCESS" | "PARTIAL" | "FAILED";

export interface SourceTableFact {
	readonly table_ref?: unknown;
	readonly qualified_name?: unknown;
	readonly metadata_qualified_name?: unknown;
	readonly guid?: unknown;
	readonly db_name?: unknown;
	readonly database_name?: unknown;
	readonly type_name?: unknown;
	readonly object_type?: unknown;
	readonly comment?: unknown;
	readonly ddl_status?: unknown;
	readonly schema_status?: unknown;
	readonly metadata_status?: unknown;
	readonly error_class?: unknown;
	readonly ddl_sha256?: unknown;
	readonly columns?: unknown;
	readonly mapping?: unknown;
	readonly source_qualified_names?: unknown;
	readonly sourceQualifiedNames?: unknown;
	readonly ddl?: unknown;
	readonly [key: string]: unknown;
}

export interface ProjectionOptions {
	readonly source_ref?: string;
	readonly source_logical_name?: string;
}

export interface TableStorageKey {
	readonly key: string;
	readonly strategy: "GUID" | "METADATA_QUALIFIED_NAME" | "LOGICAL_SOURCE_AND_QUALIFIED_NAME";
	readonly value: string;
}

export interface SchemaFactsProjectionResult {
	readonly status: ProjectionStatus;
	readonly output_dir: string;
	readonly table_count: number;
	readonly column_count: number;
	readonly partial_count: number;
}

interface ColumnInput {
	readonly name: string;
	readonly data_type?: string | null;
	readonly comment?: string | null;
	readonly raw_definition?: string | null;
	readonly is_partition_column?: boolean;
	readonly partition_ordinal?: number | null;
}

interface ParsedDdl {
	readonly columns: ColumnInput[];
	readonly partition_columns: ColumnInput[];
}

interface TableProjection {
	readonly table: Record<string, unknown>;
	readonly columns: Record<string, unknown>[];
	readonly storage: TableStorageKey;
}

function nonEmptyString(value: unknown): string | null {
	if (typeof value !== "string") return null;
	const normalized = value.trim();
	return normalized ? normalized : null;
}

function objectValue(value: unknown): Record<string, unknown> | null {
	return typeof value === "object" && value !== null && !Array.isArray(value) ? (value as Record<string, unknown>) : null;
}

function ddlObject(row: SourceTableFact): Record<string, unknown> {
	return objectValue(row.ddl) ?? {};
}

function inputLineEvidence(sourceRef: string, lineNumber: number): string[] {
	return [`${sourceRef}#L${lineNumber}`];
}

function base64url(value: string): string {
	return Buffer.from(value, "utf8").toString("base64url");
}

export function tableStorageKey(
	logicalSourceId: string,
	row: SourceTableFact,
	canonicalQualifiedName: string,
	metadataQualifiedName: string | null,
): TableStorageKey {
	const guid = nonEmptyString(row.guid);
	if (guid) return { key: `guid__${guid}`, strategy: "GUID", value: guid };
	if (metadataQualifiedName) {
		return {
			key: `metadata__${base64url(metadataQualifiedName)}`,
			strategy: "METADATA_QUALIFIED_NAME",
			value: metadataQualifiedName,
		};
	}
	const value = `${logicalSourceId}::${canonicalQualifiedName}`;
	return {
		key: `name__${base64url(value)}`,
		strategy: "LOGICAL_SOURCE_AND_QUALIFIED_NAME",
		value,
	};
}

function isQuote(character: string): boolean {
	return character === "'" || character === '"' || character === "`" || character === "[";
}

function closingQuote(character: string): string {
	return character === "[" ? "]" : character;
}

function splitTopLevel(value: string): string[] {
	const parts: string[] = [];
	let start = 0;
	let depth = 0;
	let quote: string | null = null;
	for (let index = 0; index < value.length; index += 1) {
		const character = value[index]!;
		if (quote) {
			if (character === quote) {
				if (value[index + 1] === quote) {
					index += 1;
				} else {
					quote = null;
				}
			} else if (quote === "]" && character === "]") {
				quote = null;
			}
			continue;
		}
		if (isQuote(character)) {
			quote = closingQuote(character);
			continue;
		}
		if (character === "(") depth += 1;
		if (character === ")") depth = Math.max(0, depth - 1);
		if (character === "," && depth === 0) {
			parts.push(value.slice(start, index).trim());
			start = index + 1;
		}
	}
	const tail = value.slice(start).trim();
	if (tail) parts.push(tail);
	return parts;
}

function matchingClose(value: string, openIndex: number): number {
	let depth = 0;
	let quote: string | null = null;
	for (let index = openIndex; index < value.length; index += 1) {
		const character = value[index]!;
		if (quote) {
			if (character === quote) {
				if (value[index + 1] === quote) index += 1;
				else quote = null;
			}
			continue;
		}
		if (isQuote(character)) {
			quote = closingQuote(character);
			continue;
		}
		if (character === "(") depth += 1;
		if (character === ")") {
			depth -= 1;
			if (depth === 0) return index;
		}
	}
	return -1;
}

function quotedIdentifier(value: string): { name: string; end: number } | null {
	const input = value.trimStart();
	if (!input) return null;
	const first = input[0]!;
	if (first === "[") {
		const end = input.indexOf("]", 1);
		return end < 0 ? null : { name: input.slice(1, end), end: value.length - input.length + end + 1 };
	}
	if (first === "`" || first === '"') {
		const end = input.indexOf(first, 1);
		return end < 0 ? null : { name: input.slice(1, end), end: value.length - input.length + end + 1 };
	}
	const match = /^[A-Za-z_][A-Za-z0-9_$-]*/.exec(input);
	return match ? { name: match[0], end: value.length - input.length + match[0].length } : null;
}

function commentFromDefinition(definition: string): string | null {
	const match = /\bcomment\s+('(?:''|[^'])*'|"(?:""|[^"])*")/i.exec(definition);
	if (!match) return null;
	const literal = match[1]!;
	return literal.slice(1, -1).replace(/''/g, "'").replace(/""/g, '"');
}

function parseColumnDefinition(definition: string, partition: boolean, partitionOrdinal: number | null): ColumnInput | null {
	const identifier = quotedIdentifier(definition);
	if (!identifier) return null;
	const name = identifier.name;
	const rest = definition.slice(identifier.end).trim();
	const commentMatch = /\s+comment\s+(?:'|"|`)/i.exec(rest);
	const dataType = (commentMatch ? rest.slice(0, commentMatch.index) : rest).trim() || null;
	return {
		name,
		data_type: dataType,
		comment: commentFromDefinition(definition),
		raw_definition: definition.trim(),
		is_partition_column: partition,
		partition_ordinal: partitionOrdinal,
	};
}

function parseColumnBlock(ddl: string, marker: RegExp, partition: boolean): ColumnInput[] {
	const match = marker.exec(ddl);
	if (!match || match.index < 0) return [];
	const open = ddl.indexOf("(", match.index + match[0].length);
	if (open < 0) return [];
	const close = matchingClose(ddl, open);
	if (close < 0) return [];
	return splitTopLevel(ddl.slice(open + 1, close))
		.map((definition, index) => parseColumnDefinition(definition, partition, partition ? index + 1 : null))
		.filter((column): column is ColumnInput => column !== null && !/^(constraint|primary|unique|key|index|clustered|sort)\b/i.test(column.name));
}

export function parseDdl(ddl: string): ParsedDdl {
	const regularMatch = /\bcreate\s+(?:external\s+)?table\b/i.exec(ddl);
	if (!regularMatch) return { columns: [], partition_columns: [] };
	const open = ddl.indexOf("(", regularMatch.index + regularMatch[0].length);
	const partitionMatch = /\bpartitioned\s+by\b/i.exec(ddl);
	const regularClose = open >= 0 ? matchingClose(ddl, open) : -1;
	const regular = open >= 0 && regularClose >= 0 ? splitTopLevel(ddl.slice(open + 1, regularClose)) : [];
	const columns = regular
		.map((definition) => parseColumnDefinition(definition, false, null))
		.filter((column): column is ColumnInput => column !== null && !/^(constraint|primary|unique|key|index|clustered|sort)\b/i.test(column.name));
	const partition_columns = partitionMatch ? parseColumnBlock(ddl, /\bpartitioned\s+by\b/i, true) : [];
	return { columns, partition_columns };
}

function directColumns(value: unknown): ColumnInput[] {
	if (!Array.isArray(value)) return [];
	return value.flatMap((item) => {
		const object = objectValue(item);
		const name = nonEmptyString(object?.name ?? object?.column_name ?? object?.columnName);
		if (!name) return [];
		return [{
			name,
			data_type: nonEmptyString(object?.data_type ?? object?.dataType ?? object?.type),
			comment: object?.comment === null ? null : nonEmptyString(object?.comment),
			raw_definition: nonEmptyString(object?.raw_definition ?? object?.rawDefinition ?? object?.definition),
			is_partition_column: object?.is_partition_column === true || object?.isPartitionColumn === true,
			partition_ordinal: typeof object?.partition_ordinal === "number" ? object.partition_ordinal : null,
		} satisfies ColumnInput];
	});
}

function columnInputs(row: SourceTableFact, ddlText: string | null): ParsedDdl {
	const direct = directColumns(row.columns);
	if (direct.length) {
		return {
			columns: direct.filter((column) => !column.is_partition_column),
			partition_columns: direct.filter((column) => column.is_partition_column),
		};
	}
	return ddlText ? parseDdl(ddlText) : { columns: [], partition_columns: [] };
}

function statusForComment(value: string | null, evidenceAvailable: boolean): EvidenceStatus {
	if (value !== null && value.trim() && value.trim() !== "-") return "OBSERVED";
	return evidenceAvailable ? "ABSENT" : "UNAVAILABLE";
}

function statusReason(status: EvidenceStatus, kind: "TABLE_COMMENT" | "COLUMN_COMMENT"): string {
	if (status === "OBSERVED") return `${kind}_OBSERVED_IN_METADATA_OR_DDL`;
	if (status === "ABSENT") return `${kind}_PRESENT_IN_EVIDENCE_BUT_EMPTY`;
	return `${kind}_EVIDENCE_UNAVAILABLE`;
}

function evidenceRefs(sourceRef: string, lineNumber: number, ddlText: string | null): string[] {
	const refs = inputLineEvidence(sourceRef, lineNumber);
	if (ddlText) refs.push(`${sourceRef}#L${lineNumber}#ddl`);
	return refs;
}

function sourceMappings(row: SourceTableFact, refs: string[]): Record<string, unknown>[] {
	const direct = row.source_qualified_names ?? row.sourceQualifiedNames;
	const directValues = Array.isArray(direct) ? direct : direct ? [direct] : [];
	const mapping = objectValue(row.mapping);
	if (!directValues.length && mapping) {
		const upstream = nonEmptyString(mapping.upstream_all);
		if (upstream) directValues.push(upstream);
	}
	return directValues.flatMap((value) => {
		const qualifiedName = nonEmptyString(objectValue(value)?.qualified_name ?? objectValue(value)?.qualifiedName ?? value);
		if (!qualifiedName) return [];
		return [{
			qualified_name: qualifiedName,
			relation_kind: "OBSERVED_SOURCE_MAPPING",
			evidence_refs: refs,
		}];
	});
}

function canonicalQualifiedName(row: SourceTableFact, metadataQualifiedName: string | null): string {
	const tableRef = nonEmptyString(row.table_ref);
	if (tableRef) return tableRef;
	if (metadataQualifiedName) return metadataQualifiedName.split("@", 1)[0]!;
	throw new Error("schema evidence row has neither table_ref nor qualified_name");
}

function makeTableProjection(
	row: SourceTableFact,
	lineNumber: number,
	logicalSourceId: string,
	options: ProjectionOptions,
): TableProjection {
	const ddl = ddlObject(row);
	const metadataQualifiedName = nonEmptyString(row.metadata_qualified_name ?? row.qualified_name ?? ddl.qualifiedName);
	const qualifiedName = canonicalQualifiedName(row, metadataQualifiedName);
	const guid = nonEmptyString(row.guid ?? ddl.guid);
	const databaseName = nonEmptyString(row.database_name ?? row.db_name ?? ddl.dbName);
	const objectType = nonEmptyString(row.object_type ?? row.type_name ?? ddl.type) ?? "UNKNOWN";
	const ddlText = nonEmptyString(ddl.ddl);
	const evidenceAvailable = Boolean(ddlText) || row.ddl_status !== undefined || row.metadata_status !== undefined || row.schema_status !== undefined;
	const tableComment = row.comment === null || row.comment === undefined ? null : nonEmptyString(row.comment);
	const parsed = columnInputs(row, ddlText);
	const sourceRef = options.source_ref ?? "source-layer/source-layer-table-facts.jsonl";
	const refs = evidenceRefs(sourceRef, lineNumber, ddlText);
	const storage = tableStorageKey(logicalSourceId, row, qualifiedName, metadataQualifiedName);
	const tableCommentStatus = statusForComment(tableComment, evidenceAvailable);
	const ddlStatus: EvidenceStatus = ddlText ? "OBSERVED" : "UNAVAILABLE";
	const ddlSha = nonEmptyString(row.ddl_sha256) ?? (ddlText ? sha256(ddlText) : null);
	const partitionSpec = parsed.partition_columns.map((column, index) => ({
		column_name: column.name,
		ordinal: column.partition_ordinal ?? index + 1,
	}));
	const columns = [...parsed.columns, ...parsed.partition_columns].map((column, index) => {
		const columnCommentStatus = statusForComment(column.comment ?? null, Boolean(ddlText || column.raw_definition));
		return {
			table_guid: guid,
			dataset_id: datasetId(logicalSourceId, qualifiedName),
			field_id: fieldId(logicalSourceId, qualifiedName, column.name),
			column_name: column.name,
			ordinal_position: index + 1,
			data_type: column.data_type,
			column_comment: column.comment,
			comment_status: columnCommentStatus,
			comment_reason_code: statusReason(columnCommentStatus, "COLUMN_COMMENT"),
			raw_definition: column.raw_definition,
			is_partition_column: column.is_partition_column === true,
			partition_ordinal: column.partition_ordinal,
			evidence_refs: refs,
		};
	});
	const tableStatus: ProjectionStatus = ddlText || parsed.columns.length || parsed.partition_columns.length ? "SUCCESS" : "PARTIAL";
	const table: Record<string, unknown> = {
		schema_version: SCHEMA_FACTS_SCHEMA_VERSION,
		fact_type: "TABLE",
		status: tableStatus,
		storage_key: storage.key,
		storage_key_strategy: storage.strategy,
		guid,
		logical_source_id: logicalSourceId,
		qualified_name: qualifiedName,
		database_name: databaseName,
		metadata_qualified_name: metadataQualifiedName,
		object_type: objectType,
		table_comment: tableComment,
		comment_status: tableCommentStatus,
		comment_reason_code: statusReason(tableCommentStatus, "TABLE_COMMENT"),
		partition_spec: partitionSpec,
		ddl_status: ddlStatus,
		ddl_sha256: ddlSha,
		ddl_ref: ddlText && ddlSha ? `${sourceRef}#ddl_sha256=${ddlSha}` : null,
		evidence_refs: refs,
	};
	const observed = sourceMappings(row, refs);
	if (observed.length) table.observed_source_refs = observed;
	return { table, columns, storage };
}

function readJsonl(inputPath: string): SourceTableFact[] {
	return readFileSync(inputPath, "utf8")
		.split(/\r?\n/)
		.map((line) => line.trim())
		.filter(Boolean)
		.map((line, index) => {
			const parsed: unknown = JSON.parse(line);
			const row = objectValue(parsed);
			if (!row) throw new Error(`source evidence line ${index + 1} is not an object`);
			return row as SourceTableFact;
		});
}

function writeFile(path: string, value: unknown): void {
	mkdirSync(dirname(path), { recursive: true });
	writeFileSync(path, canonicalJson(value), "utf8");
}

function removeExistingTableDirectories(outputDir: string, expectedKeys: Set<string>): void {
	const tablesDir = join(outputDir, "tables");
	if (!existsSync(tablesDir)) return;
	for (const entry of readdirSync(tablesDir, { withFileTypes: true })) {
		if (entry.isDirectory() && !expectedKeys.has(entry.name)) rmSync(join(tablesDir, entry.name), { recursive: true, force: true });
	}
}

export function projectSchemaFacts(
	inputPath: string,
	outputDir: string,
	logicalSourceId: string,
	options: ProjectionOptions = {},
): SchemaFactsProjectionResult {
	if (isAbsolute(options.source_ref ?? "")) throw new Error("source_ref must be a repository-relative evidence reference");
	const rows = readJsonl(inputPath);
	const projections = rows.map((row, index) => makeTableProjection(row, index + 1, logicalSourceId, options));
	projections.sort((left, right) => left.storage.key.localeCompare(right.storage.key));
	const keys = new Set(projections.map((projection) => projection.storage.key));
	mkdirSync(outputDir, { recursive: true });
	removeExistingTableDirectories(outputDir, keys);
	const indexRecords = projections.map(({ table, columns, storage }) => ({
		schema_version: SCHEMA_FACTS_SCHEMA_VERSION,
		fact_type: "TABLE_INDEX",
		table_storage_key: storage.key,
		guid: table.guid,
		logical_source_id: table.logical_source_id,
		qualified_name: table.qualified_name,
		metadata_qualified_name: table.metadata_qualified_name,
		dataset_id: datasetId(logicalSourceId, String(table.qualified_name)),
		status: table.status,
		table_path: `tables/${storage.key}/table.json`,
		columns_path: `tables/${storage.key}/columns.jsonl`,
		column_count: columns.length,
	}));
	for (const projection of projections) {
		const tableDir = join(outputDir, "tables", projection.storage.key);
		mkdirSync(tableDir, { recursive: true });
		writeFile(join(tableDir, "table.json"), projection.table);
		writeFileSync(join(tableDir, "columns.jsonl"), canonicalJsonl(projection.columns), "utf8");
	}
	writeFileSync(join(outputDir, "index.jsonl"), canonicalJsonl(indexRecords), "utf8");
	const partialCount = projections.filter(({ table }) => table.status !== "SUCCESS").length;
	const columnCount = projections.reduce((sum, projection) => sum + projection.columns.length, 0);
	const status: ProjectionStatus = rows.length === 0 ? "FAILED" : partialCount ? "PARTIAL" : "SUCCESS";
	const manifest = {
		schema_version: SCHEMA_FACTS_SCHEMA_VERSION,
		projection_type: "SHARED_PHYSICAL_SCHEMA_FACTS",
		status,
		logical_source_id: logicalSourceId,
		input_kind: "SOURCE_LAYER_TABLE_FACTS",
		source_ref: options.source_ref ?? "source-layer/source-layer-table-facts.jsonl",
		files: ["index.jsonl", ...projections.map(({ storage }) => `tables/${storage.key}/table.json`), ...projections.map(({ storage }) => `tables/${storage.key}/columns.jsonl`)].sort(),
		table_count: projections.length,
		column_count: columnCount,
		partial_table_count: partialCount,
		boundaries: {
			current_physical_schema_only: true,
			no_schema_bundle_or_scope_hash_directories: true,
			no_route_or_task_copies: true,
			no_constraint_key_grain_cardinality_or_business_semantic_inference: true,
			complete_ddl_retained_in_input_evidence: true,
		},
	};
	writeFile(join(outputDir, "manifest.json"), manifest);
	return { status, output_dir: outputDir, table_count: projections.length, column_count: columnCount, partial_count: partialCount };
}

function cli(): void {
	const inputPath = process.argv[2];
	const outputDir = process.argv[3];
	const logicalSourceId = process.argv[4] ?? "gfhive-test";
	if (!inputPath || !outputDir) {
		throw new Error("usage: schema-facts-projection.ts <source-table-facts.jsonl> <output-dir> [logical-source-id]");
	}
	console.log(JSON.stringify(projectSchemaFacts(resolve(inputPath), resolve(outputDir), logicalSourceId)));
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) cli();
