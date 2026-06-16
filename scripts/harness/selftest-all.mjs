#!/usr/bin/env node
/**
 * selftest-all — run every deterministic self-test in the harness kit and summarize.
 *
 * This is the kit's regression gate: it needs no agent, no network, and no install (Node built-ins
 * only). It runs each component's `--self-test`, the domain deliverable-check unit tests, and a
 * JSON-validity sweep over the committed harness JSON. It keeps going after a failure so CI shows the
 * full picture, and exits non-zero if anything failed.
 *
 *   node scripts/harness/selftest-all.mjs            # or: npm run harness:selftest
 *   node scripts/harness/selftest-all.mjs --json
 */
import { spawnSync } from "node:child_process";
import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import { dirname, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..");

const CHECK_DIR = "scripts/harness/domain-checks";
const domainCheckTests = ["required-sections", "citation-integrity", "defined-terms", "figure-reconciliation", "claim-substantiation", "checklist-coverage"]
  .map((name) => ({ name: `domain-check: ${name}`, cmd: [`${CHECK_DIR}/${name}.mjs`, "--self-test"] }));

const SUITES = [
  ...domainCheckTests,
  { name: "domain-pack", cmd: ["scripts/harness/domain-pack.mjs", "--self-test"] },
  { name: "doctor", cmd: ["scripts/harness/doctor.mjs", "--self-test"] },
  { name: "eval suite", cmd: ["scripts/harness/eval/run-eval.mjs", "--self-test"] },
  { name: "git-guard", cmd: ["scripts/harness/git-guard.mjs", "--self-test"] },
  { name: "trace grader", cmd: ["scripts/harness/grade-trace.mjs", "--self-test"] },
  { name: "otel export", cmd: ["scripts/harness/otel-export.mjs", "--self-test"] },
  { name: "plan-review", cmd: ["scripts/harness/plan-review.mjs", "--self-test"] },
  { name: "command-validation", cmd: ["scripts/harness/command-validation.mjs", "--self-test"] },
  { name: "evolve-guard", cmd: ["scripts/harness/evolve-guard.mjs", "--self-test"] },
];

// Walk every .json under .github/harness and confirm it parses — a malformed loop/pack/config is a
// real breakage the per-component self-tests would not all catch.
function jsonFiles(dir, acc = []) {
  if (!existsSync(dir)) return acc;
  for (const entry of readdirSync(dir)) {
    const p = join(dir, entry);
    const st = statSync(p);
    if (st.isDirectory()) jsonFiles(p, acc);
    else if (entry.endsWith(".json")) acc.push(p);
  }
  return acc;
}

function runJsonSweep() {
  const files = jsonFiles(join(repoRoot, ".github", "harness")).concat(
    ["harness.config.json", ".mcp.json", ".cursor/mcp.json", ".vscode/mcp.json", "package.json"]
      .map((f) => join(repoRoot, f))
      .filter((f) => existsSync(f)),
  );
  const bad = [];
  for (const f of files) {
    try { JSON.parse(readFileSync(f, "utf8")); } catch (e) { bad.push(`${relative(repoRoot, f)}: ${e.message}`); }
  }
  return { name: `json-validity (${files.length} files)`, pass: bad.length === 0, detail: bad.join("; ") };
}

const results = [];
for (const suite of SUITES) {
  if (!existsSync(join(repoRoot, suite.cmd[0]))) {
    results.push({ name: suite.name, status: "skip", detail: "script not present" });
    continue;
  }
  const r = spawnSync("node", suite.cmd, { cwd: repoRoot, encoding: "utf8", timeout: 120000, stdio: ["ignore", "pipe", "pipe"] });
  const pass = r.status === 0;
  results.push({ name: suite.name, status: pass ? "pass" : "fail", detail: pass ? "" : `exit ${r.status}\n${(r.stdout || "") + (r.stderr || "")}`.trim() });
}
const sweep = runJsonSweep();
results.push({ name: sweep.name, status: sweep.pass ? "pass" : "fail", detail: sweep.detail });

const failed = results.filter((r) => r.status === "fail");
if (process.argv.includes("--json")) {
  process.stdout.write(`${JSON.stringify({ ok: failed.length === 0, results }, null, 2)}\n`);
} else {
  process.stdout.write(`\n[selftest-all] ${results.length} suite(s)\n`);
  for (const r of results) {
    const mark = r.status === "pass" ? "✓" : r.status === "skip" ? "·" : "✗";
    process.stdout.write(`  ${mark} ${r.name}${r.status === "fail" ? `\n      ${r.detail.split("\n").join("\n      ")}` : ""}\n`);
  }
  process.stdout.write(`[selftest-all] ${failed.length === 0 ? "ALL GREEN" : `${failed.length} FAILED`}\n`);
}
process.exit(failed.length === 0 ? 0 : 1);
