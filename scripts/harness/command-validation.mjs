#!/usr/bin/env node
/**
 * CLI command guardrails for harness spawn points.
 *
 * Security goals:
 * - Allow only known executable names for model/agent command invocations.
 * - Reject shell metacharacters commonly used for command injection.
 */
import { basename } from 'node:path';

const DEFAULT_ALLOWED_EXECUTABLES = new Set([
  'codex',
  'claude',
  'gemini',
  'node',
  'npx',
  'npm',
  'ollama',
  'python',
  'python3',
]);

const SHELL_META_PATTERN = /[;&|`<>]|\$\(|\r|\n/;

function parseExecutable(command) {
  const text = String(command ?? '').trim();
  if (!text) return null;
  const pattern = /^(?:"([^"]+)"|'([^']+)'|(\S+))/;
  const match = pattern.exec(text);
  if (!match) return null;
  const raw = match[1] ?? match[2] ?? match[3] ?? '';
  const normalized = basename(raw).replace(/\.exe$/i, '').toLowerCase();
  return normalized || null;
}

export function validateCliCommand(command, opts = {}) {
  const label = opts.label ?? 'command';
  const allowedExecutables =
    opts.allowedExecutables instanceof Set
      ? opts.allowedExecutables
      : DEFAULT_ALLOWED_EXECUTABLES;

  const text = String(command ?? '').trim();
  if (!text) {
    return { ok: false, reason: `${label} is empty.` };
  }
  if (SHELL_META_PATTERN.test(text)) {
    return {
      ok: false,
      reason:
        `${label} contains shell metacharacters. ` +
        'Rejecting to prevent injection (blocked: ; & | ` < > $( ) newlines).',
    };
  }

  const executable = parseExecutable(text);
  if (!executable) {
    return { ok: false, reason: `${label} does not contain a valid executable token.` };
  }
  if (!allowedExecutables.has(executable)) {
    return {
      ok: false,
      reason: `${label} executable "${executable}" is not in allowlist: ${[...allowedExecutables].join(', ')}.`,
    };
  }

  return { ok: true, executable };
}

export function assertSafeCliCommand(command, opts = {}) {
  const result = validateCliCommand(command, opts);
  if (!result.ok) {
    throw new Error(result.reason);
  }
  return result;
}

function runSelfTest() {
  const okCases = ['claude -p', 'codex run', 'gemini --help', '"C:/Tools/node.exe" -v'];
  const badCases = ['claude -p; rm -rf /', 'bash -lc "echo hi"', 'evilcmd --x'];

  for (const cmd of okCases) {
    const result = validateCliCommand(cmd);
    if (!result.ok) {
      throw new Error(`Expected OK for: ${cmd} :: ${result.reason}`);
    }
  }
  for (const cmd of badCases) {
    const result = validateCliCommand(cmd);
    if (result.ok) {
      throw new Error(`Expected failure for: ${cmd}`);
    }
  }
  process.stdout.write('[command-validation] self-test passed\n');
}

if (
  import.meta.url === `file://${process.argv[1]}` ||
  import.meta.url === `file:///${process.argv[1]?.replaceAll('\\', '/')}`
) {
  if (process.argv.includes('--self-test')) {
    runSelfTest();
    process.exit(0);
  }
  const command = process.argv.slice(2).join(' ');
  const result = validateCliCommand(command, { label: 'cli command' });
  process.stdout.write(`${JSON.stringify(result)}\n`);
  process.exit(result.ok ? 0 : 1);
}
