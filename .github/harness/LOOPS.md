<!-- harness-kit: project-agnostic template. See SETUP.md and CREDITS.md. -->

> **Harness-kit template.** Loop commands resolve `{{tokens}}` from `harness.config.json`. Examples below are illustrative; adapt loops under `.github/harness/loops/` to your project. See SETUP.md.

# Loop Protocol — AI Agent Harness

> How any AI agent creates and runs bounded, goal-seeking iteration loops in this repository. Part
> of the [Agent Harness](./HARNESS.md).

A loop is the harness's answer to "keep going until it's actually done": re-run a check, fix what
failed using the project's skills, and repeat — with hard bounds so it can never spin forever.

---

## Loop Anatomy

Every loop is a JSON file in `.github/harness/loops/` with this shape:

```jsonc
{
  "name": "test-fix", // unique id, kebab-case, matches filename
  "kind": "convergence", // "convergence" | "workflow"
  "description": "…", // one sentence: what 'done' means
  "maxIterations": 5, // hard bound — loop MUST stop here
  "checks": [
    // commands that define convergence (exit 0 = pass)
    {
      "name": "backend-tests",
      "run": "npm test",
      "timeoutMs": 600000, // optional per-check timeout (default: none)
    },
  ],
  "rubric": [], // workflow loops: gradeable done-criteria (see below)
  "skills": ["testing"], // skills the fixing agent must load
  "instructions": [".github/instructions/04-IMPLEMENT.md"],
  "fixPrompt": "…", // instruction given to the agent on each failing iteration
  "guardrails": ["…"], // rules the loop may never violate while converging
  "onExhausted": "…", // what to do when maxIterations is hit without convergence
}
```

### Two kinds of loop

- **`convergence`** — done-ness is decided by shell commands (`checks`). These can be executed by
  `scripts/harness/run-loop.mjs` or natively by an agent. Order checks **cheapest first** (lint
  before type-check before build before tests) so each iteration gets the fastest possible feedback
  signal.
- **`workflow`** — done-ness is decided by agent judgment against the loop's `rubric`. `checks` may
  be empty; the `fixPrompt` describes the per-iteration procedure. These are executed natively by an
  agent only — the script runner will refuse them.
- **`experiment`** — there is no done-ness; the loop **optimizes a numeric `metric`** instead of
  converging on pass/fail. Each iteration the agent edits a focused `target`, the runner re-measures
  the metric and **keeps the edit only if it improved** (else reverts the target). Inspired by
  [karpathy/autoresearch](https://github.com/karpathy/autoresearch). Run with
  `scripts/harness/run-experiment.mjs` (use `--measure-only` to record just the baseline). Ends
  `converged` (net improvement), `exhausted` (budget spent, no gain), or `stuck` (no improvement for
  `noImprovementStop` iterations).

### Rubrics (workflow loops)

A workflow loop's `rubric` is a list of **explicit, independently gradeable criteria** — the
evaluator-optimizer pattern: the evaluation step grades each criterion separately and feeds the
specific gaps to the fix step. Write criteria that are checkable, not vibes: "no Blocker or Major
findings remain" grades cleanly; "the code looks good" produces noisy loops. The loop converges only
when **every** rubric item passes, and the iteration evaluating the rubric must be a genuine
re-examination — not a confirmation that the old findings are gone.

### Invariants (apply to every loop, no exceptions)

1. **Bounded.** `maxIterations` is mandatory. When exhausted, stop and follow `onExhausted` — which
   is always some form of "report honestly where you're stuck", never "try harder".
2. **Convergence must be real.** A check passes because the cause was fixed. Deleting a failing
   test, adding `any`, skipping a suite, loosening an assertion, or commenting out a lint rule is
   loop fraud — guardrails name the tempting shortcuts explicitly.
3. **Each iteration is informed.** Feed the failure output of iteration N _and the record of what
   iterations 1…N-1 attempted_ into the fix step of iteration N+1. A stateless retry that re-derives
   the same fix is a wasted iteration.
4. **No progress = stuck, immediately.** If two consecutive iterations produce the same failures for
   the same root cause, the loop is stuck — stop early and report, even with iterations left. The
   budget bounds the loop; it is not a quota to spend.
5. **Grounded reporting.** Every progress claim must point to evidence from this loop's run — a
   check that passed, a rubric item with its verdict, a diff that exists. "Fixed" means the check
   that failed now passes; anything not re-verified is reported as unverified, explicitly.
6. **Checkpointed.** Record the git baseline (commit + dirty state) before iteration 1, so any
   iteration's damage can be rolled back and the final report can say exactly what the loop changed.
   Never start a destructive fix from an unrecorded state.
7. **Scoped fixes.** A loop fixes what its checks cover. Discovering an unrelated bug mid-loop is
   reported, not fixed in-loop.

### Terminal states

Every loop run ends in exactly one of these, and the final report names which:

| State          | Meaning                                         | Runner exit code |
| -------------- | ----------------------------------------------- | ---------------- |
| `converged`    | All checks / rubric items pass                  | 0                |
| `exhausted`    | `maxIterations` reached with failures remaining | 1                |
| `stuck`        | No progress between consecutive iterations      | 3                |
| `blocked`      | Convergence would require violating a guardrail | report as stuck  |
| (config error) | Bad loop definition or arguments                | 2                |

---

## Native Execution (any agent)

Any agent can run any loop without the script. Treat the JSON as a protocol:

```
1. Read the loop JSON. Load every skill in `skills` and read every file in `instructions`.
2. Record the baseline: current commit, dirty/clean working tree.
3. iteration = 1; journal = []
4. Run all `checks` (or for workflow loops, grade every `rubric` item per `fixPrompt`).
5. All pass → terminal state `converged`; report and exit.
6. Any fail →
   a. If the failures match the previous iteration's (same checks, same root cause):
      terminal state `stuck`; report and exit — do not spend remaining iterations.
   b. If iteration == maxIterations: terminal state `exhausted`; follow `onExhausted`.
   c. If the only available fix violates a `guardrails` entry: terminal state `blocked`;
      report the conflict and exit.
   d. Otherwise apply `fixPrompt` to the failure output AND the journal of prior attempts.
      Append {iteration, what failed, what was changed} to the journal.
7. iteration += 1, go to 4.
```

Report at the end, every time: the terminal state, iterations used, final verdict per check or
rubric item (grounded in this run's output — nothing claimed that wasn't re-verified), what changed
per iteration (one line each, with the baseline commit for rollback), and any guardrail that
constrained a fix.

Then **record the run** so it shows up on the metrics dashboard. Convergence loops journal
themselves; for a workflow loop or stage, pipe the rubric verdicts to the recorder:

```bash
node scripts/harness/record-run.mjs --loop review-fix --state converged \
  --pass "Zero Blocker findings remain" --pass "Zero Major findings remain"
# or pipe a fuller spec (multi-iteration, per-stage) as JSON on stdin
```

**Claude Code:** the `run-loop` skill (`.claude/skills/run-loop/`) implements exactly this procedure
— invoke it with the loop name.

## Scripted Execution (convergence loops)

`scripts/harness/run-loop.mjs` runs convergence loops from any shell, delegating fixes to a
configurable agent CLI:

```bash
node scripts/harness/run-loop.mjs <loop-name> [options]

  --check-only          run checks and report; never invoke an agent
  --max-iterations N    override the loop's maxIterations (lower only)
  --agent "<cmd>"       agent command to receive the fix prompt on stdin
                        (default: $HARNESS_AGENT_CMD, else "claude -p")
  --list                list available loops
```

The runner implements the native procedure above: it records the git baseline, pipes the composed
fix prompt (fixPrompt + guardrails + skill paths + the attempt journal + truncated failure output)
to the agent command's stdin, re-runs the checks, and stops early when two consecutive iterations
fail identically. Each run writes a JSON journal (baseline, per-iteration check results and
durations, terminal state) to `.github/harness/runs/` (gitignored) for audit.

Local model example (optional) — works with **Ollama** (default) or **LM Studio**:

```bash
# Ollama (default, http://localhost:11434):
node scripts/harness/run-loop.mjs build-fix \
   --agent "node scripts/harness/ollama-agent.mjs --model qwen2.5-coder:14b"

# LM Studio (OpenAI-compatible, http://localhost:1234) — load a model in LM Studio first:
node scripts/harness/run-loop.mjs build-fix \
   --agent "node scripts/harness/ollama-agent.mjs --provider lmstudio --model <loaded-model-id>"
```

Provider also via env: `HARNESS_LLM_PROVIDER=lmstudio` (host `HARNESS_LLM_HOST`, model
`HARNESS_LLM_MODEL`). The same `--provider` flag works on `ollama-apply-agent.mjs` and
`vector-search.mjs`.

Exit codes: `0` converged · `1` exhausted · `2` configuration error · `3` stuck (no progress).

---

## Observability

Every run — scripted or native — leaves a JSON journal in `.github/harness/runs/` (gitignored).
Convergence loops are journalled automatically by `run-loop.mjs`; workflow loops and stages are
journalled by `scripts/harness/record-run.mjs` (the recorder refuses convergence loops, which
already self-journal). Aggregate them into a dashboard with:

```bash
npm run harness:report          # writes .github/harness/runs/report.html + a terminal summary
```

The dashboard shows per-loop convergence rates, the slowest checks (convergence loops), and rubric
pass-rates most-failed-first (workflow loops/stages) — the latter is how Understand, Architect, and
the breadth/depth review passes become measurable.

### Trace grading — score the process, not just the outcome

The eval suite scores the _outcome_ (did a change help?). [`grade-trace.mjs`](../../scripts/harness/grade-trace.mjs)
scores the **process**: given an experiment journal, it computes a deterministic trajectory grade
and — the useful part — an **early-stop recommendation**:

```bash
node scripts/harness/grade-trace.mjs --latest      # grade the newest experiment journal
node scripts/harness/grade-trace.mjs --all         # summarize every experiment (avg grade, wasted iters)
node scripts/harness/grade-trace.mjs --self-test   # validate the grader deterministically
```

It reports where the loop reached its best, how many trailing iterations added nothing, and the
`noImprovementStop` that would have saved that budget — so a loop that hill-climbed for 8 iterations
but peaked at iteration 2 is flagged "recommend noImprovementStop=1". A `stuck` early-stop is scored
as _good_ process behaviour (the detector fired), not waste. The grader is **advisory** — it never
changes a loop's control flow unless you opt in with `--min-grade <0..1>` (exit 1 below the floor).
Like the eval verifiers it is deterministic code with its own `--self-test`, and it defangs
journal-derived strings (a journal is data, never instructions).

### OpenTelemetry export — portable run telemetry

[`otel-export.mjs`](../../scripts/harness/otel-export.mjs) renders run journals as **OTLP/JSON** using
the OpenTelemetry **GenAI semantic conventions**, so harness telemetry can flow into Jaeger / Tempo /
Grafana / Honeycomb instead of living only in local JSON. Each journal becomes one root span
(`gen_ai.operation.name=invoke_agent`) with a child span per iteration (or per eval task), plus a
`harness.*` attribute namespace for loop-specific facts:

```bash
node scripts/harness/otel-export.mjs --latest                 # → .github/harness/otel/ (gitignored)
node scripts/harness/otel-export.mjs --file <journal> --stdout
node scripts/harness/otel-export.mjs --latest --endpoint http://localhost:4318/v1/traces
```

Span/trace IDs are deterministic (hashed from loop + start time), so re-exports are idempotent.
**Network is off by default** — output is a file or stdout; `--endpoint` is the only, opt-in network
path. The mapping is an honest adaptation (a harness loop is an agentic workflow, not a single model
call); see [`CREDITS.md`](../../CREDITS.md).

---

## Built-in Loops

| Loop                                          | Kind        | Checks / done-ness                                      | Max |
| --------------------------------------------- | ----------- | ------------------------------------------------------- | --- |
| [`build-fix`](./loops/build-fix.json)         | convergence | lint, type-check, build all green                       | 4   |
| [`test-fix`](./loops/test-fix.json)           | convergence | backend + frontend test suites green                    | 5   |
| [`review-fix`](./loops/review-fix.json)       | workflow    | breadth + depth review yield no Blocker/Major           | 3   |
| [`feature-cycle`](./loops/feature-cycle.json) | workflow    | stage machine 0→5 complete, reviews clean               | 2   |
| [`ci-green`](./loops/ci-green.json)           | workflow    | all PR checks green on remote                           | 5   |
| [`tdd-cycle`](./loops/tdd-cycle.json)         | workflow    | feature/bugfix built slice-by-slice, red→green→refactor | 5   |
| [`diagnose`](./loops/diagnose.json)           | workflow    | root cause named + regression test, no guess-fixing     | 5   |
| [`plan-review`](./loops/plan-review.json)     | workflow    | rival-model approves the plan (or flagged deadlock)     | 5   |

`feature-cycle` is the outermost loop: it runs the whole stage machine and uses `review-fix` as its
inner loop. `ci-green` is for remote/PR babysitting sessions and relies on the agent's PR event
tooling where available (e.g. Claude Code's `subscribe_pr_activity`) instead of polling. `tdd-cycle`
and `diagnose` are native workflow loops that enforce process discipline (test-first, evidence-first);
run them by following their rubric, not the script runner. `plan-review` has its own runner (below).

### Cross-model review (`plan-review`)

The deterministic eval scores _outcomes_ by code. `plan-review` scores the author's **judgment** by a
**different model** — a rival-provider reviewer that adversarially critiques before the same model
that produced the work signs off on it. The model that authored an artifact can't grade its own
artifact (echo chamber); a second provider catches what the first structurally can't see in itself.

It applies any of the harness **review lenses** via `--lens`, each referencing the matching stage
instruction so the rival holds the work to the SAME bar as the native pass:

| `--lens`   | Stage instruction   | Subject              | APPROVED means                                  |
| ---------- | ------------------- | -------------------- | ----------------------------------------------- |
| `plan`     | 03-ARCHITECT        | a plan / Brief       | no material concern remains (default)           |
| `breadth`  | 05-REVIEW-BREADTH   | a code change / diff | zero Blocker and zero Major findings remain     |
| `depth`    | 06-REVIEW-DEPTH     | a code change / diff | every architectural gate passes                 |
| `feedback` | 07-FEEDBACK         | challenges + change  | every challenged decision is resolved           |

```bash
# Plan (default lens): review-only — one rival pass; a human acts and re-runs.
node scripts/harness/plan-review.mjs --plan PLAN.md --reviewer "<rival-model CLI>"

# Breadth/depth: review a captured diff snapshot. Feed the breadth findings into depth as --context.
git diff main...HEAD > CHANGE.diff
node scripts/harness/plan-review.mjs --lens breadth --subject CHANGE.diff --reviewer "<rival CLI>"
node scripts/harness/plan-review.mjs --lens depth --subject CHANGE.diff --context BREADTH-FINDINGS.md --reviewer "<rival CLI>"

# Feedback: a rival evaluates review challenges with fresh eyes against the change.
node scripts/harness/plan-review.mjs --lens feedback --subject CHALLENGES.md --context CHANGE.diff --reviewer "<rival CLI>"

# Full loop (any lens): the author revises between rounds until APPROVED or a flagged deadlock.
node scripts/harness/plan-review.mjs --plan PLAN.md --reviewer "<model A>" --author "<model B>" --max-rounds 5
```

Use a **different** provider/model for `--reviewer` than authored the subject — that is the whole
point. Safety: the reviewer is **read-only** (the subject is hashed before/after each round; any
write is reverted and the round flagged); its critique **and** any `--context` (diffs, prior-pass
findings) are **untrusted**, wrapped + injection-defanged by
[`untrusted.mjs`](../../scripts/harness/untrusted.mjs) before any model consumes them; a cap reached
without approval is a **deadlock**, never relabelled "approved". It writes a `*-REVIEW-LOG.md` (the
round-by-round _why_) and journals to `runs/`, so reviews show on the dashboard and export via
`otel-export`. For **code** lenses the subject is a diff snapshot — to iterate on code _fixes_, drive
the native `review-fix` loop and use this as its rival reviewer; the verdict is uniform APPROVED |
REVISE across all lenses. Adapted from
[chaseai-yt/grill-me-codex](https://github.com/chaseai-yt/grill-me-codex) + Matt Pocock's grill-me
(MIT); see [`CREDITS.md`](../../CREDITS.md).

### Refusing dangerous git commands (`git-guard`)

[`git-guard.mjs`](../../scripts/harness/git-guard.mjs) is the executable form of the operational-
safety stance: a deterministic classifier that **blocks irreversible git commands** (force push,
`reset --hard`, `clean -f`, `--no-verify`, history rewrite) before they run. Wire it into an agent
pre-exec hook:

```bash
node scripts/harness/git-guard.mjs check "$CMD" || exit 1   # exit 1 = blocked
node scripts/harness/git-guard.mjs --explain               # list the rules
```

It never runs git — it only classifies the string (block / warn / allow). Override a block by running
the raw command yourself, deliberately. Adapted from Matt Pocock's git-guardrails (MIT).

### Experiments

| Loop                                                        | Kind       | Metric / goal                          | Max |
| ----------------------------------------------------------- | ---------- | -------------------------------------- | --- |
| [`lint-debt-experiment`](./loops/lint-debt-experiment.json) | experiment | backend ESLint warning count, minimize | 8   |

Experiments hill-climb a number rather than converge on green. Run one with
`node scripts/harness/run-experiment.mjs <name>` (or `npm run harness:experiment <name>`); add
`--measure-only` to record just the baseline metric for the dashboard without invoking an agent. The
runner snapshots **only** the declared `target` and reverts it on regression — it never runs
`git checkout`, so it cannot clobber unrelated uncommitted work.

#### Driving experiments with a local LLM (autoresearch-style)

A convergence agent only needs to _describe_ a fix, but an experiment agent must _apply_ one — the
runner re-measures files on disk and keeps the edit only if the metric improved. Use the **apply**
adapter so a local model actually rewrites the single declared `target`:

```bash
# One bounded experiment, edits driven by local qwen2.5-coder (Ollama):
node scripts/harness/run-experiment.mjs lint-debt-experiment \
  --agent "node scripts/harness/ollama-apply-agent.mjs --model qwen2.5-coder:14b"

# Same, but driven by a model loaded in LM Studio:
node scripts/harness/run-experiment.mjs lint-debt-experiment \
  --agent "node scripts/harness/ollama-apply-agent.mjs --provider lmstudio --model <loaded-model-id>"
```

`ollama-apply-agent.mjs` reads the target from `HARNESS_EXPERIMENT_TARGETS` (set by the runner),
asks the model for the complete updated file, and writes **only** that target — anything outside it
is never touched, and a bad rewrite is reverted by the keep-if-improved guard. It targets Ollama by
default or LM Studio via `--provider lmstudio` (env `HARNESS_LLM_PROVIDER`). Add `--commit` to
`run-experiment.mjs` to commit just the target after each kept improvement (a reviewable trail for
unattended runs).

For continuous overnight hill-climbing (≈ autoresearch's "100 experiments while you sleep"), the
loop runner repeatedly schedules `run-experiment.mjs` and journals every attempt to the dashboard:

```bash
# Rotate through all experiments forever, local model, commit kept wins:
npm run harness:experiment:ollama -- --commit

# Or scope + bound it explicitly:
node scripts/harness/experiment-loop.mjs --experiments lint-debt-experiment \
  --agent "node scripts/harness/ollama-apply-agent.mjs --model qwen2.5-coder:14b" \
  --interval-seconds 60 --max-cycles 50 --commit
```

It never edits code itself — it only schedules the runner, which owns the measure → apply →
keep-if-improved → journal protocol.

#### Meta-evolution: improving the harness itself (`harness-evolve`)

The experiment machinery can be pointed at a **harness artifact** instead of app code — evolving the
harness's own guidance and keeping an edit only if the **eval score** (the fitness function) rises.
This is the most dangerous loop, so it runs through a dedicated guarded runner, not `run-experiment`
directly:

```bash
# Validate the guards with NO agent (deterministic): safe target + healthy eval suite.
node scripts/harness/harness-evolve.mjs --check

# Evolve (autonomy OFF — improvements stay on disk for review, nothing is committed or pushed):
node scripts/harness/harness-evolve.mjs --agent "<your agent CLI>"

# Opt into committing each eval-verified improvement (only the target file, after integrity checks):
node scripts/harness/harness-evolve.mjs --agent "<cmd>" --commit --max-iterations 3
```

Two hard rules are enforced by [`evolve-guard.mjs`](../../scripts/harness/evolve-guard.mjs):

1. **RULE 1 — forbidden targets.** The loop's `target` may never resolve to the eval suite, any
   guardrail/security file, memory, config, or the evolve machinery itself. Checked at config time;
   the run fails fast. _A loop that can edit its own scorer reward-hacks in one iteration._
2. **RULE 2 — integrity tripwire.** The eval suite + every forbidden file is hashed before the run
   and re-checked before AND after every iteration. Any change aborts the run — that means the agent
   touched the scorer or a guardrail, which is exactly the tampering the guard exists to stop.

`run-eval --self-test` must pass before a run starts (no evolving against a broken scorer). Autonomy
is **off by default**; a real run also needs a live agent for both the edit and the eval scoring
(deterministic `--check` validates the safety machinery without one).

##### Feeding fresh field knowledge (the sensor)

The evolve agent can be handed an **external research brief** — e.g. a
[last30days](https://github.com/mvanhorn/last30days-skill) brief on current harness practice — as
**untrusted data**, so it incorporates what the field learned recently rather than only the model's
prior:

```bash
# Ingest a brief (stored raw + gitignored; a .meta.json records source + injection-marker count):
node scripts/harness/research-ingest.mjs --from last30days-brief.md --topic harness --source last30days

# Feed the newest brief into an evolve run (opt-in, loudly logged):
node scripts/harness/harness-evolve.mjs --agent "<cmd>" --research latest
```

The brief is **never executed and never committed**. It is wrapped + injection-defanged by
[`untrusted.mjs`](../../scripts/harness/untrusted.mjs) at the moment the agent sees it (via
`HARNESS_RESEARCH_FILE`). Because scraped internet content is the highest-risk input, this is opt-in,
autonomy stays off by default, and the human gate on the first commit is non-negotiable.

---

## Creating a Loop

1. Copy [`loops/_template.json`](./loops/_template.json) to `loops/<name>.json`.
2. Define **done** as commands if at all possible (`kind: "convergence"`). Only use
   `kind: "workflow"` when done-ness genuinely requires judgment — and then write a `rubric` of
   explicit, independently gradeable criteria (see Rubrics above).
3. Order `checks` cheapest-first and give long-running ones a `timeoutMs`.
4. Set `maxIterations` to the smallest number you'd accept watching by hand (2–5 is typical). Stuck
   detection ends hopeless runs early, so a generous bound costs little — but the bound is still
   mandatory.
5. Write `guardrails` for the shortcuts an agent would be tempted to take _for this specific loop_ —
   "do not delete the failing test", "do not widen the type", "do not bump the timeout".
6. Write `onExhausted` as a reporting instruction, never a retry instruction.
7. Add the loop to [`registry.json`](./registry.json) under `loops`.
8. Validate: `node scripts/harness/run-loop.mjs <name> --check-only` (convergence loops) or a dry
   read-through of the native procedure (workflow loops).

Keep loops composable: an outer workflow loop should reference inner loops by name in its
`fixPrompt` rather than duplicating their checks.
