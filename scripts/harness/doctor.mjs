#!/usr/bin/env node
/**
 * harness doctor — environment-agnostic onboarding + preflight.
 *
 * One command that meets you wherever you work (any terminal — not just VS Code) and tells you:
 *   - whether the runtime is sufficient (Node, git),
 *   - what the harness can see (config, loops, domain packs, MCP deps),
 *   - which agent CLIs and optional tooling are installed,
 *   - whether the self-tests pass,
 *   - and exactly how to register the MCP server in YOUR editor/agent.
 *
 * Usage:
 *   node scripts/harness/doctor.mjs                 # full report
 *   node scripts/harness/doctor.mjs --quick         # skip the self-tests (faster)
 *   node scripts/harness/doctor.mjs --json          # machine-readable
 *   node scripts/harness/doctor.mjs --mcp <client>  # print MCP config for a client (see list below)
 *   node scripts/harness/doctor.mjs --write-mcp <client>   # write the project-local MCP config file
 *
 * MCP clients: claude-code | cursor | vscode | windsurf | cline | claude-desktop | zed | generic
 *
 * Zero dependencies; never executes a detected CLI (it scans PATH), so it is safe to run anywhere.
 * Exit code: 0 if no blocking problem, 1 if a blocker (e.g. Node too old) is found.
 */
import { spawnSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, readdirSync, statSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..");
const require = createRequire(import.meta.url);

const C = process.stdout.isTTY
  ? { ok: "\x1b[32m", warn: "\x1b[33m", bad: "\x1b[31m", dim: "\x1b[2m", b: "\x1b[1m", x: "\x1b[0m" }
  : { ok: "", warn: "", bad: "", dim: "", b: "", x: "" };
const mark = { ok: "✓", warn: "!", bad: "✗" };

function parseArgs(argv) {
  const out = { _: [] };
  for (let i = 0; i < argv.length; i += 1) {
    const a = argv[i];
    if (!a.startsWith("--")) { out._.push(a); continue; }
    const key = a.slice(2);
    const next = argv[i + 1];
    if (next === undefined || next.startsWith("--")) out[key] = true;
    else { out[key] = next; i += 1; }
  }
  return out;
}

function onPath(bin) {
  const exts = process.platform === "win32" ? [".exe", ".cmd", ".bat", ""] : [""];
  const sep = process.platform === "win32" ? ";" : ":";
  for (const dir of (process.env.PATH || "").split(sep)) {
    if (!dir) continue;
    for (const ext of exts) {
      // Must be a regular file, not a same-named directory, to count as an installed CLI.
      try {
        const p = join(dir, bin + ext);
        if (existsSync(p) && statSync(p).isFile()) return true;
      } catch { /* ignore */ }
    }
  }
  return false;
}

function readJson(path) {
  try { return JSON.parse(readFileSync(path, "utf8")); } catch { return null; }
}

function countJsonFiles(dir, filter = () => true) {
  if (!existsSync(dir)) return 0;
  return readdirSync(dir).filter((f) => f.endsWith(".json") && !f.startsWith("_") && filter(f)).length;
}

function countPacks() {
  const dir = join(repoRoot, ".github", "harness", "domains");
  if (!existsSync(dir)) return 0;
  return readdirSync(dir).filter((n) => !n.startsWith("_") && existsSync(join(dir, n, "pack.json"))).length;
}

const MCP_CLIENTS = ["claude-code", "cursor", "vscode", "zed", "windsurf", "cline", "claude-desktop", "generic"];

function isKnownClient(client) {
  return typeof client === "string" && MCP_CLIENTS.includes(client);
}

function assertClient(client, flag) {
  if (client === true || typeof client !== "string") {
    process.stderr.write(`[doctor] ${flag} needs a client: ${MCP_CLIENTS.join(" | ")}\n`);
    process.exit(2);
  }
  if (!isKnownClient(client)) {
    process.stderr.write(`[doctor] unknown client "${client}". Valid: ${MCP_CLIENTS.join(" | ")}\n`);
    process.exit(2);
  }
}

function mcpEntry(client) {
  const abs = join(repoRoot, "scripts", "harness", "mcp-server.mjs");
  if (client === "vscode") {
    return { file: ".vscode/mcp.json", key: "servers", scope: "project",
      entry: { harness: { type: "stdio", command: "node", args: ["scripts/harness/mcp-server.mjs"], cwd: "${workspaceFolder}" } } };
  }
  if (client === "claude-code") {
    return { file: ".mcp.json", key: "mcpServers", scope: "project",
      entry: { harness: { command: "node", args: ["scripts/harness/mcp-server.mjs"] } } };
  }
  if (client === "cursor") {
    return { file: ".cursor/mcp.json", key: "mcpServers", scope: "project",
      entry: { harness: { command: "node", args: ["scripts/harness/mcp-server.mjs"] } } };
  }
  if (client === "zed") {
    return { file: ".zed/settings.json", key: "context_servers", scope: "project",
      entry: { harness: { command: { path: "node", args: ["scripts/harness/mcp-server.mjs"] } } } };
  }
  // Global-config clients: cwd must be absolute because the config lives outside the repo.
  const global = {
    "claude-desktop": "claude_desktop_config.json (Claude Desktop → Settings → Developer)",
    windsurf: "~/.codeium/windsurf/mcp_config.json",
    cline: "the Cline MCP settings (VS Code: Cline panel → MCP Servers → Configure)",
    generic: "your client's MCP config",
  };
  return { file: global[client] || global.generic, key: "mcpServers", scope: "global",
    entry: { harness: { command: "node", args: [abs] } } };
}

function renderMcp(client) {
  const m = mcpEntry(client);
  const config = m.key === "context_servers"
    ? { context_servers: m.entry }
    : { [m.key]: m.entry };
  return { ...m, json: JSON.stringify(config, null, 2) };
}

function writeMcp(client) {
  const m = renderMcp(client);
  if (m.scope !== "project") {
    process.stderr.write(`[doctor] ${client} uses a global config (${m.file}); printing it instead of writing:\n\n${m.json}\n`);
    process.exit(0);
  }
  const target = join(repoRoot, m.file);
  mkdirSync(dirname(target), { recursive: true });
  // Merge into an existing file rather than clobbering it.
  let existing = readJson(target) || {};
  const key = m.key;
  existing[key] = { ...(existing[key] || {}), ...m.entry };
  writeFileSync(target, `${JSON.stringify(existing, null, 2)}\n`);
  process.stdout.write(`[doctor] wrote ${m.file} (merged "harness" into "${key}").\n`);
  process.stdout.write(`[doctor] restart ${client} (or reload its MCP servers) to pick it up.\n`);
}

const SELF_TESTS = [
  { name: "domain packs", cmd: ["scripts/harness/domain-pack.mjs", "--self-test"] },
  { name: "eval suite", cmd: ["scripts/harness/eval/run-eval.mjs", "--self-test"] },
  { name: "git-guard", cmd: ["scripts/harness/git-guard.mjs", "--self-test"] },
  { name: "trace grader", cmd: ["scripts/harness/grade-trace.mjs", "--self-test"] },
  { name: "otel export", cmd: ["scripts/harness/otel-export.mjs", "--self-test"] },
  { name: "plan-review", cmd: ["scripts/harness/plan-review.mjs", "--self-test"] },
  { name: "command-validation", cmd: ["scripts/harness/command-validation.mjs", "--self-test"] },
];

function runSelfTests() {
  return SELF_TESTS.map((t) => {
    if (!existsSync(join(repoRoot, t.cmd[0]))) return { name: t.name, status: "skip", detail: "script not present" };
    const r = spawnSync("node", t.cmd, { cwd: repoRoot, encoding: "utf8", timeout: 60000, stdio: ["ignore", "pipe", "pipe"] });
    return { name: t.name, status: r.status === 0 ? "pass" : "fail", code: r.status };
  });
}

function gather({ quick }) {
  const nodeMajor = Number(process.versions.node.split(".")[0]);
  const config = readJson(join(repoRoot, "harness.config.json"));
  let mcpSdk = false;
  // Resolve the exact subpath mcp-server.mjs imports — not package.json, which a package's "exports"
  // map may not expose (that would give a false negative even when the SDK is installed).
  try { require.resolve("@modelcontextprotocol/sdk/server/index.js"); mcpSdk = true; } catch { mcpSdk = false; }
  const isGit = existsSync(join(repoRoot, ".git"));

  const agents = [
    { id: "claude", label: "Claude Code (claude)", mcp: "claude-code" },
    { id: "cursor-agent", label: "Cursor CLI (cursor-agent)", mcp: "cursor" },
    { id: "codex", label: "OpenAI Codex CLI (codex)", mcp: "generic" },
    { id: "gemini", label: "Gemini CLI (gemini)", mcp: "generic" },
    { id: "gh", label: "GitHub CLI (gh / Copilot)", mcp: "vscode" },
  ].map((a) => ({ ...a, present: onPath(a.id) }));

  const tooling = [
    { id: "docker", label: "Docker (dashboard / graph sidecars)" },
    { id: "ollama", label: "Ollama (local-LLM loops)" },
  ].map((t) => ({ ...t, present: onPath(t.id) }));

  return {
    node: { version: process.versions.node, ok: nodeMajor >= 20 },
    platform: `${process.platform}/${process.arch}`,
    git: isGit,
    config: { present: config !== null, valid: config !== null, name: config?.project?.name ?? null },
    loops: countJsonFiles(join(repoRoot, ".github", "harness", "loops")),
    packs: countPacks(),
    mcpSdk,
    agents,
    tooling,
    selfTests: quick ? null : runSelfTests(),
  };
}

function line(status, text, detail) {
  const color = status === "ok" ? C.ok : status === "warn" ? C.warn : C.bad;
  process.stdout.write(`  ${color}${mark[status]}${C.x} ${text}${detail ? ` ${C.dim}${detail}${C.x}` : ""}\n`);
}

function report(data) {
  const nextSteps = [];
  process.stdout.write(`\n${C.b}Harness doctor${C.x} ${C.dim}(${repoRoot})${C.x}\n\n`);

  process.stdout.write(`${C.b}Runtime${C.x}\n`);
  line(data.node.ok ? "ok" : "bad", `Node ${data.node.version}`, data.node.ok ? "(>= 20)" : "— needs >= 20; upgrade Node");
  if (!data.node.ok) nextSteps.push("Upgrade Node.js to v20 or newer — the loops use built-in fetch.");
  line("ok", `Platform ${data.platform}`);
  line(data.git ? "ok" : "warn", data.git ? "Inside a git repository" : "Not a git repository", data.git ? "" : "— loops record a baseline from git; some safety nets are git-aware");

  process.stdout.write(`\n${C.b}Harness${C.x}\n`);
  if (data.config.present) line("ok", "harness.config.json present", data.config.name ? `project: ${data.config.name}` : "");
  else { line("warn", "harness.config.json not found", "— copy/edit it to point loops at your commands"); nextSteps.push("Create harness.config.json (see SETUP.md §2) so loops resolve your project's commands."); }
  line(data.loops > 0 ? "ok" : "warn", `${data.loops} loop(s) available`, "node scripts/harness/run-loop.mjs --list");
  line(data.packs > 0 ? "ok" : "warn", `${data.packs} domain pack(s) available`, "npm run harness:domains");
  line(data.mcpSdk ? "ok" : "warn", data.mcpSdk ? "MCP SDK installed" : "MCP SDK not installed",
    data.mcpSdk ? "" : "— run `npm install` to enable the MCP stdio server (optionalDependency)");
  if (!data.mcpSdk) nextSteps.push("Run `npm install` to fetch @modelcontextprotocol/sdk if you want the MCP server.");

  process.stdout.write(`\n${C.b}Agent CLIs detected${C.x} ${C.dim}(any one is enough)${C.x}\n`);
  const anyAgent = data.agents.some((a) => a.present);
  for (const a of data.agents) line(a.present ? "ok" : "warn", a.label, a.present ? "" : "not on PATH");
  if (!anyAgent) nextSteps.push("Install at least one agent CLI (e.g. Claude Code) — or run loops with --check-only / --agent \"<cmd>\".");

  process.stdout.write(`\n${C.b}Optional tooling${C.x}\n`);
  for (const t of data.tooling) line(t.present ? "ok" : "warn", t.label, t.present ? "" : "not on PATH (optional)");

  if (data.selfTests) {
    process.stdout.write(`\n${C.b}Self-tests${C.x}\n`);
    for (const t of data.selfTests) {
      if (t.status === "skip") line("warn", `${t.name}`, "skipped — script not present");
      else line(t.status === "pass" ? "ok" : "bad", `${t.name} self-test`, t.status === "pass" ? "" : `exit ${t.code}`);
    }
    if (data.selfTests.some((t) => t.status === "fail")) nextSteps.push("A self-test failed — inspect it directly (e.g. `node scripts/harness/eval/run-eval.mjs --self-test`).");
  }

  // MCP registration: show the actual config for the detected client, plus how to get the others.
  const suggested = data.agents.find((a) => a.present)?.mcp || "claude-code";
  const m = renderMcp(suggested);
  process.stdout.write(`\n${C.b}Connect the MCP server (read-only graph/memory/metrics tools)${C.x}\n`);
  process.stdout.write(`  For ${C.b}${suggested}${C.x} — ${m.scope} config in ${C.dim}${m.file}${C.x} (key "${m.key}"):\n`);
  process.stdout.write(`${m.json.split("\n").map((l) => `      ${l}`).join("\n")}\n`);
  process.stdout.write(`  Another client: ${C.dim}node scripts/harness/doctor.mjs --mcp <${MCP_CLIENTS.join("|")}>${C.x}\n`);
  if (m.scope === "project") {
    process.stdout.write(`  Write it for you: ${C.dim}node scripts/harness/doctor.mjs --write-mcp ${suggested}${C.x}\n`);
  }

  if (nextSteps.length) {
    process.stdout.write(`\n${C.b}Next steps${C.x}\n`);
    nextSteps.forEach((s, i) => process.stdout.write(`  ${i + 1}. ${s}\n`));
  } else {
    process.stdout.write(`\n${C.ok}You're set.${C.x} Try: ${C.dim}node scripts/harness/run-loop.mjs --list${C.x} or ${C.dim}npm run harness:domains${C.x}\n`);
  }
  process.stdout.write(`\nFull guide per environment: docs/ENVIRONMENTS.md\n\n`);

  const blocker = !data.node.ok;
  return blocker ? 1 : 0;
}

// Validate the doctor's own pure logic — MCP config generation and client validation — so a
// regression there is caught like every other harness component.
function selfTest() {
  const checks = [];
  const add = (name, ok, detail) => checks.push({ name, ok, detail });

  add("rejects unknown client", isKnownClient("nope") === false);
  add("rejects boolean client", isKnownClient(true) === false);

  for (const client of MCP_CLIENTS) {
    let m;
    try { m = renderMcp(client); } catch (e) { add(`${client}: renders`, false, e.message); continue; }
    let parsed;
    try { parsed = JSON.parse(m.json); } catch (e) { add(`${client}: valid JSON`, false, e.message); continue; }
    add(`${client}: valid JSON`, true);
    const root = m.key === "context_servers" ? parsed.context_servers : parsed[m.key];
    const harness = root?.harness;
    add(`${client}: harness entry under "${m.key}"`, Boolean(harness), `expected key ${m.key}`);
    const argv = harness?.args || harness?.command?.args || [];
    const pathArg = argv[argv.length - 1];
    const isAbs = typeof pathArg === "string" && (pathArg.startsWith("/") || /^[A-Za-z]:[\\/]/.test(pathArg));
    if (m.scope === "project") add(`${client}: relative server path`, pathArg === "scripts/harness/mcp-server.mjs", `got ${pathArg}`);
    else add(`${client}: absolute server path`, isAbs, `got ${pathArg}`);
  }

  const passed = checks.every((c) => c.ok);
  process.stdout.write(`[doctor] self-test — ${checks.length} check(s)\n`);
  for (const c of checks) process.stdout.write(`  ${c.ok ? "PASS" : "FAIL"}  ${c.name}${c.ok ? "" : ` — ${c.detail}`}\n`);
  process.stdout.write(`[doctor] ${passed ? "self-test PASSED" : "self-test FAILED"}\n`);
  process.exit(passed ? 0 : 1);
}

const args = parseArgs(process.argv.slice(2));
if (args["self-test"]) selfTest();
if ("write-mcp" in args) { assertClient(args["write-mcp"], "--write-mcp"); writeMcp(args["write-mcp"]); process.exit(0); }
if ("mcp" in args) {
  assertClient(args.mcp, "--mcp");
  const m = renderMcp(args.mcp);
  process.stdout.write(`# ${args.mcp} — ${m.scope} config: ${m.file}\n# key: "${m.key}"\n\n${m.json}\n`);
  process.exit(0);
}
const data = gather({ quick: Boolean(args.quick) });
if (args.json) { process.stdout.write(`${JSON.stringify(data, null, 2)}\n`); process.exit(data.node.ok ? 0 : 1); }
process.exit(report(data));
