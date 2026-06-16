#!/usr/bin/env node
/**
 * Harness metrics report — aggregates loop run journals from .github/harness/runs/
 * into a self-contained HTML dashboard and a terminal summary.
 *
 * Journals are produced by run-loop.mjs (one JSON file per run). This script never
 * runs a loop or invokes an agent; it only reads what previous runs recorded.
 *
 * Usage:
 *   node scripts/harness/harness-report.mjs            # write report.html + print summary
 *   node scripts/harness/harness-report.mjs --json     # print aggregated metrics as JSON
 *   node scripts/harness/harness-report.mjs --no-html  # summary only, no file written
 *   node scripts/harness/harness-report.mjs --out <path>
 *
 * Output (default): .github/harness/runs/report.html (gitignored, like the journals).
 * Exit codes: 0 ok, 2 usage/IO error.
 */
import {
  existsSync,
  mkdirSync,
  readFileSync,
  readdirSync,
  statSync,
  writeFileSync,
} from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..");
const runsDir = join(repoRoot, ".github", "harness", "runs");
const lessonsDir = join(repoRoot, ".github", "harness", "memory", "lessons");
const briefsDir = join(repoRoot, ".github", "harness", "memory", "briefs");
const graphPath = join(
  repoRoot,
  ".understand-anything",
  "knowledge-graph.json",
);
const configPath = join(repoRoot, "harness.config.json");
const NON_LESSON_FILES = new Set(["_template.md", "readme.md"]);
const BRIEF_STATUSES = ["active", "implemented", "superseded"];
const TERMINAL_STATES = [
  "converged",
  "exhausted",
  "stuck",
  "blocked",
  "incomplete",
];
const APPROVAL_STATUSES = new Set([
  "pending",
  "approved",
  "rejected",
  "not-required",
]);

function fail(message) {
  console.error(`[harness-report] ${message}`);
  process.exit(2);
}

function parseArgs(argv) {
  const args = { json: false, html: true, out: undefined };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--json") args.json = true;
    else if (a === "--no-html") args.html = false;
    else if (a === "--out") args.out = argv[++i];
    else fail(`Unknown option: ${a}`);
  }
  return args;
}

function loadJournals() {
  if (!existsSync(runsDir)) return [];
  const journals = [];
  for (const file of readdirSync(runsDir)) {
    if (!file.endsWith(".json")) continue;
    const path = join(runsDir, file);
    try {
      const journal = JSON.parse(readFileSync(path, "utf8"));
      if (
        journal &&
        typeof journal.loop === "string" &&
        Array.isArray(journal.iterations)
      ) {
        journals.push({ ...journal, file });
      } else {
        console.warn(
          `[harness-report] skipping ${file}: not a recognizable run journal`,
        );
      }
    } catch (err) {
      console.warn(`[harness-report] skipping ${file}: ${err.message}`);
    }
  }
  return journals;
}

function stateOf(journal) {
  return TERMINAL_STATES.includes(journal.terminalState)
    ? journal.terminalState
    : "incomplete";
}

function firstLine(text) {
  for (const line of text.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (trimmed) return trimmed;
  }
  return "";
}

function stripHeading(summary) {
  return summary.replace(/^#+\s*/, "");
}

function listMarkdown(dir, exclude) {
  if (!existsSync(dir)) return [];
  return readdirSync(dir).filter(
    (n) => n.endsWith(".md") && !exclude.has(n.toLowerCase()),
  );
}

function loadLessons() {
  const files = listMarkdown(lessonsDir, NON_LESSON_FILES);
  const recent = files
    .map((name) => {
      const path = join(lessonsDir, name);
      let mtimeMs = null;
      let summary = "";
      try {
        mtimeMs = statSync(path).mtimeMs;
        summary = stripHeading(firstLine(readFileSync(path, "utf8")));
      } catch {
        // unreadable lesson — skip its detail, still counted
      }
      return {
        name,
        summary,
        updated: mtimeMs ? new Date(mtimeMs).toISOString() : null,
        mtimeMs: mtimeMs ?? 0,
      };
    })
    .sort((a, b) => b.mtimeMs - a.mtimeMs);
  return { count: files.length, recent };
}

function loadBriefs() {
  const files = listMarkdown(briefsDir, new Set(["readme.md"]));
  const briefs = files.map((name) => {
    let status = "unknown";
    let title = name.replace(/\.md$/, "");
    try {
      const head = firstLine(readFileSync(join(briefsDir, name), "utf8"));
      const matched = BRIEF_STATUSES.find((s) =>
        new RegExp(String.raw`[—-]\s*${s}\s*$`, "i").test(head),
      );
      if (matched) status = matched;
      const stripped = stripHeading(head)
        .replace(/^Brief:\s*/i, "")
        .replace(/\s*[—-]\s*(active|implemented|superseded)\s*$/i, "")
        .trim();
      if (stripped) title = stripped;
    } catch {
      // unreadable brief — keep filename as title
    }
    return { name, title, status };
  });
  const byStatus = briefs.reduce(
    (acc, b) => ({ ...acc, [b.status]: (acc[b.status] ?? 0) + 1 }),
    {},
  );
  return { count: briefs.length, briefs, byStatus };
}

function loadGraph() {
  if (!existsSync(graphPath))
    return { present: false, ageDays: null, sizeKb: null };
  try {
    const st = statSync(graphPath);
    return {
      present: true,
      ageDays: Math.floor((Date.now() - st.mtimeMs) / 86_400_000),
      sizeKb: Math.round(st.size / 1024),
    };
  } catch {
    return { present: false, ageDays: null, sizeKb: null };
  }
}

function loadMemory() {
  return { lessons: loadLessons(), briefs: loadBriefs(), graph: loadGraph() };
}

function loadHarnessConfig() {
  if (!existsSync(configPath)) return {};
  try {
    const parsed = JSON.parse(readFileSync(configPath, "utf8"));
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

function pickString(value, fallback) {
  return typeof value === "string" && value.trim() ? value : fallback;
}

function objectOrEmpty(value) {
  return value && typeof value === "object" ? value : {};
}

function integrationScriptStatus(path, absolutePath) {
  return { path, present: existsSync(absolutePath) };
}

function loadPipelineIntegration(config) {
  const llm = objectOrEmpty(config.llm);
  const models = objectOrEmpty(config.models);
  const routing = objectOrEmpty(config.routing);

  const provider = pickString(llm.provider, "ollama");
  const model = pickString(llm.model, "qwen2.5-coder:14b");
  const embedModel = pickString(llm.embedModel, "nomic-embed-text");
  const providerConfig = objectOrEmpty(llm[provider]);
  const hostByProvider = pickString(providerConfig.host, null);

  const integrationScripts = [
    integrationScriptStatus(
      "scripts/harness/llm-provider.mjs",
      join(repoRoot, "scripts", "harness", "llm-provider.mjs"),
    ),
    integrationScriptStatus(
      "scripts/harness/ollama-agent.mjs",
      join(repoRoot, "scripts", "harness", "ollama-agent.mjs"),
    ),
    integrationScriptStatus(
      "scripts/harness/ollama-apply-agent.mjs",
      join(repoRoot, "scripts", "harness", "ollama-apply-agent.mjs"),
    ),
    integrationScriptStatus(
      "scripts/harness/experiment-loop.mjs",
      join(repoRoot, "scripts", "harness", "experiment-loop.mjs"),
    ),
  ];

  return {
    provider,
    model,
    embedModel,
    host: hostByProvider,
    implementerModel:
      models.implementer && typeof models.implementer.model === "string"
        ? models.implementer.model
        : "gpt-5.3-codex",
    reviewerModel:
      models.reviewer && typeof models.reviewer.model === "string"
        ? models.reviewer.model
        : "claude-opus-4.8",
    routingProfiles:
      routing.profiles && typeof routing.profiles === "object"
        ? Object.keys(routing.profiles)
        : [],
    integrationScripts,
  };
}

function pendingApprovalSnapshot(recentRuns) {
  const pendingRuns = (recentRuns ?? []).filter(
    (run) => run.approval?.required && run.approval?.status === "pending",
  );
  return {
    count: pendingRuns.length,
    pendingRuns,
  };
}

function approvalOf(journal) {
  const approval = journal?.approval;
  if (!approval || typeof approval !== "object") {
    return {
      required: false,
      status: "not-required",
      note: null,
      requestedAt: null,
      decidedAt: null,
    };
  }
  const status = APPROVAL_STATUSES.has(approval.status)
    ? approval.status
    : "not-required";
  const required =
    status === "not-required" ? false : Boolean(approval.required);
  return {
    required,
    status,
    note: typeof approval.note === "string" ? approval.note : null,
    requestedAt:
      typeof approval.requestedAt === "string" ? approval.requestedAt : null,
    decidedAt:
      typeof approval.decidedAt === "string" ? approval.decidedAt : null,
  };
}

// Eval journals (kind: 'eval') are a distinct shape from loop journals; load them separately so the
// dashboard can show whether the harness measurably helps (baseline vs harness).
function loadEvalRuns() {
  if (!existsSync(runsDir)) return [];
  const runs = [];
  for (const file of readdirSync(runsDir)) {
    if (!file.startsWith("eval-") || !file.endsWith(".json")) continue;
    try {
      const run = JSON.parse(readFileSync(join(runsDir, file), "utf8"));
      if (run?.kind === "eval" && run.aggregate) runs.push({ ...run, file });
    } catch {
      // skip unreadable eval journal
    }
  }
  return runs.sort((a, b) =>
    String(b.startedAt ?? "").localeCompare(String(a.startedAt ?? "")),
  );
}

function kindOf(journal) {
  if (
    journal.kind === "convergence" ||
    journal.kind === "workflow" ||
    journal.kind === "experiment"
  ) {
    return journal.kind;
  }
  // Infer for legacy journals written before kind was recorded.
  if (
    journal.metric ||
    journal.iterations.some((it) => typeof it.metric === "number")
  )
    return "experiment";
  return journal.iterations.some((it) => Array.isArray(it.rubric))
    ? "workflow"
    : "convergence";
}

function durationMs(journal) {
  if (!journal.startedAt || !journal.finishedAt) return null;
  const ms = Date.parse(journal.finishedAt) - Date.parse(journal.startedAt);
  return Number.isFinite(ms) && ms >= 0 ? ms : null;
}

function emptyStateBucket() {
  return TERMINAL_STATES.reduce((acc, s) => ({ ...acc, [s]: 0 }), {});
}

function tallyLoop(perLoop, journal, state, kind, iterationCount) {
  if (!perLoop.has(journal.loop)) {
    perLoop.set(journal.loop, {
      loop: journal.loop,
      kind,
      runs: 0,
      byState: emptyStateBucket(),
      convergedIterations: [],
      lastStartedAt: null,
      lastState: null,
    });
  }
  const loopStats = perLoop.get(journal.loop);
  loopStats.kind = kind;
  loopStats.runs += 1;
  loopStats.byState[state] += 1;
  if (state === "converged") loopStats.convergedIterations.push(iterationCount);
  if (
    !loopStats.lastStartedAt ||
    (journal.startedAt && journal.startedAt > loopStats.lastStartedAt)
  ) {
    loopStats.lastStartedAt = journal.startedAt ?? loopStats.lastStartedAt;
    loopStats.lastState = state;
  }
}

function tallyChecks(perCheck, iteration) {
  for (const check of iteration.checks ?? []) {
    if (!check || typeof check.name !== "string") continue;
    if (!perCheck.has(check.name)) {
      perCheck.set(check.name, {
        name: check.name,
        runs: 0,
        passes: 0,
        totalDurationMs: 0,
        maxDurationMs: 0,
      });
    }
    const checkStats = perCheck.get(check.name);
    checkStats.runs += 1;
    if (check.pass) checkStats.passes += 1;
    const dur = Number.isFinite(check.durationMs) ? check.durationMs : 0;
    checkStats.totalDurationMs += dur;
    checkStats.maxDurationMs = Math.max(checkStats.maxDurationMs, dur);
  }
}

function tallyRubric(perRubric, iteration, loopName) {
  for (const entry of iteration.rubric ?? []) {
    if (!entry || typeof entry.item !== "string") continue;
    if (!perRubric.has(entry.item)) {
      perRubric.set(entry.item, {
        item: entry.item,
        loop: loopName,
        graded: 0,
        passes: 0,
      });
    }
    const rubricStats = perRubric.get(entry.item);
    rubricStats.graded += 1;
    if (entry.pass) rubricStats.passes += 1;
  }
}

function computeMetrics(journals) {
  const overall = {
    totalRuns: journals.length,
    byState: emptyStateBucket(),
    totalIterations: 0,
    convergenceRate: 0,
  };
  const perLoop = new Map();
  const perCheck = new Map();
  const perRubric = new Map();
  const experimentRuns = [];

  for (const journal of journals) {
    const state = stateOf(journal);
    const kind = kindOf(journal);
    overall.byState[state] += 1;
    overall.totalIterations += journal.iterations.length;
    tallyLoop(perLoop, journal, state, kind, journal.iterations.length);
    for (const iteration of journal.iterations) {
      tallyChecks(perCheck, iteration);
      tallyRubric(perRubric, iteration, journal.loop);
    }
    if (kind === "experiment" && journal.metric) {
      experimentRuns.push({
        loop: journal.loop,
        metricName: journal.metric.name ?? journal.loop,
        direction: journal.metric.direction ?? "minimize",
        baseline: journal.metric.baseline ?? null,
        best: journal.metric.best ?? journal.metric.baseline ?? null,
        state,
        startedAt: journal.startedAt ?? null,
        iterations: journal.iterations.length,
      });
    }
  }

  overall.convergenceRate = overall.totalRuns
    ? overall.byState.converged / overall.totalRuns
    : 0;

  const loops = [...perLoop.values()]
    .map((l) => ({
      loop: l.loop,
      kind: l.kind,
      runs: l.runs,
      byState: l.byState,
      convergenceRate: l.runs ? l.byState.converged / l.runs : 0,
      avgIterationsToConverge: l.convergedIterations.length
        ? l.convergedIterations.reduce((a, b) => a + b, 0) /
          l.convergedIterations.length
        : null,
      lastStartedAt: l.lastStartedAt,
      lastState: l.lastState,
    }))
    .sort((a, b) => b.runs - a.runs);

  const checks = [...perCheck.values()]
    .map((c) => ({
      name: c.name,
      runs: c.runs,
      passRate: c.runs ? c.passes / c.runs : 0,
      avgDurationMs: c.runs ? Math.round(c.totalDurationMs / c.runs) : 0,
      maxDurationMs: c.maxDurationMs,
    }))
    .sort((a, b) => b.avgDurationMs - a.avgDurationMs);

  // Rubric criteria graded by workflow loops/stages — most-failed first surfaces the weak spots.
  const rubric = [...perRubric.values()]
    .map((r) => ({
      item: r.item,
      loop: r.loop,
      graded: r.graded,
      passRate: r.graded ? r.passes / r.graded : 0,
    }))
    .sort((a, b) => a.passRate - b.passRate);

  const recentRuns = [...journals]
    .sort((a, b) =>
      String(b.startedAt ?? "").localeCompare(String(a.startedAt ?? "")),
    )
    .slice(0, 30)
    .map((j) => ({
      loop: j.loop,
      kind: kindOf(j),
      startedAt: j.startedAt ?? null,
      durationMs: durationMs(j),
      iterations: j.iterations.length,
      state: stateOf(j),
      approval: approvalOf(j),
      baseline: j.baseline?.commit ? j.baseline.commit.slice(0, 12) : null,
      dirty: j.baseline?.dirty ?? null,
    }));

  // Experiment runs (autoresearch-style): latest first, with metric trajectory.
  const experiments = experimentRuns
    .map((e) => {
      let improvedBy = null;
      if (e.baseline !== null && e.best !== null) {
        improvedBy =
          e.direction === "minimize"
            ? e.baseline - e.best
            : e.best - e.baseline;
      }
      return { ...e, improvedBy };
    })
    .sort((a, b) =>
      String(b.startedAt ?? "").localeCompare(String(a.startedAt ?? "")),
    );

  return {
    overall,
    loops,
    checks,
    rubric,
    experiments,
    recentRuns,
    generatedAt: new Date().toISOString(),
  };
}

// ---------- formatting helpers ----------

function fmtDuration(ms) {
  if (ms === null || ms === undefined) return "—";
  if (ms < 1000) return `${ms}ms`;
  const s = ms / 1000;
  if (s < 60) return `${s.toFixed(1)}s`;
  const m = Math.floor(s / 60);
  const rem = Math.round(s % 60);
  return `${m}m ${rem}s`;
}

function fmtPct(rate) {
  return `${Math.round(rate * 100)}%`;
}

function fmtDate(iso) {
  if (!iso) return "—";
  return iso.replace("T", " ").replace(/\..*$/, "").replace("Z", " UTC");
}

function esc(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

// ---------- terminal summary ----------

function printSummary(metrics) {
  const { overall, loops, checks, rubric } = metrics;
  console.log("\n=== Harness Loop Metrics ===");
  if (overall.totalRuns === 0) {
    console.log("No loop run journals found in .github/harness/runs/.");
    console.log(
      "Run a convergence loop first, e.g.: node scripts/harness/run-loop.mjs build-fix --check-only",
    );
    console.log(
      'Or record a workflow run, e.g.: node scripts/harness/record-run.mjs --loop review-fix --state converged --pass "..."',
    );
    return;
  }
  console.log(`Total runs:        ${overall.totalRuns}`);
  console.log(
    `Convergence rate:  ${fmtPct(overall.convergenceRate)} (${overall.byState.converged}/${overall.totalRuns})`,
  );
  console.log(
    `By state:          ${
      TERMINAL_STATES.filter((s) => overall.byState[s] > 0)
        .map((s) => `${s}=${overall.byState[s]}`)
        .join("  ") || "—"
    }`,
  );
  console.log(`Total iterations:  ${overall.totalIterations}`);

  console.log("\nPer loop:");
  for (const l of loops) {
    const avg =
      l.avgIterationsToConverge === null
        ? "—"
        : l.avgIterationsToConverge.toFixed(1);
    console.log(
      `  ${l.loop.padEnd(16)} ${(l.kind ?? "").padEnd(11)} runs=${String(l.runs).padEnd(3)} converged=${fmtPct(l.convergenceRate).padEnd(4)} avgIters=${avg}  last=${l.lastState ?? "—"}`,
    );
  }

  if (checks.length) {
    console.log("\nChecks (slowest first):");
    for (const c of checks.slice(0, 10)) {
      console.log(
        `  ${c.name.padEnd(20)} pass=${fmtPct(c.passRate).padEnd(4)} avg=${fmtDuration(c.avgDurationMs).padEnd(7)} max=${fmtDuration(c.maxDurationMs)}`,
      );
    }
  }

  if (rubric.length) {
    console.log("\nRubric criteria (most-failed first):");
    for (const r of rubric.slice(0, 12)) {
      console.log(
        `  pass=${fmtPct(r.passRate).padEnd(4)} graded=${String(r.graded).padEnd(3)} ${r.item}`,
      );
    }
  }
}

function fmtDelta(experiment) {
  if (experiment.improvedBy === null) return "—";
  const arrow = experiment.direction === "minimize" ? "↓" : "↑";
  const moved = experiment.improvedBy > 0;
  return `${moved ? arrow : "·"} ${experiment.baseline} → ${experiment.best}`;
}

function printExperiments(experiments) {
  if (!experiments.length) return;
  console.log("\nExperiments (autoresearch-style metric optimization):");
  for (const e of experiments.slice(0, 12)) {
    console.log(
      `  ${e.metricName.padEnd(24)} ${e.direction.padEnd(8)} ${fmtDelta(e).padEnd(20)} ${e.state}`,
    );
  }
}

function fmtGraph(graph) {
  if (!graph.present)
    return "NOT committed — run /understand and commit knowledge-graph.json";
  return `present (age ${graph.ageDays}d, ${graph.sizeKb} KB)`;
}

function printMemory(memory) {
  const { lessons, briefs, graph } = memory;
  console.log("\n=== Project Memory ===");
  console.log(`Lessons:   ${lessons.count} committed`);
  const briefBits = Object.entries(briefs.byStatus)
    .map(([s, n]) => `${s}=${n}`)
    .join("  ");
  const briefSuffix = briefBits ? `  (${briefBits})` : "";
  console.log(`Briefs:    ${briefs.count}${briefSuffix}`);
  console.log(`Graph:     ${fmtGraph(graph)}`);
  if (lessons.recent.length) {
    console.log("Recently updated lessons:");
    for (const l of lessons.recent.slice(0, 5)) {
      console.log(`  ${(l.summary || l.name).slice(0, 88)}`);
    }
  }
}

// ---------- HTML rendering ----------

function stateBadge(state) {
  return `<span class="badge badge-${esc(state)}">${esc(state)}</span>`;
}

function bar(rate) {
  const pct = Math.round(rate * 100);
  return `<div class="bar"><div class="bar-fill" style="width:${pct}%"></div><span class="bar-label">${pct}%</span></div>`;
}

function kindLabel(kind) {
  const k =
    kind === "convergence" || kind === "workflow" || kind === "experiment"
      ? kind
      : "workflow";
  return `<span class="kind kind-${k}">${k}</span>`;
}

function experimentDeltaCell(e) {
  if (e.improvedBy === null) return '<span class="muted">—</span>';
  const arrow = e.direction === "minimize" ? "↓" : "↑";
  const moved = e.improvedBy > 0;
  const cls = moved ? "delta-good" : "muted";
  return `<span class="${cls}">${moved ? arrow : "·"} ${esc(e.baseline)} → ${esc(e.best)}</span>`;
}

function renderExperimentsSection(experiments) {
  if (!experiments.length) return "";
  const rows = experiments
    .map(
      (e) => `<tr>
        <td class="mono">${esc(e.metricName)}</td>
        <td class="muted">${esc(e.direction)}</td>
        <td class="num">${esc(e.baseline ?? "—")}</td>
        <td class="num">${esc(e.best ?? "—")}</td>
        <td>${experimentDeltaCell(e)}</td>
        <td>${stateBadge(e.state)}</td>
      </tr>`,
    )
    .join("");
  return `
    <section class="panel">
      <h2>Experiments <span class="subtitle">(autoresearch-style — metric optimization, keep-if-improved)</span></h2>
      <table>
        <thead><tr><th>Metric</th><th>Goal</th><th class="num">Baseline</th><th class="num">Best</th><th>Trajectory</th><th>Result</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </section>`;
}

function briefStatusClass(status) {
  if (status === "implemented") return "badge-converged";
  if (status === "superseded") return "badge-incomplete";
  if (status === "active") return "badge-blocked";
  return "badge-incomplete";
}

function renderMemorySection(memory) {
  const graphCardValue = memory.graph.present
    ? `${memory.graph.ageDays}d`
    : "—";
  const graphCardLabel = memory.graph.present
    ? "Knowledge graph age"
    : "Knowledge graph missing";
  const memoryCards = `
    <section class="cards">
      <div class="card"><div class="card-value">${memory.lessons.count}</div><div class="card-label">Lessons committed</div></div>
      <div class="card"><div class="card-value">${memory.briefs.count}</div><div class="card-label">Architecture Briefs</div></div>
      <div class="card"><div class="card-value">${graphCardValue}</div><div class="card-label">${graphCardLabel}</div></div>
    </section>`;

  const lessonRows = memory.lessons.recent
    .slice(0, 10)
    .map(
      (l) => `<tr>
        <td>${esc(l.summary || "—")}</td>
        <td class="mono muted">${esc(l.name)}</td>
        <td class="muted">${esc(l.updated ? fmtDate(l.updated) : "—")}</td>
      </tr>`,
    )
    .join("");
  const lessonsPanel = `
    <section class="panel">
      <h2>Recent lessons <span class="subtitle">(latest 10 by update · ${memory.lessons.count} total)</span></h2>
      ${
        memory.lessons.count
          ? `<table><thead><tr><th>Summary</th><th>File</th><th>Updated</th></tr></thead><tbody>${lessonRows}</tbody></table>`
          : '<p class="muted">No lessons committed yet.</p>'
      }
    </section>`;

  const briefRows = memory.briefs.briefs
    .map(
      (b) => `<tr>
        <td>${esc(b.title)}</td>
        <td><span class="badge ${briefStatusClass(b.status)}">${esc(b.status)}</span></td>
        <td class="mono muted">${esc(b.name)}</td>
      </tr>`,
    )
    .join("");
  const briefsPanel = `
    <section class="panel">
      <h2>Architecture Briefs</h2>
      ${
        memory.briefs.count
          ? `<table><thead><tr><th>Brief</th><th>Status</th><th>File</th></tr></thead><tbody>${briefRows}</tbody></table>`
          : '<p class="muted">No Architecture Briefs persisted yet — harness stage 1 (Architect) writes them to <code>.github/harness/memory/briefs/</code>.</p>'
      }
    </section>`;

  return `<h2 class="section-title">Project memory</h2>${memoryCards}${lessonsPanel}${briefsPanel}`;
}

function renderPendingApprovalsSection(recentRuns) {
  const pending = pendingApprovalSnapshot(recentRuns);
  const card = `
    <section class="cards">
      <div class="card"><div class="card-value">${pending.count}</div><div class="card-label">Pending approvals</div></div>
      <div class="card"><div class="card-value">${recentRuns.length}</div><div class="card-label">Recent runs scanned</div></div>
      <div class="card"><div class="card-value">explicit-only</div><div class="card-label">Pending source policy</div></div>
    </section>`;

  const pendingRows = pending.pendingRuns
    .slice(0, 10)
    .map(
      (run) => `<tr>
        <td class="mono">${esc(run.loop)}</td>
        <td class="muted">${esc(fmtDate(run.startedAt))}</td>
        <td class="muted">${esc(fmtDate(run.approval?.requestedAt))}</td>
        <td class="muted">${esc(run.approval?.note ?? "—")}</td>
        <td>${stateBadge(run.state)}</td>
      </tr>`,
    )
    .join("");

  const approvalQueue = pending.count
    ? `<table><thead><tr><th>Loop</th><th>Started</th><th>Requested</th><th>Note</th><th>Run state</th></tr></thead><tbody>${pendingRows}</tbody></table>`
    : '<p class="muted">No explicitly pending approvals right now.</p>';

  return `
    <h2 class="section-title">Pending approvals</h2>
    ${card}
    <section class="panel">
      <h2>Approval queue <span class="subtitle">(explicit journal approval markers only)</span></h2>
      ${approvalQueue}
    </section>`;
}

function renderPipelineSection(pipeline) {
  const scriptRows = pipeline.integrationScripts
    .map(
      (entry) => `<tr>
        <td class="mono">${esc(entry.path)}</td>
        <td>${entry.present ? '<span class="badge badge-converged">present</span>' : '<span class="badge badge-stuck">missing</span>'}</td>
      </tr>`,
    )
    .join("");

  return `
    <h2 class="section-title">Pipeline integrations</h2>
    <section class="cards">
      <div class="card"><div class="card-value mono">${esc(pipeline.provider)}</div><div class="card-label">Local LLM provider</div></div>
      <div class="card"><div class="card-value mono">${esc(pipeline.model)}</div><div class="card-label">Inference model</div></div>
      <div class="card"><div class="card-value mono">${esc(pipeline.embedModel)}</div><div class="card-label">Embedding model</div></div>
      <div class="card"><div class="card-value mono">${esc(pipeline.routingProfiles.length || 0)}</div><div class="card-label">Routing profiles</div></div>
    </section>
    <section class="panel">
      <h2>Local LLM in pipeline</h2>
      <p class="muted">Provider host: <code>${esc(pipeline.host || "not configured")}</code></p>
      <p class="muted">Model split: implementer <code>${esc(pipeline.implementerModel)}</code> · reviewer <code>${esc(pipeline.reviewerModel)}</code></p>
      <table>
        <thead><tr><th>Integration script</th><th>Status</th></tr></thead>
        <tbody>${scriptRows}</tbody>
      </table>
    </section>`;
}

function renderEvalsSection(evals) {
  if (!evals || evals.length === 0) return "";
  const rows = evals
    .slice(0, 15)
    .map((run) => {
      const a = run.aggregate || {};
      const deltaCls = (a.delta ?? 0) > 0 ? "delta-good" : "muted";
      const verdict =
        run.verdict === "rejected"
          ? stateBadge("blocked")
          : stateBadge("converged");
      return `<tr>
        <td class="muted">${esc(fmtDate(run.startedAt))}</td>
        <td class="num">${esc(a.baselineScore ?? "—")}</td>
        <td class="num">${esc(a.harnessScore ?? "—")}</td>
        <td class="${deltaCls}">${(a.delta ?? 0) > 0 ? "↑" : "·"} ${esc(a.delta ?? "—")}</td>
        <td class="num">${esc(a.dangerousFlagged ?? 0)}</td>
        <td>${verdict}</td>
      </tr>`;
    })
    .join("");
  return `
    <h2 class="section-title">Evals <span class="subtitle">(does the harness measurably help?)</span></h2>
    <section class="panel">
      <table>
        <thead><tr><th>Run</th><th class="num">Baseline</th><th class="num">Harness</th><th>Δ</th><th class="num">Risks</th><th>Verdict</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
      <p class="muted">Scores are mean deterministic-verifier pass rate. A run is <strong>rejected</strong> if the dangerous-diff control flags any change, regardless of score.</p>
    </section>`;
}

function renderHtml(metrics) {
  const {
    overall,
    loops,
    checks,
    rubric,
    experiments,
    recentRuns,
    memory,
    evals,
    pipeline,
    generatedAt,
  } = metrics;
  const refreshSeconds =
    Number.isFinite(metrics.refreshSeconds) && metrics.refreshSeconds > 0
      ? Math.floor(metrics.refreshSeconds)
      : 60;
  const hasData = overall.totalRuns > 0;

  const statCards = hasData
    ? `
    <section class="cards">
      <div class="card"><div class="card-value">${overall.totalRuns}</div><div class="card-label">Total runs</div></div>
      <div class="card"><div class="card-value">${fmtPct(overall.convergenceRate)}</div><div class="card-label">Convergence rate</div></div>
      <div class="card"><div class="card-value">${overall.totalIterations}</div><div class="card-label">Total iterations</div></div>
      <div class="card"><div class="card-value">${loops.length}</div><div class="card-label">Loops exercised</div></div>
    </section>`
    : "";

  const stateChips = hasData
    ? `<section class="chips">${TERMINAL_STATES.filter(
        (s) => overall.byState[s] > 0,
      )
        .map(
          (s) =>
            `${stateBadge(s)} <span class="chip-count">${overall.byState[s]}</span>`,
        )
        .join("")}</section>`
    : "";

  const loopRows = loops
    .map(
      (l) => `<tr>
        <td class="mono">${esc(l.loop)}</td>
        <td>${kindLabel(l.kind)}</td>
        <td class="num">${l.runs}</td>
        <td>${bar(l.convergenceRate)}</td>
        <td class="num">${l.avgIterationsToConverge === null ? "—" : l.avgIterationsToConverge.toFixed(1)}</td>
        <td>${l.lastState ? stateBadge(l.lastState) : "—"}</td>
        <td class="muted">${esc(fmtDate(l.lastStartedAt))}</td>
      </tr>`,
    )
    .join("");

  const checkRows = checks
    .map(
      (c) => `<tr>
        <td class="mono">${esc(c.name)}</td>
        <td class="num">${c.runs}</td>
        <td>${bar(c.passRate)}</td>
        <td class="num">${esc(fmtDuration(c.avgDurationMs))}</td>
        <td class="num">${esc(fmtDuration(c.maxDurationMs))}</td>
      </tr>`,
    )
    .join("");

  const rubricRows = rubric
    .map(
      (r) => `<tr>
        <td>${esc(r.item)}</td>
        <td class="mono muted">${esc(r.loop)}</td>
        <td class="num">${r.graded}</td>
        <td>${bar(r.passRate)}</td>
      </tr>`,
    )
    .join("");

  const runRows = recentRuns
    .map(
      (r) => `<tr>
        <td class="mono">${esc(r.loop)}</td>
        <td>${kindLabel(r.kind)}</td>
        <td class="muted">${esc(fmtDate(r.startedAt))}</td>
        <td class="num">${esc(fmtDuration(r.durationMs))}</td>
        <td class="num">${r.iterations}</td>
        <td>${stateBadge(r.state)}</td>
        <td class="mono muted">${esc(r.baseline ?? "—")}${r.dirty ? ' <span class="dirty">dirty</span>' : ""}</td>
      </tr>`,
    )
    .join("");

  const emptyNotice = hasData
    ? ""
    : `<section class="empty">
        <h2>No runs recorded yet</h2>
        <p>Populate this dashboard by running a convergence loop:</p>
        <pre class="mono">node scripts/harness/run-loop.mjs build-fix --check-only</pre>
        <p>… or recording a workflow stage/loop run (Understand, Architect, review-fix, …):</p>
        <pre class="mono">node scripts/harness/record-run.mjs --loop review-fix --state converged --pass "Zero Blocker findings remain"</pre>
        <p>Each writes a journal to <code>.github/harness/runs/</code>, then re-run this report.</p>
      </section>`;

  const checksSection = checks.length
    ? `
    <section class="panel">
      <h2>Checks <span class="subtitle">(convergence loops — slowest first)</span></h2>
      <table>
        <thead><tr><th>Check</th><th class="num">Runs</th><th>Pass rate</th><th class="num">Avg</th><th class="num">Max</th></tr></thead>
        <tbody>${checkRows}</tbody>
      </table>
    </section>`
    : "";

  const rubricSection = rubric.length
    ? `
    <section class="panel">
      <h2>Rubric criteria <span class="subtitle">(workflow stages — most-failed first)</span></h2>
      <table>
        <thead><tr><th>Criterion</th><th>Loop</th><th class="num">Graded</th><th>Pass rate</th></tr></thead>
        <tbody>${rubricRows}</tbody>
      </table>
    </section>`
    : "";

  const tables = hasData
    ? `
    <section class="panel">
      <h2>Per loop</h2>
      <table>
        <thead><tr><th>Loop</th><th>Kind</th><th class="num">Runs</th><th>Convergence</th><th class="num">Avg iters</th><th>Last</th><th>Last run</th></tr></thead>
        <tbody>${loopRows}</tbody>
      </table>
    </section>
    ${checksSection}
    ${rubricSection}
    ${renderExperimentsSection(experiments)}
    <section class="panel">
      <h2>Recent runs <span class="subtitle">(latest 30)</span></h2>
      <table>
        <thead><tr><th>Loop</th><th>Kind</th><th>Started</th><th class="num">Duration</th><th class="num">Iters</th><th>State</th><th>Baseline</th></tr></thead>
        <tbody>${runRows}</tbody>
      </table>
    </section>`
    : "";

  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Harness Loop Metrics — Harness Kit</title>
<style>
  :root {
    color-scheme: light dark;
    --bg: #f6f7f9; --panel: #ffffff; --border: #e2e5ea; --text: #1b1f24; --muted: #6b7280;
    --accent: #2563eb; --accent-soft: #dbeafe;
    --converged: #15803d; --converged-bg: #dcfce7;
    --exhausted: #b45309; --exhausted-bg: #fef3c7;
    --stuck: #b91c1c; --stuck-bg: #fee2e2;
    --blocked: #7c3aed; --blocked-bg: #ede9fe;
    --incomplete: #475569; --incomplete-bg: #e2e8f0;
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --bg: #0f1419; --panel: #1a212b; --border: #2a323d; --text: #e6e9ee; --muted: #9aa4b2;
      --accent: #60a5fa; --accent-soft: #1e3a5f;
      --converged: #4ade80; --converged-bg: #14331f;
      --exhausted: #fbbf24; --exhausted-bg: #3a2c0a;
      --stuck: #f87171; --stuck-bg: #3a1414;
      --blocked: #c4b5fd; --blocked-bg: #2a1f47;
      --incomplete: #cbd5e1; --incomplete-bg: #1f2937;
    }
  }
  * { box-sizing: border-box; }
  body { margin: 0; background: var(--bg); color: var(--text); font: 14px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }
  .wrap { max-width: 1100px; margin: 0 auto; padding: 32px 20px 64px; }
  header h1 { margin: 0 0 4px; font-size: 22px; }
  header .meta { color: var(--muted); font-size: 13px; }
  .cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 14px; margin: 24px 0; }
  .card { background: var(--panel); border: 1px solid var(--border); border-radius: 10px; padding: 18px; }
  .card-value { font-size: 28px; font-weight: 650; }
  .card-label { color: var(--muted); font-size: 13px; margin-top: 2px; }
  .chips { margin: 0 0 24px; display: flex; flex-wrap: wrap; gap: 10px; align-items: center; }
  .chip-count { font-weight: 600; margin-right: 8px; }
  .panel { background: var(--panel); border: 1px solid var(--border); border-radius: 10px; padding: 18px 20px; margin-bottom: 20px; }
  .panel h2 { margin: 0 0 14px; font-size: 16px; }
  .section-title { margin: 30px 0 10px; font-size: 18px; }
  .subtitle { color: var(--muted); font-weight: 400; font-size: 13px; }
  table { width: 100%; border-collapse: collapse; }
  th, td { text-align: left; padding: 9px 10px; border-bottom: 1px solid var(--border); }
  th { color: var(--muted); font-weight: 600; font-size: 12px; text-transform: uppercase; letter-spacing: .03em; }
  tr:last-child td { border-bottom: none; }
  td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; }
  .mono { font-family: "SF Mono", "Cascadia Code", Consolas, "Liberation Mono", monospace; font-size: 13px; }
  .muted { color: var(--muted); }
  .badge { display: inline-block; padding: 2px 9px; border-radius: 999px; font-size: 12px; font-weight: 600; }
  .badge-converged { color: var(--converged); background: var(--converged-bg); }
  .badge-exhausted { color: var(--exhausted); background: var(--exhausted-bg); }
  .badge-stuck { color: var(--stuck); background: var(--stuck-bg); }
  .badge-blocked { color: var(--blocked); background: var(--blocked-bg); }
  .badge-incomplete { color: var(--incomplete); background: var(--incomplete-bg); }
  .kind { display: inline-block; font-size: 11px; padding: 1px 7px; border-radius: 5px; font-weight: 600; }
  .kind-convergence { color: var(--accent); background: var(--accent-soft); }
  .kind-workflow { color: var(--blocked); background: var(--blocked-bg); }
  .kind-experiment { color: var(--exhausted); background: var(--exhausted-bg); }
  .delta-good { color: var(--converged); font-weight: 600; }
  .bar { position: relative; background: var(--border); border-radius: 6px; height: 18px; min-width: 90px; overflow: hidden; }
  .bar-fill { position: absolute; inset: 0 auto 0 0; background: var(--accent); border-radius: 6px; }
  .bar-label { position: relative; display: block; text-align: center; font-size: 11px; font-weight: 600; line-height: 18px; mix-blend-mode: difference; color: #fff; }
  .dirty { color: var(--stuck); font-weight: 600; font-size: 11px; }
  .empty { background: var(--panel); border: 1px dashed var(--border); border-radius: 10px; padding: 28px; text-align: center; }
  .empty h2 { margin: 0 0 8px; }
  .refresh { margin-top: 8px; color: var(--muted); font-size: 12px; }
  pre { background: var(--accent-soft); color: var(--text); padding: 12px 14px; border-radius: 8px; overflow-x: auto; text-align: left; }
  code { font-family: "SF Mono", "Cascadia Code", Consolas, monospace; font-size: 13px; }
</style>
</head>
<body>
  <div class="wrap">
    <header>
      <h1>Harness Metrics</h1>
      <div class="meta">Harness Kit · generated ${esc(fmtDate(generatedAt))} · sources: <code>.github/harness/runs/</code> + <code>memory/</code></div>
      <div class="refresh">Auto refresh every <span id="refresh-seconds">${refreshSeconds}</span>s · next reload in <span id="refresh-countdown">${refreshSeconds}</span>s</div>
    </header>
    ${renderMemorySection(memory)}
    ${renderPendingApprovalsSection(recentRuns)}
    ${renderPipelineSection(pipeline)}
    ${renderEvalsSection(evals)}
    <h2 class="section-title">Loop runs</h2>
    ${statCards}
    ${stateChips}
    ${emptyNotice}
    ${tables}
  </div>
  <script>
    (() => {
      const refreshSeconds = ${refreshSeconds};
      let remaining = refreshSeconds;
      const countdownEl = document.getElementById('refresh-countdown');
      const tick = () => {
        if (countdownEl) countdownEl.textContent = String(remaining);
        remaining -= 1;
        if (remaining < 0) window.location.reload();
      };
      tick();
      setInterval(tick, 1000);
    })();
  </script>
</body>
</html>
`;
}

// ---------- main ----------

const args = parseArgs(process.argv.slice(2));
const journals = loadJournals();
const metrics = computeMetrics(journals);
metrics.memory = loadMemory();
metrics.evals = loadEvalRuns();
const config = loadHarnessConfig();
metrics.pipeline = loadPipelineIntegration(config);
metrics.refreshSeconds =
  Number.isFinite(config?.dashboard?.intervalSeconds) &&
  config.dashboard.intervalSeconds > 0
    ? Math.floor(config.dashboard.intervalSeconds)
    : 60;

if (args.json) {
  console.log(JSON.stringify(metrics, null, 2));
  process.exit(0);
}

printSummary(metrics);
printExperiments(metrics.experiments);
printMemory(metrics.memory);

if (args.html) {
  const outPath = args.out
    ? resolve(repoRoot, args.out)
    : join(runsDir, "report.html");
  try {
    mkdirSync(dirname(outPath), { recursive: true });
    writeFileSync(outPath, renderHtml(metrics));
    console.log(`\n[harness-report] HTML written: ${outPath}`);
  } catch (err) {
    fail(`could not write HTML report: ${err.message}`);
  }
}
