"""
Configuration — Loads settings from ``config.toml`` or environment variables.

Hierarchy (highest priority first):
  1. Environment variables (``OVERMIND_LLM_URL``, etc.)
  2. ``config.toml`` in project root
  3. Built-in defaults
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class LLMConfig:
    """LLM backend configuration."""

    provider: str = "qwen-vllm"  # qwen-vllm | openai-compat | stub
    base_url: str = "http://localhost:8000"
    model: str = "Qwen/Qwen2.5-Omni-7B"
    max_tokens: int = 256
    temperature: float = 0.3
    timeout_s: float = 30.0
    api_key: str = ""


@dataclass
class StellarisConfig:
    """Stellaris installation paths."""

    install_dir: str = "G:/SteamLibrary/steamapps/common/Stellaris"
    user_data_dir: str = "C:/Users/Fintz/OneDrive/Documents/Paradox Interactive/Stellaris"
    mod_name: str = "stellaris_overmind"


@dataclass
class BridgePathConfig:
    """File bridge paths."""

    # Autosave directory (enables autosave mode if it exists)
    save_dir: str = "C:/Users/Fintz/OneDrive/Documents/Paradox Interactive/Stellaris/save games"
    player_name: str = ""  # auto-detected from save if empty

    # Directive output directory (mod reads this)
    bridge_dir: str = "C:/Users/Fintz/OneDrive/Documents/Paradox Interactive/Stellaris/mod/stellaris_overmind/ai_bridge"
    poll_interval_s: float = 2.0


@dataclass
class EmpireStartConfig:
    """Empire definition loaded at startup."""

    ethics: list[str] = field(default_factory=lambda: ["Militarist", "Materialist"])
    civics: list[str] = field(default_factory=lambda: ["Technocracy"])
    traits: list[str] = field(default_factory=lambda: ["Intelligent"])
    origin: str = "Prosperous Unification"
    government: str = "Oligarchy"


@dataclass
class OvermindConfig:
    """Top-level configuration container."""

    stellaris: StellarisConfig = field(default_factory=StellarisConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    bridge: BridgePathConfig = field(default_factory=BridgePathConfig)
    empire: EmpireStartConfig = field(default_factory=EmpireStartConfig)
    log_level: str = "INFO"
    max_retries: int = 2


def load_config(config_path: Path | None = None) -> OvermindConfig:
    """Load configuration from TOML file and environment overrides."""
    cfg = OvermindConfig()

    # Try loading TOML if available
    if config_path is None:
        config_path = _PROJECT_ROOT / "config.toml"

    if config_path.exists():
        cfg = _load_toml(config_path, cfg)

    # Environment overrides (highest priority)
    _apply_env_overrides(cfg)

    return cfg


def _load_toml(path: Path, cfg: OvermindConfig) -> OvermindConfig:
    """Parse config.toml into the config dataclass."""
    try:
        import tomllib  # Python 3.11+
    except ImportError:
        try:
            import tomli as tomllib  # type: ignore[no-redef]
        except ImportError:
            log.warning("No TOML parser available; skipping %s", path)
            return cfg

    raw = path.read_text(encoding="utf-8")
    data = tomllib.loads(raw)

    # Stellaris section
    if "stellaris" in data:
        st = data["stellaris"]
        cfg.stellaris.install_dir = st.get("install_dir", cfg.stellaris.install_dir)
        cfg.stellaris.user_data_dir = st.get("user_data_dir", cfg.stellaris.user_data_dir)
        cfg.stellaris.mod_name = st.get("mod_name", cfg.stellaris.mod_name)

    # LLM section
    if "llm" in data:
        llm = data["llm"]
        cfg.llm.provider = llm.get("provider", cfg.llm.provider)
        cfg.llm.base_url = llm.get("base_url", cfg.llm.base_url)
        cfg.llm.model = llm.get("model", cfg.llm.model)
        cfg.llm.max_tokens = llm.get("max_tokens", cfg.llm.max_tokens)
        cfg.llm.temperature = llm.get("temperature", cfg.llm.temperature)
        cfg.llm.timeout_s = llm.get("timeout_s", cfg.llm.timeout_s)

    # Bridge section
    if "bridge" in data:
        br = data["bridge"]
        cfg.bridge.save_dir = br.get("save_dir", cfg.bridge.save_dir)
        cfg.bridge.player_name = br.get("player_name", cfg.bridge.player_name)
        cfg.bridge.bridge_dir = br.get("bridge_dir", cfg.bridge.bridge_dir)
        cfg.bridge.poll_interval_s = br.get("poll_interval_s", cfg.bridge.poll_interval_s)

    # Empire section
    if "empire" in data:
        emp = data["empire"]
        cfg.empire.ethics = emp.get("ethics", cfg.empire.ethics)
        cfg.empire.civics = emp.get("civics", cfg.empire.civics)
        cfg.empire.traits = emp.get("traits", cfg.empire.traits)
        cfg.empire.origin = emp.get("origin", cfg.empire.origin)
        cfg.empire.government = emp.get("government", cfg.empire.government)

    cfg.log_level = data.get("log_level", cfg.log_level)
    cfg.max_retries = data.get("max_retries", cfg.max_retries)

    log.info("Loaded config from %s", path)
    return cfg


def _apply_env_overrides(cfg: OvermindConfig) -> None:
    """Override config values from environment variables."""
    if v := os.environ.get("OVERMIND_LLM_PROVIDER"):
        cfg.llm.provider = v
    if v := os.environ.get("OVERMIND_LLM_URL"):
        cfg.llm.base_url = v
    if v := os.environ.get("OVERMIND_LLM_MODEL"):
        cfg.llm.model = v
    if v := os.environ.get("OVERMIND_LLM_API_KEY"):
        cfg.llm.api_key = v
    if v := os.environ.get("OVERMIND_BRIDGE_DIR"):
        cfg.bridge.bridge_dir = v
    if v := os.environ.get("OVERMIND_LOG_LEVEL"):
        cfg.log_level = v
