# Stellaris Overmind — LLM‑Driven AI Overhaul for Stellaris 4.3.4

A **non‑cheating, expert‑level Stellaris AI** powered by a local LLM.

The AI plays within Stellaris 4.3.4 rules, respects fog‑of‑war, adapts to
ethics/civics/traits/origins, and makes macro‑strategic decisions like a
strong human player — live, without pausing the game.

## Quick Links

- [Project Overview](docs/PROJECT_OVERVIEW.md) — full specification
- [Ruleset Spec](docs/RULESET_SPEC.md) — how rulesets work
- [Patch Meta 4.3.4](docs/META_4.3.4.md) — curated strategic meta
- [Personality System](docs/PERSONALITY_SYSTEM.md) — leader shards & government weighting
- [Exporter Spec](docs/EXPORTER_SPEC.md) — game state → JSON
- [Executor Spec](docs/EXECUTOR_SPEC.md) — LLM directives → game actions

## Repository Structure

```
docs/           Project specs and contributor docs
engine/         Python AI engine (ruleset generator, decision engine, validator)
mod/            Clausewitz mod files (game integration)
examples/       Sample rulesets, events, and decisions
```

## Status

**Early development** — architecture defined, engine scaffolded, specs written.

## License

TBD
