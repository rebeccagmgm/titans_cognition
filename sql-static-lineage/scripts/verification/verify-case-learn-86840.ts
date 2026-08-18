import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

type JsonRecord = Record<string, any>;

const workspace = resolve(import.meta.dirname, "../../..");
const outputDir = resolve(workspace, "output/case-learn-86840");
const manifest = JSON.parse(readFileSync(resolve(outputDir, "learning-manifest.json"), "utf8")) as JsonRecord;
const profilePath = resolve(workspace, manifest.profile);
const profile = JSON.parse(readFileSync(profilePath, "utf8")) as JsonRecord;

function sha256(value: string | Buffer): string {
	return createHash("sha256").update(value).digest("hex");
}

let passed = 0;
let failed = 0;
function check(name: string, condition: boolean): void {
	if (condition) passed += 1;
	else failed += 1;
	console.log(`${condition ? "OK" : "FAIL"} ${name}`);
}

check("case id is case-learn-86840", manifest.case_id === "case-learn-86840");
check("exactly 8 stages are recorded", manifest.stage_count === 8 && manifest.stages?.length === 8);
check(
	"stage numbers are 1..8",
	JSON.stringify(manifest.stages?.map((stage: JsonRecord) => stage.stage_no)) ===
		JSON.stringify([1, 2, 3, 4, 5, 6, 7, 8]),
);
check(
	"stage files are numbered and present",
	(manifest.stages ?? []).every((stage: JsonRecord) => {
		const path = resolve(outputDir, stage.file);
		return /^[0-9]{2}-[a-z0-9-]+\.json$/.test(stage.file) && readFileSync(path, "utf8").length > 0;
	}),
);
check(
	"stage file hashes match manifest",
	(manifest.stages ?? []).every(
		(stage: JsonRecord) => sha256(readFileSync(resolve(outputDir, stage.file))) === stage.sha256,
	),
);
check("profile hash matches manifest", sha256(readFileSync(profilePath)) === manifest.profile_sha256);

const stages = (manifest.stages ?? []).map(
	(stage: JsonRecord) => JSON.parse(readFileSync(resolve(outputDir, stage.file), "utf8")) as JsonRecord,
);
check(
	"each stage envelope has the case id",
	stages.every((stage) => stage.case_id === "case-learn-86840"),
);
check(
	"each stage envelope has matching stage number",
	stages.every((stage, index) => stage.stage_no === index + 1),
);
check("stage 5 names target field", stages[4]?.output?.target_field === "dyna_nom_prin");
check("stage 6 stores lineage output", Array.isArray(stages[5]?.output?.statements));
check("stage 7 stores plan facts", Array.isArray(stages[6]?.output?.plans));
check(
	"stage 3 stores sql-static-lineage IR",
	stages[2]?.output?.statements?.every((item: JsonRecord) => Boolean(item.parser_ir)) === true,
);
check(
	"stage 1 matches current SQL and Schema evidence",
	(() => {
		const sourcePath = resolve(workspace, profile.source_sql);
		const schemaPath = resolve(workspace, profile.schema_evidence);
		return (
			stages[0]?.output?.source_sha256 === sha256(readFileSync(sourcePath)) &&
			stages[0]?.output?.schema_evidence?.sha256 === sha256(readFileSync(schemaPath))
		);
	})(),
);
const bindingRows =
	stages[4]?.output?.expressions?.flatMap((expression: JsonRecord) => expression.input_columns ?? []) ?? [];
const bindingComplete =
	bindingRows.length > 0 &&
	bindingRows.every((row: JsonRecord) => row.resolution === "bound" && row.physical?.length > 0);
check("stage 5 status reflects binding completeness", stages[4]?.status === (bindingComplete ? "SUCCESS" : "PARTIAL"));
const lineageRows =
	stages[5]?.output?.statements?.flatMap((statement: JsonRecord) => statement.target_outputs ?? []) ?? [];
const lineageComplete = lineageRows.length > 0 && lineageRows.every((row: JsonRecord) => row.origins?.length > 0);
check("stage 6 status reflects lineage completeness", stages[5]?.status === (lineageComplete ? "SUCCESS" : "PARTIAL"));
check(
	"stage 8 does not claim a complete journey",
	stages[7]?.status !== "SUCCESS" || stages[7]?.output?.status === "PARTIAL",
);
check("manifest does not claim business acceptance", manifest.not_claimed?.includes("business_acceptance") === true);

console.log(`--- ${passed} passed, ${failed} failed ---`);
process.exit(failed ? 1 : 0);
