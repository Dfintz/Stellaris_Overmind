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
    model: str = "Qwen/Qwen2.5-7B-Instruct-GPTQ-Int4"
    max_tokens: int = 256
    temperature: float = 0.3
    timeout_s: float = 30.0
    api_key: str = ""

    # Hybrid / online mode
    mode: str = "local"                       # local | online | hybrid
    online_base_url: str = ""                 # e.g. https://openrouter.ai/api/v1
    online_model: str = ""                    # e.g. qwen/qwen-2.5-72b-instruct
    online_api_key: str = ""
    online_max_tokens: int = 256
    online_temperature: float = 0.3
    online_timeout_s: float = 60.0

    # Prompt optimization
    compact_json: bool = True                 # minified JSON in prompts
    prompt_cache: bool = True                 # cache static prompt prefixes


@dataclass
class StellarisConfig:
    """Stellaris installation paths."""

    install_dir: str = ""
    user_data_dir: str = ""
    mod_name: str = "stellaris_overmind"


@dataclass
class BridgePathConfig:
    """File bridge paths."""

    # Autosave directory (enables autosave mode if it exists)
    save_dir: str = ""
    player_name: str = ""  # auto-detected from save if empty

    # Directive output directory (mod reads this)
    bridge_dir: str = ""
    poll_interval_s: float = 2.0


@dataclass
class EmpireStartConfig:
    """Empire definition loaded at startup.

    If all fields are empty (``auto_detect = true``), the engine reads the
    player's ethics/civics/origin/government from the first save file
    automatically — no manual config needed.

    In ``ai`` mode this is always ignored — empires are auto-detected.
    """

    auto_detect: bool = True
    ethics: list[str] = field(default_factory=list)
    civics: list[str] = field(default_factory=list)
    traits: list[str] = field(default_factory=list)
    origin: str = ""
    government: str = ""


@dataclass
class TargetConfig:
    """Which empires the Overmind controls.

    Modes:
      - ``player`` — control the human player's empire (default)
      - ``ai``     — control AI empires (replace Stellaris' built-in AI)
    """

    mode: str = "player"                    # "player" | "ai"
    ai_country_ids: list[int] = field(default_factory=list)  # empty = all AI
    ai_exclude_ids: list[int] = field(default_factory=list)  # skip these AIs
    ai_exclude_fallen: bool = True          # skip Fallen Empires by default


@dataclass
class MultiAgentConfig:
    """Multi-agent council configuration."""

    enabled: bool = False
    parallel: bool = True
    arbiter_uses_llm: bool = True


@dataclass
class PlannerConfig:
    """Strategic planner configuration."""

    enabled: bool = False
    provider: str = "same"           # "same" = use main LLM provider
    base_url: str = ""               # only if provider != "same"
    model: str = ""                  # only if provider != "same"
    interval_years: int = 5          # how often to re-plan
    max_tokens: int = 512            # planner gets more room than sub-agents
    temperature: float = 0.4


@dataclass
class TrainingConfig:
    """Training pipeline configuration."""

    replay_dir: str = "training/replay_buffer"
    sft_threshold: float = 0.3              # min composite score for SFT data
    dpo_margin: float = 0.2                 # min score gap for DPO pairs
    teacher_model: str = ""                 # e.g. qwen/qwen-2.5-72b-instruct
    teacher_base_url: str = ""              # e.g. https://openrouter.ai/api/v1
    teacher_api_key: str = ""               # API key for teacher endpoint
    quantize_method: str = "gptq"           # gptq | awq
    quantize_bits: int = 4


@dataclass
class OvermindConfig:
    """Top-level configuration container."""

    stellaris: StellarisConfig = field(default_factory=StellarisConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    bridge: BridgePathConfig = field(default_factory=BridgePathConfig)
    empire: EmpireStartConfig = field(default_factory=EmpireStartConfig)
    target: TargetConfig = field(default_factory=TargetConfig)
    multi_agent: MultiAgentConfig = field(default_factory=MultiAgentConfig)
    planner: PlannerConfig = field(default_factory=PlannerConfig)
    training: TrainingConfig = field(default_factory=TrainingConfig)
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
        cfg.llm.mode = llm.get("mode", cfg.llm.mode)
        cfg.llm.compact_json = llm.get("compact_json", cfg.llm.compact_json)
        cfg.llm.prompt_cache = llm.get("prompt_cache", cfg.llm.prompt_cache)

        # Online sub-section
        if "online" in llm:
            ol = llm["online"]
            cfg.llm.online_base_url = ol.get("base_url", cfg.llm.online_base_url)
            cfg.llm.online_model = ol.get("model", cfg.llm.online_model)
            cfg.llm.online_api_key = ol.get("api_key", cfg.llm.online_api_key)
            cfg.llm.online_max_tokens = ol.get("max_tokens", cfg.llm.online_max_tokens)
            cfg.llm.online_temperature = ol.get(
                "temperature", cfg.llm.online_temperature,
            )
            cfg.llm.online_timeout_s = ol.get("timeout_s", cfg.llm.online_timeout_s)

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
        cfg.empire.auto_detect = emp.get("auto_detect", cfg.empire.auto_detect)
        cfg.empire.ethics = emp.get("ethics", cfg.empire.ethics)
        cfg.empire.civics = emp.get("civics", cfg.empire.civics)
        cfg.empire.traits = emp.get("traits", cfg.empire.traits)
        cfg.empire.origin = emp.get("origin", cfg.empire.origin)
        cfg.empire.government = emp.get("government", cfg.empire.government)
        # If any field is set, disable auto-detect
        if cfg.empire.ethics or cfg.empire.origin:
            cfg.empire.auto_detect = emp.get("auto_detect", False)

    cfg.log_level = data.get("log_level", cfg.log_level)
    cfg.max_retries = data.get("max_retries", cfg.max_retries)

    # Target section
    if "target" in data:
        tgt = data["target"]
        cfg.target.mode = tgt.get("mode", cfg.target.mode)
        cfg.target.ai_country_ids = tgt.get("ai_country_ids", cfg.target.ai_country_ids)
        cfg.target.ai_exclude_ids = tgt.get("ai_exclude_ids", cfg.target.ai_exclude_ids)
        cfg.target.ai_exclude_fallen = tgt.get("ai_exclude_fallen", cfg.target.ai_exclude_fallen)

    # Multi-agent section
    if "multi_agent" in data:
        ma = data["multi_agent"]
        cfg.multi_agent.enabled = ma.get("enabled", cfg.multi_agent.enabled)
        cfg.multi_agent.parallel = ma.get("parallel", cfg.multi_agent.parallel)
        cfg.multi_agent.arbiter_uses_llm = ma.get(
            "arbiter_uses_llm", cfg.multi_agent.arbiter_uses_llm,
        )

    # Planner section
    if "planner" in data:
        pl = data["planner"]
        cfg.planner.enabled = pl.get("enabled", cfg.planner.enabled)
        cfg.planner.provider = pl.get("provider", cfg.planner.provider)
        cfg.planner.base_url = pl.get("base_url", cfg.planner.base_url)
        cfg.planner.model = pl.get("model", cfg.planner.model)
        cfg.planner.interval_years = pl.get("interval_years", cfg.planner.interval_years)
        cfg.planner.max_tokens = pl.get("max_tokens", cfg.planner.max_tokens)
        cfg.planner.temperature = pl.get("temperature", cfg.planner.temperature)

    # Training section
    if "training" in data:
        tr = data["training"]
        cfg.training.replay_dir = tr.get("replay_dir", cfg.training.replay_dir)
        cfg.training.sft_threshold = tr.get("sft_threshold", cfg.training.sft_threshold)
        cfg.training.dpo_margin = tr.get("dpo_margin", cfg.training.dpo_margin)
        cfg.training.teacher_model = tr.get("teacher_model", cfg.training.teacher_model)
        cfg.training.teacher_base_url = tr.get("teacher_base_url", cfg.training.teacher_base_url)
        cfg.training.quantize_method = tr.get("quantize_method", cfg.training.quantize_method)
        cfg.training.quantize_bits = tr.get("quantize_bits", cfg.training.quantize_bits)

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
    if v := os.environ.get("OVERMIND_LLM_ONLINE_API_KEY"):
        cfg.llm.online_api_key = v
    if v := os.environ.get("OVERMIND_LLM_MODE"):
        cfg.llm.mode = v
    if v := os.environ.get("OVERMIND_BRIDGE_DIR"):
        cfg.bridge.bridge_dir = v
    if v := os.environ.get("OVERMIND_LOG_LEVEL"):
        cfg.log_level = v
