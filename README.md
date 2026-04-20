# Stellaris Overmind — LLM‑Driven AI Overhaul for Stellaris 4.3.4

A **non‑cheating, expert‑level Stellaris AI** powered by a local LLM.

The AI plays within Stellaris 4.3.4 rules, respects fog‑of‑war, adapts to
ethics/civics/traits/origins, and makes macro‑strategic decisions like a
strong human player — live, without pausing the game.

## Features

- **Dual mode** — control the player's empire or replace AI empires
- **Multi-agent council** — domestic + military sub-agents with government-weighted arbitration
- **Strategic planner** — periodic long-term assessments injected into decision prompts
- **Hybrid LLM provider** — local (vLLM/Ollama), online (OpenRouter/Azure Foundry), or auto-failover hybrid
- **AI personality system** — 4 Clausewitz personality variants (balanced/aggressive/defensive/full assault) with 4.3.4 weapon meta
- **Policy enforcement** — Academic Privilege, war economy, cooperative stance applied automatically
- **Live console dashboard** — Rich TUI with token rates, decision stats, keyboard controls
- **Training pipeline** — SFT/DPO curation, teacher distillation, GPTQ/AWQ quantization, eval benchmarks
- **Fog-of-war safe** — all game state filtered by intel level before reaching the LLM

## Quick Start

```powershell
# 1. Start the LLM (Docker)
docker compose up qwen -d

# 2. Start the engine
python -m engine.main

# 3. In Stellaris console
run ai_commands.txt
```

Or with the Rich dashboard:
```powershell
python -m engine.main --console
```

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
engine/         Python AI engine (20+ modules)
  main.py         Entry point (--console, --provider)
  game_loop.py    GameLoopController + AILoopController
  multi_agent.py  Council orchestrator (domestic + military agents)
  strategic_planner.py  Long-term strategic assessments
  decision_engine.py    Single-agent prompt builder + parser
  save_reader.py  Clausewitz .sav parser → state snapshots
  bridge.py       Autosave watcher + directive writer + console commands
  hybrid_provider.py    Local/online/hybrid LLM failover
  validator.py    Fog-of-war + whitelist + ruleset validation
  config.py       All configuration dataclasses
  metrics.py      Runtime metrics aggregator
  console.py      Rich TUI dashboard
  prompt_cache.py Prompt prefix caching
  mcp_client.py   MCP server client (wiki, save analysis)
mod/            Clausewitz mod files
  events/         Monthly directive reader, player/AI init
  common/         On-actions, scripted effects, modifiers, AI personalities
training/       Model optimization pipeline
  evaluate.py     6-scenario benchmark suite
  curate.py       SFT + DPO dataset generation
  fine_tune.py    LoRA/QLoRA training (wandb, unsloth)
  distill.py      Teacher→student distillation
  quantize.py     GPTQ/AWQ quantization
scripts/        Utility scripts
  collect_teacher.py   Cloud teacher data collection
  upload_to_foundry.py Azure AI Foundry upload
  auto_execute.py      Auto-send console commands to Stellaris
examples/       Sample rulesets, events, and decisions
tests/          464 tests (pytest)
```

## Configuration

Copy `config.example.toml` to `config.toml` and edit. Key sections:

| Section | Purpose |
|---|---|
| `[llm]` | Provider, model, mode (local/online/hybrid), timeout |
| `[bridge]` | Save directory, bridge directory, poll interval |
| `[empire]` | Ethics, civics, traits, origin, government |
| `[target]` | Player or AI mode |
| `[multi_agent]` | Council enabled, parallel, arbiter |
| `[planner]` | Strategic planner enabled, interval |
| `[training]` | SFT/DPO thresholds, teacher model, quantization |

## Requirements

- Python 3.11+
- Stellaris 4.3.4 (non-Ironman for console commands)
- GPU with ≥6GB VRAM (for Qwen 7B GPTQ-Int4) or cloud API

## License

MIT
