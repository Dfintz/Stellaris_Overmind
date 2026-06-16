# Credits & Citations

This harness-kit is an original orchestration layer, but several of its ideas and components are
adapted from prior work. Attributions below; inline source links also appear in the header comments
of the adapted files.

## Direct inspirations

### karpathy/autoresearch — experiment loop

- **Source:** https://github.com/karpathy/autoresearch (MIT)
- **What we adapted:** the autonomous, metric-optimizing "experiment" loop — edit a focused target,
  re-measure a single numeric metric, **keep the edit only if it improved, else revert**, and repeat
  under a bounded budget while journaling every attempt.
- **Where:** [`scripts/harness/run-experiment.mjs`](scripts/harness/run-experiment.mjs),
  [`scripts/harness/experiment-loop.mjs`](scripts/harness/experiment-loop.mjs),
  [`.github/harness/loops/lint-debt-experiment.json`](.github/harness/loops/lint-debt-experiment.json).
- **How we differ:** autoresearch optimizes a single-GPU LLM training run (`val_bpb`); here the same
  hill-climb pattern is generalized to any shell-measurable code metric (lint/type/test/size), the
  agent is pluggable (any CLI, including a local model), and reverts are in-memory snapshots of the
  declared target only (never `git reset`).

### Egonex-AI/Understand-Anything — knowledge graph

- **Source:** https://github.com/Egonex-AI/Understand-Anything
- **What we adapted:** the deterministic code knowledge-graph that the harness treats as structural
  memory, and the graph-refresh sidecar that regenerates it.
- **Where:** [`scripts/harness/graph-refresh-loop.mjs`](scripts/harness/graph-refresh-loop.mjs),
  [`scripts/harness/refresh-graph.mjs`](scripts/harness/refresh-graph.mjs),
  [`scripts/harness/Dockerfile.graph-refresh`](scripts/harness/Dockerfile.graph-refresh).
- **Note:** the graph features require a local checkout of that plugin (see `SETUP.md`); the rest of
  the harness works without it.

### Model Context Protocol (MCP)

- **Source:** https://modelcontextprotocol.io · SDK: https://github.com/modelcontextprotocol
- **What we adapted:** exposing the harness's graph / memory / vector tools over MCP so any
  MCP-aware agent can call them.
- **Where:** [`scripts/harness/mcp-server.mjs`](scripts/harness/mcp-server.mjs),
  [`scripts/harness/mcp-tools.mjs`](scripts/harness/mcp-tools.mjs).

### Ollama — local LLM runtime

- **Source:** https://ollama.com
- **What we adapted:** local, zero-cost model inference for loop agents and embeddings, so the
  improvement loops can run without a hosted API.
- **Where:** [`scripts/harness/llm-provider.mjs`](scripts/harness/llm-provider.mjs),
  [`scripts/harness/ollama-agent.mjs`](scripts/harness/ollama-agent.mjs),
  [`scripts/harness/ollama-apply-agent.mjs`](scripts/harness/ollama-apply-agent.mjs),
  [`scripts/harness/vector-search.mjs`](scripts/harness/vector-search.mjs).

### LM Studio — local LLM runtime (OpenAI-compatible)

- **Source:** https://lmstudio.ai
- **What we adapted:** an alternative local runtime via its OpenAI-compatible API
  (`/v1/chat/completions`, `/v1/embeddings`), selectable alongside Ollama with `--provider lmstudio`.
- **Where:** [`scripts/harness/llm-provider.mjs`](scripts/harness/llm-provider.mjs) (shared adapter
  used by the agents and vector search).

### Anthropic Agent Skills / Claude Code & GitHub Copilot

- **Source:** https://docs.claude.com (Agent Skills) · https://github.com/features/copilot
- **What we adapted:** the "skills + workflow instructions" structuring and the multi-agent adapter
  idea (the same content served to Claude Code, Copilot/Codex, and other runtimes).
- **Where:** the workflow stage machine in
  [`.github/harness/HARNESS.md`](.github/harness/HARNESS.md) and the stage instructions under
  [`.github/instructions/`](.github/instructions/).

### chaseai-yt/grill-me-codex — cross-model adversarial plan review

- **Source:** https://github.com/chaseai-yt/grill-me-codex (MIT)
- **What we adapted:** the two-act pattern's Act 2 — a rival, cross-provider model reviews a locked
  plan READ-ONLY over bounded rounds, the author revises between rounds, and a cap reached without
  approval is a flagged deadlock (never a fake "approved"). Two artifacts: the plan (the _what_) and
  a round-by-round review log (the _why_).
- **Where:** [`scripts/harness/plan-review.mjs`](scripts/harness/plan-review.mjs),
  [`.github/harness/loops/plan-review.json`](.github/harness/loops/plan-review.json).
- **How we differ:** provider-agnostic (any two CLIs over stdin, including local models), the reviewer
  critique is wrapped + injection-defanged as untrusted data before the author sees it, read-only is
  enforced by hashing the subject before/after each round (revert + flag on a write), and each run
  journals to `runs/` so it grades + exports through the existing observability. We replay the full
  prior-round log each round (stateless) instead of resuming one reviewer session, and we generalize
  the cross-model reviewer beyond plans to **all harness review lenses** via `--lens` (breadth, depth,
  feedback), each referencing the matching stage instruction so the rival applies the same bar.

### Matt Pocock — Skills For Real Engineers

- **Source:** https://github.com/mattpocock/skills (MIT)
- **What we adapted:** the `grill-me` / `grill-with-docs` alignment-interrogation idea (interview the
  human one question at a time, build a shared language in `CONTEXT.md`, record decisions as ADRs),
  and `git-guardrails` (block dangerous git commands). Act 1 of grill-me-codex is also his work.
- **Where:** [`skills/grill/SKILL.md`](skills/grill/SKILL.md),
  [`.github/harness/templates/CONTEXT.template.md`](.github/harness/templates/CONTEXT.template.md),
  [`.github/harness/templates/adr.template.md`](.github/harness/templates/adr.template.md),
  [`scripts/harness/git-guard.mjs`](scripts/harness/git-guard.mjs).
- **How we differ:** the grill skill is wired into the harness stage machine (it feeds Architect and
  pairs with the `plan-review` loop), and git-guardrails is generalized from a Claude-Code-only hook
  into an agent-neutral deterministic classifier with a `--self-test`, usable from any runtime.

## Original to this kit

- The unified harness contract (skill routing + stage machine + loop protocol), the five
  architectural review gates, the convergence/workflow/experiment loop taxonomy, the config-token
  layer (`harness.config.json` + `scripts/harness/config.mjs`), the live metrics dashboard
  (`scripts/harness/report-server.mjs`), and the deterministic trajectory critic
  (`scripts/harness/grade-trace.mjs`) that scores a loop's _process_ and recommends early-stopping.
- The harness-native framing of the adapted patterns above: the `plan-review` loop as a first-class
  workflow loop (read-only reviewer + untrusted-wrapped critique + run journaling), the agent-neutral
  `git-guard` classifier, and the `tdd-cycle` / `diagnose` workflow loops as rubric-graded process
  discipline.

## Foundations & reference harnesses

These shaped the design and vocabulary; no code was copied from them.

- **Pi** (Earendil, MIT) — https://pi.dev/docs/latest — a minimal terminal coding harness. We adapted
  its **structured compaction/handoff summary format** (Goal / Constraints / Progress / Key Decisions
  / Next Steps / Critical Context + read/modified files) as the context-discipline convention in
  [`HARNESS_CARD.md`](HARNESS_CARD.md), and its candid security stance ("no built-in sandbox"; real
  isolation must come from a container/VM; prompt injection from untrusted content cannot be reliably
  prevented in-process) reinforced this kit's threat model.
- **OpenAI — Harness Engineering** — https://openai.com/index/harness-engineering/ — repo-local
  instructions, architectural constraints, validation, telemetry.
- **Anthropic — Effective harnesses for long-running agents** —
  https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents — self-verification
  and handoff artifacts across many context windows.
- **Agent Skill evals** — OpenAI _Testing Agent Skills with Evals_ and OpenHands _How to Evaluate
  Agent Skills_ — the no-skill-baseline + deterministic-verifier approach behind
  [`scripts/harness/eval/`](scripts/harness/eval/).
- **awesome-harness-engineering** (CC0) — https://github.com/walkinglabs/awesome-harness-engineering —
  the field map (CAR / HarnessCard framing, evals & observability, Lurkr capability-risk scanning)
  that informed the HarnessCard and the `dangerous-diff` control.
- **dpolivaev/spec-loop** (MIT) — https://github.com/dpolivaev/spec-loop — a design-first skill
  framework (write the next _small_ spec → review → implement with tests → repeat). Reinforced the
  kit's incremental Architect→Implement→Review cadence and the value of keeping the spec local to the
  next step; no code was copied.
- **OpenTelemetry — GenAI semantic conventions** —
  https://opentelemetry.io/docs/specs/semconv/gen-ai/ — the attribute vocabulary (`gen_ai.*`,
  agent-invocation spans) that [`scripts/harness/otel-export.mjs`](scripts/harness/otel-export.mjs)
  emits so run journals are portable into any OTel backend. We adapt it: a harness loop is an agentic
  workflow, not a single model call, so the loop maps to an agent-invocation span with iteration/task
  child spans, and loop-specific facts live under a `harness.*` namespace.

## License

Released under the MIT License (see `LICENSE`). Adapted components retain their upstream licenses;
where a file adapts upstream work, its header notes the source.
