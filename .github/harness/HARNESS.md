# AI Agent Harness — your project

Harness-kit template note: project-specific values (name, validation commands, model) come from
`harness.config.json`. The skill-routing tables and any multi-tenant (gate 4b) examples below are
illustrative from the kit's origin project. Replace them with your project's own skills and drop
gates that do not apply. See `SETUP.md` and `CREDITS.md`.

> **Audience:** Every AI coding agent working in this repository (Claude Code, GitHub Copilot,
> Codex, Cursor, Gemini, or any other). This document is agent-agnostic: it unifies all project
> skills and workflow instructions into one operating contract.

The harness answers three questions for any agent, on any task:

1. **What do I load?** → [Skill Routing](#skill-routing)
2. **What sequence do I follow?** → [Workflow Stage Machine](#workflow-stage-machine)
3. **How do I iterate until done?** → [Loops](#loops) (full protocol in [`LOOPS.md`](./LOOPS.md))

A machine-readable index of everything below lives in [`registry.json`](./registry.json).

---

## Default Prompt Routing

The kit ships a harness-first prompt routing policy through `scripts/harness/prompt-router.mjs` and
`harness.config.json`.

- `npm run harness:route -- --task "<prompt>"` classifies a prompt against the trivial/non-trivial policy.
- `npm run harness:feature -- --task "<feature task>"` or `npm run harness:handoff:feature -- --task "<feature task>"` prints the full operator handoff plan.
- `npm run harness:handoff:review -- --task "<review task>"` prints the review-only handoff plan.
- `npm run harness:review` runs the plan-review workflow (backward-compatible behavior).

### Model Roles In The Shipped Environment Policy

- **Claude Opus 4.8** owns **Understand, Architect, Review Breadth, Review Depth, and Feedback**.
- **GPT-5.3 Codex** owns **Implement** and targeted fix loops.
- **Cross-model review** runs Codex first, then Opus as the independent challenger.

---

## Authority Chain

When guidance conflicts, higher entries win:

1. `CLAUDE.md` and `.github/copilot-instructions.md` — coding standards, conventions, warnings
2. `.github/instructions/0*.md` — workflow stage instructions (this harness orchestrates them)
3. Skill files (`.github/skills/`, `.claude/skills/`) — domain patterns and checklists
4. This harness — orchestration, routing, and loop protocol

The harness never overrides standards; it tells you **when** to apply which document.

---

## Agent Adapters

The same skill content is published in two trees. Use the one your runtime loads natively and treat
the other as reference — do not load both copies of the same skill.

| Runtime                    | Native skills               | Native instructions                                        |
| -------------------------- | --------------------------- | ---------------------------------------------------------- |
| Claude Code                | `.claude/skills/*/SKILL.md` | `CLAUDE.md`, `.github/instructions/`                       |
| Copilot / Codex            | `.github/skills/*/SKILL.md` | `.github/copilot-instructions.md`, `.github/instructions/` |
| Other agents (Cursor, etc) | `.github/skills/*/SKILL.md` | `AGENTS.md` (repo root), `.github/instructions/`           |

Workflow-stage skills (`architect`, `implement`, `review-breadth`, `review-depth`, `feedback`) exist
only under `.claude/skills/` as invocable commands; non-Claude agents get identical content from the
corresponding `.github/instructions/0*.md` file.

---

## Workflow Stage Machine

Every non-trivial task moves through these stages. A task is **non-trivial** when it modifies more
than one file, changes APIs/shared types/routes/database behavior, or touches auth, security,
tenancy, caching, or infrastructure. Trivial one-file typo/doc fixes may skip straight to Implement.

```text
┌──────────────┐
│ 0 UNDERSTAND │  graph freshness + architecture discovery
└──────┬───────┘
       ▼
┌──────────────┐
│ 1 ARCHITECT  │  gates 1–5 → Architecture Brief
└──────┬───────┘
       ▼
┌──────────────┐     ┌────────────────────────────────────┐
│ 2 IMPLEMENT  │◄────┤ review-fix loop (Blocker/Major     │
└──────┬───────┘     │ findings route back to Implement)  │
       ▼             └────────────────▲───────────────────┘
┌──────────────┐                      │
│ 3 REVIEW     │  breadth pass ───────┤
│   (BREADTH)  │                      │
└──────┬───────┘                      │
       ▼                              │
┌──────────────┐                      │
│ 4 REVIEW     │  depth pass ─────────┘
│   (DEPTH)    │
└──────┬───────┘
       ▼
┌──────────────┐
│ 5 FEEDBACK   │  evaluate reviewer challenges → verdicts
└──────────────┘
```

### Stage Reference

| #   | Stage          | Instruction file                                 | Claude Code skill                        | Mandatory output                                                         |
| --- | -------------- | ------------------------------------------------ | ---------------------------------------- | ------------------------------------------------------------------------ |
| 0   | Understand     | `.github/instructions/02-UNDERSTAND-WORKFLOW.md` | `understand-process` (`.github/skills/`) | Component/layer impact map, graph status                                 |
| 1   | Architect      | `.github/instructions/03-ARCHITECT.md`           | `/architect`                             | Architecture Brief (files, decisions, constraints, Do-NOTs, assumptions) |
| 2   | Implement      | `.github/instructions/04-IMPLEMENT.md`           | `/implement`                             | Code + completed self-review checklist                                   |
| 3   | Review Breadth | `.github/instructions/05-REVIEW-BREADTH.md`      | `/review-breadth`                        | Findings list (severity-tagged)                                          |
| 4   | Review Depth   | `.github/instructions/06-REVIEW-DEPTH.md`        | `/review-depth`                          | Gate verdicts + structural findings                                      |
| 5   | Feedback       | `.github/instructions/07-FEEDBACK.md`            | `/feedback`                              | Verdict table + updated Brief (if changed)                               |

### Stage Contract (applies to every stage)

1. **Memory before discovery.** Consult the two memory surfaces before re-deriving anything: the
   committed knowledge graph (`.understand-anything/knowledge-graph.json`) for structure, and the
   harness memory store ([`memory/`](./memory/README.md)) for lessons and prior Architecture Briefs.
   Rediscovering what a previous session already recorded is wasted budget.
2. **Context Sufficiency Check first.** Every stage instruction begins with one. Inventory what you
   have, identify what you need, and request missing context before producing output. Never guess at
   an Architecture Brief, reviewer intent, or file contents you were not given.
3. **Carry artifacts forward — and persist them.** The Architecture Brief from stage 1 is input to
   stages 2, 4, and 5; save it to `memory/briefs/` per that directory's protocol so a later session
   inherits the gate decisions. Breadth findings from stage 3 are pasted into stage 4 to avoid
   duplication.
4. **Honor the gates.** Stages 1 and 4 run the five architectural gates (Domain Alignment,
   Generality, Data Ownership, Layer Boundaries, Reuse — plus 4b Multi-Tenant Isolation).
   Implementations that bypass a gate decision must be flagged, not silently merged.
5. **Close with status.** Non-trivial tasks end with the Understand status line (graph status, tools
   used, residual risk) per `02-UNDERSTAND-WORKFLOW.md`.

---

## Skill Routing

Load a skill **before** writing code in its area. Triggers below are matched against the task
description and the files being touched.

### Domain Skills

| Skill                 | Load when the task involves…                                            |
| --------------------- | ----------------------------------------------------------------------- |
| `backend-service`     | Services, controllers, routes, Joi schemas, entities, migrations        |
| `frontend-component`  | React components, pages, hooks, frontend services, React Query          |
| `full-stack-feature`  | End-to-end features spanning backend API + frontend UI + shared types   |
| `testing`             | Unit, integration, component, or E2E tests                              |
| `discord-bot`         | Slash commands, sharding, IPC, guild management, role sync              |
| `infrastructure`      | Bicep IaC, Azure Container Apps, Docker, GitHub Actions, deploy scripts |
| `security-encryption` | Auth, encryption, GDPR, consent, audit logging, TOTP/WebAuthn, SSO      |
| `star-citizen-domain` | Ships, fleets, activities, mining, trading, bounties, RSI sync, crew    |
| `understand-process`  | Any non-trivial change (always pairs with stage 0)                      |

Multiple skills can apply: a domain-specific feature loads `domain-specific` + `backend-service`; an
end-to-end feature with tests loads `full-stack-feature` + `testing`.

### Workflow Skills (stage executors)

`architect`, `implement`, `review-breadth`, `review-depth`, `feedback` — invoked explicitly per
stage (see Stage Reference table). They are not auto-loaded by topic; they are the stage.

---

## Validation Matrix

Run the narrowest command that covers the change; loops use these as their convergence checks.

| Scope touched       | Required before completion                                                                                         |
| ------------------- | ------------------------------------------------------------------------------------------------------------------ |
| Backend code        | `npm run lint --workspace=backend` · `npm run type-check` · `npm test --workspace=backend -- <changed>.test.ts`    |
| Frontend code       | `npm run lint --workspace=frontend` · `npm run type-check` · `npm test --workspace=frontend -- <changed>.test.tsx` |
| Shared types        | `npm run build --workspace=@<org>/<shared-types-package>` then rebuild dependents                             |
| Migrations/entities | Migration generated + backend tests pass                                                                           |
| API contract        | `npm run test:pact --workspace=backend` · `npm run test:openapi --workspace=backend`                               |
| Full feature        | All of the above for touched scopes; E2E if user-facing flow changed                                               |

Hard rules (from `CLAUDE.md`, restated because loops are tempted to violate them):

- Never skip, delete, or weaken a failing test to make a loop converge — fix the cause.
- Never reduce coverage below the 40% backend threshold.
- Never add `any` to silence the type-checker.
- Never touch `/api/v1/` routes or `docs-archive/`.

---

## Loops

A **loop** is a bounded, goal-seeking iteration: run a check, and while it fails, apply a fix
informed by the relevant skills, then re-check. Every loop must declare an **exit condition** (a
command for convergence loops, a gradeable rubric for workflow loops), a **max iteration count**,
and an **escalation** path — unbounded retry is forbidden. Every run ends in a named terminal state
(`converged`, `exhausted`, `stuck`, or `blocked`), records its git baseline before touching
anything, and reports only progress it can ground in check output or rubric verdicts.

Built-in loops (definitions in [`loops/`](./loops/), protocol and authoring guide in
[`LOOPS.md`](./LOOPS.md)):

| Loop            | Converges on                                 | Kind        |
| --------------- | -------------------------------------------- | ----------- |
| `build-fix`     | Lint + type-check + build green              | convergence |
| `test-fix`      | Workspace test suites green                  | convergence |
| `review-fix`    | No Blocker/Major findings from breadth+depth | workflow    |
| `feature-cycle` | Full stage machine (0→5) complete and clean  | workflow    |
| `ci-green`      | PR checks green on the remote                | workflow    |

Run a convergence loop from any shell or agent CLI:

```bash
node scripts/harness/run-loop.mjs test-fix            # native agent fixes between checks
node scripts/harness/run-loop.mjs build-fix --check-only   # report convergence state, no agent
```

Claude Code runs loops natively via the `run-loop` skill; other agents follow the loop JSON as a
protocol (see `LOOPS.md` § Native Execution). New loops are created by copying
`loops/_template.json` — see `LOOPS.md` § Creating a Loop.

Every run leaves a JSON journal in `.github/harness/runs/` (gitignored): convergence loops via
`run-loop.mjs`, workflow loops/stages via `scripts/harness/record-run.mjs`. Aggregate them into a
dashboard with `npm run harness:report` — per-loop convergence rates, slowest checks, and the rubric
pass-rates that make Understand/Architect/Review activity measurable.

---

## Harness Self-Improvement: Phase Integration Snapshot

The harness includes a closed-loop optimization path for its own guidance, with guarded evolution,
observability, and deterministic scoring.

### Phase 3 — Meta-Optimization Loop (`harness-evolve`)

- Target: `.github/harness/evolve/candidate-instructions.md` (editable guidance surface)
- Guardrails: forbidden target validation + suite integrity tripwire in
  `scripts/harness/evolve-guard.mjs`
- Iteration control: bounded loop with no-improvement early stop

Run with:

- `npm run harness:evolve`
- `npm run harness:evolve:dry-run`
- `npm run harness:evolve:check`

### Phase 4 — Observability

- Journals: `.github/harness/runs/*.jsonl`
- Dashboard: `npm run harness:report`
- OTLP/JSON export: `npm run harness:otel`

### Phase 5 — Outcome Scoring & Feedback

- Trajectory scorer: `npm run harness:grade`
- Self-test checks: `npm run harness:grade:self-test`, `npm run harness:evolve:self-test`
- Feedback path: run -> journal -> grade -> evolve adjustment -> next measured cycle

See `LOOPS.md` for scoring semantics and loop protocol details.

---

## Memory

Persistent, committed memory keeps sessions from rediscovering what earlier sessions learned. Full
protocol: [`memory/README.md`](./memory/README.md).

- **Structure** — `.understand-anything/knowledge-graph.json` (Understand-Anything graph:
  components, layers, dependencies; edges carry a `confidence` tag — `EXTRACTED` for AST-derived
  facts). Committed; refresh incrementally with `/understand` and commit the result. Caches under
  `.understand-anything/` stay gitignored. **Query it, don't read it** — the graph is
  multi-megabyte;
  `npm run harness:graph -- <status|banner|neighbors|dependents|path|layers|layer|hubs>` returns
  only the slice you need (`scripts/harness/graph.mjs`). `status` is the freshness gate from
  stage 0.
- **Lessons** — `memory/lessons/`: one non-obvious, hard-won fact per file; first line is the
  scannable summary. Write via the `remember` skill (Claude Code) or the protocol directly.
  Agent-local lesson stores (e.g. Copilot's memory tool) are promoted into this committed store with
  `npm run harness:migrate-memory`.
- **Briefs** — `memory/briefs/`: Architecture Briefs persisted from stage 1, updated by stage 5.
  Settled unless challenged through the Feedback stage.

Memory coverage is observable: `npm run harness:report` surfaces committed lesson count, Brief
count/status, and knowledge-graph freshness alongside the loop metrics.

Memory is consulted at stage 0 of every non-trivial task (see Stage Contract) and written back
whenever a session learns something the next one shouldn't have to re-derive — including the
diagnosis from any loop that ends `stuck` or `exhausted`.

### Optional: context compression

For long loop runs, [Headroom](https://github.com/chopratejas/headroom) can wrap the agent CLI to
compress tool outputs and logs before they reach the model (`pip install "headroom-ai[all]"`, then
`HARNESS_AGENT_CMD="headroom wrap claude -p"` or `--agent "headroom wrap claude -p"` on the loop
runner). It is an efficiency adapter, not a dependency — nothing in the harness requires it.

---

## Optional Local AI Tooling

Implemented scaffolding (optional, all adapters):

1. **MCP wrappers plus first-class stdio transport.** `scripts/harness/mcp-tools.mjs` exposes stable
   JSON command wrappers for `graph.mjs` plus `memory/lessons/` and `memory/briefs/`, and
   `scripts/harness/mcp-server.mjs` exposes the same tools through MCP tool schema + stdio
   transport: `npm run harness:mcp -- list-tools` and `npm run harness:mcp:server`.
2. **Dockerized deterministic graph refresh.** `scripts/harness/refresh-graph.mjs` runs
   scan/import/build/validate/save with plugin scripts and core APIs. Optional sidecar profile
   (`graph-refresh`) runs `scripts/harness/graph-refresh-loop.mjs` continuously:
   `UNDERSTAND_PLUGIN_ROOT=<path> npm run dev:up:graph-refresh`.
3. **Local Ollama adapter for loop runner fan-out.** `scripts/harness/ollama-agent.mjs` consumes the
   loop runner prompt from stdin and calls `/api/generate` on Ollama. Use with:
   `npm run harness:loop -- build-fix --agent "node scripts/harness/ollama-agent.mjs --model qwen2.5-coder:14b"`.
4. **Optional local embeddings + vector retrieval tier.** `scripts/harness/vector-search.mjs` can
   index semantic vectors over committed memory plus graph nodes, then run cosine retrieval:
   `npm run harness:vector -- index --scope all` and
   `npm run harness:vector -- search --query "tenant isolation" --scope all --top 8`.

Guardrail: keep local models on low-stakes/high-volume work (lint/format, triage, enrichment). Do
not route architecture gates, multi-tenant isolation, or security review decisions to local models.

---

## Maintenance Principle

Every harness component exists to compensate for something the current models can't yet do reliably
on their own. As models improve, some scaffolding becomes unnecessary — prune it rather than letting
it ossify. The `Model:` lines at the top of each `.github/instructions/0*.md` and the stage skills
are **advisory provenance, not a runtime requirement**: any capable agent runs these stages. Treat a
component that no longer earns its context cost as debt to remove.
