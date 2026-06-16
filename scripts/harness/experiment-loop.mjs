#!/usr/bin/env node
/**
 * Continuous experiment runner — autoresearch-style overnight hill-climbing.
 *
 * karpathy/autoresearch runs ~100 short experiments while you sleep; run-experiment.mjs
 * runs a single bounded experiment and exits. This wrapper closes that gap: it repeatedly
 * invokes run-experiment.mjs for one (or a rotation of) experiment loop(s) on an interval,
 * so a local LLM keeps attempting improvements unattended. Every attempt is journaled by the
 * underlying runner, so the harness dashboard reflects progress live.
 *
 * It never edits code itself — it only schedules run-experiment.mjs, which owns the
 * measure → agent → keep-if-improved → journal protocol.
 *
 * Usage:
 *   node scripts/harness/experiment-loop.mjs --experiments lint-debt-experiment \
 *     --agent "node scripts/harness/ollama-apply-agent.mjs --model qwen2.5-coder:14b" --commit
 *
 * Options:
 *   --experiments <a,b>     Comma-separated experiment loop names to rotate through
 *                           (default: HARNESS_EXPERIMENTS, else all kind:experiment loops).
 *   --agent "<cmd>"         Agent command passed through to run-experiment.mjs
 *                           (default: HARNESS_AGENT_CMD).
 *   --interval-seconds <n>  Pause between cycles (default 60, env HARNESS_EXPERIMENT_INTERVAL_SECONDS).
 *   --max-cycles <n>        Stop after N cycles (default 0 = run forever).
 *   --max-iterations <n>    Cap iterations per experiment invocation (passed through).
 *   --commit                Auto-commit kept improvements (passed through).
 *   --run-once              One cycle through the experiment list, then exit.
 *   --help                  Show this help.
 *
 * Exit codes: 0 normal completion (max-cycles/run-once), 2 configuration error.
 */
import { spawnSync } from 'node:child_process';
import { existsSync, readFileSync, readdirSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const loopsDir = join(repoRoot, '.github', 'harness', 'loops');
const runExperimentScript = resolve(repoRoot, 'scripts', 'harness', 'run-experiment.mjs');

function fail(message) {
  console.error(`[experiment-loop] ${message}`);
  process.exit(2);
}

function parseArgs(argv) {
  const flags = { _: [] };
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (!arg.startsWith('--')) {
      flags._.push(arg);
      continue;
    }
    if (arg === '--help' || arg === '--run-once' || arg === '--commit') {
      flags[arg.slice(2)] = true;
      continue;
    }
    const key = arg.slice(2);
    const next = argv[i + 1];
    if (next === undefined || next.startsWith('--')) {
      throw new Error(`Missing value for --${key}`);
    }
    flags[key] = next;
    i += 1;
  }
  return flags;
}

function parsePositiveInt(value, fallback) {
  const number = Number(value);
  return Number.isFinite(number) && number > 0 ? Math.floor(number) : fallback;
}

function parseNonNegativeInt(value, fallback) {
  const number = Number(value);
  return Number.isFinite(number) && number >= 0 ? Math.floor(number) : fallback;
}

function sleep(ms) {
  return new Promise(resolveSleep => {
    setTimeout(resolveSleep, ms);
  });
}

function discoverExperiments() {
  if (!existsSync(loopsDir)) return [];
  const names = [];
  for (const file of readdirSync(loopsDir)) {
    if (!file.endsWith('.json') || file.startsWith('_')) continue;
    try {
      const loop = JSON.parse(readFileSync(join(loopsDir, file), 'utf8'));
      if (loop.kind === 'experiment' && typeof loop.name === 'string') names.push(loop.name);
    } catch {
      // ignore unparseable loop definitions
    }
  }
  return names;
}

function showHelp() {
  process.stdout.write(
    `${JSON.stringify(
      {
        usage:
          'node scripts/harness/experiment-loop.mjs --experiments <a,b> --agent "<cmd>" [--interval-seconds n] [--max-cycles n] [--commit] [--run-once]',
        notes: [
          'Schedules run-experiment.mjs repeatedly for autoresearch-style overnight hill-climbing.',
          'Each attempt is journaled and shows on the harness dashboard.',
        ],
        envFallbacks: [
          'HARNESS_EXPERIMENTS',
          'HARNESS_AGENT_CMD',
          'HARNESS_EXPERIMENT_INTERVAL_SECONDS',
        ],
      },
      null,
      2
    )}\n`
  );
}

function runExperimentOnce(name, { agent, maxIterations, commit }) {
  const args = [runExperimentScript, name];
  if (agent) args.push('--agent', agent);
  if (maxIterations) args.push('--max-iterations', String(maxIterations));
  if (commit) args.push('--commit');

  const stamp = new Date().toISOString();
  process.stdout.write(`[experiment-loop] ${stamp} starting experiment "${name}"\n`);
  const result = spawnSync(process.execPath, args, {
    cwd: repoRoot,
    stdio: 'inherit',
    // run-experiment.mjs exit codes: 0 improved, 1 exhausted, 2 config error, 3 stuck.
    env: process.env,
  });
  const code = result.status ?? (result.signal ? `signal ${result.signal}` : 'unknown');
  process.stdout.write(`[experiment-loop] experiment "${name}" finished (exit ${code})\n`);
  return result.status ?? 1;
}

async function main() {
  const flags = parseArgs(process.argv.slice(2));
  if (flags.help) {
    showHelp();
    return;
  }

  const experimentsRaw =
    flags.experiments || process.env.HARNESS_EXPERIMENTS || discoverExperiments().join(',');
  const experiments = String(experimentsRaw)
    .split(',')
    .map(s => s.trim())
    .filter(Boolean);
  if (experiments.length === 0) {
    fail('No experiments to run. Pass --experiments or define kind:experiment loops.');
  }

  const agent = flags.agent || process.env.HARNESS_AGENT_CMD || '';
  const intervalSeconds = parsePositiveInt(
    flags['interval-seconds'] ?? process.env.HARNESS_EXPERIMENT_INTERVAL_SECONDS,
    60
  );
  const maxIterations = flags['max-iterations']
    ? parsePositiveInt(flags['max-iterations'], 0)
    : 0;
  const maxCycles = flags['run-once'] ? 1 : parseNonNegativeInt(flags['max-cycles'], 0);
  const commit = Boolean(flags.commit);

  process.stdout.write(
    `[experiment-loop] starting (experiments=${experiments.join(', ')}, interval=${intervalSeconds}s, ` +
      `maxCycles=${maxCycles || 'infinite'}, commit=${commit ? 'on' : 'off'}, agent=${agent || '(default)'})\n`
  );

  let stopping = false;
  const stop = signal => {
    process.stdout.write(`[experiment-loop] received ${signal}, finishing current cycle then exiting\n`);
    stopping = true;
  };
  process.on('SIGTERM', () => stop('SIGTERM'));
  process.on('SIGINT', () => stop('SIGINT'));

  let cycle = 0;
  for (;;) {
    cycle += 1;
    process.stdout.write(`[experiment-loop] === cycle ${cycle} ===\n`);
    for (const name of experiments) {
      if (stopping) break;
      runExperimentOnce(name, { agent, maxIterations, commit });
    }

    if (stopping) break;
    if (maxCycles > 0 && cycle >= maxCycles) {
      process.stdout.write(`[experiment-loop] reached max cycles (${maxCycles}) — done.\n`);
      break;
    }
    await sleep(intervalSeconds * 1000);
    if (stopping) break;
  }
}

main().catch(error => {
  process.stderr.write(
    `[experiment-loop] fatal: ${error instanceof Error ? error.message : String(error)}\n`
  );
  process.exit(2);
});
