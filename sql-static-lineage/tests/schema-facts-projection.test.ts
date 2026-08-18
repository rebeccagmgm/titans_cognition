import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { afterEach, describe, expect, it } from "vitest";

import {
	parseDdl,
	projectSchemaFacts,
	tableStorageKey,
} from "../scripts/machine-facts/schema-facts-projection.ts";

const workspace = resolve(import.meta.dirname, "../..");
const roots: string[] = [];

afterEach(() => {
	for (const root of roots.splice(0)) rmSync(root, { recursive: true, force: true });
});

function fixtureRoot(rows: readonly Record<string, unknown>[]): { input: string; output: string } {
	const root = mkdtempSync(join(tmpdir(), "titans-schema-facts-"));
	roots.push(root);
	const input = join(root, "source-layer-table-facts.jsonl");
	const output = join(root, "machine-facts", "projections", "schema-facts");
	writeFileSync(input, rows.map((row) => JSON.stringify(row)).join("\n") + "\n", "utf8");
	return { input, output };
}

function row(overrides: Record<string, unknown> = {}): Record<string, unknown> {
	return {
		table_ref: "odata_n_tit.d_ref_otc_option_deal",
		qualified_name: "odata_n_tit.d_ref_otc_option_deal@gfhive",
		guid: "21587e80-bb82-4283-bfb1-5b357162e54d",
		db_name: "odata_n_tit",
		type_name: "hive_table",
		comment: "场外交易-期权交易合同要素表",
		metadata_status: "LOCAL_INVENTORY_GUID",
		ddl_status: "SUCCESS",
		mapping: {
			upstream_all: "TITANS_DM.REF_OTC_OPTION_DEAL@gforacle_gftzdb#gftzdb",
		},
		ddl: {
			qualifiedName: "odata_n_tit.d_ref_otc_option_deal@gfhive",
			dbName: "odata_n_tit",
			type: "hive / Hive内部表",
			ddl: "create table d_ref_otc_option_deal(key_otc_trade_id string comment '内部合约ID',dynamic_notional decimal(20,4) comment '动态名义本金') partitioned by (busi_date string comment '业务日期');",
		},
		...overrides,
	};
}

describe("schema facts projection", () => {
	it("publishes one shared manifest/index and one table directory per storage key", () => {
		const { input, output } = fixtureRoot([
			row(),
			row({ table_ref: "odata_n_tit.z_no_guid", qualified_name: "odata_n_tit.z_no_guid@gfhive", guid: null }),
		]);
		const result = projectSchemaFacts(input, output, "gfhive-test");
		const firstManifestBytes = readFileSync(join(output, "manifest.json"), "utf8");
		const firstIndexBytes = readFileSync(join(output, "index.jsonl"), "utf8");
		projectSchemaFacts(input, output, "gfhive-test");

		expect(result).toMatchObject({ status: "SUCCESS", table_count: 2, column_count: 6 });
		expect(readFileSync(join(output, "manifest.json"), "utf8")).toBe(firstManifestBytes);
		expect(readFileSync(join(output, "index.jsonl"), "utf8")).toBe(firstIndexBytes);
		const manifest = JSON.parse(readFileSync(join(output, "manifest.json"), "utf8")) as Record<string, unknown>;
		const index = readFileSync(join(output, "index.jsonl"), "utf8").trim().split("\n").map((line) => JSON.parse(line) as Record<string, unknown>);
		expect(manifest).toMatchObject({
			projection_type: "SHARED_PHYSICAL_SCHEMA_FACTS",
			status: "SUCCESS",
			boundaries: expect.objectContaining({ no_schema_bundle_or_scope_hash_directories: true }),
		});
		expect(index).toHaveLength(2);
		expect(index.map((item) => item.table_path)).not.toContain(expect.stringContaining("schema_bundle_sha256"));
		expect(index.every((item) => typeof item.columns_path === "string")).toBe(true);
	});

	it("keeps current database, exact metadata names, observed source mapping, comments, partition, and DDL refs", () => {
		const { input, output } = fixtureRoot([row()]);
		projectSchemaFacts(input, output, "gfhive-test");
		const index = JSON.parse(readFileSync(join(output, "index.jsonl"), "utf8")) as Record<string, unknown>;
		const table = JSON.parse(readFileSync(join(output, String(index.table_path)), "utf8")) as Record<string, unknown>;
		const columns = readFileSync(join(output, String(index.columns_path)), "utf8").trim().split("\n").map((line) => JSON.parse(line) as Record<string, unknown>);

		expect(table).toMatchObject({
			guid: "21587e80-bb82-4283-bfb1-5b357162e54d",
			qualified_name: "odata_n_tit.d_ref_otc_option_deal",
			database_name: "odata_n_tit",
			metadata_qualified_name: "odata_n_tit.d_ref_otc_option_deal@gfhive",
			table_comment: "场外交易-期权交易合同要素表",
			comment_status: "OBSERVED",
			partition_spec: [{ column_name: "busi_date", ordinal: 1 }],
			ddl_status: "OBSERVED",
			observed_source_refs: [{
				qualified_name: "TITANS_DM.REF_OTC_OPTION_DEAL@gforacle_gftzdb#gftzdb",
				relation_kind: "OBSERVED_SOURCE_MAPPING",
			}],
		});
		expect(String(table.ddl_ref)).toMatch(/^source-layer\/source-layer-table-facts\.jsonl#ddl_sha256=[0-9a-f]{64}$/);
		expect(columns[0]).toMatchObject({
			column_name: "key_otc_trade_id",
			field_id: "field:gfhive-test:odata_n_tit.d_ref_otc_option_deal.key_otc_trade_id",
			column_comment: "内部合约ID",
			comment_status: "OBSERVED",
			is_partition_column: false,
		});
		expect(columns[2]).toMatchObject({ column_name: "busi_date", is_partition_column: true, partition_ordinal: 1 });
	});

	it("distinguishes absent and unavailable comments and preserves missing GUID fallback", () => {
		const absent = row({ table_ref: "odata_n_tit.absent", qualified_name: "odata_n_tit.absent@gfhive", guid: null, comment: "-", ddl: undefined, ddl_status: "SUCCESS" });
		const unavailable = row({ table_ref: "odata_n_tit.unavailable", qualified_name: "odata_n_tit.unavailable@gfhive", guid: null, comment: null, ddl: undefined, ddl_status: undefined, metadata_status: undefined, schema_status: undefined, mapping: undefined });
		const { input, output } = fixtureRoot([absent, unavailable]);
		projectSchemaFacts(input, output, "gfhive-test");
		const records = readFileSync(join(output, "index.jsonl"), "utf8").trim().split("\n").map((line) => JSON.parse(line) as Record<string, unknown>);
		for (const index of records) {
			const table = JSON.parse(readFileSync(join(output, String(index.table_path)), "utf8")) as Record<string, unknown>;
			if (table.qualified_name === "odata_n_tit.absent") {
				expect(table).toMatchObject({ guid: null, storage_key_strategy: "METADATA_QUALIFIED_NAME", comment_status: "ABSENT" });
			} else {
				expect(table).toMatchObject({ guid: null, storage_key_strategy: "METADATA_QUALIFIED_NAME", comment_status: "UNAVAILABLE", ddl_status: "UNAVAILABLE" });
			}
		}
	});

	it("falls back to a safe logical name when both GUID and metadata qualified name are unavailable", () => {
		const storage = tableStorageKey("gfhive-test", { guid: null }, "odata_n_tit.no_guid", null);
		expect(storage.strategy).toBe("LOGICAL_SOURCE_AND_QUALIFIED_NAME");
		expect(storage.key).toMatch(/^name__/);
		expect(storage.key).not.toContain("/");
	});

	it("does not let physical location or source mapping alter existing dataset/field identity", () => {
		const first = row();
		const second = row({ db_name: "another_db", qualified_name: "odata_n_tit.d_ref_otc_option_deal@gfhive", mapping: { upstream_all: "OTHER.OBJECT@oracle" } });
		const firstRoot = fixtureRoot([first]);
		const secondRoot = fixtureRoot([second]);
		projectSchemaFacts(firstRoot.input, firstRoot.output, "gfhive-test");
		projectSchemaFacts(secondRoot.input, secondRoot.output, "gfhive-test");
		const firstIndex = JSON.parse(readFileSync(join(firstRoot.output, "index.jsonl"), "utf8")) as Record<string, unknown>;
		const secondIndex = JSON.parse(readFileSync(join(secondRoot.output, "index.jsonl"), "utf8")) as Record<string, unknown>;
		const firstTable = JSON.parse(readFileSync(join(firstRoot.output, String(firstIndex.table_path)), "utf8")) as Record<string, unknown>;
		const secondTable = JSON.parse(readFileSync(join(secondRoot.output, String(secondIndex.table_path)), "utf8")) as Record<string, unknown>;
		const firstColumn = JSON.parse(readFileSync(join(firstRoot.output, String(firstIndex.columns_path)), "utf8").split("\n")[0]!) as Record<string, unknown>;
		const secondColumn = JSON.parse(readFileSync(join(secondRoot.output, String(secondIndex.columns_path)), "utf8").split("\n")[0]!) as Record<string, unknown>;
		expect(secondTable.dataset_id).toBeUndefined();
		expect(firstColumn.dataset_id).toBe(secondColumn.dataset_id);
		expect(firstColumn.field_id).toBe(secondColumn.field_id);
	});

	it("parses columns and partition columns without emitting constraints or semantic facts", () => {
		const parsed = parseDdl("create table t(a string comment 'A', b decimal(20,4)) partitioned by (dt string comment 'D') stored as orc;");
		expect(parsed.columns.map((column) => column.name)).toEqual(["a", "b"]);
		expect(parsed.partition_columns).toMatchObject([{ name: "dt", data_type: "string", partition_ordinal: 1 }]);
		expect(parsed.columns.some((column) => /primary|unique|constraint/i.test(column.name))).toBe(false);
	});

	it("matches the four-route shared projection surface and target location evidence", () => {
		const sourcePath = join(workspace, "machine-facts", "registry", "source-layer", "source-layer-table-facts.jsonl");
		const output = join(mkdtempSync(join(tmpdir(), "titans-schema-facts-four-routes-")), "schema-facts");
		roots.push(resolve(output, ".."));
		const result = projectSchemaFacts(sourcePath, output, "gfhive-test");
		expect(result.table_count).toBeGreaterThan(0);
		const target = readFileSync(join(output, "index.jsonl"), "utf8")
			.trim()
			.split("\n")
			.map((line) => JSON.parse(line) as Record<string, unknown>)
			.find((item) => item.qualified_name === "odata_n_tit.d_ref_otc_option_deal");
		expect(target).toBeDefined();
		const table = JSON.parse(readFileSync(join(output, String(target!.table_path)), "utf8")) as Record<string, unknown>;
		expect(table).toMatchObject({
			guid: "21587e80-bb82-4283-bfb1-5b357162e54d",
			database_name: "odata_n_tit",
			metadata_qualified_name: "odata_n_tit.d_ref_otc_option_deal@gfhive",
		});
		expect(String(JSON.stringify(table))).not.toMatch(/schema_bundle_sha256|scope_sha256|semantic_status|grain|cardinality/i);

		const projectedFieldIds = new Set<string>();
		const indexRecords = readFileSync(join(output, "index.jsonl"), "utf8").trim().split("\n").map((line) => JSON.parse(line) as Record<string, unknown>);
		for (const indexRecord of indexRecords) {
			const columnsPath = String(indexRecord.columns_path);
			for (const line of readFileSync(join(output, columnsPath), "utf8").split("\n").map((item) => item.trim()).filter(Boolean)) {
				const column = JSON.parse(line) as Record<string, unknown>;
				if (typeof column.field_id === "string") projectedFieldIds.add(column.field_id);
			}
		}
		const columnsByField = new Set<string>();
		const taskIds = ["86840", "86841", "86842", "220650"];
		const routeMatchCounts = new Map<string, number>();
		for (const taskId of taskIds) {
			const path = join(workspace, "machine-facts", "registry", "tasks", taskId, "bundle", "field-expression-nodes.jsonl");
			const expressions = readFileSync(path, "utf8")
				.trim()
				.split("\n")
				.map((line) => JSON.parse(line) as Record<string, unknown>);
			let routeMatches = 0;
			for (const expression of expressions) {
				const inputs = Array.isArray(expression.input_fields) ? expression.input_fields : [];
				for (const input of inputs) {
					const fieldId = typeof input === "object" && input !== null ? (input as Record<string, unknown>).field_id : null;
					if (typeof fieldId === "string") columnsByField.add(fieldId);
					if (typeof fieldId === "string" && projectedFieldIds.has(fieldId)) routeMatches += 1;
				}
			}
			routeMatchCounts.set(taskId, routeMatches);
		}
		const targetIndex = indexRecords.find((item) => item.qualified_name === "odata_n_tit.d_ref_otc_option_deal");
		const targetColumns = readFileSync(join(output, String(targetIndex!.columns_path)), "utf8").trim().split("\n").map((line) => JSON.parse(line) as Record<string, unknown>);
		expect(targetColumns.some((column) => column.column_name === "dynamic_notional")).toBe(true);
		expect(projectedFieldIds.has("field:gfhive-test:odata_n_tit.d_ref_otc_option_deal.dynamic_notional")).toBe(true);
		expect(columnsByField.size).toBeGreaterThan(0);
		expect([...routeMatchCounts.values()].every((count) => count > 0)).toBe(true);
	});
});
