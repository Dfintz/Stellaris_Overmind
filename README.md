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
- **Hybrid LLM provider** — local (Ollama/LM Studio/vLLM), online (OpenRouter/Azure Foundry), or auto-failover hybrid
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

### Option A: Interactive wizard (recommended)

```powershell
pip install -e ".[dev,console]"
python -m engine --setup
```

The wizard will:
1. Auto-detect your Stellaris install path (scans Steam libraries)
2. Auto-detect your save games directory (supports OneDrive)
3. Detect running Ollama and available models
4. Let you choose: AI mode or Player advisor mode
5. Configure council, planner, fast decisions, recording
6. Generate `config.toml` automatically
7. **Install the mod** into your Stellaris mod folder (junction + descriptor)

The wizard also runs automatically on first launch if no config exists.
After setup, just enable "Stellaris Overmind" in the Stellaris launcher → Mods.

Supports network LLM endpoints — enter `http://192.168.1.100:11434` for
Ollama on another machine, or any OpenAI-compatible URL.

### Option B: PowerShell setup script

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

### Option C: Manual setup

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
# Or for sub-agents (faster, smaller):
ollama pull qwen2.5:3b              # 3B Q4, ~2GB VRAM
```

**LM Studio (alternative — parallel requests, GUI):**
```
# Download from https://lmstudio.ai
# Search and download: Qwen2.5 3B Instruct (Q4_K_M)
# Recommended settings: Context=4096, GPU Offload=max, Concurrent Predictions=4
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
| `F` | Toggle fast decisions (code-only for trivial cases) |
| `L` | Open live log viewer in a new terminal window |
| `O` | Open options/setup wizard in a new terminal |
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
fast_decisions = true              # code-only fast path for trivial decisions
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

## Meta Management

The engine's strategic knowledge is version-locked. When Stellaris gets a new
patch, the meta rules need updating. Meta files live in `docs/meta/` as
structured JSON.

**Scaffold a new version's meta:**
```powershell
# From the latest save file (auto-detects version):
python scripts/scaffold_meta.py --detect

# For a specific version (copies from existing):
python scripts/scaffold_meta.py 4.5.0 --from 4.3.4

# List available meta versions:
python scripts/scaffold_meta.py --list
```

**Recommended sources for updating meta:**
| Source | What it provides |
|---|---|
| [Stellaris Wiki Patch Notes](https://stellaris.paradoxwikis.com) | Official mechanical changes |
| [stellaris-build.com](https://stellaris-build.com) | Community-tested builds + tier lists |
| Aktion YouTube | Ship combat testing (weapon verdicts) |
| Stefan Anon / MontuPlays | Economy optimization guides |
| Game files `common/defines/` | Raw numeric values |

**Important:** Meta must be tested in real gameplay — don't just copy patch notes.

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

## Credits & Community Resources

This project would not exist without the open-source ecosystem and the
Stellaris community. Thanks to the following people, projects, and tools.

### Game & official sources
- **Paradox Development Studio** — [Stellaris](https://www.stellaris.com/) and the Clausewitz engine
- **[Stellaris Paradox Wiki](https://stellaris.paradoxwikis.com/)** — modding reference, scopes, effects, on_actions, ship designer
- **[Paradox Modding Forums](https://forum.paradoxplaza.com/forum/forums/stellaris-mods.900/)** — event scripting reference

### Stellaris community (meta & strategy)
- **[stellaris-build.com](https://stellaris-build.com)** — community build database + tier lists
- **[Aktion — "We Tested 200+ Ship Builds"](https://www.youtube.com/watch?v=KRlRjbOg0Ag)** — ship & combat meta source for `docs/META_4.3.4.md`
- **[KaelGotRice — "4.3 Meta: Strongest Builds"](https://www.youtube.com/watch?v=KsQA9-SrKD8)** — build & origin meta source for `docs/META_4.3.4.md`
- **Stefan Anon** (YouTube) — economy/empire optimization guides
- **MontuPlays** (YouTube) — patch breakdowns and meta analysis
- **r/Stellaris** and the Stellaris Modding Den (Discord) — countless tips

### Stellaris modding & save-parsing tools
- **[stellaris-dashboard](https://github.com/eliasdoehne/stellaris-dashboard)** (Elias Doehne) — reference for high-performance Rust save parsing (maturin + jomini); cited in [engine/clausewitz_parser.py](engine/clausewitz_parser.py)
- **[jomini](https://github.com/rakaly/jomini)** (Rakaly) — Rust crate for Paradox script/save parsing — perf benchmark reference
- **[Rakaly save analyzer](https://rakaly.com/)** — community save inspection used to validate parsed-state shape
- **[CWTools](https://github.com/cwtools/cwtools)** + **[Paradox Script VSCode extension](https://github.com/cwtools/cwtools-vscode)** — Clausewitz syntax highlighting / validation while authoring `mod/`
- **[Irony Mod Manager](https://github.com/bcssov/IronyModManager)** — mod testing & conflict checks

### MCP servers (dev-time enrichment)
The engine integrates with MCP servers for ruleset/meta authoring (not at runtime). Wired in [engine/mcp_client.py](engine/mcp_client.py):
- **`stellaris-wiki-mcp`** — `wiki_game_data`, `wiki_search`, `wiki_patch_notes` for meta authoring
- **`stellaris-save-mcp`** — `save_empires`, `save_empire_detail`, `game_version` for save inspection
- **[Model Context Protocol](https://modelcontextprotocol.io/)** (Anthropic) — protocol spec
- **[GitHub MCP Server](https://github.com/github/github-mcp-server)** — used during development for repo operations
- **[Microsoft Docs MCP](https://learn.microsoft.com/)** — Azure / Foundry documentation lookup during integration

### LLM runtimes
- **[Ollama](https://ollama.com)** — local LLM serving (default backend)
- **[LM Studio](https://lmstudio.ai)** — GUI LLM host with OpenAI-compatible API
- **[vLLM](https://github.com/vllm-project/vllm)** — high-throughput Docker inference
- **[TensorRT-LLM](https://github.com/NVIDIA/TensorRT-LLM)** — optional accelerated profile
- **[Qwen2.5](https://qwenlm.github.io/)** (Alibaba) — primary model family
- **[OpenRouter](https://openrouter.ai/)**, **[Together AI](https://www.together.ai/)**, **[Groq](https://groq.com/)**, **[Azure AI Foundry](https://ai.azure.com/)** — supported cloud endpoints

### Python ecosystem
- **[Rich](https://github.com/Textualize/rich)** — TUI dashboard rendering
- **[pytest](https://pytest.org/)** — 464+ test suite
- **[ruff](https://github.com/astral-sh/ruff)** — linting + formatting
- **[mypy](https://mypy-lang.org/)** — strict static type checking

### Training & fine-tuning stack
- **[Hugging Face Transformers / Datasets / Accelerate](https://huggingface.co/)** — model + data tooling
- **[PEFT](https://github.com/huggingface/peft)** — LoRA / QLoRA adapters
- **[TRL](https://github.com/huggingface/trl)** — SFT and DPO trainers
- **[bitsandbytes](https://github.com/bitsandbytes-foundation/bitsandbytes)** — 4/8-bit quantization
- **[Unsloth](https://github.com/unslothai/unsloth)** — optional 2× faster LoRA training
- **[GPTQ](https://github.com/IST-DASLab/gptq)** / **[AWQ](https://github.com/mit-han-lab/llm-awq)** — post-training quantization
- **[Weights & Biases](https://wandb.ai/)** — optional experiment tracking

### Security & CI
- **[CodeQL](https://codeql.github.com/)** — static security analysis
- **[Dependabot](https://github.com/dependabot)** — dependency updates
- **[pip-audit](https://github.com/pypa/pip-audit)** — vulnerability scanning
- **[Snyk](https://snyk.io/)** / **[SonarQube](https://www.sonarsource.com/)** — code quality during development

### Tooling used to build this project
- **[Visual Studio Code](https://code.visualstudio.com/)** with **[GitHub Copilot](https://github.com/features/copilot)** and **[Claude Code](https://www.anthropic.com/claude-code)** (Anthropic) — paired-AI development workflow
- **[GitHub Actions](https://github.com/features/actions)** — CI/CD

If we missed your tool or guide, please open an issue or PR — we want to credit you.

---

## License

MIT — see [LICENSE](LICENSE).

