# Stellaris Overmind — LLM‑Driven AI Overhaul for Stellaris 4.3.4

A **non‑cheating, expert‑level Stellaris AI** powered by a local LLM.

The AI plays within Stellaris 4.3.4 rules, respects fog‑of‑war, adapts to
ethics/civics/traits/origins, and makes macro‑strategic decisions like a
strong human player — live, without pausing the game.

<img width="1917" height="940" alt="image" src="https://github.com/user-attachments/assets/9a079a78-c705-4be8-937b-53e653e41902" />

## Features

- **Dual mode** — strategic advisor for the player; AI personality override for AI empires
- **Player mode** — displays suggestions in the TUI (the human decides and acts)
- **AI mode** — steers Stellaris’ native AI via personality overrides + stat modifiers (no queue bypass)
- **Multi-agent council** — domestic + military sub-agents with government-weighted arbitration
- **Strategic planner** — periodic long-term assessments injected into decision prompts
- **Hybrid LLM provider** — local (Ollama/vLLM), online (OpenRouter/Azure Foundry), or auto-failover hybrid
- **AI personality system** — 4 Clausewitz personality variants (balanced/aggressive/defensive/full assault) with 4.3.4 weapon meta
- **Policy enforcement** — Academic Privilege, war economy, cooperative stance applied automatically
- **Auto-detect empire** — reads ethics/civics/origin/government from save file (no manual config needed)
- **Live console dashboard** — Rich TUI with token rates, decision stats, suggestion panel, keyboard controls
- **Training pipeline** — SFT/DPO curation, teacher distillation, GPTQ/AWQ quantization, eval benchmarks
- **Fog-of-war safe** — all game state filtered by intel level before reaching the LLM

## Prerequisites

- **Python 3.11+** — [python.org](https://www.python.org/downloads/)
- **Stellaris 4.3.4** — Steam (non-Ironman saves recommended for AI mode)
- **GPU with ≥6GB VRAM** — for Qwen 7B Q4 via Ollama (or use a cloud API instead)

---

## Setup (first time)

### Option A: Automated setup (recommended)

```powershell
# From the project root:
.\scripts\setup.ps1
```

This will:
1. Install Python dependencies (`pip install -e ".[dev]"`)
2. Create `config.toml` from the example (auto-detects your Stellaris user dir)
3. Create the `ai_bridge/` directory
4. Symlink the mod into your Stellaris mod folder
5. Verify everything is in place

### Option B: Manual setup

```powershell
# 1. Clone and install
git clone https://github.com/youruser/Stellaris_Overmind.git
cd Stellaris_Overmind
pip install -e ".[dev,console]"

# 2. Create config
cp config.example.toml config.toml
# Edit config.toml — set save_dir and bridge_dir to your Stellaris paths

# 3. Link the mod into Stellaris
#    Windows (run as admin):
cmd /c mklink /J "C:\Users\YOU\Documents\Paradox Interactive\Stellaris\mod\stellaris_overmind" "mod\stellaris_overmind"
#    Copy the mod descriptor too:
cp mod\stellaris_overmind.mod "C:\Users\YOU\Documents\Paradox Interactive\Stellaris\mod\"

# 4. Enable the mod in the Stellaris launcher
```

### Install the LLM

**Ollama (recommended — fastest, simplest):**
```powershell
# Install Ollama from https://ollama.com
ollama pull qwen2.5:latest          # 7B Q4, ~5GB VRAM
```

**Docker vLLM (alternative — GPTQ quantized):**
```powershell
docker compose up qwen -d
```

**Cloud API (no GPU needed):**
Set `mode = "online"` in config.toml and configure `[llm.online]` with an
OpenAI-compatible endpoint (OpenRouter, Together, Azure AI Foundry, etc.).

---

## Running

### Player Mode (default) — Strategic Advisor

The engine watches your autosaves, runs the LLM, and shows you what to do next.
You stay in control — the AI just advises.

```powershell
# With Rich TUI dashboard (recommended):
python -m engine.main --console

# Plain logging (no TUI):
python -m engine.main
```

**How it works:**
1. Start the engine
2. Launch Stellaris → start/load a game with the Overmind mod enabled
3. The engine detects autosaves automatically (polls every 2s)
4. After each save, the LLM produces a suggestion (e.g. "FOCUS_TECH — Build research labs")
5. The suggestion appears in the TUI's yellow panel and is saved to `overmind_suggestion.txt`
6. You decide whether to follow it

**TUI keyboard controls:**
| Key | Action |
|-----|--------|
| `M` | Cycle LLM mode (local → online → hybrid) |
| `C` | Toggle multi-agent council |
| `P` | Toggle strategic planner |
| `R` | Toggle decision recording (for training) |
| `Q` | Quit |

### AI Mode — Steer AI Empires

The engine controls AI empires by overriding their Clausewitz personality
(aggressiveness, combat bravery, weapon preferences) and applying stat modifiers.
Stellaris's native AI handles all micro-decisions (build queues, research, fleets).

```powershell
# Set mode in config.toml:
#   [target]
#   mode = "ai"

# Then run:
python -m engine.main --console
```

**How it works:**
1. The engine reads the save file and identifies all AI empires
2. For each AI empire, it generates a ruleset from that empire's ethics/civics/origin
3. The LLM decides macro strategy (e.g. PREPARE_WAR, FOCUS_TECH)
4. The mod applies personality overrides + stat modifiers that nudge native AI behavior
5. Stellaris's native AI handles the actual execution (build order, fleet comp, etc.)

**AI mode config options (config.toml):**
```toml
[target]
mode = "ai"
# ai_country_ids = [1, 2, 5]     # specific country IDs (empty = all)
# ai_exclude_ids = [3]            # skip these
ai_exclude_fallen = true           # skip Fallen Empires
```

### Offline Testing (no GPU)

```powershell
python -m engine.main --provider stub
```

Uses a deterministic stub that returns valid actions — useful for testing
the pipeline without an LLM.

---

## Config Reference

Copy `config.example.toml` to `config.toml` and edit. Key sections:

| Section | Purpose |
|---|---|
| `[llm]` | Provider (`ollama`/`openai-compat`/`qwen-vllm`/`stub`), model, mode (`local`/`online`/`hybrid`), timeout |
| `[llm.online]` | Cloud API fallback — base_url, model, api_key |
| `[bridge]` | `save_dir` (autosave folder), `bridge_dir` (mod reads from here), `poll_interval_s` |
| `[empire]` | `auto_detect = true` (default) or manual: ethics, civics, traits, origin, government |
| `[target]` | `mode = "player"` (advisor) or `mode = "ai"` (AI empire control) |
| `[multi_agent]` | `enabled`, `parallel`, `arbiter_uses_llm` |
| `[planner]` | `enabled`, `interval_years`, optional separate provider |
| `[training]` | `replay_dir`, SFT/DPO thresholds, teacher model, quantization |

**Ollama config example:**
```toml
[llm]
provider = "ollama"
mode = "local"
base_url = "http://localhost:11434"
model = "qwen2.5:latest"
timeout_s = 60.0
```

**Cloud API config example:**
```toml
[llm]
provider = "openai-compat"
mode = "online"

[llm.online]
base_url = "https://openrouter.ai/api/v1"
model = "qwen/qwen-2.5-72b-instruct"
api_key = ""  # or set OVERMIND_LLM_ONLINE_API_KEY env var
```

---

## Stellaris Setup

1. **Enable the mod** — Stellaris launcher → Mods → enable "Stellaris Overmind"
2. **Autosave frequency** — Settings → Game → Autosave: Monthly (recommended)
3. **Non-Ironman** — AI mode requires non-Ironman saves for mod event access
4. **Start a game** — the engine auto-detects your empire from the save file

---

## Architecture Overview

```
┌─────────────────┐     autosave (.sav)     ┌─────────────────┐
│   Stellaris      │ ──────────────────────► │   Python Engine  │
│   (Clausewitz)   │                         │                  │
│                  │ ◄── personality flags    │  save_reader     │
│  native AI reads │     + stat modifiers     │  decision_engine │
│  personality +   │     (via mod events)     │  multi_agent     │
│  modifiers and   │                         │  strategic_planner│
│  makes its own   │  suggestion.txt ──────► │  bridge          │
│  micro decisions │  (player reads in TUI)  │  validator        │
└─────────────────┘                         └────────┬─────────┘
                                                     │
                                               ┌─────▼─────┐
                                               │  LLM       │
                                               │  (Ollama/  │
                                               │   vLLM/    │
                                               │   cloud)   │
                                               └───────────┘
```

## License

MIT
