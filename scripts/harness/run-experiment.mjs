#!/usr/bin/env node
/**
 * Harness experiment runner — autoresearch-style optimization loop.
 *
 * Inspired by karpathy/autoresearch: instead of converging on pass/fail checks, an experiment
 * OPTIMIZES a numeric metric. Each iteration the agent edits a focused target, the runner
 * re-measures the metric, and KEEPS the edit only if it improved — otherwise it reverts the
 * target to its pre-iteration contents. Over a bounded budget this hill-climbs the metric and
 * journals every attempt for the dashboard.
 *
 * This is the third harness loop kind (alongside convergence and workflow). It needs its own
 * runner because run-loop.mjs only understands pass/fail checks — it has no concept of a metric,
 * a direction, or keep-if-improved reverts.
 *
 * Usage:
 *   node scripts/harness/run-experiment.mjs <name> [options]
 *     --measure-only        measure the baseline metric and exit; never invoke an agent
 *     --max-iterations N    override the loop's maxIterations (lower only)
 *     --agent "<cmd>"       agent command receiving the improvement prompt on stdin
 *                           (default: $HARNESS_AGENT_CMD, else "claude -p")
 *     --list                list available experiment loops
 *
 * Safety: the runner snapshots ONLY the declared target files (in memory) before each agent
 * iteration and restores exactly those on regression — it never runs `git checkout`/`reset`, so
 * it cannot clobber unrelated uncommitted work. The agent must confine edits to the target
 * (a guardrail); edits outside it are not reverted and are reported.
 *
 * Exit codes: 0 improved, 1 exhausted (no net improvement), 2 configuration error,
 *             3 stuck (no improvement for noImprovementStop iterations).
 */
import { execSync, spawnSync } from 'node:child_process';
import { existsSync, mkdirSync, readFileSync, readdirSync, statSync, writeFileSync } from 'node:fs';
import { dirname, join, relative, resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';
import { assertSafeCliCommand } from './command-validation.mjs';
import { resolveTokens } from './config.mjs';

const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const loopsDir = join(repoRoot, '.github', 'harness', 'loops');
const runsDir = join(repoRoot, '.github', 'harness', 'runs');
const HEAD_CHARS = 2000;
const TAIL_CHARS = 6000;

function fail(message) {
  console.error(`[run-experiment] ${message}`);
  process.exit(2);
}

function parseArgs(argv) {
  const args = {
    name: undefined,
    measureOnly: false,
    maxIterations: undefined,
    agent: undefined,
    list: false,
    commit: false,
  };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--list') args.list = true;
    else if (a === '--measure-only') args.measureOnly = true;
    else if (a === '--commit') args.commit = true;
    else if (a === '--max-iterations') args.maxIterations = Number(argv[++i]);
    else if (a === '--agent') args.agent = argv[++i];
    else if (a.startsWith('--')) fail(`Unknown option: ${a}`);
    else if (args.name) fail(`Unexpected argument: ${a}`);
    else args.name = a;
  }
  return args;
}

function listExperiments() {
  for (const file of readdirSync(loopsDir).filter(f => f.endsWith('.json') && !f.startsWith('_'))) {
    const loop = JSON.parse(readFileSync(join(loopsDir, file), 'utf8'));
    if (loop.kind === 'experiment') {
      console.log(
        `${loop.name.padEnd(22)} ${loop.metric?.direction?.padEnd(8) ?? ''} ${loop.description}`
      );
    }
  }
}

function loadLoop(name) {
  const path = join(loopsDir, `${name}.json`);
  if (!existsSync(path))
    fail(`No loop named "${name}" in ${loopsDir}. Use --list to see experiments.`);
  const loop = JSON.parse(readFileSync(path, 'utf8'));
  if (loop.kind !== 'experiment') {
    fail(
      `Loop "${name}" is kind "${loop.kind}", not "experiment" — use run-loop.mjs for convergence loops.`
    );
  }
  if (!Number.isInteger(loop.maxIterations) || loop.maxIterations < 1) {
    fail(`Loop "${name}" has an invalid maxIterations — experiments must be bounded.`);
  }
  if (
    !loop.metric ||
    typeof loop.metric.run !== 'string' ||
    typeof loop.metric.extract !== 'string'
  ) {
    fail(
      `Loop "${name}" needs metric.run (command) and metric.extract (regex capturing a number).`
    );
  }
  if (loop.metric.direction !== 'minimize' && loop.metric.direction !== 'maximize') {
    fail(`Loop "${name}" metric.direction must be "minimize" or "maximize".`);
  }
  if (!Array.isArray(loop.target) || loop.target.length === 0) {
    fail(`Loop "${name}" needs a non-empty target[] (the file(s) the agent optimizes).`);
  }
  return loop;
}

function gitBaseline() {
  const baseline = { commit: null, dirty: null };
  try {
    baseline.commit = execSync('git rev-parse HEAD', { cwd: repoRoot, encoding: 'utf8' }).trim();
    baseline.dirty =
      execSync('git status --porcelain', { cwd: repoRoot, encoding: 'utf8' }).trim() !== '';
  } catch {
    // not a git repo or git unavailable — baseline stays null
  }
  return baseline;
}

// Resolve target globs to concrete files via `git ls-files` (tracked) so snapshots are precise
// and we never walk node_modules. Falls back to literal paths that exist.
function resolveTargets(patterns) {
  const files = new Set();
  for (const pattern of patterns) {
    try {
      const out = execSync(`git ls-files -- "${pattern}"`, {
        cwd: repoRoot,
        encoding: 'utf8',
      }).trim();
      for (const line of out.split('\n')) {
        if (line.trim()) files.add(line.trim());
      }
    } catch {
      // ignore — handled by literal-path fallback below
    }
    const literal = join(repoRoot, pattern);
    if (existsSync(literal) && statSync(literal).isFile()) {
      files.add(relative(repoRoot, literal).split(sep).join('/'));
    }
  }
  return [...files];
}

function snapshotTargets(files) {
  const snapshot = new Map();
  for (const rel of files) {
    const abs = join(repoRoot, rel);
    if (existsSync(abs)) snapshot.set(rel, readFileSync(abs, 'utf8'));
  }
  return snapshot;
}

function restoreTargets(snapshot) {
  for (const [rel, content] of snapshot) {
    writeFileSync(join(repoRoot, rel), content);
  }
}

function truncateOutput(text) {
  if (text.length <= HEAD_CHARS + TAIL_CHARS) return text;
  const omitted = text.length - HEAD_CHARS - TAIL_CHARS;
  return `${text.slice(0, HEAD_CHARS)}\n… [${omitted} chars omitted] …\n${text.slice(-TAIL_CHARS)}`;
}

/**
 * Run the metric command and extract a number via the loop's regex. Returns
 * { value, output } where value is null when the command failed or no number matched
 * (callers treat a null mid-run as "not improved" and revert).
 */
function measureMetric(loop) {
  const { run, extract, timeoutMs } = loop.metric;
  let raw = '';
  try {
    raw = execSync(resolveTokens(run), {
      cwd: repoRoot,
      stdio: ['ignore', 'pipe', 'pipe'],
      encoding: 'utf8',
      timeout: timeoutMs,
    });
  } catch (err) {
    raw = `${err.stdout ?? ''}\n${err.stderr ?? ''}`.trim();
  }
  const match = new RegExp(extract).exec(raw);
  const value = match?.[1] === undefined ? null : Number(match[1]);
  return { value: Number.isFinite(value) ? value : null, output: truncateOutput(raw) };
}

function isImproved(direction, candidate, best) {
  return direction === 'minimize' ? candidate < best : candidate > best;
}

function composeImprovementPrompt(loop, iteration, best, current, journal) {
  const { name, direction } = loop.metric;
  const history = journal
    .filter(e => e.metric !== null)
    .map(e => `- Iteration ${e.iteration}: ${name}=${e.metric} (${e.kept ? 'KEPT' : 'reverted'}).`);
  return [
    `You are iteration ${iteration}/${loop.maxIterations} of the harness EXPERIMENT "${loop.name}".`,
    `Protocol: .github/harness/LOOPS.md. Definition: .github/harness/loops/${loop.name}.json.`,
    loop.skills?.length ? `Load these skills first: ${loop.skills.join(', ')}.` : '',
    loop.instructions?.length
      ? `Read these instructions first: ${loop.instructions.join(', ')}.`
      : '',
    '',
    `Goal: ${direction} the metric "${name}". Best so far: ${best}. Current on disk: ${current}.`,
    `You may ONLY edit: ${loop.target.join(', ')}. The runner re-measures after you finish and`,
    `keeps your edit only if "${name}" improved; otherwise it reverts the target automatically.`,
    '',
    loop.fixPrompt ?? '',
    '',
    'Guardrails (never violate these to move the metric):',
    ...(loop.guardrails ?? []).map(g => `- ${g}`),
    '',
    ...(history.length > 0 ? ['## Prior attempts this run', ...history, ''] : []),
    'Make one focused improvement now. Do not re-run the metric command yourself; the runner does.',
  ]
    .filter(line => line !== undefined)
    .join('\n');
}

function invokeAgent(agentCmd, prompt, targetFiles) {
  assertSafeCliCommand(agentCmd, { label: 'run-experiment agent command' });
  console.log(`[run-experiment]   invoking agent: ${agentCmd}`);
  const result = spawnSync(agentCmd, {
    cwd: repoRoot,
    shell: true,
    input: prompt,
    stdio: ['pipe', 'inherit', 'inherit'],
    // Expose the declared target(s) so file-editing adapters (e.g. ollama-apply-agent.mjs)
    // know exactly which file to rewrite without parsing them out of the prompt.
    env: { ...process.env, HARNESS_EXPERIMENT_TARGETS: targetFiles.join(',') },
  });
  if (result.error) fail(`Agent command failed to start: ${result.error.message}`);
  if (result.status !== 0)
    console.warn(`[run-experiment]   agent exited ${result.status}; re-measuring anyway`);
}

// Commit ONLY the declared target files after a kept improvement, so an autonomous
// (e.g. overnight) run leaves a reviewable trail without sweeping in unrelated work.
function commitTargets(targetFiles, loop, iteration, metricName, value) {
  try {
    execSync(`git add -- ${targetFiles.map(f => `"${f}"`).join(' ')}`, {
      cwd: repoRoot,
      stdio: 'ignore',
    });
    const staged = execSync('git diff --cached --name-only', {
      cwd: repoRoot,
      encoding: 'utf8',
    }).trim();
    if (!staged) return;
    const message = `chore(harness): ${loop.name} iter ${iteration} — ${metricName}=${value}`;
    execSync(`git commit -m "${message}" --no-verify`, { cwd: repoRoot, stdio: 'ignore' });
    console.log(`[run-experiment]   committed target(s): ${message}`);
  } catch (err) {
    console.warn(`[run-experiment]   auto-commit failed: ${err.message}`);
  }
}

function writeJournal(journalFile, record) {
  try {
    mkdirSync(runsDir, { recursive: true });
    writeFileSync(journalFile, JSON.stringify(record, null, 2));
  } catch (err) {
    console.warn(`[run-experiment] could not write journal: ${err.message}`);
  }
}

const args = parseArgs(process.argv.slice(2));
if (args.list) {
  listExperiments();
  process.exit(0);
}
if (!args.name)
  fail('Usage: run-experiment.mjs <name> [--measure-only] [--max-iterations N] [--agent "<cmd>"]');

const loop = loadLoop(args.name);
let maxIterations = loop.maxIterations;
if (args.maxIterations !== undefined) {
  if (!Number.isInteger(args.maxIterations) || args.maxIterations < 1)
    fail('--max-iterations must be a positive integer');
  maxIterations = Math.min(maxIterations, args.maxIterations);
}
const agentCmd = args.agent ?? process.env.HARNESS_AGENT_CMD ?? 'claude -p';
const commitOnImprove = args.commit || process.env.HARNESS_EXPERIMENT_COMMIT === 'true';
const direction = loop.metric.direction;
const noImprovementStop = Number.isInteger(loop.noImprovementStop)
  ? loop.noImprovementStop
  : maxIterations;

const targetFiles = resolveTargets(loop.target);
if (targetFiles.length === 0) fail(`target ${JSON.stringify(loop.target)} resolved to no files.`);

const baseline = gitBaseline();
const startedAt = new Date();
const journalFile = join(
  runsDir,
  `${loop.name}-${startedAt.toISOString().replace(/[:.]/g, '-')}.json`
);
const record = {
  loop: loop.name,
  kind: 'experiment',
  startedAt: startedAt.toISOString(),
  baseline,
  terminalState: null,
  metric: { name: loop.metric.name ?? loop.name, direction },
  iterations: [],
};

console.log(`[run-experiment] "${loop.name}" — ${loop.description}`);
console.log(`[run-experiment] target: ${targetFiles.join(', ')}`);
if (baseline.dirty) {
  console.log(
    '[run-experiment] working tree DIRTY — the runner reverts only the target; other changes are yours to manage.'
  );
}

function finish(terminalState, exitCode, message) {
  record.terminalState = terminalState;
  record.finishedAt = new Date().toISOString();
  writeJournal(journalFile, record);
  const log = exitCode === 0 ? console.log : console.error;
  log(`[run-experiment] ${message}`);
  log(`[run-experiment] journal: ${journalFile}`);
  process.exit(exitCode);
}

console.log('[run-experiment] measuring baseline…');
const baseMeasure = measureMetric(loop);
if (baseMeasure.value === null) {
  fail(
    `baseline metric did not produce a number (regex ${JSON.stringify(loop.metric.extract)} on the command output). Cannot optimize an unmeasurable metric.`
  );
}
record.metric.baseline = baseMeasure.value;
let best = baseMeasure.value;
console.log(`[run-experiment] baseline ${record.metric.name} = ${best} (goal: ${direction})`);

if (args.measureOnly) {
  record.metric.best = best;
  record.metric.improvedBy = 0;
  finish(
    'exhausted',
    1,
    `measured baseline ${record.metric.name}=${best} (--measure-only, no optimization attempted).`
  );
}

let noImprovementStreak = 0;
for (let iteration = 1; iteration <= maxIterations; iteration++) {
  console.log(
    `[run-experiment] iteration ${iteration}/${maxIterations} — best ${record.metric.name}=${best}`
  );
  const preIteration = snapshotTargets(targetFiles);

  invokeAgent(
    agentCmd,
    composeImprovementPrompt(loop, iteration, best, best, record.iterations),
    targetFiles
  );

  const measure = measureMetric(loop);
  const improved = measure.value !== null && isImproved(direction, measure.value, best);

  if (improved) {
    best = measure.value;
    noImprovementStreak = 0;
    console.log(`[run-experiment]   ${record.metric.name}=${measure.value} — IMPROVED, kept.`);
    if (commitOnImprove) {
      commitTargets(targetFiles, loop, iteration, record.metric.name, measure.value);
    }
  } else {
    restoreTargets(preIteration);
    noImprovementStreak += 1;
    const shown = measure.value === null ? 'unmeasurable' : measure.value;
    console.log(
      `[run-experiment]   ${record.metric.name}=${shown} — no improvement, reverted target.`
    );
  }

  record.iterations.push({
    iteration,
    at: new Date().toISOString(),
    metric: measure.value,
    best,
    kept: improved,
  });

  if (!improved && noImprovementStreak >= noImprovementStop) {
    record.metric.best = best;
    record.metric.improvedBy = baseMeasure.value - best; // positive = moved toward goal for minimize
    const verdict =
      best === baseMeasure.value
        ? 'no improvement over baseline'
        : `best ${record.metric.name}=${best}`;
    finish(
      'stuck',
      3,
      `stuck: ${noImprovementStreak} iteration(s) without improvement — stopping early. ${verdict}. onExhausted: ${loop.onExhausted ?? '(none)'}`
    );
  }
}

record.metric.best = best;
record.metric.improvedBy = baseMeasure.value - best;
const netImproved = isImproved(direction, best, baseMeasure.value);
if (netImproved) {
  finish(
    'converged',
    0,
    `improved ${record.metric.name}: ${baseMeasure.value} → ${best} over ${maxIterations} iteration(s).`
  );
}
finish(
  'exhausted',
  1,
  `exhausted ${maxIterations} iteration(s) with no net improvement (best ${record.metric.name}=${best}, baseline ${baseMeasure.value}). onExhausted: ${loop.onExhausted ?? '(none)'}`
);
