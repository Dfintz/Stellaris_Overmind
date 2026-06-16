#!/usr/bin/env node
// Attribution & adaptations: see CREDITS.md (autoresearch, Understand-Anything, MCP, Ollama, LM Studio).
/**
 * First-class MCP stdio server for harness graph + memory + vector tools.
 *
 * This server exposes the existing wrappers in scripts/harness/mcp-tools.mjs
 * over the MCP protocol using stdio transport.
 */
import { spawnSync } from 'node:child_process';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

// @modelcontextprotocol/sdk is an OPTIONAL dependency, loaded lazily only when the stdio server is
// actually started — so `--help` and `--list-tools` work without it, and a missing SDK yields a clear
// install hint instead of a raw ERR_MODULE_NOT_FOUND stack trace.
async function loadSdk() {
  try {
    const [{ Server }, { StdioServerTransport }, { CallToolRequestSchema, ListToolsRequestSchema }] =
      await Promise.all([
        import('@modelcontextprotocol/sdk/server/index.js'),
        import('@modelcontextprotocol/sdk/server/stdio.js'),
        import('@modelcontextprotocol/sdk/types.js'),
      ]);
    return { Server, StdioServerTransport, CallToolRequestSchema, ListToolsRequestSchema };
  } catch {
    throw new Error(
      'The MCP stdio server needs the optional @modelcontextprotocol/sdk package. Run `npm install` ' +
        'to add it. (`--list-tools` and scripts/harness/mcp-tools.mjs work without it.)'
    );
  }
}

const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const wrapperPath = join(repoRoot, 'scripts', 'harness', 'mcp-tools.mjs');

function objectSchema(properties = {}, required = []) {
  return {
    type: 'object',
    properties,
    required,
    additionalProperties: false,
  };
}

function parseArguments(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return {};
  }
  return value;
}

function readRequiredString(args, key) {
  const value = args[key];
  if (typeof value !== 'string' || value.trim().length === 0) {
    throw new Error(`Missing required argument: ${key}`);
  }
  return value;
}

function readOptionalString(args, key) {
  const value = args[key];
  if (value === undefined || value === null) return undefined;
  if (typeof value !== 'string') {
    throw new TypeError(`Argument ${key} must be a string`);
  }
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : undefined;
}

function readOptionalPositiveInt(args, key) {
  const value = args[key];
  if (value === undefined || value === null) return undefined;
  const number = Number(value);
  if (!Number.isFinite(number) || number < 1) {
    throw new Error(`Argument ${key} must be a positive integer`);
  }
  return Math.floor(number);
}

function readOptionalFiniteNumber(args, key) {
  const value = args[key];
  if (value === undefined || value === null) return undefined;
  const number = Number(value);
  if (!Number.isFinite(number)) {
    throw new TypeError(`Argument ${key} must be a finite number`);
  }
  return number;
}

function readOptionalBoolean(args, key) {
  const value = args[key];
  if (value === undefined || value === null) return undefined;
  if (typeof value !== 'boolean') {
    throw new TypeError(`Argument ${key} must be a boolean`);
  }
  return value;
}

function pushOptionalCliArg(args, name, value) {
  if (value === undefined) return;
  if (typeof value === 'boolean') {
    if (value) args.push(`--${name}`);
    return;
  }
  args.push(`--${name}`, String(value));
}

const toolSpecs = [
  {
    name: 'graph-status',
    description: 'Returns graph freshness and drift against HEAD.',
    inputSchema: objectSchema(),
    toCliArgs: () => [],
  },
  {
    name: 'graph-neighbors',
    description: 'Returns neighboring nodes for a graph node id.',
    inputSchema: objectSchema(
      {
        nodeId: {
          type: 'string',
          description: 'Graph node id, for example file:backend/src/app.ts',
        },
        depth: { type: 'integer', minimum: 1, description: 'Traversal depth (default 1)' },
        type: { type: 'string', description: 'Optional edge type filter' },
      },
      ['nodeId']
    ),
    toCliArgs: args => {
      const nodeId = readRequiredString(args, 'nodeId');
      const depth = readOptionalPositiveInt(args, 'depth');
      const edgeType = readOptionalString(args, 'type');

      const cliArgs = ['--node-id', nodeId];
      if (depth !== undefined) cliArgs.push('--depth', String(depth));
      if (edgeType) cliArgs.push('--type', edgeType);
      return cliArgs;
    },
  },
  {
    name: 'graph-dependents',
    description: 'Returns files that depend on a file path.',
    inputSchema: objectSchema(
      {
        filePath: { type: 'string', description: 'Workspace-relative file path' },
      },
      ['filePath']
    ),
    toCliArgs: args => ['--file-path', readRequiredString(args, 'filePath')],
  },
  {
    name: 'graph-path',
    description: 'Returns a shortest path between two node ids.',
    inputSchema: objectSchema(
      {
        srcId: { type: 'string', description: 'Source node id' },
        dstId: { type: 'string', description: 'Destination node id' },
      },
      ['srcId', 'dstId']
    ),
    toCliArgs: args => [
      '--src-id',
      readRequiredString(args, 'srcId'),
      '--dst-id',
      readRequiredString(args, 'dstId'),
    ],
  },
  {
    name: 'graph-layers',
    description: 'Returns all architectural layers and counts.',
    inputSchema: objectSchema(),
    toCliArgs: () => [],
  },
  {
    name: 'graph-layer',
    description: 'Returns all nodes in a named layer.',
    inputSchema: objectSchema(
      {
        name: { type: 'string', description: 'Layer name' },
      },
      ['name']
    ),
    toCliArgs: args => ['--name', readRequiredString(args, 'name')],
  },
  {
    name: 'graph-hubs',
    description: 'Returns highest-degree hubs.',
    inputSchema: objectSchema({
      top: { type: 'integer', minimum: 1, description: 'Maximum number of hubs (default 10)' },
      type: { type: 'string', description: 'Optional node type filter' },
    }),
    toCliArgs: args => {
      const top = readOptionalPositiveInt(args, 'top');
      const nodeType = readOptionalString(args, 'type');
      const cliArgs = [];
      if (top !== undefined) cliArgs.push('--top', String(top));
      if (nodeType) cliArgs.push('--type', nodeType);
      return cliArgs;
    },
  },
  {
    name: 'memory-list',
    description: 'Lists harness memory lessons/briefs with summaries.',
    inputSchema: objectSchema({
      scope: {
        type: 'string',
        enum: ['lessons', 'briefs', 'all'],
        default: 'all',
        description: 'Memory scope filter',
      },
    }),
    toCliArgs: args => {
      const scope = readOptionalString(args, 'scope');
      return scope ? ['--scope', scope] : [];
    },
  },
  {
    name: 'memory-read',
    description: 'Reads a lesson or brief by name.',
    inputSchema: objectSchema(
      {
        scope: {
          type: 'string',
          enum: ['lessons', 'briefs', 'all'],
          default: 'all',
          description: 'Memory scope filter',
        },
        name: { type: 'string', description: 'File name without .md is also accepted' },
      },
      ['name']
    ),
    toCliArgs: args => {
      const name = readRequiredString(args, 'name');
      const scope = readOptionalString(args, 'scope');
      const cliArgs = ['--name', name];
      if (scope) cliArgs.push('--scope', scope);
      return cliArgs;
    },
  },
  {
    name: 'memory-search',
    description: 'Searches lessons/briefs by filename, summary, and body.',
    inputSchema: objectSchema(
      {
        query: { type: 'string', description: 'Case-insensitive search query' },
        scope: {
          type: 'string',
          enum: ['lessons', 'briefs', 'all'],
          default: 'all',
          description: 'Memory scope filter',
        },
        limit: {
          type: 'integer',
          minimum: 1,
          description: 'Maximum number of results (default 20)',
        },
      },
      ['query']
    ),
    toCliArgs: args => {
      const query = readRequiredString(args, 'query');
      const scope = readOptionalString(args, 'scope');
      const limit = readOptionalPositiveInt(args, 'limit');

      const cliArgs = ['--query', query];
      if (scope) cliArgs.push('--scope', scope);
      if (limit !== undefined) cliArgs.push('--limit', String(limit));
      return cliArgs;
    },
  },
  {
    name: 'vector-status',
    description: 'Reports local vector-index status and corpus coverage.',
    inputSchema: objectSchema(),
    toCliArgs: () => [],
  },
  {
    name: 'vector-index',
    description: 'Builds or refreshes local embeddings for memory and graph corpora.',
    inputSchema: objectSchema({
      scope: {
        type: 'string',
        description: 'all|memory|lessons|briefs|graph (comma-separated allowed)',
      },
      provider: {
        type: 'string',
        description: 'Local LLM provider for embeddings: ollama (default) or lmstudio',
      },
      model: {
        type: 'string',
        description: 'Embedding model name (default nomic-embed-text)',
      },
      host: {
        type: 'string',
        description: 'Ollama host URL (default http://localhost:11434)',
      },
      maxTextChars: {
        type: 'integer',
        minimum: 1,
        description: 'Maximum characters embedded per document',
      },
      graphLimit: {
        type: 'integer',
        minimum: 1,
        description: 'Optional limit for graph nodes embedded in one run',
      },
      timeoutMs: {
        type: 'integer',
        minimum: 1,
        description: 'Embedding request timeout in milliseconds',
      },
      force: {
        type: 'boolean',
        description: 'Force re-embedding even when cached hashes match',
      },
      verbose: {
        type: 'boolean',
        description: 'Emit embedding progress to stderr',
      },
    }),
    toCliArgs: args => {
      const cliArgs = [];
      pushOptionalCliArg(cliArgs, 'scope', readOptionalString(args, 'scope'));
      pushOptionalCliArg(cliArgs, 'provider', readOptionalString(args, 'provider'));
      pushOptionalCliArg(cliArgs, 'model', readOptionalString(args, 'model'));
      pushOptionalCliArg(cliArgs, 'host', readOptionalString(args, 'host'));
      pushOptionalCliArg(cliArgs, 'max-text-chars', readOptionalPositiveInt(args, 'maxTextChars'));
      pushOptionalCliArg(cliArgs, 'graph-limit', readOptionalPositiveInt(args, 'graphLimit'));
      pushOptionalCliArg(cliArgs, 'timeout-ms', readOptionalPositiveInt(args, 'timeoutMs'));
      pushOptionalCliArg(cliArgs, 'force', readOptionalBoolean(args, 'force'));
      pushOptionalCliArg(cliArgs, 'verbose', readOptionalBoolean(args, 'verbose'));
      return cliArgs;
    },
  },
  {
    name: 'vector-search',
    description: 'Runs semantic retrieval over the local vector index.',
    inputSchema: objectSchema(
      {
        query: { type: 'string', description: 'Search query text' },
        scope: {
          type: 'string',
          description: 'all|memory|lessons|briefs|graph (comma-separated allowed)',
        },
        provider: {
          type: 'string',
          description: 'Local LLM provider for embeddings: ollama (default) or lmstudio',
        },
        top: {
          type: 'integer',
          minimum: 1,
          description: 'Maximum number of results to return',
        },
        minScore: {
          type: 'number',
          description: 'Optional cosine similarity lower bound',
        },
        model: { type: 'string', description: 'Embedding model name' },
        host: { type: 'string', description: 'Ollama host URL' },
        maxTextChars: {
          type: 'integer',
          minimum: 1,
          description: 'Max characters per embedded document',
        },
        graphLimit: {
          type: 'integer',
          minimum: 1,
          description: 'Optional graph node indexing limit',
        },
        timeoutMs: {
          type: 'integer',
          minimum: 1,
          description: 'Embedding request timeout in milliseconds',
        },
        force: {
          type: 'boolean',
          description: 'Force rebuild/re-embed before search',
        },
        noAutoIndex: {
          type: 'boolean',
          description: 'Disable automatic index build when coverage is missing',
        },
        verbose: {
          type: 'boolean',
          description: 'Emit indexing progress to stderr',
        },
      },
      ['query']
    ),
    toCliArgs: args => {
      const query = readRequiredString(args, 'query');
      const cliArgs = ['--query', query];
      pushOptionalCliArg(cliArgs, 'scope', readOptionalString(args, 'scope'));
      pushOptionalCliArg(cliArgs, 'provider', readOptionalString(args, 'provider'));
      pushOptionalCliArg(cliArgs, 'top', readOptionalPositiveInt(args, 'top'));
      pushOptionalCliArg(cliArgs, 'min-score', readOptionalFiniteNumber(args, 'minScore'));
      pushOptionalCliArg(cliArgs, 'model', readOptionalString(args, 'model'));
      pushOptionalCliArg(cliArgs, 'host', readOptionalString(args, 'host'));
      pushOptionalCliArg(cliArgs, 'max-text-chars', readOptionalPositiveInt(args, 'maxTextChars'));
      pushOptionalCliArg(cliArgs, 'graph-limit', readOptionalPositiveInt(args, 'graphLimit'));
      pushOptionalCliArg(cliArgs, 'timeout-ms', readOptionalPositiveInt(args, 'timeoutMs'));
      pushOptionalCliArg(cliArgs, 'force', readOptionalBoolean(args, 'force'));
      pushOptionalCliArg(cliArgs, 'no-auto-index', readOptionalBoolean(args, 'noAutoIndex'));
      pushOptionalCliArg(cliArgs, 'verbose', readOptionalBoolean(args, 'verbose'));
      return cliArgs;
    },
  },
  {
    name: 'harness-loops',
    description:
      'Lists available harness loops (convergence/workflow/experiment) with kind, description, and metric. Read-only; loops are executed via the CLI, not over MCP.',
    inputSchema: objectSchema(),
    toCliArgs: () => [],
  },
  {
    name: 'harness-report',
    description:
      'Returns aggregated harness metrics (loops, checks, rubric, experiments, recent runs, memory) as JSON. Read-only.',
    inputSchema: objectSchema(),
    toCliArgs: () => [],
  },
];

const toolByName = new Map(toolSpecs.map(spec => [spec.name, spec]));

function parseJsonIfPossible(value) {
  if (!value) return null;
  try {
    return JSON.parse(value);
  } catch {
    return null;
  }
}

function runWrapper(toolName, cliArgs) {
  const result = spawnSync(process.execPath, [wrapperPath, toolName, ...cliArgs], {
    cwd: repoRoot,
    encoding: 'utf8',
    stdio: ['ignore', 'pipe', 'pipe'],
  });

  const stdout = (result.stdout || '').trim();
  const stderr = (result.stderr || '').trim();
  const parsed = parseJsonIfPossible(stdout);

  const payload = parsed || {
    ok: result.status === 0,
    stdout,
    stderr,
    exitCode: result.status,
  };

  const ok =
    result.status === 0 && !(payload && typeof payload === 'object' && payload.ok === false);

  return {
    ok,
    payload,
    stdout,
    stderr,
    exitCode: result.status ?? 1,
  };
}

function toStructuredContent(value) {
  if (value && typeof value === 'object' && !Array.isArray(value)) {
    return value;
  }
  return undefined;
}

function textPayload(value) {
  return JSON.stringify(value, null, 2);
}

function showHelp() {
  const payload = {
    usage: {
      command: 'node scripts/harness/mcp-server.mjs',
      description: 'Starts MCP stdio server for harness graph/memory/vector tools.',
      options: {
        '--help': 'Show this help output and exit.',
        '--list-tools': 'Print server tool metadata and exit.',
      },
    },
    tools: toolSpecs.map(spec => ({
      name: spec.name,
      description: spec.description,
    })),
  };

  process.stdout.write(`${textPayload(payload)}\n`);
}

function showTools() {
  const payload = {
    tools: toolSpecs.map(spec => ({
      name: spec.name,
      description: spec.description,
      inputSchema: spec.inputSchema,
    })),
  };

  process.stdout.write(`${textPayload(payload)}\n`);
}

function createServer(sdk) {
  const { Server, ListToolsRequestSchema, CallToolRequestSchema } = sdk;
  const server = new Server(
    {
      name: 'sc-fleet-harness-mcp',
      version: '1.0.0',
    },
    {
      capabilities: {
        tools: {},
      },
      instructions:
        'Use harness graph, memory, and vector tools to query architecture context, dependency paths, and semantic retrieval over committed lessons/briefs/graph nodes.',
    }
  );

  server.setRequestHandler(ListToolsRequestSchema, async () => {
    return {
      tools: toolSpecs.map(spec => ({
        name: spec.name,
        description: spec.description,
        inputSchema: spec.inputSchema,
      })),
    };
  });

  server.setRequestHandler(CallToolRequestSchema, async request => {
    const toolName = request.params.name;
    const spec = toolByName.get(toolName);

    if (!spec) {
      return {
        isError: true,
        content: [
          {
            type: 'text',
            text: textPayload({ ok: false, error: `Unknown tool: ${toolName}` }),
          },
        ],
      };
    }

    let cliArgs;
    try {
      cliArgs = spec.toCliArgs(parseArguments(request.params.arguments));
    } catch (error) {
      return {
        isError: true,
        content: [
          {
            type: 'text',
            text: textPayload({
              ok: false,
              error: error instanceof Error ? error.message : String(error),
            }),
          },
        ],
      };
    }

    const result = runWrapper(toolName, cliArgs);
    const structuredContent = toStructuredContent(result.payload);

    if (!result.ok) {
      const errorPayload = {
        ok: false,
        tool: toolName,
        exitCode: result.exitCode,
        stderr: result.stderr || undefined,
        result: result.payload,
      };

      return {
        isError: true,
        structuredContent,
        content: [{ type: 'text', text: textPayload(errorPayload) }],
      };
    }

    return {
      structuredContent,
      content: [{ type: 'text', text: textPayload(result.payload) }],
    };
  });

  return server;
}

async function main() {
  const args = process.argv.slice(2);
  if (args.includes('--help') || args.includes('-h')) {
    showHelp();
    return;
  }

  if (args.includes('--list-tools')) {
    showTools();
    return;
  }

  const sdk = await loadSdk();
  const server = createServer(sdk);
  const transport = new sdk.StdioServerTransport();
  await server.connect(transport);
}

try {
  await main();
} catch (error) {
  process.stderr.write(
    `${textPayload({
      ok: false,
      error: error instanceof Error ? error.message : String(error),
    })}\n`
  );
  process.exit(1);
}
