"""
Game Loop Controller — The live loop that connects Stellaris ↔ LLM.

This is the main runtime orchestrator.  It:
  1. Polls the bridge for new state snapshots
  2. Runs the decision pipeline (ruleset → personality → prompt → LLM → validate)
  3. Writes validated directives back to the bridge
  4. Handles LLM latency gracefully (never blocks the game)
  5. Provides fallback behavior when the LLM is unavailable

The controller runs in a single thread.  LLM calls are synchronous (blocking)
but the polling loop means the game continues while we wait.  If a new snapshot
arrives while the LLM is still thinking, the new snapshot takes priority.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field

from engine.bridge import BridgeConfig, BridgeWriter, UnifiedBridge
from engine.config import MultiAgentConfig, PlannerConfig
from engine.decision_engine import Directive, build_prompt, parse_llm_response
from engine.llm_provider import LLMProvider, LLMProviderError, StubProvider
from engine.personality_shards import build_personality
from engine.recorder import GameRecorder
from engine.ruleset_generator import generate_ruleset
from engine.validator import validate_directive

log = logging.getLogger(__name__)

_LOC_PATTERN = re.compile(r"%[A-Z_]+%")


def _empire_display_name(state: dict, country_id: int) -> str:
    """Extract a human-readable empire name from state, falling back to ID."""
    name = state.get("empire", {}).get("name", "")
    # Stellaris saves often contain unresolved localization keys like %ADJECTIVE%
    if not name or _LOC_PATTERN.search(name):
        # Try adjective or species as fallback
        adj = state.get("empire", {}).get("adjective", "")
        if adj and not _LOC_PATTERN.search(adj):
            return adj
        species = state.get("empire", {}).get("species", "")
        if species:
            return species
        gov = state.get("empire", {}).get("government", "")
        return f"{gov}#{country_id}" if gov else f"Empire#{country_id}"
    return name


def _build_constructive_suggestion(
    directive: Directive, state: dict, ruleset: dict,  # noqa: ARG001
) -> str:
    """Build a detailed, actionable suggestion for the player.

    Instead of just 'BUILD_FLEET', explains what to build, where, and why.
    """
    action = directive.action
    reason = directive.reason[:100]
    year = state.get("year", 2200)
    economy = state.get("economy", {})
    fleets = state.get("fleets", [])
    colonies = state.get("colonies", [])
    tech = state.get("technology", {})
    fleet_power = sum(f.get("power", 0) for f in fleets) if fleets else 0
    alloys = economy.get("alloys", 0)
    colony_count = len(colonies) if isinstance(colonies, list) else 0

    parts = [f"[bold yellow]{action}[/bold yellow]"]

    if action == "BUILD_FLEET":
        if year < 2230:
            parts.append("Build corvettes with [cyan]Autocannon + Plasma[/cyan] (swarm meta).")
            parts.append(f"Current fleet: {fleet_power} power. Target: fill naval cap.")
        elif year < 2280:
            parts.append("Add [cyan]cruisers[/cyan] with Kinetic Artillery + Neutron Launchers.")
            parts.append("Keep corvette screen for point defense.")
        else:
            parts.append("Build [cyan]battleship artillery[/cyan] + titan. Split fleets vs AoE.")
        if alloys > 200:
            parts.append(f"You have {alloys} alloys — good time to invest.")

    elif action == "IMPROVE_ECONOMY":
        monthly = economy.get("monthly_net", {})
        energy = monthly.get("energy", 0) if isinstance(monthly, dict) else 0
        minerals = monthly.get("minerals", 0) if isinstance(monthly, dict) else 0
        issues = []
        if energy < 10:
            issues.append(f"energy income low ({energy}/mo)")
        if minerals < 20:
            issues.append(f"mineral income low ({minerals}/mo)")
        if issues:
            parts.append(f"Priority: fix {', '.join(issues)}.")
        parts.append("Build [cyan]mining districts[/cyan] > energy districts. Specialize planets.")
        if year > 2230:
            parts.append("Set planet designations for +efficiency bonus.")

    elif action == "FOCUS_TECH":
        tech_count = tech.get("count", 0) if isinstance(tech, dict) else 0
        researching = tech.get("in_progress", {}) if isinstance(tech, dict) else {}
        parts.append(f"Tech count: {tech_count}.")
        if researching:
            fields = ", ".join(f"{k}: {v}" for k, v in researching.items())
            parts.append(f"Researching: {fields}.")
        parts.append("Build [cyan]research labs[/cyan]. Set Academic Privilege policy.")
        if year > 2250:
            parts.append("Prioritize [cyan]repeatables[/cyan] (+naval cap, +damage).")

    elif action == "COLONIZE":
        parts.append(f"Currently {colony_count} colonies.")
        parts.append("Prioritize planets with [cyan]high habitability[/cyan] and rare features.")
        parts.append("Set colony designation immediately for efficiency bonus.")

    elif action == "PREPARE_WAR":
        target = directive.target or "nearest rival"
        parts.append(f"Target: {target}.")
        parts.append("Claim their systems (influence cost). Build up fleet to 1.5x their power.")
        parts.append("Set war economy edict before declaring.")

    elif action == "BUILD_STARBASE":
        parts.append("Upgrade starbases at [cyan]chokepoints[/cyan] and trade routes.")
        parts.append("Anchorages for naval cap. Shipyards for build speed.")

    elif action == "DIPLOMACY":
        parts.append("Send envoys to improve relations. Consider migration pacts, research agreements.")
        parts.append("Federations scale hard in 4.3 — consider forming one.")

    elif action == "ESPIONAGE":
        parts.append("Assign envoys to spy networks on rivals.")
        parts.append("Smear campaigns weaken enemies. Gather intel before wars.")

    elif action == "EXPAND":
        parts.append("Claim unclaimed systems. Prioritize chokepoints and resource-rich systems.")
        parts.append("Build science ships to survey adjacent systems.")

    elif action == "DEFEND":
        parts.append("Reinforce border starbases. Position fleets at chokepoints.")
        parts.append("Consider defensive pacts with friendly neighbors.")

    elif action == "CONSOLIDATE":
        parts.append("Focus on stability. Upgrade buildings, clear blockers.")
        parts.append("Address unemployment and housing on existing colonies.")

    if reason:
        parts.append(f"[dim]Reason: {reason}[/dim]")

    return "\n".join(parts)


@dataclass
class EmpireConfig:
    """Static configuration for the AI-controlled empire."""

    ethics: list[str]
    civics: list[str]
    traits: list[str]
    origin: str
    government: str


@dataclass
class LoopStats:
    """Runtime statistics for monitoring."""

    decisions_made: int = 0
    decisions_failed: int = 0
    llm_errors: int = 0
    validation_errors: int = 0
    snapshots_processed: int = 0
    last_decision_time_ms: float = 0.0
    last_action: str = ""
    last_suggestion: str = ""
    game_year: int = 0
    scored_count: int = 0
    avg_composite_score: float = 0.0
    action_scores: dict[str, list[float]] = field(default_factory=dict)
    empire_status: dict[str, str] = field(default_factory=dict)  # name → last action


class GameLoopController:
    """The main live loop connecting Stellaris to the LLM."""

    def __init__(
        self,
        empire: EmpireConfig,
        provider: LLMProvider | None = None,
        bridge_config: BridgeConfig | None = None,
        max_retries: int = 2,
        recorder: GameRecorder | None = None,
        multi_agent_config: MultiAgentConfig | None = None,
        planner_config: PlannerConfig | None = None,
        planner_provider: LLMProvider | None = None,
    ) -> None:
        self._empire = empire
        self._provider = provider or StubProvider()
        self._bridge_config = bridge_config or BridgeConfig()
        self._bridge = UnifiedBridge(self._bridge_config)
        self._writer = BridgeWriter(self._bridge_config)
        self._max_retries = max_retries
        self._running = False
        self._recorder = recorder or GameRecorder()
        self.stats = LoopStats()
        self._auto_detect = not empire.ethics  # empty = auto-detect from save

        if self._auto_detect:
            # Deferred: will generate ruleset from first save snapshot
            self._ruleset = {}
            self._personality = {}
            log.info("Empire auto-detect enabled — ruleset will be generated from first save")
        else:
            # Pre-compute static ruleset and personality
            self._ruleset = generate_ruleset(
                ethics=empire.ethics,
                civics=empire.civics,
                traits=empire.traits,
                origin=empire.origin,
                government=empire.government,
            )
            self._personality = build_personality(
                ethics=empire.ethics,
                civics=empire.civics,
                traits=empire.traits,
                origin=empire.origin,
                government=empire.government,
            )

        # Multi-agent council (opt-in)
        self._council = None
        ma = multi_agent_config or MultiAgentConfig()
        if ma.enabled:
            from engine.multi_agent import CouncilOrchestrator

            self._council = CouncilOrchestrator(
                provider=self._provider,
                government=empire.government,
                personality=self._personality,
                ruleset=self._ruleset,
                parallel=ma.parallel,
                arbiter_uses_llm=ma.arbiter_uses_llm,
            )

        log.info(
            "Controller initialized: origin=%s gov=%s meta_tier=%s provider=%s multi_agent=%s",
            empire.origin, empire.government,
            self._ruleset.get("meta_tier", "?"),
            self._provider.name,
            ma.enabled,
        )

        # Strategic planner (opt-in)
        self._planner = None
        pc = planner_config or PlannerConfig()
        if pc.enabled:
            from engine.strategic_planner import StrategicPlanner

            if planner_provider is not None:
                resolved_provider = planner_provider
            elif pc.provider == "same":
                resolved_provider = self._provider
            else:
                resolved_provider = None  # code-only
            self._planner = StrategicPlanner(
                provider=resolved_provider,
                ruleset=self._ruleset,
                personality=self._personality,
                interval_years=pc.interval_years,
            )
            log.info("Strategic planner enabled: interval=%dy", pc.interval_years)

    def run(self) -> None:
        """Start the live loop.  Blocks until ``stop()`` is called."""
        self._running = True
        log.info("Game loop started — polling every %.1fs", self._bridge_config.poll_interval_s)

        while self._running:
            try:
                self._tick()
            except KeyboardInterrupt:
                log.info("Interrupted — shutting down")
                break
            except Exception:
                log.exception("Unhandled error in game loop tick")
            time.sleep(self._bridge_config.poll_interval_s)

        log.info("Game loop stopped — %d decisions made", self.stats.decisions_made)
        log.info("Recorded %d decisions for training", self._recorder.record_count)

    def stop(self) -> None:
        """Signal the loop to stop after the current tick."""
        self._running = False

    def tick_once(self, state: dict) -> Directive | None:
        """Run a single decision cycle with an explicit state dict.

        Useful for testing and programmatic use without the file bridge.
        """
        return self._process_snapshot(state)

    # ------------------------------------------------------------------ #
    # Internal
    # ------------------------------------------------------------------ #

    def _tick(self) -> None:
        """One iteration of the polling loop."""
        snapshot = self._bridge.read_snapshot()
        if snapshot is None:
            return  # no new state — nothing to do

        self.stats.snapshots_processed += 1
        year = snapshot.get("year", 0)
        if year:
            self.stats.game_year = year

        # Refresh ruleset if empire changed mid-game (government reform)
        self._maybe_refresh_ruleset(snapshot)

        # Check for ack from previous directive (JSON mode only)
        ack = self._bridge.read_ack()
        if ack:
            log.debug("Previous directive acknowledged: %s", ack.get("status"))
            self._writer.clear_directive()

        # Retroactively score older decisions now that we have fresh state
        self._recorder.update_outcomes(snapshot)

        # Refresh strategic plan if due
        self._maybe_replan(snapshot)

        directive = self._process_snapshot(snapshot)
        if directive is not None:
            self._emit_directive(directive, snapshot)
            # Record the decision for training
            self._recorder.record_decision(
                state=snapshot,
                decision=directive.to_dict(),
                event=snapshot.get("event"),
                validated=True,
                llm_latency_ms=self.stats.last_decision_time_ms,
                provider=self._provider.name,
            )

    def _process_snapshot(self, state: dict) -> Directive | None:
        """Run the full decision pipeline on a state snapshot."""
        event = state.get("event")

        # Multi-agent council path
        if self._council is not None:
            return self._process_council(state, event)

        # Single-agent path (original)
        prompt = build_prompt(self._ruleset, self._personality, state, event)

        # Query LLM with retries
        directive = self._query_llm(prompt)
        if directive is None:
            return None

        # Validate
        result = validate_directive(directive.to_dict(), self._ruleset, state)
        if not result.valid:
            self.stats.validation_errors += 1
            log.warning(
                "Directive rejected: action=%s errors=%s",
                directive.action, result.errors,
            )
            # Retry once with error feedback
            if self._max_retries > 0:
                return self._retry_with_feedback(prompt, result.errors, state)
            return None

        for w in result.warnings:
            log.info("Validation warning: %s", w)

        self.stats.decisions_made += 1
        self.stats.last_action = directive.action
        return directive

    def _query_llm(self, prompt: str) -> Directive | None:
        """Call the LLM and parse the response."""
        t0 = time.monotonic()
        try:
            response = self._provider.complete(prompt)
        except LLMProviderError as exc:
            self.stats.llm_errors += 1
            log.error("LLM error: %s", exc)
            return None

        self.stats.last_decision_time_ms = (time.monotonic() - t0) * 1000
        log.info(
            "LLM responded in %.0fms (tokens: %d→%d)",
            response.latency_ms,
            response.prompt_tokens,
            response.completion_tokens,
        )

        try:
            return parse_llm_response(response.text)
        except ValueError as exc:
            self.stats.decisions_failed += 1
            log.warning("Failed to parse LLM response: %s", exc)
            return None

    def _retry_with_feedback(
        self, original_prompt: str, errors: list[str], state: dict,
    ) -> Directive | None:
        """Re-query the LLM with validation error feedback."""
        feedback = (
            "\n\nYour previous response was REJECTED for these reasons:\n"
            + "\n".join(f"- {e}" for e in errors)
            + "\n\nPlease try again, fixing the above issues."
        )
        directive = self._query_llm(original_prompt + feedback)
        if directive is None:
            return None

        result = validate_directive(directive.to_dict(), self._ruleset, state)
        if not result.valid:
            log.error("Retry also rejected: %s", result.errors)
            self.stats.decisions_failed += 1
            return None

        self.stats.decisions_made += 1
        self.stats.last_action = directive.action
        return directive

    def _emit_directive(self, directive: Directive, state: dict) -> None:
        """Write the directive to the bridge and display as a suggestion."""
        payload = directive.to_dict()
        payload["timestamp"] = f"{state.get('year', 0)}.{state.get('month', 0)}"
        payload["meta"] = {
            "provider": self._provider.name,
            "latency_ms": round(self.stats.last_decision_time_ms),
            "meta_tier": self._ruleset.get("meta_tier", "?"),
        }
        self._writer.write_directive(payload)

        # Player mode: write human-readable suggestion (no direct execution)
        stellaris_dir = None
        if self._bridge_config.save_dir and self._bridge_config.save_dir.exists():
            stellaris_dir = self._bridge_config.save_dir.parent
        self._writer.write_suggestion(payload, stellaris_dir)

        # Build constructive suggestion with specific actions
        suggestion = _build_constructive_suggestion(directive, state, self._ruleset)
        self.stats.last_suggestion = suggestion

        # Log the suggestion prominently
        log.info(">>> SUGGESTION: %s", suggestion)

    def _process_council(self, state: dict, event: str | None) -> Directive | None:
        """Run the multi-agent council pipeline on a state snapshot."""
        strategic_context = None
        if self._planner is not None:
            strategic_context = self._planner.context

        result = self._council.decide(state, event, strategic_context=strategic_context)
        directive = result.directive
        self.stats.last_decision_time_ms = result.total_latency_ms

        log.info(
            "Council: method=%s agents=%d latency=%.0fms",
            result.arbitration_method,
            len(result.recommendations),
            result.total_latency_ms,
        )
        for rec in result.recommendations:
            log.debug(
                "  %s → %s (conf=%.2f): %s",
                rec.agent_role, rec.action, rec.confidence, rec.reasoning,
            )

        # Validate (same gate as single-agent)
        vresult = validate_directive(directive.to_dict(), self._ruleset, state)
        if not vresult.valid:
            self.stats.validation_errors += 1
            log.warning(
                "Council directive rejected: action=%s errors=%s",
                directive.action, vresult.errors,
            )
            return None

        for w in vresult.warnings:
            log.info("Validation warning: %s", w)

        self.stats.decisions_made += 1
        self.stats.last_action = directive.action
        return directive

    def _maybe_replan(self, state: dict) -> None:
        """Run the strategic planner if it's time for a new plan."""
        if self._planner is None:
            return
        year = state.get("year", 0)
        if self._planner.should_replan(year):
            self._planner.plan(state)

    def _maybe_refresh_ruleset(self, state: dict) -> None:
        """Regenerate ruleset if the empire's ethics/civics changed mid-game.

        On first call with auto-detect, generates the initial ruleset from
        save data and updates the empire config to match.
        """
        empire_info = state.get("empire", {})
        if not empire_info:
            return

        current_ethics = sorted(empire_info.get("ethics", []))
        current_civics = sorted(empire_info.get("civics", []))
        current_origin = empire_info.get("origin", "")
        current_gov = empire_info.get("government", "")

        # Auto-detect: first snapshot populates the empire config
        if self._auto_detect and not self._empire.ethics:
            log.info(
                "Auto-detected empire: ethics=%s civics=%s origin=%s gov=%s",
                current_ethics, current_civics, current_origin, current_gov,
            )
            self._empire.ethics = list(current_ethics)
            self._empire.civics = list(current_civics)
            self._empire.origin = current_origin
            self._empire.government = current_gov
            # Force regeneration below
        else:
            config_ethics = sorted(self._empire.ethics)
            config_civics = sorted(self._empire.civics)
            if current_ethics == config_ethics and current_civics == config_civics:
                return  # no change

        log.info(
            "Empire changed: ethics=%s civics=%s — regenerating ruleset",
            current_ethics, current_civics,
        )
        self._empire.ethics = list(current_ethics) or self._empire.ethics
        self._empire.civics = list(current_civics) or self._empire.civics
        self._empire.origin = current_origin or self._empire.origin
        self._empire.government = current_gov or self._empire.government

        self._ruleset = generate_ruleset(
            ethics=self._empire.ethics,
            civics=self._empire.civics,
            traits=self._empire.traits,
            origin=self._empire.origin,
            government=self._empire.government,
        )
        self._personality = build_personality(
            ethics=self._empire.ethics,
            civics=self._empire.civics,
            traits=self._empire.traits,
            origin=self._empire.origin,
            government=self._empire.government,
        )
        # Sync council with updated context
        if self._council is not None:
            self._council.update_context(
                government=self._empire.government,
                personality=self._personality,
                ruleset=self._ruleset,
            )
        # Sync planner with updated context
        if self._planner is not None:
            self._planner.update_context(
                ruleset=self._ruleset,
                personality=self._personality,
            )


# ====================================================================== #
# AI Mode Controller — controls AI empires instead of the player
# ====================================================================== #

class AILoopController:
    """Controls one or more AI empires using the LLM.

    In AI mode, the engine:
      1. Parses the save to find AI countries
      2. For each AI empire, auto-detects ethics/civics/traits/origin
      3. Generates a per-empire ruleset and personality
      4. Runs the decision pipeline for each empire (parallel optional)
      5. Writes per-empire directives (``directive_<cid>.json``)
      6. Records decisions for training data collection

    The mod then reads these and executes scoped to each AI country.
    """

    def __init__(
        self,
        provider: LLMProvider | None = None,
        bridge_config: BridgeConfig | None = None,
        max_retries: int = 2,
        country_ids: list[int] | None = None,
        exclude_ids: list[int] | None = None,
        exclude_fallen: bool = True,
        multi_agent_config: MultiAgentConfig | None = None,
        parallel_empires: bool = False,
        recorder: GameRecorder | None = None,
        fast_decisions: bool = True,
        fast_cutoff_year: int = 2250,
    ) -> None:
        self._provider = provider or StubProvider()
        self._bridge_config = bridge_config or BridgeConfig()
        self._writer = BridgeWriter(self._bridge_config)
        self._max_retries = max_retries
        self._country_ids = country_ids
        self._exclude_ids = exclude_ids
        self._exclude_fallen = exclude_fallen
        self._multi_agent_config = multi_agent_config or MultiAgentConfig()
        self._parallel_empires = parallel_empires
        self._recorder = recorder
        self._fast_decisions = fast_decisions
        self._fast_cutoff_year = fast_cutoff_year
        self._running = False

        # Cache rulesets/personalities per country ID
        self._rulesets: dict[int, dict] = {}
        self._personalities: dict[int, dict] = {}
        # Cache previous states for event detection
        self._previous_states: dict[int, dict] = {}
        # Cache councils for multi-agent mode
        self._councils: dict[int, object] = {}

        self.stats = LoopStats()

        log.info(
            "AI controller initialized: ids=%s exclude=%s parallel=%s multi_agent=%s",
            country_ids or "all", exclude_ids or "none",
            parallel_empires, self._multi_agent_config.enabled,
        )

    def run(self) -> None:
        """Start the AI live loop.  Blocks until ``stop()`` is called."""
        from engine.save_reader import SaveReader, SaveWatcherConfig

        self._running = True
        reader = SaveReader(SaveWatcherConfig(
            save_dir=self._bridge_config.save_dir,
            poll_interval_s=self._bridge_config.poll_interval_s,
        ))

        log.info("AI loop started — polling every %.1fs", self._bridge_config.poll_interval_s)

        while self._running:
            try:
                states = reader.read_ai_states(
                    country_ids=self._country_ids,
                    exclude_ids=self._exclude_ids,
                    exclude_fallen=self._exclude_fallen,
                )
                if states:
                    # Update game year from first state
                    year = states[0].get("year", 0)
                    if year:
                        self.stats.game_year = year
                    # Retroactively score older decisions
                    if self._recorder:
                        updated = self._recorder.update_outcomes(states[0])
                        if updated:
                            self._score_completed_records()
                    self._process_all(states)
            except KeyboardInterrupt:
                log.info("Interrupted — shutting down")
                break
            except Exception:
                log.exception("Unhandled error in AI loop tick")
            time.sleep(self._bridge_config.poll_interval_s)

        log.info("AI loop stopped — %d decisions made", self.stats.decisions_made)
        if self._recorder:
            log.info("Recorded %d AI decisions for training", self._recorder.record_count)

    def stop(self) -> None:
        self._running = False

    def _score_completed_records(self) -> None:
        """Score records that now have state_after filled."""
        from engine.scorer import score_outcome

        for rec in self._recorder.get_records():
            if rec.state_after is not None and rec.outcome_scores is None:
                cid = rec.state_before.get("country_id", 0)
                ruleset = self._rulesets.get(cid, {})
                scores = score_outcome(
                    rec.state_before, rec.state_after, rec.decision, ruleset,
                )
                rec.outcome_scores = scores.to_dict()
                rec.meta_alignment = scores.meta_alignment

                action = rec.decision.get("action", "?")
                if action not in self.stats.action_scores:
                    self.stats.action_scores[action] = []
                self.stats.action_scores[action].append(scores.composite)
                self.stats.scored_count += 1

                all_scores = [
                    s for lst in self.stats.action_scores.values() for s in lst
                ]
                self.stats.avg_composite_score = (
                    sum(all_scores) / len(all_scores) if all_scores else 0.0
                )

                empire_name = _empire_display_name(rec.state_before, cid)
                log.info(
                    "[%s] outcome scored: %s → %.2f (econ=%.2f fleet=%.2f meta=%.2f)",
                    empire_name, action, scores.composite,
                    scores.economy_delta, scores.fleet_delta, scores.meta_alignment,
                )

    def process_states(self, states: list[dict]) -> list[Directive | None]:
        """Process a list of AI empire states.  For testing."""
        return self._process_all(states)

    def _process_all(self, states: list[dict]) -> list[Directive | None]:
        """Run the decision pipeline for each AI empire."""
        if self._parallel_empires and len(states) > 1:
            return self._process_parallel(states)
        return self._process_sequential(states)

    def _process_sequential(self, states: list[dict]) -> list[Directive | None]:
        """Process empires one at a time."""
        results: list[Directive | None] = []
        for state in states:
            cid = state.get("country_id", 0)
            directive = self._process_one(cid, state)
            results.append(directive)
            self._emit_and_record(cid, directive, state)
        return results

    def _process_parallel(self, states: list[dict]) -> list[Directive | None]:
        """Process empires concurrently using threads."""
        from concurrent.futures import ThreadPoolExecutor, as_completed

        results_map: dict[int, Directive | None] = {}

        with ThreadPoolExecutor(max_workers=min(len(states), 4)) as pool:
            futures = {
                pool.submit(self._process_one, s.get("country_id", 0), s): s
                for s in states
            }
            for future in as_completed(futures):
                state = futures[future]
                cid = state.get("country_id", 0)
                directive = future.result()
                results_map[cid] = directive
                self._emit_and_record(cid, directive, state)

        # Return in original order
        return [results_map.get(s.get("country_id", 0)) for s in states]

    def _emit_and_record(
        self, country_id: int, directive: Directive | None, state: dict,
    ) -> None:
        """Write directive to bridge and record for training.

        AI empires rely on the mod's personality overrides and stat modifiers
        to influence Stellaris's native AI — we do NOT issue direct console
        commands (add_district, add_building, etc.) because that bypasses
        the native build queues and economic planning.
        """
        if directive is not None:
            payload = directive.to_dict()
            payload["country_id"] = country_id
            payload["timestamp"] = f"{state.get('year', 0)}.{state.get('month', 0)}"
            self._writer.write_directive_for(country_id, payload)

            # Record for training
            if self._recorder is not None:
                self._recorder.record_decision(
                    state=state,
                    decision=directive.to_dict(),
                    event=state.get("event"),
                    validated=True,
                    llm_latency_ms=self.stats.last_decision_time_ms,
                    provider=self._provider.name,
                )

    def _process_one(self, country_id: int, state: dict) -> Directive | None:
        """Run the decision pipeline for one AI empire."""
        empire_info = state.get("empire", {})
        ethics = empire_info.get("ethics", [])
        civics = empire_info.get("civics", [])
        origin = empire_info.get("origin", "")
        government = empire_info.get("government", "")
        traits = []  # traits aren't stored in country.government; use empty

        # Generate or refresh ruleset for this empire
        self._ensure_ruleset(country_id, ethics, civics, traits, origin, government)

        ruleset = self._rulesets[country_id]
        personality = self._personalities[country_id]

        # Detect events by comparing to previous state
        event = state.get("event")
        if not event and country_id in self._previous_states:
            event = self._detect_event(country_id, state)
        self._previous_states[country_id] = state

        # Fast code-only path for obvious early-game decisions (skips LLM)
        if not event and self._fast_decisions:
            fast = self._try_fast_decision(country_id, state, ruleset)
            if fast is not None:
                return fast

        # Multi-agent path
        if self._multi_agent_config.enabled:
            return self._process_council(country_id, state, event, ruleset, personality)

        # Single-agent path
        prompt = build_prompt(ruleset, personality, state, event)

        # Query LLM
        t0 = time.monotonic()
        try:
            response = self._provider.complete(prompt)
        except LLMProviderError as exc:
            self.stats.llm_errors += 1
            log.error("AI empire %d LLM error: %s", country_id, exc)
            return None

        self.stats.last_decision_time_ms = (time.monotonic() - t0) * 1000

        try:
            directive = parse_llm_response(response.text)
        except ValueError as exc:
            self.stats.decisions_failed += 1
            log.warning("AI empire %d parse error: %s", country_id, exc)
            return None

        # Validate
        result = validate_directive(directive.to_dict(), ruleset, state)
        if not result.valid:
            self.stats.validation_errors += 1
            empire_name = _empire_display_name(state, country_id)
            log.warning(
                "[%s] directive rejected: %s", empire_name, result.errors,
            )
            return None

        self.stats.decisions_made += 1
        empire_name = _empire_display_name(state, country_id)
        self.stats.last_action = f"{directive.action} ({empire_name})"
        self.stats.empire_status[empire_name] = directive.action
        log.info(
            "[%s] → %s (%.0fms)",
            empire_name, directive.action, self.stats.last_decision_time_ms,
        )
        return directive

    def _process_council(
        self,
        country_id: int,
        state: dict,
        event: str | None,
        ruleset: dict,
        personality: dict,
    ) -> Directive | None:
        """Run multi-agent council for one AI empire."""
        from engine.multi_agent import CouncilOrchestrator

        if country_id not in self._councils:
            self._councils[country_id] = CouncilOrchestrator(
                provider=self._provider,
                government=state.get("empire", {}).get("government", "Oligarchy"),
                personality=personality,
                ruleset=ruleset,
                parallel=self._multi_agent_config.parallel,
                arbiter_uses_llm=self._multi_agent_config.arbiter_uses_llm,
            )

        council = self._councils[country_id]
        result = council.decide(state, event)
        directive = result.directive
        self.stats.last_decision_time_ms = result.total_latency_ms

        # Validate
        vresult = validate_directive(directive.to_dict(), ruleset, state)
        if not vresult.valid:
            self.stats.validation_errors += 1
            empire_name = _empire_display_name(state, country_id)
            log.warning(
                "[%s] council rejected: %s", empire_name, vresult.errors,
            )
            return None

        self.stats.decisions_made += 1
        empire_name = _empire_display_name(state, country_id)
        self.stats.last_action = f"{directive.action} ({empire_name})"
        self.stats.empire_status[empire_name] = directive.action
        log.info(
            "[%s] council → %s (%.0fms)",
            empire_name, directive.action, result.total_latency_ms,
        )
        return directive

    def _try_fast_decision(
        self,
        country_id: int,
        state: dict,
        ruleset: dict,
    ) -> Directive | None:
        """Return a code-only directive for situations where the optimal
        action is clear from the game state.  Returns None to defer to LLM."""
        year = state.get("year", 2200)
        economy = state.get("economy", {})
        fleets = state.get("fleets", [])
        colonies = state.get("colonies", [])
        known_empires = state.get("known_empires", [])
        tech = state.get("technology", {})
        fleet_power = sum(f.get("power", 0) for f in fleets) if fleets else 0
        monthly = economy.get("monthly_net", {})
        alloys = economy.get("alloys", 0)
        minerals = economy.get("minerals", 0)
        energy = economy.get("energy", 0)
        colony_count = len(colonies) if isinstance(colonies, list) else 0
        tech_count = tech.get("count", 0) if isinstance(tech, dict) else 0

        action = None
        reason = None

        # --- Emergency: resource deficit ---
        if energy < -10 or minerals < -15:
            action = "IMPROVE_ECONOMY"
            reason = "Critical resource deficit (fast path)"

        # --- Early game (pre-2220): economy foundation ---
        elif year < 2220:
            if fleet_power < 500 and alloys > 30:
                action = "BUILD_FLEET"
                reason = "Minimal fleet for early defense (fast path)"
            elif colony_count < 2 and year > 2210:
                action = "COLONIZE"
                reason = "Need initial expansion (fast path)"
            else:
                action = "IMPROVE_ECONOMY"
                reason = "Early economy ramp (fast path)"

        # --- Mid transition (2220-cutoff): diversify ---
        elif year < self._fast_cutoff_year:
            hostile = [
                e for e in known_empires
                if isinstance(e, dict)
                and e.get("attitude", "").lower() in ("hostile", "belligerent")
            ]
            # Hostile neighbor → military
            if hostile and fleet_power < 2000:
                action = "BUILD_FLEET"
                reason = "Hostile empire detected, fleet power low (fast path)"
            # Tech behind pace (should have ~40+ by 2230, ~60+ by 2240)
            elif tech_count < (year - 2200) * 2.5:
                action = "FOCUS_TECH"
                reason = f"Tech count {tech_count} behind pace (fast path)"
            # Can expand but haven't
            elif colony_count < 4 and year < 2240:
                action = "COLONIZE"
                reason = f"Only {colony_count} colonies, should expand (fast path)"
            # Alloy surplus → fleet
            elif alloys > 300 and fleet_power < 3000:
                action = "BUILD_FLEET"
                reason = "Alloy surplus, convert to fleet power (fast path)"
            # Economy weak
            elif isinstance(monthly, dict) and monthly.get("energy", 0) < 10:
                action = "IMPROVE_ECONOMY"
                reason = "Monthly energy income too low (fast path)"
            else:
                # Non-trivial situation — let LLM decide
                return None

        # --- Post-cutoff: let LLM handle complex mid/late game ---
        else:
            return None

        directive = Directive(action=action, reason=reason)

        result = validate_directive(directive.to_dict(), ruleset, state)
        if not result.valid:
            return None

        self.stats.decisions_made += 1
        self.stats.last_decision_time_ms = 0.0
        empire_name = _empire_display_name(state, country_id)
        self.stats.last_action = f"{directive.action} ({empire_name})⚡"
        self.stats.empire_status[empire_name] = f"{directive.action}⚡"
        log.info(
            "[%s] fast → %s",
            empire_name, directive.action,
        )
        return directive

    def _ensure_ruleset(
        self,
        country_id: int,
        ethics: list[str],
        civics: list[str],
        traits: list[str],
        origin: str,
        government: str,
    ) -> None:
        """Generate ruleset if missing, or refresh if empire reformed."""
        cached = self._rulesets.get(country_id)
        if cached is not None:
            # Check if ethics/civics changed (mid-game reform)
            old_ethics = sorted(cached.get("_source_ethics", []))
            new_ethics = sorted(ethics)
            old_civics = sorted(cached.get("_source_civics", []))
            new_civics = sorted(civics)
            if old_ethics == new_ethics and old_civics == new_civics:
                return  # no change
            log.info(
                "AI empire %d reformed: ethics=%s civics=%s — regenerating",
                country_id, new_ethics, new_civics,
            )

        ruleset = generate_ruleset(
            ethics=ethics, civics=civics, traits=traits,
            origin=origin, government=government,
        )
        # Store source for later comparison
        ruleset["_source_ethics"] = list(ethics)
        ruleset["_source_civics"] = list(civics)

        self._rulesets[country_id] = ruleset
        self._personalities[country_id] = build_personality(
            ethics=ethics, civics=civics, traits=traits,
            origin=origin, government=government,
        )

        # Refresh council if it exists
        if country_id in self._councils:
            self._councils[country_id].update_context(
                government=government,
                personality=self._personalities[country_id],
                ruleset=ruleset,
            )

        if cached is None:
            log.info("Generated ruleset for AI empire %d (%s)", country_id, government)

    def _detect_event(self, country_id: int, state: dict) -> str | None:
        """Detect triggering events by comparing to previous state."""
        prev = self._previous_states.get(country_id)
        if prev is None:
            return None

        # War started
        prev_wars = prev.get("wars", [])
        curr_wars = state.get("wars", [])
        if len(curr_wars) > len(prev_wars):
            return "WAR_STARTED"

        # War ended
        if len(curr_wars) < len(prev_wars):
            return "WAR_ENDED"

        # Colony gained
        prev_colonies = prev.get("colonies", [])
        curr_colonies = state.get("colonies", [])
        if len(curr_colonies) > len(prev_colonies):
            return "COLONY_GAINED"

        # Fleet lost (significant power drop)
        prev_power = sum(f.get("power", 0) for f in prev.get("fleets", []))
        curr_power = sum(f.get("power", 0) for f in state.get("fleets", []))
        if prev_power > 0 and curr_power < prev_power * 0.5:
            return "FLEET_DESTROYED"

        # Economy crash
        prev_energy = prev.get("economy", {}).get("energy", 0)
        curr_energy = state.get("economy", {}).get("energy", 0)
        if prev_energy > 50 and curr_energy < 0:
            return "ECONOMY_CRASH"

        return None
