# AGENTS.md

Entry point for any AI coding agent working in a repository that has adopted this harness.

**Start here:** read [`.github/harness/HARNESS.md`](.github/harness/HARNESS.md). It is the operating
contract — it tells you what to load, what sequence to follow, and how to iterate until done.

**Setting up the engine in this environment?** Run `node scripts/harness/doctor.mjs` for a preflight
and the MCP registration for your client. Per-environment recipes: [`docs/ENVIRONMENTS.md`](docs/ENVIRONMENTS.md).

Quick map:

- **Operating contract & stage machine:** [`.github/harness/HARNESS.md`](.github/harness/HARNESS.md)
- **Loop protocol (convergence / workflow / experiment):** [`.github/harness/LOOPS.md`](.github/harness/LOOPS.md)
- **Workflow stage instructions:** [`.github/instructions/`](.github/instructions/) (02–07)
- **Memory (read at session start, write before session end):** [`.github/harness/memory/`](.github/harness/memory/)
- **Machine-readable index:** [`.github/harness/registry.json`](.github/harness/registry.json)
- **Project commands & config:** [`harness.config.json`](harness.config.json)

Prompt routing shortcuts:

- `npm run harness:route -- --task "<prompt>"` — classify a prompt against the harness policy.
- `npm run harness:feature -- --task "<feature task>"` — print the full stage/model handoff.
- `npm run harness:handoff:review -- --task "<review task>"` — print the review-only handoff.
- `npm run harness:review` — run the plan-review workflow (backward-compatible behavior).

This file is intentionally short: it points at the harness rather than duplicating it. Replace this
note's specifics with your project's own conventions docs as needed.
