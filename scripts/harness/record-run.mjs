#!/usr/bin/env node
/**
 * Harness workflow-run recorder — persists a journal for a WORKFLOW-kind loop or stage so
 * agent-graded runs (Understand, Architect, Review-Breadth/Depth, Feedback, review-fix,
 * feature-cycle, ci-green) become visible on the metrics dashboard.
 *
 * Convergence loops (build-fix, test-fix) are recorded automatically by run-loop.mjs; this
 * recorder is ONLY for judgment-graded runs that the script runner refuses to execute.
 *
 * Usage (primary — pipe a JSON spec on stdin):
 *   echo '{ "loop": "review-fix", "terminalState": "converged",
 *           "rubric": [ { "item": "Zero Blocker findings remain", "pass": true } ] }' \
 *     | node scripts/harness/record-run.mjs
 *
 * Usage (quick — flags, rubric items repeatable):
 *   node scripts/harness/record-run.mjs --loop architect --state converged \
 *     --pass "Gates 1-5 evaluated" --pass "Architecture Brief written" --fail "Do-NOTs listed"
 *
 * The recorder fills in startedAt/finishedAt, the git baseline, the per-iteration timestamps,
 * the failedItems list, and kind="workflow" automatically.
 *
 * Exit codes: 0 written, 2 usage/validation error.
 */
import { execSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..");
const loopsDir = join(repoRoot, ".github", "harness", "loops");
const runsDir = join(repoRoot, ".github", "harness", "runs");
const TERMINAL_STATES = ["converged", "exhausted", "stuck", "blocked"];
const APPROVAL_STATUSES = new Set([
  "pending",
  "approved",
  "rejected",
  "not-required",
]);

function fail(message) {
  console.error(`[record-run] ${message}`);
  process.exit(2);
}

function printHelp() {
  console.log(
    [
      "Record a workflow (judgment-graded) loop or stage run for the metrics dashboard.",
      "",
      "Pipe a JSON spec on stdin, or use flags:",
      "  --loop <name>     loop or stage name (e.g. review-fix, feature-cycle, architect)",
      "  --state <state>   terminal state: converged | exhausted | stuck | blocked",
      "  --approval-status <status>  pending | approved | rejected | not-required",
      "  --approval-required         mark this run as requiring approval",
      '  --approval-note "<text>"    approval context note',
      '  --pass "<item>"   a rubric criterion that passed (repeatable)',
      '  --fail "<item>"   a rubric criterion that failed (repeatable)',
      "  --help            show this help",
      "",
      "stdin spec shape:",
      '  { "loop": "review-fix", "terminalState": "converged",',
      '    "startedAt": "<ISO optional>",',
      '    "iterations": [ { "rubric": [ { "item": "...", "pass": true } ] } ] }',
      '  (or a top-level "rubric" array for a single-iteration run)',
    ].join("\n"),
  );
}

function parseArgs(argv) {
  const args = {
    loop: undefined,
    state: undefined,
    approvalStatus: undefined,
    approvalRequired: false,
    approvalNote: undefined,
    pass: [],
    fail: [],
    help: false,
  };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--help" || a === "-h") args.help = true;
    else if (a === "--loop") args.loop = argv[++i];
    else if (a === "--state") args.state = argv[++i];
    else if (a === "--approval-status") args.approvalStatus = argv[++i];
    else if (a === "--approval-required") args.approvalRequired = true;
    else if (a === "--approval-note") args.approvalNote = argv[++i];
    else if (a === "--pass") args.pass.push(argv[++i]);
    else if (a === "--fail") args.fail.push(argv[++i]);
    else fail(`Unknown option: ${a}`);
  }
  return args;
}

function resolveApprovalStatus(rawApproval, args) {
  const statusCandidate =
    typeof args.approvalStatus === "string"
      ? args.approvalStatus
      : rawApproval.status;
  if (APPROVAL_STATUSES.has(statusCandidate)) return statusCandidate;
  if (args.approvalRequired) return "pending";
  return "not-required";
}

function resolveApprovalRequired(rawApproval, args, status) {
  const requiredCandidate =
    typeof rawApproval.required === "boolean"
      ? rawApproval.required
      : Boolean(args.approvalRequired);
  if (status === "not-required") return false;
  if (status === "pending") return true;
  return requiredCandidate;
}

function resolveApprovalNote(rawApproval, args) {
  if (typeof args.approvalNote === "string" && args.approvalNote.trim()) {
    return args.approvalNote.trim();
  }
  if (typeof rawApproval.note === "string" && rawApproval.note.trim()) {
    return rawApproval.note.trim();
  }
  return undefined;
}

function resolveApprovalTimestamp(rawApproval, field, nowIso) {
  if (typeof rawApproval[field] === "string") return rawApproval[field];
  return nowIso;
}

function normalizeApproval(rawApproval, args, nowIso) {
  const raw = rawApproval && typeof rawApproval === "object" ? rawApproval : {};
  const status = resolveApprovalStatus(raw, args);
  const required = resolveApprovalRequired(raw, args, status);
  const noteCandidate = resolveApprovalNote(raw, args);

  if (!required && status !== "not-required") {
    fail(
      `approval status ${JSON.stringify(status)} requires --approval-required or approval.required=true`,
    );
  }

  const requestedAt =
    status === "pending"
      ? resolveApprovalTimestamp(raw, "requestedAt", nowIso)
      : undefined;
  const decidedAt =
    status === "approved" || status === "rejected"
      ? resolveApprovalTimestamp(raw, "decidedAt", nowIso)
      : undefined;

  return {
    required,
    status,
    ...(noteCandidate ? { note: noteCandidate } : {}),
    ...(requestedAt ? { requestedAt } : {}),
    ...(decidedAt ? { decidedAt } : {}),
  };
}

function readStdin() {
  if (process.stdin.isTTY) return null;
  try {
    const text = readFileSync(0, "utf8");
    return text?.trim() ? text : null;
  } catch {
    return null;
  }
}

function gitBaseline() {
  const baseline = { commit: null, dirty: null };
  try {
    baseline.commit = execSync("git rev-parse HEAD", {
      cwd: repoRoot,
      encoding: "utf8",
    }).trim();
    baseline.dirty =
      execSync("git status --porcelain", {
        cwd: repoRoot,
        encoding: "utf8",
      }).trim() !== "";
  } catch {
    // not a git repo or git unavailable — baseline stays null
  }
  return baseline;
}

function loadLoopDef(name) {
  const path = join(loopsDir, `${name}.json`);
  if (!existsSync(path)) return null;
  try {
    return JSON.parse(readFileSync(path, "utf8"));
  } catch (err) {
    fail(`loop definition ${name}.json is not valid JSON: ${err.message}`);
  }
}

function normalizeRubricItem(raw, where) {
  if (!raw || typeof raw !== "object")
    fail(`${where}: each rubric entry must be an object`);
  if (typeof raw.item !== "string" || raw.item.trim() === "")
    fail(`${where}: rubric "item" must be a non-empty string`);
  if (typeof raw.pass !== "boolean")
    fail(`${where}: rubric "${raw.item}" needs a boolean "pass"`);
  return { item: raw.item.trim(), pass: raw.pass };
}

function buildSpec(stdinText, args) {
  let spec = {};
  if (stdinText) {
    try {
      spec = JSON.parse(stdinText);
    } catch (err) {
      fail(`stdin is not valid JSON: ${err.message}`);
    }
    if (!spec || typeof spec !== "object") fail("stdin JSON must be an object");
  }

  // Flag overrides / convenience construction.
  if (args.loop) spec.loop = args.loop;
  if (args.state) spec.terminalState = args.state;
  if (args.pass.length || args.fail.length) {
    const flagRubric = [
      ...args.pass.map((item) => ({ item, pass: true })),
      ...args.fail.map((item) => ({ item, pass: false })),
    ];
    spec.rubric = [
      ...(Array.isArray(spec.rubric) ? spec.rubric : []),
      ...flagRubric,
    ];
  }
  return spec;
}

const args = parseArgs(process.argv.slice(2));
if (args.help) {
  printHelp();
  process.exit(0);
}

const spec = buildSpec(readStdin(), args);

if (typeof spec.loop !== "string" || spec.loop.trim() === "") {
  fail('a loop/stage name is required (stdin "loop" or --loop)');
}
const loopName = spec.loop.trim();
// Constrain the name: it flows into both the loop-definition read path and the journal write
// path, so reject anything that could escape .github/harness/ (path traversal / file inclusion).
if (!/^[A-Za-z0-9._-]+$/.test(loopName)) {
  fail(
    `invalid loop/stage name ${JSON.stringify(loopName)} — use letters, digits, dot, dash, underscore only.`,
  );
}
if (!TERMINAL_STATES.includes(spec.terminalState)) {
  fail(
    `terminalState must be one of: ${TERMINAL_STATES.join(", ")} (got ${JSON.stringify(spec.terminalState)})`,
  );
}

// If this name maps to a defined loop, it must be a workflow loop — convergence loops are
// recorded by run-loop.mjs. Unknown names are allowed (ad-hoc stage runs like "architect").
const loopDef = loadLoopDef(loopName);
if (loopDef?.kind === "convergence") {
  fail(
    `"${loopName}" is a convergence loop — record it via run-loop.mjs, not this recorder.`,
  );
}

// Normalize iterations: explicit iterations[] win; else a single iteration from top-level rubric.
let rawIterations;
if (Array.isArray(spec.iterations) && spec.iterations.length > 0) {
  rawIterations = spec.iterations;
} else if (Array.isArray(spec.rubric) && spec.rubric.length > 0) {
  rawIterations = [{ rubric: spec.rubric }];
} else {
  fail(
    'no rubric verdicts provided — supply "iterations" with rubric arrays, a top-level "rubric", or --pass/--fail',
  );
}

const nowIso = new Date().toISOString();
const approval = normalizeApproval(spec.approval, args, nowIso);
const iterations = rawIterations.map((iteration, index) => {
  const rubricRaw = Array.isArray(iteration.rubric) ? iteration.rubric : [];
  if (rubricRaw.length === 0)
    fail(`iteration ${index + 1} has no rubric verdicts`);
  const rubric = rubricRaw.map((entry) =>
    normalizeRubricItem(entry, `iteration ${index + 1}`),
  );
  return {
    iteration: index + 1,
    at: typeof iteration.at === "string" ? iteration.at : nowIso,
    rubric,
    failedItems: rubric.filter((r) => !r.pass).map((r) => r.item),
  };
});

// Soft-check graded criteria against the loop's declared rubric (nudge, don't block).
if (loopDef && Array.isArray(loopDef.rubric) && loopDef.rubric.length > 0) {
  const declared = new Set(loopDef.rubric.map((r) => String(r).trim()));
  const gradedItems = new Set(
    iterations.flatMap((it) => it.rubric.map((r) => r.item)),
  );
  for (const item of gradedItems) {
    if (!declared.has(item))
      console.warn(
        `[record-run] note: graded criterion not in ${loopName}.rubric: "${item}"`,
      );
  }
  for (const item of declared) {
    if (!gradedItems.has(item))
      console.warn(
        `[record-run] note: declared criterion not graded this run: "${item}"`,
      );
  }
}

// Consistency nudge: a "converged" run should have no failed items on its final iteration.
const finalFailed = iterations.at(-1).failedItems.length > 0;
if (spec.terminalState === "converged" && finalFailed) {
  console.warn(
    '[record-run] note: terminalState is "converged" but the final iteration still has failing rubric items.',
  );
}

const startedAt =
  typeof spec.startedAt === "string"
    ? spec.startedAt
    : (iterations[0]?.at ?? nowIso);
const record = {
  loop: loopName,
  kind: "workflow",
  startedAt,
  finishedAt: nowIso,
  baseline: gitBaseline(),
  approval,
  terminalState: spec.terminalState,
  iterations,
};

const outFile = join(
  runsDir,
  `${loopName}-${nowIso.replace(/[:.]/g, "-")}.json`,
);
try {
  mkdirSync(runsDir, { recursive: true });
  writeFileSync(outFile, JSON.stringify(record, null, 2));
} catch (err) {
  fail(`could not write run journal: ${err.message}`);
}

const passed = iterations.at(-1).rubric.filter((r) => r.pass).length;
const total = iterations.at(-1).rubric.length;
console.log(
  `[record-run] recorded ${loopName} (${record.terminalState}) — ${passed}/${total} rubric items passed on the final iteration.`,
);
console.log(`[record-run] journal: ${outFile}`);
