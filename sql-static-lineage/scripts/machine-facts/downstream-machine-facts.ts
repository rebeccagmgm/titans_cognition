import { basename } from "node:path";

import { main } from "./downstream-machine-facts-by-task.ts";

if (process.argv[1] && basename(process.argv[1]).startsWith("downstream-machine-facts")) main();
