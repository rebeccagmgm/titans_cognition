import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";

import { schema118141Mapping } from "../plans/schema-118141.ts";

type SchemaMapping = Record<string, Record<string, string>>;

const workspace = resolve(import.meta.dirname, "../../..");
const outputPath = resolve(
	workspace,
	process.argv[2] ?? "sqllens/fixtures/machine-facts-independent-schema.json",
);
const starTables = new Set([
	"PDATA_N.T98_OTC_DERI_COMP_SALE_INFO",
	"PDATA_N.T98_OTC_COMP_MNG_RELA_INFO",
]);

function recordsFromMapping(mapping: SchemaMapping): Record<string, unknown>[] {
	return Object.entries(mapping).map(([qualifiedName, columns]) => {
		const parts = qualifiedName.split(".");
		return {
			db: parts.at(-2),
			table: parts.at(-1),
			qualified_name: qualifiedName,
			status: "SUCCESS",
			source: "SCHEMA_118141_TS",
			metadata_qualified_name: qualifiedName,
			required_for_star: starTables.has(qualifiedName),
			columns: Object.keys(columns).map((name) => ({ name, partition: name === "busi_date" || name === "grp_id" })),
		};
	});
}

const evidence = {
	schema_version: "machine-facts-schema-evidence-v1",
	source: "SCHEMA_118141_TS",
	evidence_boundary: "Materialized from the validated 118141 Schema fixture; no business rows were read.",
	required_table_count: Object.keys(schema118141Mapping).length,
	required_star_table_count: [...starTables].filter((qualifiedName) => qualifiedName in schema118141Mapping).length,
	success_count: Object.keys(schema118141Mapping).length,
	unresolved_count: 0,
	records: recordsFromMapping(schema118141Mapping),
};

mkdirSync(dirname(outputPath), { recursive: true });
writeFileSync(outputPath, `${JSON.stringify(evidence, null, 2)}\n`, "utf8");
console.log(JSON.stringify({ output: outputPath, records: evidence.records.length }, null, 2));
