import { execFile } from "node:child_process";
import { createHash } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, renameSync, rmSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { promisify } from "node:util";

import { buildPlanFacts } from "../plans/plan-adapter.ts";
import { SqlSession } from "../../src/index.ts";

type JsonRecord = Record<string, any>;

export interface SchemaRefreshTable {
	db: string;
	table: string;
	qualified_name: string;
	required_for_star: boolean;
}

interface GenericProfile {
	case_id?: string;
	dialect?: string;
	schema_evidence?: string | string[];
	tasks: Array<{ sql_snapshot: string }>;
}

const execFileAsync = promisify(execFile);
const workspace = resolve(import.meta.dirname, "../../..");
const opencliEntry = resolve(
	process.env.APPDATA ?? "",
	"npm/node_modules/@jackwener/opencli/dist/src/main.js",
);

function positiveEnvNumber(name: string, fallback: number): number {
	const value = Number(process.env[name]);
	return Number.isFinite(value) && value > 0 ? value : fallback;
}

const sha256 = (value: string): string => createHash("sha256").update(value).digest("hex");
const normalizeIdentifier = (value: string): string => value.replace(/[`"\[\]]/g, "").toLowerCase();

function errorText(error: unknown): string {
	return error instanceof Error ? error.message : String(error);
}

export function isSzDataRateLimited(error: unknown): boolean {
	const message = errorText(error);
	return /限流|rate.?limit|threshold=\d+|dimension=USER/i.test(message);
}

function json<T>(path: string): T {
	return JSON.parse(readFileSync(path, "utf8")) as T;
}

function resolveEvidencePath(profile: GenericProfile): string {
	const configured = Array.isArray(profile.schema_evidence)
		? profile.schema_evidence[0]
		: profile.schema_evidence;
	if (!configured) throw new Error("schema_evidence is required for schema refresh");
	return resolve(workspace, configured);
}

export function discoverRequiredTables(profilePath: string): SchemaRefreshTable[] {
	const profile = json<GenericProfile>(resolve(workspace, profilePath));
	const physical = new Set<string>();
	const stars = new Set<string>();
	const starPattern = /select\s+(?:[a-zA-Z_][\w]*\.)?\*\s+from\s+([`"\[\]\w.]+)/gis;
	const dialect = profile.dialect ?? "databricks";

	for (const task of profile.tasks) {
		const sql = readFileSync(resolve(workspace, task.sql_snapshot), "utf8");
		for (const match of sql.matchAll(starPattern)) stars.add(normalizeIdentifier(match[1]!));
		const session = SqlSession.create(sql, dialect as any);
		for (const [statementIndex, cell] of session.doc.statements.entries()) {
			const plan = buildPlanFacts(cell, sql, { statement_index: statementIndex, dialect });
			for (const table of plan.physical_inputs) physical.add(normalizeIdentifier(table));
		}
	}

	return [...physical]
		.flatMap((qualifiedName): SchemaRefreshTable[] => {
			const parts = qualifiedName.split(".");
			if (parts.length < 2) return [];
			return [{
				db: parts.at(-2)!,
				table: parts.at(-1)!,
				qualified_name: qualifiedName,
				required_for_star: stars.has(qualifiedName),
			}];
		})
		.sort((left, right) => left.qualified_name.localeCompare(right.qualified_name));
}

async function opencli(args: string[]): Promise<any[]> {
	let lastError: unknown;
	const attempts = Math.floor(positiveEnvNumber("MACHINE_FACTS_SCHEMA_REFRESH_ATTEMPTS", 4));
	const timeout = positiveEnvNumber("MACHINE_FACTS_SCHEMA_REFRESH_TIMEOUT_MS", 120_000);
	for (let attempt = 0; attempt < attempts; attempt += 1) {
		try {
			const { stdout } = await execFileAsync(
				process.execPath,
				[opencliEntry, "szdata", ...args, "-f", "json"],
				{ cwd: workspace, encoding: "utf8", maxBuffer: 20 * 1024 * 1024, timeout },
			);
			return JSON.parse(stdout) as any[];
		} catch (error) {
			lastError = error;
			if (attempt + 1 < attempts) {
				const delayMs = isSzDataRateLimited(error)
					? 15_000 * (attempt + 1)
					: 1_500 * (attempt + 1);
				await new Promise((resolveDelay) => setTimeout(resolveDelay, delayMs));
			}
		}
	}
	throw lastError;
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

function parseDdlColumns(ddl: string): JsonRecord[] {
	const firstOpen = ddl.indexOf("(");
	const main = firstOpen >= 0 ? parenthesizedAt(ddl, firstOpen) : null;
	if (!main) return [];
	const excluded = new Set(["constraint", "primary", "foreign", "unique", "key"]);
	const parseClause = (clause: string, partition: boolean): JsonRecord[] =>
		splitTopLevel(clause).flatMap((raw) => {
			const definition = raw.trim();
			const match = definition.match(/^(?:`([^`]+)`|"([^"]+)"|\[([^\]]+)\]|([A-Za-z_][\w$]*))/);
			const name = match?.slice(1).find(Boolean);
			return !name || excluded.has(name.toLowerCase())
				? []
				: [{ name: normalizeIdentifier(name), partition, raw_definition: definition }];
		});
	const columns = parseClause(main.content, false);
	const partitionMatch = /partitioned\s+by\s*\(/i.exec(ddl.slice(main.end));
	if (!partitionMatch) return columns;
	const partitionOpen = main.end + partitionMatch.index + partitionMatch[0].lastIndexOf("(");
	const partition = parenthesizedAt(ddl, partitionOpen);
	return partition ? [...columns, ...parseClause(partition.content, true)] : columns;
}

async function collectTable(ref: SchemaRefreshTable): Promise<JsonRecord> {
	try {
		const summaryRows = await opencli(["table", "--db", ref.db, "--table", ref.table, "--view", "summary"]);
		const table = summaryRows[0]?.table;
		if (!table?.guid) return { ...ref, status: "NOT_FOUND", source: "SZDATA_TABLE" };
		const ddlRows = await opencli(["table-ddl", "--guid", table.guid]);
		const ddlRow = ddlRows.find((row) => row.guid === table.guid) ?? ddlRows[0];
		if (!ddlRow?.ddl) return { ...ref, status: "DDL_UNAVAILABLE", guid: table.guid, source: "SZDATA_TABLE_DDL" };
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
			error_message: error instanceof Error ? error.message.slice(-1000) : String(error).slice(-1000),
		};
	}
}

function writeAtomic(path: string, value: unknown): void {
	mkdirSync(dirname(path), { recursive: true });
	const temp = `${path}.tmp-${process.pid}`;
	const backup = `${path}.bak`;
	writeFileSync(temp, `${JSON.stringify(value, null, 2)}\n`, "utf8");
	if (existsSync(backup)) rmSync(backup, { force: true });
	if (existsSync(path)) renameSync(path, backup);
	try {
		renameSync(temp, path);
		if (existsSync(backup)) rmSync(backup, { force: true });
	} catch (error) {
		if (!existsSync(path) && existsSync(backup)) renameSync(backup, path);
		if (existsSync(temp)) rmSync(temp, { force: true });
		throw error;
	}
}

export async function refreshSchemaEvidence(profilePath: string): Promise<JsonRecord> {
	const profile = json<GenericProfile>(resolve(workspace, profilePath));
	const evidencePath = resolveEvidencePath(profile);
	const requiredTables = discoverRequiredTables(profilePath);
	const prior = existsSync(evidencePath) ? json<JsonRecord>(evidencePath) : {};
	const priorRecords = Array.isArray(prior.records) ? (prior.records as JsonRecord[]) : [];
	const priorSuccesses = new Map(
		priorRecords
			.filter((record) => record.status === "SUCCESS")
			.map((record) => [normalizeIdentifier(String(record.qualified_name)), record]),
	);
	const missing = requiredTables.filter((table) => !priorSuccesses.has(table.qualified_name));
	const fetched = new Map<string, JsonRecord>();
	for (const table of missing) fetched.set(table.qualified_name, await collectTable(table));
	const records = requiredTables.map((table) => priorSuccesses.get(table.qualified_name) ?? fetched.get(table.qualified_name));
	const result = {
		schema_version: "machine-facts-schema-evidence-v1",
		case_id: profile.case_id,
		captured_at: new Date().toISOString(),
		source: "SZDATA_TABLE_DDL",
		collection_mode: "SQL_PLAN_MISSING_TABLES_ONLY",
		required_table_count: requiredTables.length,
		required_star_table_count: requiredTables.filter((table) => table.required_for_star).length,
		success_count: records.filter((record) => record?.status === "SUCCESS").length,
		unresolved_count: records.filter((record) => record?.status !== "SUCCESS").length,
		records,
	};
	writeAtomic(evidencePath, result);
	return {
		output: evidencePath,
		required_table_count: requiredTables.length,
		missing_table_count: missing.length,
		fetched_success_count: [...fetched.values()].filter((record) => record.status === "SUCCESS").length,
		success_count: result.success_count,
		unresolved: records
			.filter((record) => record?.status !== "SUCCESS")
			.map((record) => ({ table: record?.qualified_name, status: record?.status })),
	};
}
