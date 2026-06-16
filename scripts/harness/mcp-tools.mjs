#!/usr/bin/env node
// Attribution & adaptations: see CREDITS.md (autoresearch, Understand-Anything, MCP, Ollama, LM Studio).
/**
 * MCP-ready wrappers for harness graph + memory + vector tools.
 *
 * This script does not implement an MCP transport server on its own.
 * It exposes stable JSON commands that an MCP server can call directly.
 *
 * Usage examples:
 *   node scripts/harness/mcp-tools.mjs list-tools
 *   node scripts/harness/mcp-tools.mjs graph-status
 *   node scripts/harness/mcp-tools.mjs graph-neighbors --node-id "file:backend/src/app.ts" --depth 2
 *   node scripts/harness/mcp-tools.mjs memory-search --query "tenant" --scope lessons --limit 10
 *   node scripts/harness/mcp-tools.mjs vector-search --query "tenant isolation" --scope all --top 5
 */
import { spawnSync } from 'node:child_process';
import { existsSync, readFileSync, readdirSync, statSync } from 'node:fs';
import { dirname, join, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const graphCliPath = join(repoRoot, 'scripts', 'harness', 'graph.mjs');
const vectorCliPath = join(repoRoot, 'scripts', 'harness', 'vector-search.mjs');
const reportCliPath = join(repoRoot, 'scripts', 'harness', 'harness-report.mjs');
const lessonsDir = join(repoRoot, '.github', 'harness', 'memory', 'lessons');
const briefsDir = join(repoRoot, '.github', 'harness', 'memory', 'briefs');
const loopsDir = join(repoRoot, '.github', 'harness', 'loops');

function toWorkspacePath(pathValue) {
  return relative(repoRoot, pathValue).replace(/\\/g, '/');
}

const TOOL_NAMES = [
  'graph-status',
  'graph-neighbors',
  'graph-dependents',
  'graph-path',
  'graph-layers',
  'graph-layer',
  'graph-hubs',
  'memory-list',
  'memory-read',
  'memory-search',
  'vector-status',
  'vector-index',
  'vector-search',
  'harness-loops',
  'harness-report',
];

function parseArgs(argv) {
  const flags = { _: [] };
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (!arg.startsWith('--')) {
      flags._.push(arg);
      continue;
    }

    if (arg === '--help') {
      flags.help = true;
      continue;
    }

    const key = arg.slice(2);
    const next = argv[i + 1];
    if (!next || next.startsWith('--')) {
      flags[key] = true;
      continue;
    }

    flags[key] = next;
    i += 1;
  }
  return flags;
}

function normalizeScope(scope) {
  const value = String(scope || 'all').toLowerCase();
  if (value === 'lessons' || value === 'briefs' || value === 'all') {
    return value;
  }
  throw new Error(`Invalid scope "${scope}". Expected lessons, briefs, or all.`);
}

function getScopeDirs(scope) {
  if (scope === 'lessons') return [{ scope: 'lessons', dir: lessonsDir }];
  if (scope === 'briefs') return [{ scope: 'briefs', dir: briefsDir }];
  return [
    { scope: 'lessons', dir: lessonsDir },
    { scope: 'briefs', dir: briefsDir },
  ];
}

function listMarkdownFiles(dir) {
  if (!existsSync(dir)) return [];
  return readdirSync(dir)
    .filter(
      file => file.endsWith('.md') && file !== '_template.md' && file.toLowerCase() !== 'readme.md'
    )
    .filter(file => statSync(join(dir, file)).isFile())
    .sort((a, b) => a.localeCompare(b));
}

function firstMeaningfulLine(content) {
  const lines = content.split('\n');
  for (const line of lines) {
    const trimmed = line.replace(/^#+\s*/, '').trim();
    if (trimmed.length > 0) return trimmed;
  }
  return '(empty)';
}

function readMemoryEntries(scope) {
  const entries = [];
  for (const item of getScopeDirs(scope)) {
    const files = listMarkdownFiles(item.dir);
    for (const file of files) {
      const absolutePath = join(item.dir, file);
      const content = readFileSync(absolutePath, 'utf8');
      entries.push({
        scope: item.scope,
        name: file,
        path: absolutePath,
        workspacePath: toWorkspacePath(absolutePath),
        summary: firstMeaningfulLine(content),
        content,
        mtimeMs: statSync(absolutePath).mtimeMs,
      });
    }
  }
  return entries;
}

function runCli(cliPath, args) {
  const result = spawnSync(process.execPath, [cliPath, ...args], {
    cwd: repoRoot,
    encoding: 'utf8',
    stdio: ['ignore', 'pipe', 'pipe'],
  });

  const stdout = (result.stdout || '').trim();
  const stderr = (result.stderr || '').trim();

  let parsed = null;
  if (stdout) {
    try {
      parsed = JSON.parse(stdout);
    } catch {
      parsed = null;
    }
  }

  return {
    ok: result.status === 0,
    exitCode: result.status,
    data: parsed,
    stdout,
    stderr,
    command: ['node', toWorkspacePath(cliPath), ...args].join(' '),
  };
}

function runGraphCli(args) {
  return runCli(graphCliPath, args);
}

function runVectorCli(args) {
  return runCli(vectorCliPath, args);
}

// Read all loop definitions directly (fast, no spawn). Mirrors the runners' loaders
// but returns a compact, JSON-friendly catalog for agents to discover what exists.
function readLoopCatalog() {
  if (!existsSync(loopsDir)) return [];
  const loops = [];
  for (const file of readdirSync(loopsDir)) {
    if (!file.endsWith('.json') || file.startsWith('_')) continue;
    try {
      const loop = JSON.parse(readFileSync(join(loopsDir, file), 'utf8'));
      if (!loop || typeof loop.name !== 'string') continue;
      loops.push({
        name: loop.name,
        kind: loop.kind ?? 'convergence',
        description: loop.description ?? '',
        maxIterations: loop.maxIterations ?? null,
        metric:
          loop.metric && typeof loop.metric === 'object'
            ? { name: loop.metric.name ?? loop.name, direction: loop.metric.direction ?? null }
            : null,
        file: toWorkspacePath(join(loopsDir, file)),
      });
    } catch {
      // skip unparseable loop definitions
    }
  }
  return loops.sort((a, b) => a.name.localeCompare(b.name));
}

function printJson(data, code = 0) {
  process.stdout.write(`${JSON.stringify(data, null, 2)}\n`);
  process.exit(code);
}

function listToolsPayload() {
  return {
    tools: [
      {
        name: 'graph-status',
        description: 'Returns graph freshness and drift against HEAD.',
      },
      {
        name: 'graph-neighbors',
        description: 'Returns neighboring nodes for a graph node id.',
        input: { nodeId: 'string', depth: 'number?', type: 'string?' },
      },
      {
        name: 'graph-dependents',
        description: 'Returns files that depend on a file path.',
        input: { filePath: 'string' },
      },
      {
        name: 'graph-path',
        description: 'Returns a shortest path between two node ids.',
        input: { srcId: 'string', dstId: 'string' },
      },
      {
        name: 'graph-layers',
        description: 'Returns all architectural layers and counts.',
      },
      {
        name: 'graph-layer',
        description: 'Returns all nodes in a named layer.',
        input: { name: 'string' },
      },
      {
        name: 'graph-hubs',
        description: 'Returns highest-degree hubs.',
        input: { top: 'number?', type: 'string?' },
      },
      {
        name: 'memory-list',
        description: 'Lists harness memory lessons/briefs with summaries.',
        input: { scope: 'lessons|briefs|all' },
      },
      {
        name: 'memory-read',
        description: 'Reads a lesson or brief by name.',
        input: { scope: 'lessons|briefs|all', name: 'string' },
      },
      {
        name: 'memory-search',
        description: 'Searches lessons/briefs by filename, summary, and body.',
        input: { query: 'string', scope: 'lessons|briefs|all', limit: 'number?' },
      },
      {
        name: 'vector-status',
        description: 'Reports local vector-index status and corpus coverage.',
      },
      {
        name: 'vector-index',
        description: 'Builds or refreshes local embeddings for memory and graph corpora.',
        input: {
          scope: 'all|memory|lessons|briefs|graph',
          provider: 'ollama|lmstudio?',
          model: 'string?',
          host: 'string?',
          maxTextChars: 'number?',
          graphLimit: 'number?',
          timeoutMs: 'number?',
          force: 'boolean?',
          verbose: 'boolean?',
        },
      },
      {
        name: 'vector-search',
        description: 'Runs semantic retrieval over the local vector index.',
        input: {
          query: 'string',
          scope: 'all|memory|lessons|briefs|graph?',
          provider: 'ollama|lmstudio?',
          top: 'number?',
          minScore: 'number?',
          model: 'string?',
          host: 'string?',
          maxTextChars: 'number?',
          graphLimit: 'number?',
          timeoutMs: 'number?',
          force: 'boolean?',
          noAutoIndex: 'boolean?',
          verbose: 'boolean?',
        },
      },
      {
        name: 'harness-loops',
        description:
          'Lists available harness loops (convergence/workflow/experiment) with kind, description, and metric. Read-only; execute loops via the CLI, not MCP.',
      },
      {
        name: 'harness-report',
        description:
          'Returns aggregated harness metrics (loops, checks, rubric, experiments, recent runs, memory) as JSON. Read-only.',
      },
    ],
  };
}

function showHelp() {
  printJson({
    usage: {
      command: 'node scripts/harness/mcp-tools.mjs <tool> [--flags]',
      tools: TOOL_NAMES,
    },
    examples: [
      'node scripts/harness/mcp-tools.mjs list-tools',
      'node scripts/harness/mcp-tools.mjs graph-status',
      'node scripts/harness/mcp-tools.mjs graph-neighbors --node-id "file:backend/src/app.ts" --depth 2',
      'node scripts/harness/mcp-tools.mjs memory-search --query "tenant" --scope all --limit 5',
      'node scripts/harness/mcp-tools.mjs vector-search --query "tenant isolation" --scope all --top 8',
    ],
  });
}

function requireValue(flags, key, message) {
  const value = flags[key];
  if (typeof value !== 'string' || value.length === 0) {
    throw new Error(message);
  }
  return value;
}

function toPositiveInt(value, fallback) {
  if (value === undefined || value === true) return fallback;
  const number = Number(value);
  if (!Number.isFinite(number) || number < 1) {
    throw new Error(`Expected a positive integer, received: ${value}`);
  }
  return Math.floor(number);
}

function toFiniteNumber(value, fallback) {
  if (value === undefined || value === true) return fallback;
  const number = Number(value);
  if (!Number.isFinite(number)) {
    throw new TypeError(`Expected a finite number, received: ${value}`);
  }
  return number;
}

function pushFlagValue(args, flags, key) {
  if (flags[key] === undefined) return;
  args.push(`--${key}`, requireValue(flags, key, `--${key} requires a value`));
}

function pushPositiveFlagValue(args, flags, key) {
  if (flags[key] === undefined) return;
  const value = requireValue(flags, key, `--${key} requires a value`);
  args.push(`--${key}`, String(toPositiveInt(value)));
}

function pushNumberFlagValue(args, flags, key) {
  if (flags[key] === undefined) return;
  const value = requireValue(flags, key, `--${key} requires a value`);
  args.push(`--${key}`, String(toFiniteNumber(value)));
}

function pushBooleanFlag(args, flags, key) {
  if (flags[key] === undefined) return;
  if (flags[key] !== true) {
    throw new Error(`--${key} does not take a value`);
  }
  args.push(`--${key}`);
}

function handleGraphTool(toolName, flags) {
  if (!existsSync(graphCliPath)) {
    printJson({ ok: false, error: `graph CLI not found at ${graphCliPath}` }, 2);
  }

  let response;
  if (toolName === 'graph-status') {
    response = runGraphCli(['status', '--json']);
  } else if (toolName === 'graph-neighbors') {
    const nodeId = requireValue(flags, 'node-id', 'graph-neighbors requires --node-id');
    const args = ['neighbors', nodeId, '--json'];
    if (flags.depth) args.push('--depth', String(toPositiveInt(flags.depth, 1)));
    if (typeof flags.type === 'string') args.push('--type', flags.type);
    response = runGraphCli(args);
  } else if (toolName === 'graph-dependents') {
    const filePath = requireValue(flags, 'file-path', 'graph-dependents requires --file-path');
    response = runGraphCli(['dependents', filePath, '--json']);
  } else if (toolName === 'graph-path') {
    const srcId = requireValue(flags, 'src-id', 'graph-path requires --src-id');
    const dstId = requireValue(flags, 'dst-id', 'graph-path requires --dst-id');
    response = runGraphCli(['path', srcId, dstId, '--json']);
  } else if (toolName === 'graph-layers') {
    response = runGraphCli(['layers', '--json']);
  } else if (toolName === 'graph-layer') {
    const name = requireValue(flags, 'name', 'graph-layer requires --name');
    response = runGraphCli(['layer', name, '--json']);
  } else if (toolName === 'graph-hubs') {
    const args = ['hubs', '--json'];
    if (flags.top) args.push('--top', String(toPositiveInt(flags.top, 10)));
    if (typeof flags.type === 'string') args.push('--type', flags.type);
    response = runGraphCli(args);
  } else {
    throw new Error(`Unsupported graph tool: ${toolName}`);
  }

  printJson(response, response.ok ? 0 : 1);
}

function handleMemoryList(flags) {
  const scope = normalizeScope(flags.scope);
  const entries = readMemoryEntries(scope)
    .sort((a, b) => b.mtimeMs - a.mtimeMs)
    .map(entry => ({
      scope: entry.scope,
      name: entry.name,
      path: entry.workspacePath,
      summary: entry.summary,
      mtimeMs: entry.mtimeMs,
    }));
  printJson({ ok: true, scope, count: entries.length, entries });
}

function handleMemoryRead(flags) {
  const scope = normalizeScope(flags.scope || 'all');
  const name = requireValue(flags, 'name', 'memory-read requires --name');
  const normalizedName = name.endsWith('.md') ? name : `${name}.md`;

  const entries = readMemoryEntries(scope);
  const match = entries.find(entry => entry.name.toLowerCase() === normalizedName.toLowerCase());
  if (!match) {
    printJson({ ok: false, error: `Memory file not found: ${normalizedName}`, scope }, 1);
  }

  printJson({
    ok: true,
    scope: match.scope,
    name: match.name,
    path: match.workspacePath,
    summary: match.summary,
    mtimeMs: match.mtimeMs,
    content: match.content,
  });
}

function handleMemorySearch(flags) {
  const query = requireValue(flags, 'query', 'memory-search requires --query').toLowerCase();
  const scope = normalizeScope(flags.scope || 'all');
  const limit = toPositiveInt(flags.limit, 20);

  const entries = readMemoryEntries(scope)
    .map(entry => {
      const haystack = `${entry.name}\n${entry.summary}\n${entry.content}`.toLowerCase();
      const index = haystack.indexOf(query);
      return {
        ...entry,
        matchIndex: index,
      };
    })
    .filter(entry => entry.matchIndex >= 0)
    .sort((a, b) => {
      if (a.matchIndex !== b.matchIndex) return a.matchIndex - b.matchIndex;
      return b.mtimeMs - a.mtimeMs;
    })
    .slice(0, limit)
    .map(entry => ({
      scope: entry.scope,
      name: entry.name,
      path: entry.workspacePath,
      summary: entry.summary,
      mtimeMs: entry.mtimeMs,
    }));

  printJson({
    ok: true,
    scope,
    query,
    limit,
    count: entries.length,
    entries,
  });
}

function handleVectorTool(toolName, flags) {
  if (!existsSync(vectorCliPath)) {
    printJson({ ok: false, error: `vector CLI not found at ${vectorCliPath}` }, 2);
  }

  let response;
  if (toolName === 'vector-status') {
    response = runVectorCli(['status']);
  } else if (toolName === 'vector-index') {
    const args = ['index'];
    pushFlagValue(args, flags, 'scope');
    pushFlagValue(args, flags, 'provider');
    pushFlagValue(args, flags, 'model');
    pushFlagValue(args, flags, 'host');
    pushPositiveFlagValue(args, flags, 'max-text-chars');
    pushPositiveFlagValue(args, flags, 'graph-limit');
    pushPositiveFlagValue(args, flags, 'timeout-ms');
    pushBooleanFlag(args, flags, 'force');
    pushBooleanFlag(args, flags, 'verbose');
    response = runVectorCli(args);
  } else if (toolName === 'vector-search') {
    const query = requireValue(flags, 'query', 'vector-search requires --query');
    const args = ['search', '--query', query];
    pushFlagValue(args, flags, 'scope');
    pushFlagValue(args, flags, 'provider');
    pushPositiveFlagValue(args, flags, 'top');
    pushNumberFlagValue(args, flags, 'min-score');
    pushFlagValue(args, flags, 'model');
    pushFlagValue(args, flags, 'host');
    pushPositiveFlagValue(args, flags, 'max-text-chars');
    pushPositiveFlagValue(args, flags, 'graph-limit');
    pushPositiveFlagValue(args, flags, 'timeout-ms');
    pushBooleanFlag(args, flags, 'force');
    pushBooleanFlag(args, flags, 'no-auto-index');
    pushBooleanFlag(args, flags, 'verbose');
    response = runVectorCli(args);
  } else {
    throw new Error(`Unsupported vector tool: ${toolName}`);
  }

  printJson(response, response.ok ? 0 : 1);
}

function handleHarnessLoops() {
  const loops = readLoopCatalog();
  printJson({ ok: true, count: loops.length, loops });
}

function handleHarnessReport() {
  if (!existsSync(reportCliPath)) {
    printJson({ ok: false, error: `report CLI not found at ${reportCliPath}` }, 2);
  }
  const response = runCli(reportCliPath, ['--json']);
  printJson(response, response.ok ? 0 : 1);
}

function main() {
  const flags = parseArgs(process.argv.slice(2));
  const tool = flags._[0];

  if (flags.help || !tool) {
    showHelp();
    return;
  }

  if (tool === 'list-tools') {
    printJson(listToolsPayload());
    return;
  }

  if (tool.startsWith('graph-')) {
    handleGraphTool(tool, flags);
    return;
  }

  if (tool === 'memory-list') {
    handleMemoryList(flags);
    return;
  }

  if (tool === 'memory-read') {
    handleMemoryRead(flags);
    return;
  }

  if (tool === 'memory-search') {
    handleMemorySearch(flags);
    return;
  }

  if (tool.startsWith('vector-')) {
    handleVectorTool(tool, flags);
    return;
  }

  if (tool === 'harness-loops') {
    handleHarnessLoops();
    return;
  }

  if (tool === 'harness-report') {
    handleHarnessReport();
    return;
  }

  throw new Error(`Unknown tool: ${tool}`);
}

try {
  main();
} catch (error) {
  printJson(
    {
      ok: false,
      error: error instanceof Error ? error.message : String(error),
    },
    2
  );
}
