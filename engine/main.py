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
import sys
from pathlib import Path

from engine.bridge import BridgeConfig
from engine.config import load_config
from engine.game_loop import EmpireConfig, GameLoopController
from engine.llm_provider import LLMProvider, StubProvider
from engine.qwen_provider import OpenAICompatProvider, QwenVLLMProvider


def _build_provider(cfg) -> LLMProvider:
    """Instantiate the correct LLM provider from config."""
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

    if name in ("openai-compat", "openai", "ollama"):
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
    args = parser.parse_args()

    # Load config
    cfg = load_config(args.config)
    if args.provider:
        cfg.llm.provider = args.provider

    # Setup logging
    logging.basicConfig(
        level=getattr(logging, cfg.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    log = logging.getLogger("overmind")

    # Build provider
    provider = _build_provider(cfg)
    log.info("LLM provider: %s", provider.name)

    if not provider.is_available():
        log.warning("LLM provider is not reachable — will use stub fallback")
        if not isinstance(provider, StubProvider):
            provider = StubProvider()

    # Build empire config
    empire = EmpireConfig(
        ethics=cfg.empire.ethics,
        civics=cfg.empire.civics,
        traits=cfg.empire.traits,
        origin=cfg.empire.origin,
        government=cfg.empire.government,
    )

    # Build bridge config
    save_dir = Path(cfg.bridge.save_dir) if cfg.bridge.save_dir else Path("")
    bridge = BridgeConfig(
        save_dir=save_dir,
        player_name=cfg.bridge.player_name,
        bridge_dir=Path(cfg.bridge.bridge_dir),
        poll_interval_s=cfg.bridge.poll_interval_s,
    )

    # Create and run the controller
    controller = GameLoopController(
        empire=empire,
        provider=provider,
        bridge_config=bridge,
        max_retries=cfg.max_retries,
    )

    log.info("=" * 60)
    log.info("  STELLARIS OVERMIND — Live Loop")
    log.info("  Provider : %s", provider.name)
    log.info("  Origin   : %s", empire.origin)
    log.info("  Mode     : %s", bridge.mode)
    if bridge.mode == "autosave":
        log.info("  Save Dir : %s", bridge.save_dir)
    log.info("  Bridge   : %s", bridge.bridge_dir)
    log.info("=" * 60)

    controller.run()


if __name__ == "__main__":
    main()
