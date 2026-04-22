# Changelog

## 2025-04-22 — Setup Wizard, Constructive Suggestions, Bug Fixes

### Setup Wizard
- **Interactive first-run wizard** (`engine/setup_wizard.py`) — auto-launches when no config.toml exists
  - 6-step guided setup: Mode → Paths → LLM → Options → Recording → Summary
  - Auto-discovers Stellaris install (scans Steam library on C:-H: drives)
  - Auto-discovers user data (Documents/Paradox, supports OneDrive)
  - Auto-detects running Ollama + available models
  - Supports network LLM endpoints (ip:port, DNS names)
  - Run manually: `python -m engine --setup`
- **Configurable fast cutoff year** — `[target] fast_cutoff_year = 2250`

### Constructive Player Suggestions
- Player mode now shows specific, actionable advice instead of bare action names
- BUILD_FLEET: weapon loadouts per game phase, alloy check
- IMPROVE_ECONOMY: diagnoses low income areas, recommends districts
- FOCUS_TECH: shows research count, current projects, priority guidance
- PREPARE_WAR: target, fleet ratio, edict checklist
- All 11 actions have phase-aware, detailed guidance

### Bug Fixes
- **Validator: None in known_systems** — chained `.get()` could produce None in set. Replaced with explicit loop
- **json.dumps safety** — added `default=str` to prevent crashes on non-serializable ruleset values
- **State type safety** — `in_progress` field checked with `isinstance(dict)` instead of truthy
- **Name resolution** — extracted `_is_resolved_name()` helper for consistent localization handling
- **Dead code** — removed unreachable `action is None` check in fast path
- **TUI: Rich markup garbling** — Decisions panel uses `Text()` objects instead of f-string markup
- **TUI: missing [F] label** — replaced bracket notation with `F:ON` to avoid Rich markup parsing
- **Setup wizard: input validation** — error message only shown on invalid input

---

## 2025-04-22 — Version-Aware Meta System

### Meta Management
- **Game version auto-detection** — `detect_game_version()` extracts version from save metadata (e.g. "Cetus v4.3.4" → "4.3.4")
- **Meta loader** (`engine/meta_loader.py`) — loads version-specific meta from `docs/meta/X.Y.Z.json`, falls back to nearest version
- **Structured meta file** (`docs/meta/4.3.4.json`) — weapon verdicts, fleet templates, economy rules, origin tiers, crisis counters, ascension meta
- **Scaffold script** (`scripts/scaffold_meta.py`) — `python scripts/scaffold_meta.py 4.5.0 --from 4.3.4` creates a new meta file pre-filled from the base version
  - `--detect` auto-detects version from latest save
  - `--list` shows available versions
- State snapshots now carry detected game version instead of hardcoded constant

### Files Added
- `engine/meta_loader.py` — version-aware meta loading with fallback chain
- `docs/meta/4.3.4.json` — structured meta for Stellaris 4.3.4
- `scripts/scaffold_meta.py` — scaffolding tool for new patch versions

---

## 2025-04-22 — AI Mode Live Session

### Major Features
- **AI Mode launch** — Engine runs all AI empires via Ollama (qwen2.5 7B), controlling 17-19 empires per tick
- **Rich TUI dashboard** — Real-time monitoring with token rates, decisions, outcomes, and empire status board
- **Outcome scoring** — Retroactive decision evaluation across 6 dimensions (economy, fleet, tech, expansion, stability, meta alignment)
- **Empire status board** — Shows each empire and their current action at a glance
- **Parallel log viewer** — Press `[L]` to open a live log tail in a new terminal window
- **Fast decision path** — Code-only decisions for trivial situations (togglable with `[F]`)

### Performance
- Latency reduced from **13.2s → ~3.5s** per LLM decision (73% reduction)
  - Code-only arbiter (eliminated 3rd LLM call per council decision)
  - max_tokens 256 → 50 (response is only 4 lines)
  - Compact JSON in prompts (separators, no indent)
  - Split meta rules by agent role (domestic vs military)
  - Removed leaders, policies, starbases from agent state (saves ~500 tokens)
- Fast path bypasses LLM entirely for obvious early/mid-game decisions (~0ms)
- Token throughput: ~1,100 tok/s sustained

### Bug Fixes
- **Ruleset key mismatch** — Clausewitz IDs (`ethic_militarist`) now normalized to display names (`Militarist`) for lookup. Was causing empty rulesets for all empires.
- **Colony dict validation** — `set()` on colony dicts caused `TypeError: unhashable type`. Fixed to extract names.
- **BUILD_FLEET fog-of-war** — Ship type targets (corvette, etc.) no longer rejected as spatial violations
- **BUILD_STARBASE validation** — Descriptive targets ("chokepoints") no longer rejected
- **COLONIZE validation** — Planet name targets no longer require spatial matching (native AI picks)
- **PREPARE_WAR localization** — Targets with `%ADJ%` unresolved keys skip empire validation
- **Empire name resolution** — Handles Stellaris localization templates (`%ADJECTIVE%`), falls back to species/government name
- **Token stats** — Added `_SimpleProviderStats` to `OpenAICompatProvider` and `QwenVLLMProvider`
- **Avg latency** — Metrics now feed latency into rolling deque correctly
- **Game year display** — Added `game_year` to `LoopStats`, synced to TUI header
- **Rich markup escaping** — Empire names with brackets no longer garble the TUI
- **Console stability** — Fixed layout jitter, reduced refresh to 1/s, fixed log panel height
- **Controls rendering** — `[F]` and other key labels render correctly using `Text.append()`

### AI Decision Quality
- **Decision diversity** — Now produces FOCUS_TECH, COLONIZE, PREPARE_WAR, BUILD_STARBASE, DIPLOMACY, ESPIONAGE (was only BUILD_FLEET/IMPROVE_ECONOMY)
- **Ethics-aware traditions** — Recommendations vary by ethics (Militarist → Supremacy, Xenophile → Diplomacy/Commerce)
- **Phase-aware prompts** — LLM gets game-phase-specific guidance for each agent role
- **Empire strategy profiles** — LLM sees war_tendency, fleet_budget, trade_focus from actual ethics/civics
- **Expanded meta rules** — 19 rules covering all 11 actions with Stellaris 4.3.4 specifics

### Recording & Training
- **Recorder wired for AI mode** — Decisions saved to `training/replay_buffer/` JSONL files
- **Outcome scoring pipeline** — `OutcomeScorer` runs on decisions with 12+ game-month lookback
- **Per-action scores** — Tracked and displayed in TUI Outcomes panel

### Configuration
- `config.toml` created for AI mode with Ollama provider
- `[target] fast_decisions = true` — Toggleable fast decision path
- `--log-file` arg — Custom log file path (auto-set to `overmind.log` in console mode)
- `--console` now writes logs to file for parallel tail viewing

### Files Changed (14 files, +695 -157 lines)
- `engine/config.py` — Added `fast_decisions` to `TargetConfig`
- `engine/console.py` — Empire board, log viewer, controls overhaul
- `engine/decision_engine.py` — Ethics-aware tradition guidance
- `engine/game_loop.py` — Fast path, outcome scoring, empire status, game year
- `engine/main.py` — Recorder wiring, log file, console config
- `engine/metrics.py` — Outcome tracking, empire status, latency fix
- `engine/multi_agent.py` — Split meta, compact prompts, phase guidance, strategy profiles
- `engine/qwen_provider.py` — Stats tracking for all providers
- `engine/ruleset_generator.py` — Key normalization fix
- `engine/save_reader.py` — Empire name localization handling
- `engine/strategic_knowledge.py` — Ethics-aware tradition guidance
- `engine/validator.py` — Spatial/empire validation overhaul
- `tests/test_dual_mode.py` — Fast decisions test fix
- `tests/test_multi_agent.py` — Updated for compact prompts
