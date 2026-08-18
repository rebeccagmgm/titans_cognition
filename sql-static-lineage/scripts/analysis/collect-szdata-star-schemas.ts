import { execFile } from "node:child_process";
import { createHash } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { promisify } from "node:util";

import { buildPlanFacts } from "../plans/plan-adapter.ts";
import { SqlSession } from "../../src/index.ts";

interface TaskProfile {
	sql_snapshot: string;
}

interface ProcessingProfile {
	case_id: string;
	schema_evidence: string;
	tasks: TaskProfile[];
}

interface TableRef {
	db: string;
	table: string;
	qualified_name: string;
	required_for_star: boolean;
}

const execFileAsync = promisify(execFile);
const workspace = resolve(import.meta.dirname, "../..");
const profileArgument = process.argv.slice(2).find((argument) => !argument.startsWith("--"));
const profilePath = resolve(
	workspace,
	profileArgument ?? "cases/indicator-journey-rgstcomp-mthend/processing-graph-profile.json",
);
const profile = JSON.parse(readFileSync(profilePath, "utf8")) as ProcessingProfile;
const evidencePath = resolve(workspace, profile.schema_evidence);
const opencliEntry = resolve(process.env.APPDATA ?? "", "npm/node_modules/@jackwener/opencli/dist/src/main.js");

const sha256 = (value: string): string => createHash("sha256").update(value).digest("hex");
const normalizeIdentifier = (value: string): string => value.replace(/[`"\[\]]/g, "").toLowerCase();

function requiredTablesFromSql(): TableRef[] {
	const physical = new Set<string>();
	const stars = new Set<string>();
	const pattern = /select\s+(?:[a-zA-Z_][\w]*\.)?\*\s+from\s+([`"\[\]\w.]+)/gis;
	for (const task of profile.tasks) {
		const sql = readFileSync(resolve(workspace, task.sql_snapshot), "utf8");
		for (const match of sql.matchAll(pattern)) {
			stars.add(normalizeIdentifier(match[1]!));
		}
		const session = SqlSession.create(sql, "databricks");
		for (const [statementIndex, cell] of session.doc.statements.entries()) {
			const plan = buildPlanFacts(cell, sql, { statement_index: statementIndex, dialect: "databricks" });
			for (const table of plan.physical_inputs) physical.add(normalizeIdentifier(table));
		}
	}
	return [...physical]
		.flatMap((qualifiedName): TableRef[] => {
			const parts = qualifiedName.split(".");
			if (parts.length < 2) return [];
			return [
				{
					db: parts.at(-2)!,
					table: parts.at(-1)!,
					qualified_name: qualifiedName,
					required_for_star: stars.has(qualifiedName),
				},
			];
		})
		.sort((left, right) => left.qualified_name.localeCompare(right.qualified_name));
}

async function opencli(args: string[]): Promise<any[]> {
	const { stdout } = await execFileAsync(process.execPath, [opencliEntry, "szdata", ...args, "-f", "json"], {
		cwd: workspace,
		encoding: "utf8",
		maxBuffer: 20 * 1024 * 1024,
		timeout: 120_000,
	});
	return JSON.parse(stdout) as any[];
}

function parenthesizedAt(sql: string, open: number): { content: string; end: number } | null {
	if (sql[open] !== "(") return null;
	let depth = 1;
	let quote: "'" | '"' | "`" | null = null;
	for (let index = open + 1; index < sql.length; index += 1) {
		const char = sql[index]!;
		if (quote) {
			if (char === quote) {
				if (quote === "'" && sql[index + 1] === "'") index += 1;
				else quote = null;
			}
			continue;
		}
		if (char === "'" || char === '"' || char === "`") quote = char;
		else if (char === "(") depth += 1;
		else if (char === ")") {
			depth -= 1;
			if (depth === 0) return { content: sql.slice(open + 1, index), end: index + 1 };
		}
	}
	return null;
}

function splitTopLevel(value: string): string[] {
	const parts: string[] = [];
	let start = 0;
	let parenDepth = 0;
	let angleDepth = 0;
	let quote: "'" | '"' | "`" | null = null;
	for (let index = 0; index < value.length; index += 1) {
		const char = value[index]!;
		if (quote) {
			if (char === quote) {
				if (quote === "'" && value[index + 1] === "'") index += 1;
				else quote = null;
			}
			continue;
		}
		if (char === "'" || char === '"' || char === "`") quote = char;
		else if (char === "(") parenDepth += 1;
		else if (char === ")") parenDepth -= 1;
		else if (char === "<") angleDepth += 1;
		else if (char === ">") angleDepth = Math.max(0, angleDepth - 1);
		else if (char === "," && parenDepth === 0 && angleDepth === 0) {
			parts.push(value.slice(start, index));
			start = index + 1;
		}
	}
	parts.push(value.slice(start));
	return parts;
}

function parseColumnClause(clause: string, partition: boolean): Record<string, any>[] {
	const excluded = new Set(["constraint", "primary", "foreign", "unique", "key"]);
	return splitTopLevel(clause).flatMap((rawDefinition) => {
		const definition = rawDefinition.trim();
		const nameMatch = definition.match(/^(?:`([^`]+)`|"([^"]+)"|\[([^\]]+)\]|([A-Za-z_][\w$]*))/);
		const name = nameMatch?.slice(1).find(Boolean);
		if (!name || excluded.has(name.toLowerCase())) return [];
		return [{ name: normalizeIdentifier(name), partition, raw_definition: definition }];
	});
}

function parseDdlColumns(ddl: string): Record<string, any>[] {
	const firstOpen = ddl.indexOf("(");
	const main = firstOpen >= 0 ? parenthesizedAt(ddl, firstOpen) : null;
	if (!main) return [];
	const columns = parseColumnClause(main.content, false);
	const partitionMatch = /partitioned\s+by\s*\(/i.exec(ddl.slice(main.end));
	if (!partitionMatch) return columns;
	const partitionOpen = main.end + partitionMatch.index + partitionMatch[0].lastIndexOf("(");
	const partition = parenthesizedAt(ddl, partitionOpen);
	return partition ? [...columns, ...parseColumnClause(partition.content, true)] : columns;
}

async function collectTable(ref: TableRef): Promise<Record<string, any>> {
	try {
		const summaryRows = await opencli(["table", "--db", ref.db, "--table", ref.table, "--view", "summary"]);
		const table = summaryRows[0]?.table;
		if (!table?.guid) {
			return { ...ref, status: "NOT_FOUND", source: "SZDATA_TABLE" };
		}
		const ddlRows = await opencli(["table-ddl", "--guid", table.guid]);
		const ddlRow = ddlRows.find((row) => row.guid === table.guid) ?? ddlRows[0];
		if (!ddlRow?.ddl) {
			return {
				...ref,
				status: "DDL_UNAVAILABLE",
				guid: table.guid,
				source: "SZDATA_TABLE_DDL",
			};
		}
		const columns = parseDdlColumns(ddlRow.ddl);
		return {
			...ref,
			status: columns.length > 0 ? "SUCCESS" : "DDL_PARSE_FAILED",
			guid: table.guid,
			metadata_qualified_name: ddlRow.qualifiedName,
			table_status: table.status,
			description: table.description,
			ddl_sha256: sha256(ddlRow.ddl),
			ddl: ddlRow.ddl,
			columns,
			source: "SZDATA_TABLE_DDL",
		};
	} catch (error) {
		return {
			...ref,
			status: "QUERY_FAILED",
			source: "SZDATA_TABLE_DDL",
			error_class: error instanceof Error ? error.name : "UnknownError",
		};
	}
}

async function mapConcurrent<T, R>(items: T[], limit: number, worker: (item: T) => Promise<R>): Promise<R[]> {
	const results = new Array<R>(items.length);
	let next = 0;
	await Promise.all(
		Array.from({ length: Math.min(limit, items.length) }, async () => {
			while (next < items.length) {
				const index = next;
				next += 1;
				results[index] = await worker(items[index]!);
			}
		}),
	);
	return results;
}

const requiredTables = requiredTablesFromSql();
const resume = process.argv.includes("--resume");
const priorRecords =
	resume && existsSync(evidencePath)
		? ((JSON.parse(readFileSync(evidencePath, "utf8")) as Record<string, any>).records as Record<string, any>[])
		: [];
const priorSuccesses = new Map(
	priorRecords.filter((record) => record.status === "SUCCESS").map((record) => [record.qualified_name, record]),
);
const unresolvedTables = requiredTables.filter((table) => !priorSuccesses.has(table.qualified_name));
const retriedRecords = await mapConcurrent(unresolvedTables, 1, collectTable);
const retriedByName = new Map(retriedRecords.map((record) => [record.qualified_name, record]));
const records = requiredTables.map(
	(table) => priorSuccesses.get(table.qualified_name) ?? retriedByName.get(table.qualified_name),
);
const successCount = records.filter((record) => record.status === "SUCCESS").length;
const evidence = {
	schema_version: "szdata-schema-evidence-v1",
	case_id: profile.case_id,
	captured_at: new Date().toISOString(),
	source: "SZDATA_TABLE_DDL",
	collection_mode: resume ? "RESUME_SUCCESSFUL_RECORDS" : "FRESH",
	required_table_count: requiredTables.length,
	required_star_table_count: requiredTables.filter((table) => table.required_for_star).length,
	success_count: successCount,
	unresolved_count: records.length - successCount,
	records,
};
mkdirSync(resolve(evidencePath, ".."), { recursive: true });
writeFileSync(evidencePath, JSON.stringify(evidence, null, 2) + "\n", "utf8");
console.log(
	JSON.stringify(
		{
			output: evidencePath,
			required_table_count: requiredTables.length,
			success_count: successCount,
			unresolved: records
				.filter((record) => record.status !== "SUCCESS")
				.map((record) => ({ table: record.qualified_name, status: record.status })),
		},
		null,
		2,
	),
);
