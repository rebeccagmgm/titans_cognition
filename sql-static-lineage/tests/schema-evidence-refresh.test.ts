import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, relative, resolve } from "node:path";
import { afterEach, describe, expect, it } from "vitest";

import { discoverRequiredTables, isSzDataRateLimited } from "../scripts/machine-facts/schema-evidence-refresh.ts";

const workspace = resolve(import.meta.dirname, "../..");
const roots: string[] = [];

afterEach(() => {
	for (const root of roots.splice(0)) rmSync(root, { recursive: true, force: true });
});

describe("schema evidence refresh discovery", () => {
	it("classifies platform throttling separately from ordinary failures", () => {
		expect(isSzDataRateLimited(new Error("MCP 全局限流命中, dimension=USER, threshold=5"))).toBe(true);
		expect(isSzDataRateLimited(new Error("根据guid查询ddl失败：通用错误"))).toBe(false);
	});

	it("discovers physical inputs from SQL plan rather than a configured table list", () => {
		const root = mkdtempSync(join(tmpdir(), "titans-schema-refresh-"));
		roots.push(root);
		const sql = join(root, "task.sql");
		const profile = join(root, "profile.json");
		writeFileSync(sql, "INSERT OVERWRITE TABLE pdata_n.target SELECT source.id FROM pdata_n.source source JOIN pdata_n.reference reference ON source.id = reference.id;\n", "utf8");
		writeFileSync(profile, JSON.stringify({
			dialect: "databricks",
			tasks: [{ sql_snapshot: relative(workspace, sql).replace(/\\/g, "/") }],
		}), "utf8");

		const tables = discoverRequiredTables(relative(workspace, profile).replace(/\\/g, "/"));

		expect(tables.map((table) => table.qualified_name)).toEqual([
			"pdata_n.reference",
			"pdata_n.source",
		]);
	});
});
