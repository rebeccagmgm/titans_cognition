import {
	datasetId,
	fieldId,
	normalizeName,
	type FieldExpressionRecord,
	type OutputFieldBindingRecord,
	type SchemaReferenceRecord,
	type StatementRecord,
	type UnknownOutcomeRecord,
} from "./machine-facts-contract.ts";

type Token = {
	readonly kind: "word" | "symbol" | "string";
	readonly value: string;
};

type ParsedInsert = {
	readonly target: string;
	readonly targetColumns: readonly string[];
	readonly staticPartitionColumns: readonly string[];
	readonly dynamicPartitionColumns: readonly string[];
};

type ParsedCreate = {
	readonly statementId: string;
	readonly target: string;
	readonly columns: readonly string[];
	readonly partitionColumns: readonly string[];
};

export interface WriteOutputContext {
	readonly statementId: string;
	readonly statementType: string;
	readonly rawSql: string;
	readonly expressions: readonly FieldExpressionRecord[];
}

export interface OutputBindingResult {
	readonly bindings: readonly OutputFieldBindingRecord[];
	readonly unknowns: readonly UnknownOutcomeRecord[];
}

export interface OutputBindingInput {
	readonly taskId: string;
	readonly logicalSourceId: string;
	readonly statements: readonly StatementRecord[];
	readonly writes: readonly WriteOutputContext[];
	readonly schemaRefs: readonly SchemaReferenceRecord[];
	readonly declaredWrites: readonly string[];
}

function tokensOf(sql: string): Token[] {
	const tokens: Token[] = [];
	let index = 0;
	while (index < sql.length) {
		const char = sql[index]!;
		const next = sql[index + 1];
		if (/\s/.test(char)) {
			index += 1;
			continue;
		}
		if (char === "-" && next === "-") {
			index += 2;
			while (index < sql.length && sql[index] !== "\n") index += 1;
			continue;
		}
		if (char === "/" && next === "*") {
			index += 2;
			while (index < sql.length && !(sql[index] === "*" && sql[index + 1] === "/")) index += 1;
			index = Math.min(sql.length, index + 2);
			continue;
		}
		if (char === "'") {
			let value = "";
			index += 1;
			while (index < sql.length) {
				if (sql[index] === "'" && sql[index + 1] === "'") {
					value += "'";
					index += 2;
					continue;
				}
				if (sql[index] === "'") {
					index += 1;
					break;
				}
				value += sql[index];
				index += 1;
			}
			tokens.push({ kind: "string", value });
			continue;
		}
		if (char === "`" || char === '"' || char === "[") {
			const close = char === "[" ? "]" : char;
			let value = "";
			index += 1;
			while (index < sql.length) {
				if (sql[index] === close && sql[index + 1] === close && close !== "]") {
					value += close;
					index += 2;
					continue;
				}
				if (sql[index] === close) {
					index += 1;
					break;
				}
				value += sql[index];
				index += 1;
			}
			tokens.push({ kind: "word", value });
			continue;
		}
		if (/[A-Za-z0-9_$-]/.test(char)) {
			let value = char;
			index += 1;
			while (index < sql.length && /[A-Za-z0-9_$-]/.test(sql[index]!)) {
				value += sql[index];
				index += 1;
			}
			tokens.push({ kind: "word", value });
			continue;
		}
		if ("().,=".includes(char)) tokens.push({ kind: "symbol", value: char });
		index += 1;
	}
	return tokens;
}

function word(token: Token | undefined, value: string): boolean {
	return token?.kind === "word" && token.value.toLowerCase() === value.toLowerCase();
}

function identifierAt(tokens: readonly Token[], start: number): { value: string; next: number } | null {
	if (tokens[start]?.kind !== "word") return null;
	const parts = [tokens[start]!.value];
	let index = start + 1;
	while (tokens[index]?.value === "." && tokens[index + 1]?.kind === "word") {
		parts.push(tokens[index + 1]!.value);
		index += 2;
	}
	return { value: normalizeName(parts.join(".")), next: index };
}

function parenthesizedSegments(tokens: readonly Token[], openIndex: number): { segments: Token[][]; next: number } | null {
	if (tokens[openIndex]?.value !== "(") return null;
	const segments: Token[][] = [[]];
	let depth = 1;
	for (let index = openIndex + 1; index < tokens.length; index += 1) {
		const token = tokens[index]!;
		if (token.value === "(") depth += 1;
		if (token.value === ")") {
			depth -= 1;
			if (depth === 0) return { segments: segments.filter((segment) => segment.length > 0), next: index + 1 };
		}
		if (token.value === "," && depth === 1) segments.push([]);
		else segments[segments.length - 1]!.push(token);
	}
	return null;
}

function columnNames(segments: readonly Token[][]): string[] {
	const constraints = new Set(["constraint", "primary", "unique", "foreign", "check"]);
	return segments.flatMap((segment) => {
		const first = segment.find((token) => token.kind === "word");
		if (!first || constraints.has(first.value.toLowerCase())) return [];
		return [normalizeName(first.value)];
	});
}

function parseInsert(sql: string): ParsedInsert | null {
	const tokens = tokensOf(sql);
	let index = tokens.findIndex((token) => word(token, "insert"));
	if (index < 0) return null;
	index += 1;
	if (word(tokens[index], "overwrite") || word(tokens[index], "into")) index += 1;
	if (word(tokens[index], "table")) index += 1;
	const target = identifierAt(tokens, index);
	if (!target) return null;
	index = target.next;

	let targetColumns: string[] = [];
	if (tokens[index]?.value === "(") {
		const list = parenthesizedSegments(tokens, index);
		if (!list) return null;
		targetColumns = columnNames(list.segments);
		index = list.next;
	}

	const staticPartitionColumns: string[] = [];
	const dynamicPartitionColumns: string[] = [];
	for (; index < tokens.length && !word(tokens[index], "select"); index += 1) {
		if (!word(tokens[index], "partition") || tokens[index + 1]?.value !== "(") continue;
		const list = parenthesizedSegments(tokens, index + 1);
		if (!list) return null;
		for (const segment of list.segments) {
			const name = columnNames([segment])[0];
			if (!name) continue;
			if (segment.some((token) => token.value === "=")) staticPartitionColumns.push(name);
			else dynamicPartitionColumns.push(name);
		}
		index = list.next - 1;
	}
	return { target: target.value, targetColumns, staticPartitionColumns, dynamicPartitionColumns };
}

function parseCreate(statement: StatementRecord): ParsedCreate | null {
	if (statement.statement_type !== "CREATE_TABLE") return null;
	const tokens = tokensOf(statement.raw_sql);
	let index = tokens.findIndex((token) => word(token, "create"));
	if (index < 0) return null;
	index += 1;
	if (word(tokens[index], "or") && word(tokens[index + 1], "replace")) index += 2;
	if (!word(tokens[index], "table")) return null;
	index += 1;
	if (word(tokens[index], "if") && word(tokens[index + 1], "not") && word(tokens[index + 2], "exists")) index += 3;
	const target = identifierAt(tokens, index);
	if (!target || tokens[target.next]?.value !== "(") return null;
	const list = parenthesizedSegments(tokens, target.next);
	if (!list) return null;
	const columns = columnNames(list.segments);
	const partitionColumns: string[] = [];
	for (let cursor = list.next; cursor < tokens.length - 2; cursor += 1) {
		if (!word(tokens[cursor], "partitioned") || !word(tokens[cursor + 1], "by") || tokens[cursor + 2]?.value !== "(") continue;
		const partitions = parenthesizedSegments(tokens, cursor + 2);
		if (partitions) partitionColumns.push(...columnNames(partitions.segments));
		break;
	}
	return { statementId: statement.statement_id, target: target.value, columns, partitionColumns };
}

function tableTail(value: string): string {
	return normalizeName(value).split(".").at(-1) ?? normalizeName(value);
}

function targetMatches(candidate: string, target: string): boolean {
	const left = normalizeName(candidate);
	const right = normalizeName(target);
	return left === right || tableTail(left) === tableTail(right);
}

function schemaForTarget(
	target: string,
	schemaRefs: readonly SchemaReferenceRecord[],
	declaredWrites: readonly string[],
): SchemaReferenceRecord | null {
	const usable = schemaRefs.filter((record) => record.status === "SUCCESS" && record.qualified_name);
	const exact = usable.filter((record) => normalizeName(record.qualified_name!) === normalizeName(target));
	if (exact.length === 1) return exact[0]!;
	const byTail = usable.filter((record) => tableTail(record.qualified_name!) === tableTail(target));
	if (byTail.length === 1) return byTail[0]!;
	const declared = declaredWrites.filter((write) => targetMatches(write, target));
	if (declared.length === 1) {
		const selected = usable.filter((record) => normalizeName(record.qualified_name!) === normalizeName(declared[0]!));
		if (selected.length === 1) return selected[0]!;
	}
	return null;
}

function resolvedDataset(target: string, schemaRef: SchemaReferenceRecord | null, declaredWrites: readonly string[]): string {
	if (schemaRef?.qualified_name) return normalizeName(schemaRef.qualified_name);
	const declared = declaredWrites.filter((write) => targetMatches(write, target));
	return declared.length === 1 ? normalizeName(declared[0]!) : normalizeName(target);
}

function nonPartitionColumns(schemaRef: SchemaReferenceRecord | null): string[] {
	if (!schemaRef) return [];
	const partitions = new Set(schemaRef.partition_columns.map(normalizeName));
	return schemaRef.physical_columns
		.map((column) => normalizeName(String(column)))
		.filter((column) => column && !partitions.has(column));
}

function sameColumns(left: readonly string[], right: readonly string[]): boolean {
	return left.length === right.length && left.every((column, index) => normalizeName(column) === normalizeName(right[index] ?? ""));
}

function prefixColumns(prefix: readonly string[], full: readonly string[]): boolean {
	return prefix.length < full.length && prefix.every((column, index) => normalizeName(column) === normalizeName(full[index] ?? ""));
}

function gap(
	input: OutputBindingInput,
	write: WriteOutputContext,
	outcome: "UNKNOWN" | "NOT_EVALUABLE",
	reason: string,
	message: string,
	subject: string,
	extra: Record<string, unknown> = {},
): UnknownOutcomeRecord {
	return {
		unknown_id: `unknown:output-binding:${input.taskId}:${write.statementId}:${reason.toLowerCase()}`,
		task_id: input.taskId,
		statement_id: write.statementId,
		outcome_class: outcome,
		reason_code: reason,
		message,
		subject,
		...extra,
	};
}

export function deriveOutputFieldBindings(input: OutputBindingInput): OutputBindingResult {
	const creates = input.statements.map(parseCreate).filter((item): item is ParsedCreate => item !== null);
	const bindings: OutputFieldBindingRecord[] = [];
	const unknowns: UnknownOutcomeRecord[] = [];

	for (const write of input.writes) {
		if (write.statementType !== "INSERT_OVERWRITE" && write.statementType !== "INSERT_INTO") continue;
		const parsed = parseInsert(write.rawSql);
		if (!parsed) {
			unknowns.push(gap(input, write, "NOT_EVALUABLE", "OUTPUT_BINDING_NOT_PROVABLE", "INSERT target could not be parsed", write.statementId));
			continue;
		}
		if (parsed.dynamicPartitionColumns.length > 0) {
			unknowns.push(gap(
				input,
				write,
				"NOT_EVALUABLE",
				"DYNAMIC_PARTITION_BINDING_NOT_PROVABLE",
				`dynamic partition columns require engine-specific output mapping: ${parsed.dynamicPartitionColumns.join(", ")}`,
				parsed.target,
			));
			continue;
		}
		const expressions = [...write.expressions].sort((left, right) => left.ordinal - right.ordinal);
		if (expressions.length === 0 || expressions.some((expression, ordinal) => expression.ordinal !== ordinal)) {
			unknowns.push(gap(input, write, "NOT_EVALUABLE", "OUTPUT_BINDING_NOT_PROVABLE", "root output expressions are missing or not contiguous", parsed.target));
			continue;
		}

		const schemaRef = schemaForTarget(parsed.target, input.schemaRefs, input.declaredWrites);
		const dataset = resolvedDataset(parsed.target, schemaRef, input.declaredWrites);
		const physicalColumns = nonPartitionColumns(schemaRef);
		const createCandidates = creates.filter((create) => targetMatches(create.target, parsed.target));
		const create = createCandidates.length === 1 ? createCandidates[0]! : null;
		let targetColumns: string[];
		let targetOrdinals: number[];
		let bindingMethod: OutputFieldBindingRecord["binding_method"];
		let evidenceRefs: string[] = [write.statementId];

		if (parsed.targetColumns.length > 0) {
			targetColumns = [...parsed.targetColumns];
			targetOrdinals = targetColumns.map((_, ordinal) => ordinal);
			bindingMethod = "EXPLICIT_TARGET_COLUMN_LIST";
		} else if (create && create.columns.length === expressions.length) {
			targetColumns = [...create.columns];
			targetOrdinals = targetColumns.map((_, ordinal) => ordinal);
			bindingMethod = "SQL_CREATE_POSITIONAL";
			evidenceRefs.push(create.statementId);
		} else if (physicalColumns.length === expressions.length) {
			targetColumns = physicalColumns;
			targetOrdinals = targetColumns.map((_, ordinal) => ordinal);
			bindingMethod = "TARGET_SCHEMA_POSITIONAL";
		} else {
			unknowns.push(gap(
				input,
				write,
				"NOT_EVALUABLE",
				"OUTPUT_BINDING_NOT_PROVABLE",
				`SELECT output count ${expressions.length} does not match a provable target column count`,
				dataset,
				{ select_output_count: expressions.length, sql_create_column_count: create?.columns.length ?? null, physical_target_column_count: physicalColumns.length || null },
			));
			continue;
		}
		if (targetColumns.length !== expressions.length) {
			unknowns.push(gap(input, write, "NOT_EVALUABLE", "OUTPUT_BINDING_NOT_PROVABLE", `target column count ${targetColumns.length} does not match SELECT output count ${expressions.length}`, dataset));
			continue;
		}
		if (schemaRef) evidenceRefs.push(schemaRef.schema_ref_id);

		let targetSchemaStatus: OutputFieldBindingRecord["target_schema_status"] = schemaRef ? "MATCH" : "NOT_AVAILABLE";
		if (bindingMethod === "EXPLICIT_TARGET_COLUMN_LIST") {
			const referenceColumns = physicalColumns.length > 0 ? physicalColumns : create?.columns ?? [];
			if (referenceColumns.length > 0) {
				const indexes = targetColumns.map((column) => referenceColumns.findIndex((candidate) => normalizeName(candidate) === normalizeName(column)));
				const uniqueIndexes = new Set(indexes);
				if (indexes.some((ordinal) => ordinal < 0) || uniqueIndexes.size !== indexes.length) {
					unknowns.push(gap(input, write, "NOT_EVALUABLE", "OUTPUT_BINDING_SCHEMA_CONFLICT", "an explicit target column is missing or duplicated in the available target schema", dataset));
					continue;
				}
				targetOrdinals = indexes;
				if (!schemaRef && create) {
					evidenceRefs.push(create.statementId);
					targetSchemaStatus = "MATCH";
				}
			}
		} else if (schemaRef && !sameColumns(targetColumns, physicalColumns)) {
			if (prefixColumns(targetColumns, physicalColumns)) {
				targetSchemaStatus = "DRIFT_EXTRA_TARGET_COLUMNS";
				const extras = physicalColumns.slice(targetColumns.length);
				unknowns.push(gap(
					input,
					write,
					"UNKNOWN",
					"TARGET_SCHEMA_DRIFT",
					`physical target has ${extras.length} trailing column(s) not produced by this INSERT`,
					dataset,
					{ unbound_target_fields: extras.map((column) => fieldId(input.logicalSourceId, dataset, column)) },
				));
			} else {
				unknowns.push(gap(input, write, "NOT_EVALUABLE", "OUTPUT_BINDING_SCHEMA_CONFLICT", "task-local or explicit target columns conflict with the current physical target schema", dataset));
				continue;
			}
		}

		for (const [ordinal, expression] of expressions.entries()) {
			const targetField = normalizeName(targetColumns[ordinal]!);
			bindings.push({
				binding_id: `output-binding:${input.taskId}:${write.statementId}:${ordinal}`,
				task_id: input.taskId,
				statement_id: write.statementId,
				expression_id: expression.expression_id,
				target_dataset_id: datasetId(input.logicalSourceId, dataset),
				target_field_id: fieldId(input.logicalSourceId, dataset, targetField),
				target_dataset: dataset,
				target_field: targetField,
				source_ordinal: ordinal,
				target_ordinal: targetOrdinals[ordinal]!,
				binding_method: bindingMethod,
				binding_status: "RESOLVED",
				target_schema_status: targetSchemaStatus,
				static_partition_columns: parsed.staticPartitionColumns,
				evidence_refs: evidenceRefs,
			});
		}
	}

	return { bindings, unknowns };
}
