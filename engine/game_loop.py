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
import time
from dataclasses import dataclass, field

from engine.bridge import BridgeConfig, BridgeWriter, UnifiedBridge
from engine.decision_engine import Directive, build_prompt, parse_llm_response
from engine.llm_provider import LLMProvider, LLMProviderError, StubProvider
from engine.personality_shards import build_personality
from engine.recorder import GameRecorder
from engine.ruleset_generator import generate_ruleset
from engine.validator import validate_directive

log = logging.getLogger(__name__)


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


class GameLoopController:
    """The main live loop connecting Stellaris to the LLM."""

    def __init__(
        self,
        empire: EmpireConfig,
        provider: LLMProvider | None = None,
        bridge_config: BridgeConfig | None = None,
        max_retries: int = 2,
        recorder: GameRecorder | None = None,
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

        # Pre-compute static ruleset and personality (they don't change mid-game)
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

        log.info(
            "Controller initialized: origin=%s gov=%s meta_tier=%s provider=%s",
            empire.origin, empire.government,
            self._ruleset.get("meta_tier", "?"),
            self._provider.name,
        )

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

        # Refresh ruleset if empire changed mid-game (government reform)
        self._maybe_refresh_ruleset(snapshot)

        # Check for ack from previous directive (JSON mode only)
        ack = self._bridge.read_ack()
        if ack:
            log.debug("Previous directive acknowledged: %s", ack.get("status"))
            self._writer.clear_directive()

        # Retroactively score older decisions now that we have fresh state
        self._recorder.update_outcomes(snapshot)

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
        """Write the directive to the bridge for the mod to consume."""
        payload = directive.to_dict()
        payload["timestamp"] = f"{state.get('year', 0)}.{state.get('month', 0)}"
        payload["meta"] = {
            "provider": self._provider.name,
            "latency_ms": round(self.stats.last_decision_time_ms),
            "meta_tier": self._ruleset.get("meta_tier", "?"),
        }
        self._writer.write_directive(payload)

    def _maybe_refresh_ruleset(self, state: dict) -> None:
        """Regenerate ruleset if the empire's ethics/civics changed mid-game."""
        empire_info = state.get("empire", {})
        if not empire_info:
            return

        current_ethics = sorted(empire_info.get("ethics", []))
        current_civics = sorted(empire_info.get("civics", []))
        config_ethics = sorted(self._empire.ethics)
        config_civics = sorted(self._empire.civics)

        if current_ethics != config_ethics or current_civics != config_civics:
            log.info(
                "Empire changed mid-game: ethics=%s civics=%s — regenerating ruleset",
                current_ethics, current_civics,
            )
            self._ruleset = generate_ruleset(
                ethics=current_ethics or self._empire.ethics,
                civics=current_civics or self._empire.civics,
                traits=self._empire.traits,
                origin=empire_info.get("origin", self._empire.origin),
                government=empire_info.get("government", self._empire.government),
            )
            self._personality = build_personality(
                ethics=current_ethics or self._empire.ethics,
                civics=current_civics or self._empire.civics,
                traits=self._empire.traits,
                origin=empire_info.get("origin", self._empire.origin),
                government=empire_info.get("government", self._empire.government),
            )
