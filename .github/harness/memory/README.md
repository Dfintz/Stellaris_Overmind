# Agent Memory

> Committed, agent-agnostic memory so no agent rediscovers what a previous session already learned.
> Part of the [Agent Harness](../HARNESS.md). Read at session start; write back before session end.

Two complementary memory surfaces can exist in a project that adopts this harness:

| Surface                                    | What it remembers                                                                    | Who writes it                                                 |
| ------------------------------------------ | ------------------------------------------------------------------------------------ | ------------------------------------------------------------- |
| Knowledge graph (optional, see SETUP)      | Code structure: components, layers, dependencies, call sites                         | The graph pipeline (regenerate incrementally; commit results) |
| `.github/harness/memory/` (this directory) | Everything the graph can't: lessons, gotchas, settled decisions, Architecture Briefs | Any agent, following the protocol below                       |

The knowledge graph answers "how does this codebase fit together"; this directory answers "what did
we already learn the hard way". Consult both before discovery; neither replaces the project's own
coding-standards docs.

---

## Layout

```
memory/
├── README.md          # this protocol
├── lessons/           # one lesson per file — hard-won, non-obvious facts
│   └── _template.md
└── briefs/            # Architecture Briefs from harness stage 1 (Architect)
    └── README.md
```

## Read protocol (session start)

1. List `lessons/` and read the one-line summaries (first line of each file). Read a lesson in full
   only when it touches the task at hand.
2. Before architecting or implementing in an area, check `briefs/` for a prior Brief covering it —
   gate decisions already made there are not re-litigated, they are followed or explicitly
   challenged via the Feedback stage.
3. **Never auto-load `quarantine/`.** It holds autonomous, unreviewed writes (see
   [`quarantine/README.md`](./quarantine/README.md)). Only promoted entries in `lessons/` are trusted.

## Write protocol (when you learn something)

Write a lesson when you discover something **non-obvious that cost real effort** and that the repo's
existing docs don't record: a misleading error message and its actual cause, a tool or environment
quirk, a convention that exists but isn't written down, why an obvious-looking approach fails here.
Loop runs that end `stuck` or `exhausted` are prime lesson candidates — record the diagnosis so the
next attempt doesn't start from zero.

Rules (one lesson per file, format in [`lessons/_template.md`](./lessons/_template.md)):

- **First line is a one-line summary** — that's what future sessions scan.
- **Don't save what the repo already records.** Link it instead of copying it.
- **Update, don't duplicate.** If a lesson on the topic exists, amend it.
- **Delete lessons that turn out to be wrong.** Stale memory is worse than no memory.
- **Record corrections and confirmed approaches alike**, including _why_ they mattered.
- **Never store secrets, tokens, or PII.** This directory is committed.
- Filenames: `kebab-case` topic, e.g. `jest-esm-transform-quirk.md`.
- **Autonomous/untrusted-derived writes go to [`quarantine/`](./quarantine/README.md), not
  `lessons/`.** A human promotes them after review. A self-improving loop that writes straight to
  `lessons/` is a memory-poisoning vector — see `briefs/self-improving-harness.md`.

> This kit ships the protocol and structure only — no lessons. Your project's lessons accumulate
> here as agents work.
