"""
Stellaris Overmind — Entry Point

Start the AI live loop:
    python -m engine.main
    python -m engine.main --config path/to/config.toml
    python -m engine.main --provider stub   # offline testing
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent

from engine.bridge import BridgeConfig
from engine.config import load_config
from engine.game_loop import EmpireConfig, GameLoopController
from engine.hybrid_provider import HybridProvider
from engine.llm_provider import LLMProvider, StubProvider
from engine.qwen_provider import OpenAICompatProvider, QwenVLLMProvider


def _build_local_provider(cfg) -> LLMProvider | None:
    """Instantiate the local LLM provider from config."""
    name = cfg.llm.provider.lower()

    if name == "stub":
        return StubProvider()

    if name == "qwen-vllm":
        return QwenVLLMProvider(
            base_url=cfg.llm.base_url,
            model=cfg.llm.model,
            max_tokens=cfg.llm.max_tokens,
            temperature=cfg.llm.temperature,
            timeout_s=cfg.llm.timeout_s,
        )

    if name in ("openai-compat", "openai", "ollama", "azure", "foundry"):
        return OpenAICompatProvider(
            base_url=cfg.llm.base_url,
            model=cfg.llm.model,
            api_key=cfg.llm.api_key,
            max_tokens=cfg.llm.max_tokens,
            temperature=cfg.llm.temperature,
            timeout_s=cfg.llm.timeout_s,
        )

    logging.warning("Unknown provider '%s', falling back to stub", name)
    return StubProvider()


def _build_online_provider(cfg) -> LLMProvider | None:
    """Build the online API provider from [llm.online] config."""
    if not cfg.llm.online_base_url or not cfg.llm.online_model:
        return None

    return OpenAICompatProvider(
        base_url=cfg.llm.online_base_url,
        model=cfg.llm.online_model,
        api_key=cfg.llm.online_api_key,
        max_tokens=cfg.llm.online_max_tokens,
        temperature=cfg.llm.online_temperature,
        timeout_s=cfg.llm.online_timeout_s,
    )


def _build_provider(cfg) -> LLMProvider:
    """Build the final provider, handling local/online/hybrid modes."""
    mode = cfg.llm.mode.lower()
    local = _build_local_provider(cfg)
    online = _build_online_provider(cfg)

    if mode == "online":
        if online is None:
            logging.warning("Online mode requested but no [llm.online] config; using local")
            return local or StubProvider()
        return HybridProvider(online_provider=online, mode="online")

    if mode == "hybrid":
        if online is None:
            logging.warning("Hybrid mode requested but no [llm.online] config; using local only")
            return local or StubProvider()
        return HybridProvider(
            local_provider=local or StubProvider(),
            online_provider=online,
            mode="hybrid",
        )

    # Default: local only
    return local or StubProvider()


def _build_planner_provider(cfg, main_provider: LLMProvider) -> LLMProvider | None:
    """Build the planner's LLM provider.

    Returns *None* if the planner should use code-only assessment.
    Returns *main_provider* if ``provider = "same"``.
    Otherwise builds a separate OpenAI-compat provider from planner config.
    Supports ``provider = "online"`` to use the [llm.online] endpoint.
    """
    if not cfg.planner.enabled:
        return None

    prov = cfg.planner.provider.lower()
    if prov == "same":
        return main_provider

    if prov == "none":
        return None

    if prov == "online":
        online = _build_online_provider(cfg)
        if online is not None:
            return online
        logging.warning("Planner provider='online' but no [llm.online] config")
        return main_provider

    # Separate provider for the planner (e.g. Ollama with a larger model)
    return OpenAICompatProvider(
        base_url=cfg.planner.base_url or cfg.llm.base_url,
        model=cfg.planner.model or cfg.llm.model,
        api_key=cfg.llm.api_key,
        max_tokens=cfg.planner.max_tokens,
        temperature=cfg.planner.temperature,
        timeout_s=cfg.llm.timeout_s,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="overmind",
        description="Stellaris Overmind — LLM-driven AI live loop",
    )
    parser.add_argument(
        "--config", type=Path, default=None,
        help="Path to config.toml (default: project root)",
    )
    parser.add_argument(
        "--provider", type=str, default=None,
        help="Override LLM provider: qwen-vllm | openai-compat | stub",
    )
    parser.add_argument(
        "--console", action="store_true",
        help="Launch Rich TUI dashboard instead of plain logging",
    )
    parser.add_argument(
        "--log-file", type=Path, default=None,
        help="Write logs to file (auto-set to overmind.log when using --console)",
    )
    parser.add_argument(
        "--setup", action="store_true",
        help="Run the interactive setup wizard (creates config.toml)",
    )
    args = parser.parse_args()

    # Run setup wizard if requested or if config doesn't exist
    if args.setup:
        from engine.setup_wizard import run_wizard, write_config
        config = run_wizard()
        write_config(config)
        return

    # Auto-detect missing config
    config_path = args.config
    if config_path is None:
        from engine.setup_wizard import ensure_config
        config_path = ensure_config()

    # Load config
    cfg = load_config(config_path)
    if args.provider:
        cfg.llm.provider = args.provider

    # Setup logging
    log_level = getattr(logging, cfg.log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    # When using --console, also write logs to a file for a parallel tail view
    log_file = args.log_file
    if args.console and log_file is None:
        log_file = _PROJECT_ROOT / "overmind.log"
    if log_file is not None:
        file_handler = logging.FileHandler(log_file, mode="w", encoding="utf-8")
        file_handler.setLevel(log_level)
        file_handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(name)s] %(levelname)s: %(message)s", datefmt="%H:%M:%S",
        ))
        logging.getLogger().addHandler(file_handler)

    log = logging.getLogger("overmind")

    # Build provider
    provider = _build_provider(cfg)
    log.info("LLM provider: %s", provider.name)

    if not provider.is_available():
        log.warning("LLM provider is not reachable — will use stub fallback")
        if not isinstance(provider, StubProvider):
            provider = StubProvider()

    # Build bridge config
    save_dir = Path(cfg.bridge.save_dir) if cfg.bridge.save_dir else Path("")
    bridge = BridgeConfig(
        save_dir=save_dir,
        player_name=cfg.bridge.player_name,
        bridge_dir=Path(cfg.bridge.bridge_dir),
        poll_interval_s=cfg.bridge.poll_interval_s,
    )

    # Build planner provider (may differ from main provider)
    planner_provider = _build_planner_provider(cfg, provider)

    target_mode = cfg.target.mode.lower()

    if target_mode == "ai":
        # AI mode — control AI empires
        from engine.game_loop import AILoopController
        from engine.recorder import GameRecorder

        recorder = GameRecorder(
            replay_dir=Path(cfg.training.replay_dir),
        )

        controller = AILoopController(
            provider=provider,
            bridge_config=bridge,
            max_retries=cfg.max_retries,
            country_ids=cfg.target.ai_country_ids or None,
            exclude_ids=cfg.target.ai_exclude_ids or None,
            exclude_fallen=cfg.target.ai_exclude_fallen,
            multi_agent_config=cfg.multi_agent,
            parallel_empires=cfg.multi_agent.parallel,
            recorder=recorder,
            fast_decisions=cfg.target.fast_decisions,
            fast_cutoff_year=cfg.target.fast_cutoff_year,
        )

        log.info("=" * 60)
        log.info("  STELLARIS OVERMIND — AI Mode")
        log.info("  Provider : %s", provider.name)
        log.info("  LLM Mode : %s", cfg.llm.mode)
        log.info("  Target   : AI empires")
        log.info("  IDs      : %s", cfg.target.ai_country_ids or "all")
        log.info("  Exclude  : %s", cfg.target.ai_exclude_ids or "none")
        log.info("  Fallen   : %s", "excluded" if cfg.target.ai_exclude_fallen else "included")
        log.info("  Council  : %s", "enabled" if cfg.multi_agent.enabled else "disabled")
        log.info("  Parallel : %s", cfg.multi_agent.parallel)
        if bridge.mode == "autosave":
            log.info("  Save Dir : %s", bridge.save_dir)
        log.info("  Bridge   : %s", bridge.bridge_dir)
        log.info("=" * 60)

    else:
        # Player mode (default) — control the human player's empire
        empire = EmpireConfig(
            ethics=cfg.empire.ethics,
            civics=cfg.empire.civics,
            traits=cfg.empire.traits,
            origin=cfg.empire.origin,
            government=cfg.empire.government,
        )

        controller = GameLoopController(
            empire=empire,
            provider=provider,
            bridge_config=bridge,
            max_retries=cfg.max_retries,
            multi_agent_config=cfg.multi_agent,
            planner_config=cfg.planner,
            planner_provider=planner_provider,
        )

        auto_label = " (auto-detect)" if cfg.empire.auto_detect else ""
        log.info("=" * 60)
        log.info("  STELLARIS OVERMIND — Player Mode")
        log.info("  Provider : %s", provider.name)
        log.info("  LLM Mode : %s", cfg.llm.mode)
        if cfg.empire.auto_detect:
            log.info("  Empire   : auto-detect from save file")
        else:
            log.info("  Origin   : %s", empire.origin)
        log.info("  Bridge   : %s (%s)", bridge.bridge_dir, bridge.mode)
        log.info("  Council  : %s", "enabled" if cfg.multi_agent.enabled else "disabled")
        log.info("  Planner  : %s", "enabled" if cfg.planner.enabled else "disabled")
        log.info("=" * 60)

    # Launch with or without console TUI
    if args.console:
        _run_with_console(controller, provider, cfg, target_mode, log_file)
    else:
        controller.run()


def _run_with_console(
    controller: object,
    provider: LLMProvider,
    cfg: object,
    target_mode: str,
    log_file: Path | None = None,
) -> None:
    """Run the game loop in a background thread with the Rich TUI in foreground."""
    import threading

    from engine.console import ConsoleConfig, run_console
    from engine.metrics import MetricsCollector

    metrics = MetricsCollector()
    console_config = ConsoleConfig(
        llm_mode=cfg.llm.mode,
        council_enabled=cfg.multi_agent.enabled,
        planner_enabled=cfg.planner.enabled,
        recording_enabled=hasattr(controller, "_recorder") and controller._recorder is not None,
        fast_decisions=cfg.target.fast_decisions,
    )
    stop_event = threading.Event()

    # Game loop in background thread
    def _loop_thread() -> None:
        try:
            controller.run()
        finally:
            stop_event.set()

    # Stats sync thread — periodically pulls from controller/provider
    def _stats_sync_thread() -> None:
        while not stop_event.is_set():
            if hasattr(controller, "stats"):
                metrics.update_from_loop(controller.stats)
                metrics.update_settings(
                    game_year=getattr(controller.stats, "game_year", None),
                )
            if hasattr(provider, "stats"):
                metrics.update_from_provider(provider.stats)
            # Pull prompt cache stats if available
            if hasattr(controller, "_prompt_cache"):
                metrics.update_from_cache(controller._prompt_cache.stats)
            elif hasattr(controller, "prompt_cache"):
                metrics.update_from_cache(controller.prompt_cache.stats)
            # Push TUI toggle back to controller
            if hasattr(controller, "_fast_decisions"):
                controller._fast_decisions = console_config.fast_decisions
            stop_event.wait(1.0)

    loop_thread = threading.Thread(target=_loop_thread, daemon=True)
    sync_thread = threading.Thread(target=_stats_sync_thread, daemon=True)
    loop_thread.start()
    sync_thread.start()

    # Foreground: console TUI (blocks until Q or Ctrl+C)
    run_console(
        metrics_collector=metrics,
        console_config=console_config,
        stop_event=stop_event,
        provider_name=provider.name,
        target_mode=target_mode,
        log_file=str(log_file) if log_file else None,
    )

    # Shutdown
    if hasattr(controller, "stop"):
        controller.stop()
    loop_thread.join(timeout=5)


if __name__ == "__main__":
    main()
