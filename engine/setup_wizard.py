"""
Setup Wizard — Interactive first-run configuration and path auto-discovery.

When no ``config.toml`` exists, the engine launches this wizard to guide
the user through initial setup.  Can also be run standalone:

    python -m engine.setup_wizard
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

log = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent

# RFC 1918 / loopback prefixes for local vs cloud detection
_LOCAL_URL_MARKERS = (
    "localhost", "127.0.0.1", "127.0.0.", "::1",
    "192.168.", "10.", "172.16.", "172.17.", "172.18.", "172.19.",
    "172.20.", "172.21.", "172.22.", "172.23.", "172.24.", "172.25.",
    "172.26.", "172.27.", "172.28.", "172.29.", "172.30.", "172.31.",
    "169.254.",  # link-local
)


def _is_local_url(url: str) -> bool:
    """Return True if the URL points to localhost or a private network address."""
    return any(marker in url for marker in _LOCAL_URL_MARKERS)


def _validate_url_scheme(url: str) -> str:
    """Validate that a URL uses http:// or https:// and return it unchanged.

    Raises ValueError if the scheme is missing or invalid.
    """
    if not url.startswith(("http://", "https://")):
        raise ValueError(
            f"Invalid URL scheme: '{url}'. Must start with http:// or https://"
        )
    return url


# ======================================================================== #
# Path Auto-Discovery
# ======================================================================== #

def discover_stellaris_install() -> Path | None:
    """Find the Stellaris installation directory."""
    candidates = []

    if sys.platform == "win32":
        # Common Steam locations on Windows
        for drive in ["C:/", "D:/", "E:/", "F:/", "G:/", "H:/"]:
            candidates.extend([
                Path(drive) / "Program Files (x86)/Steam/steamapps/common/Stellaris",
                Path(drive) / "Program Files/Steam/steamapps/common/Stellaris",
                Path(drive) / "SteamLibrary/steamapps/common/Stellaris",
                Path(drive) / "Steam/steamapps/common/Stellaris",
                Path(drive) / "Games/Steam/steamapps/common/Stellaris",
            ])
    else:
        home = Path.home()
        candidates.extend([
            home / ".steam/steam/steamapps/common/Stellaris",
            home / ".local/share/Steam/steamapps/common/Stellaris",
        ])

    for p in candidates:
        if p.exists() and ((p / "stellaris.exe").exists() or (p / "stellaris").exists()):
            return p

    return None


def discover_user_data() -> Path | None:
    """Find the Stellaris user data directory (saves, mods, logs)."""
    candidates = []

    if sys.platform == "win32":
        home = Path.home()
        candidates.extend([
            home / "Documents/Paradox Interactive/Stellaris",
            home / "OneDrive/Documents/Paradox Interactive/Stellaris",
            Path(os.environ.get("USERPROFILE", "")) / "Documents/Paradox Interactive/Stellaris",
        ])
    else:
        home = Path.home()
        candidates.extend([
            home / ".local/share/Paradox Interactive/Stellaris",
            home / "Documents/Paradox Interactive/Stellaris",
        ])

    for p in candidates:
        if p.exists():
            return p

    return None


def discover_save_dir(user_data: Path | None = None) -> Path | None:
    """Find the save games directory."""
    if user_data is None:
        user_data = discover_user_data()
    if user_data is not None:
        save_dir = user_data / "save games"
        if save_dir.exists():
            return save_dir
    return None


def check_ollama(base_url: str = "http://localhost:11434") -> tuple[bool, str]:
    """Check if Ollama is running and what models are available."""
    import urllib.error
    import urllib.request
    try:
        _validate_url_scheme(base_url)
        req = urllib.request.Request(f"{base_url.rstrip('/')}/api/tags")
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode())
            models = [m["name"] for m in data.get("models", [])]
            return True, ", ".join(models) if models else "no models pulled"
    except (urllib.error.URLError, OSError, json.JSONDecodeError, ValueError) as exc:
        log.debug("Ollama check failed: %s", exc)
        return False, "not reachable"


def check_lm_studio(base_url: str = "http://localhost:1234") -> tuple[bool, str]:
    """Check if LM Studio is running and what models are loaded."""
    import urllib.error
    import urllib.request
    try:
        _validate_url_scheme(base_url)
        req = urllib.request.Request(f"{base_url.rstrip('/')}/v1/models")
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode())
            models = [m["id"] for m in data.get("data", [])]
            return True, ", ".join(models) if models else "no models loaded"
    except (urllib.error.URLError, OSError, json.JSONDecodeError, ValueError) as exc:
        log.debug("LM Studio check failed: %s", exc)
        return False, "not reachable"


def list_ollama_models(base_url: str = "http://localhost:11434") -> list[str]:
    """Return list of model names available in Ollama."""
    import urllib.error
    import urllib.request
    try:
        _validate_url_scheme(base_url)
        req = urllib.request.Request(f"{base_url.rstrip('/')}/api/tags")
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode())
            return [m["name"] for m in data.get("models", [])]
    except (urllib.error.URLError, OSError, json.JSONDecodeError, ValueError) as exc:
        log.debug("Ollama model listing failed: %s", exc)
        return []


def pull_ollama_model(
    model: str,
    base_url: str = "http://localhost:11434",
) -> bool:
    """Pull a model from Ollama's registry. Shows progress."""
    import urllib.request
    import urllib.error

    url = f"{base_url.rstrip('/')}/api/pull"
    payload = json.dumps({"name": model, "stream": True}).encode()
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    print(f"  Pulling {model} from Ollama registry...")
    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            last_status = ""
            for line in resp:
                line = line.decode().strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                except json.JSONDecodeError:
                    continue
                status = msg.get("status", "")
                if status != last_status:
                    if "pulling" in status or "downloading" in status:
                        total = msg.get("total", 0)
                        completed = msg.get("completed", 0)
                        if total > 0:
                            pct = completed / total * 100
                            size_gb = total / (1024**3)
                            print(
                                f"\r  {status} ({pct:.0f}% of {size_gb:.1f} GB)   ",
                                end="", flush=True,
                            )
                        else:
                            print(f"\r  {status}   ", end="", flush=True)
                    elif status == "success":
                        print(f"\n  Model {model} pulled successfully!")
                        return True
                    else:
                        print(f"\r  {status}   ", end="", flush=True)
                    last_status = status
                elif msg.get("total", 0) > 0:
                    total = msg["total"]
                    completed = msg.get("completed", 0)
                    pct = completed / total * 100
                    print(f"\r  {status} ({pct:.0f}%)   ", end="", flush=True)
        print()
        return True
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode() if exc.fp else str(exc)
        print(f"\n  Failed to pull {model}: HTTP {exc.code} — {detail}")
        return False
    except urllib.error.URLError as exc:
        print(f"\n  Failed to pull {model}: {exc.reason}")
        return False
    except Exception as exc:
        print(f"\n  Failed to pull {model}: {exc}")
        return False


# ======================================================================== #
# Interactive Setup Wizard
# ======================================================================== #

def _ask(prompt: str, default: str = "") -> str:
    """Prompt user with a default value."""
    if default:
        result = input(f"  {prompt} [{default}]: ").strip()
        return result if result else default
    return input(f"  {prompt}: ").strip()


def _ask_choice(prompt: str, options: list[str], default: str = "") -> str:
    """Prompt user to pick from options."""
    print(f"  {prompt}")
    for i, opt in enumerate(options, 1):
        marker = " (default)" if opt == default else ""
        print(f"    {i}. {opt}{marker}")
    while True:
        raw = input(f"  Choice [1-{len(options)}]: ").strip()
        if not raw and default:
            return default
        try:
            idx = int(raw) - 1
            if 0 <= idx < len(options):
                return options[idx]
            else:
                print(f"  Please enter 1-{len(options)}")
        except ValueError:
            if raw in options:
                return raw
            print(f"  Please enter 1-{len(options)}")


def _ask_bool(prompt: str, default: bool = True) -> bool:
    """Prompt yes/no."""
    d = "Y/n" if default else "y/N"
    raw = input(f"  {prompt} [{d}]: ").strip().lower()
    if not raw:
        return default
    return raw in ("y", "yes", "1", "true")


def run_wizard() -> dict:
    """Run the interactive setup wizard. Returns config dict."""
    print("\n" + "=" * 60)
    print("  STELLARIS OVERMIND — First-Run Setup")
    print("=" * 60)

    config: dict = {}

    # --- 1. Mode ---
    print("\n[1/6] Game Mode")
    mode = _ask_choice(
        "How should the Overmind operate?",
        ["ai — Control all AI empires", "player — Strategic advisor (suggestions only)"],
        default="ai — Control all AI empires",
    )
    config["target_mode"] = "ai" if mode.startswith("ai") else "player"

    # --- 2. Paths ---
    print("\n[2/6] Stellaris Paths")
    install = discover_stellaris_install()
    user_data = discover_user_data()
    save_dir = discover_save_dir(user_data)

    if install:
        print(f"  Found Stellaris at: {install}")
        config["install_dir"] = _ask("Stellaris install path", str(install))
    else:
        config["install_dir"] = _ask("Stellaris install path (not found — enter manually)")

    if user_data:
        print(f"  Found user data at: {user_data}")
        config["user_data_dir"] = _ask("User data path", str(user_data))
    else:
        config["user_data_dir"] = _ask("User data path (not found — enter manually)")

    if save_dir:
        config["save_dir"] = _ask("Save games path", str(save_dir))
    else:
        config["save_dir"] = _ask("Save games path", str(Path(config["user_data_dir"]) / "save games"))

    config["bridge_dir"] = str(
        Path(config["user_data_dir"]) / "mod/stellaris_overmind/ai_bridge"
    )

    # --- 3. LLM Provider ---
    print("\n[3/6] LLM Provider")
    ollama_ok, ollama_info = check_ollama()
    lmstudio_ok, lmstudio_info = check_lm_studio()

    if ollama_ok:
        print(f"  Ollama detected locally: {ollama_info}")
    if lmstudio_ok:
        print(f"  LM Studio detected locally: {lmstudio_info}")

    # Build provider options based on what's detected
    provider_options = []
    default_provider = "stub — Offline testing (no LLM needed)"

    if ollama_ok:
        provider_options.append("ollama — Local or network Ollama (recommended)")
        default_provider = "ollama — Local or network Ollama (recommended)"
    if lmstudio_ok:
        provider_options.append("lm-studio — LM Studio (local, parallel requests)")
        if not ollama_ok:
            default_provider = "lm-studio — LM Studio (local, parallel requests)"
    provider_options.append("ollama — Local or network Ollama (recommended)" if "ollama" not in str(provider_options) else "")
    provider_options.append("lm-studio — LM Studio (local, parallel requests)" if "lm-studio" not in str(provider_options) else "")
    provider_options = [p for p in provider_options if p]  # remove empty
    provider_options.extend([
        "openai-compat — Any OpenAI-compatible API (vLLM, cloud, etc.)",
        "stub — Offline testing (no LLM needed)",
    ])

    provider = _ask_choice(
        "LLM backend:",
        provider_options,
        default=default_provider,
    )

    if provider.startswith("ollama"):
        config["provider"] = "ollama"
        default_url = "http://localhost:11434"
        url = _ask("Ollama URL (local, network, or remote — e.g. http://192.168.1.50:11434)", default_url)
        config["base_url"] = url.rstrip("/")

        # Always probe the entered URL (may differ from auto-detect)
        ollama_ok, ollama_info = check_ollama(config["base_url"])
        if ollama_ok:
            print(f"  Connected to {config['base_url']}: {ollama_info}")
        else:
            print(f"  Warning: could not reach {config['base_url']} — check the address later")

        # Model selection
        available_models = list_ollama_models(config["base_url"]) if ollama_ok else []
        recommended = [
            "qwen2.5:3b", "qwen2.5:7b", "qwen2.5:latest",
            "gemma3:4b", "phi4-mini", "llama3.2:3b",
        ]

        if available_models:
            print(f"  Models already pulled: {', '.join(available_models)}")
            # Offer pulled models + recommended ones not yet pulled
            model_options = list(available_models)
            for r in recommended:
                if r not in model_options:
                    model_options.append(f"{r} (not pulled — will download)")
            config["model"] = _ask_choice(
                "Which model to use for decisions?",
                model_options,
                default=available_models[0],
            )
        else:
            config["model"] = _ask_choice(
                "Which model? (will be pulled automatically)",
                recommended,
                default="qwen2.5:3b",
            )

        # Clean up " (not pulled ...)" suffix if present
        config["model"] = config["model"].split(" (")[0].strip()

        # Auto-pull if model not available
        if ollama_ok and config["model"] not in available_models:
            if _ask_bool(f"Pull {config['model']} now? (~2-5 GB download)", default=True):
                pull_ollama_model(config["model"], config["base_url"])
            else:
                print(f"  Skipped — pull manually later: ollama pull {config['model']}")

    elif provider.startswith("lm-studio"):
        config["provider"] = "lm-studio"
        default_url = "http://localhost:1234"
        url = _ask("LM Studio URL (local, network, or remote — e.g. http://192.168.1.50:1234)", default_url)
        config["base_url"] = url.rstrip("/")

        # Always probe the entered URL
        lms_ok, lms_info = check_lm_studio(config["base_url"])
        if lms_ok:
            print(f"  Connected to {config['base_url']}: {lms_info}")
        else:
            print(f"  Warning: could not reach {config['base_url']} — check the address later")

        if lms_ok and lms_info != "no models loaded":
            loaded = lms_info.split(", ")
            config["model"] = _ask_choice(
                "Which loaded model to use?",
                loaded,
                default=loaded[0],
            )
        else:
            if lms_ok:
                print("  No model loaded in LM Studio.")
            print("  Recommended models to download in LM Studio:")
            print("    Sub-agent:  Qwen2.5 3B Instruct (Q4_K_M) — ~2 GB")
            print("    Planner:    Qwen2.5 7B Instruct (Q4_K_M) — ~4.7 GB")
            print("    Alternatives: Gemma 3 4B, Phi-4-mini, Llama 3.2 3B")
            config["model"] = _ask(
                "Model name (load it in LM Studio first)",
                "qwen2.5-3b-instruct",
            )

    elif provider.startswith("openai"):
        config["provider"] = "openai-compat"
        print("  Enter any OpenAI-compatible endpoint (vLLM, OpenRouter, Azure, etc.)")
        config["base_url"] = _ask("API base URL", "https://openrouter.ai/api/v1")
        config["model"] = _ask("Model name", "qwen/qwen-2.5-72b-instruct")
        config["api_key"] = _ask("API key (leave empty if not needed)", "")

        # Detect if it's a local/network endpoint vs cloud
        if _is_local_url(config["base_url"]):
            config["mode"] = "local"
        else:
            config["mode"] = "online"
    else:
        config["provider"] = "stub"
        config["base_url"] = ""
        config["model"] = "stub"

    # --- 4. Engine Options ---
    print("\n[4/6] Engine Options")
    config["multi_agent"] = _ask_bool("Enable multi-agent council?", default=True)
    config["planner"] = _ask_bool("Enable strategic planner?", default=False)

    if config["planner"] and config["provider"] in ("ollama", "lm-studio", "openai-compat"):
        use_separate = _ask_bool(
            "Use a separate (larger) model for the planner?",
            default=False,
        )
        if use_separate:
            # Ask where the planner model runs
            planner_same_host = _ask_bool(
                f"Is the planner model on the same server ({config['base_url']})?",
                default=True,
            )
            if planner_same_host:
                config["planner_base_url"] = config["base_url"]
            else:
                config["planner_base_url"] = _ask(
                    "Planner server URL (local, network, or remote)",
                    config["base_url"],
                )

            if config["provider"] == "ollama":
                # Ollama: list models + offer pull
                planner_recommended = [
                    "qwen2.5:7b", "qwen2.5:14b", "gemma3:12b", "phi4:14b",
                ]
                available = list_ollama_models(config["planner_base_url"])
                planner_options = []
                for r in planner_recommended:
                    if r in available:
                        planner_options.append(r)
                    else:
                        planner_options.append(f"{r} (not pulled — will download)")
                for a in available:
                    if a not in planner_recommended and a != config["model"]:
                        planner_options.insert(0, a)

                config["planner_model"] = _ask_choice(
                    "Planner model (runs every ~5 in-game years, can be slower/larger):",
                    planner_options if planner_options else planner_recommended,
                    default=planner_options[0] if planner_options else "qwen2.5:7b",
                )
                config["planner_model"] = config["planner_model"].split(" (")[0].strip()

                # Auto-pull planner model if needed
                if config["planner_model"] not in available:
                    if _ask_bool(f"Pull {config['planner_model']} now?", default=True):
                        pull_ollama_model(config["planner_model"], config["planner_base_url"])
                    else:
                        print(f"  Skipped — pull manually: ollama pull {config['planner_model']}")
            else:
                # LM Studio / openai-compat: just ask for model name
                config["planner_model"] = _ask("Planner model name", "qwen2.5-7b-instruct")
                if config["provider"] == "lm-studio":
                    print("  Make sure this model is loaded in LM Studio.")
        else:
            config["planner_model"] = ""
    else:
        config["planner_model"] = ""

    config["fast_decisions"] = _ask_bool("Enable fast decisions (skip LLM for trivial cases)?", default=True)
    config["fast_cutoff_year"] = int(_ask("Fast decision cutoff year", "2250"))

    # --- 5. Recording ---
    print("\n[5/6] Training Data")
    config["recording"] = _ask_bool("Record decisions for training?", default=True)
    config["replay_dir"] = _ask("Replay buffer directory", "training/replay_buffer")

    # --- 6. Summary ---
    print("\n[6/6] Summary")
    print(f"  Mode:          {config['target_mode']}")
    print(f"  Provider:      {config['provider']} ({config.get('model', 'n/a')})")
    print(f"  Install:       {config['install_dir']}")
    print(f"  Save dir:      {config['save_dir']}")
    print(f"  Council:       {'ON' if config['multi_agent'] else 'OFF'}")
    print(f"  Planner:       {'ON' if config['planner'] else 'OFF'}")
    print(f"  Fast (<{config['fast_cutoff_year']}): {'ON' if config['fast_decisions'] else 'OFF'}")
    print(f"  Recording:     {'ON' if config['recording'] else 'OFF'}")

    if not _ask_bool("\nSave this configuration?", default=True):
        print("  Aborted.")
        sys.exit(0)

    return config


def install_mod(user_data_dir: str) -> bool:
    """Install the Overmind mod into the Stellaris mod directory.

    Creates a junction/symlink from the Stellaris mod folder to the project's
    mod directory, writes the .mod descriptor, and ensures ai_bridge/ exists.

    Returns True on success.
    """
    user_data = Path(user_data_dir)
    mod_dir = user_data / "mod"
    mod_target = mod_dir / "stellaris_overmind"
    mod_desc_target = mod_dir / "stellaris_overmind.mod"
    mod_source = _PROJECT_ROOT / "mod" / "stellaris_overmind"
    bridge_dir = mod_source / "ai_bridge"

    if not mod_source.exists():
        print(f"  ERROR: Mod source not found: {mod_source}")
        return False

    # Ensure mod directory exists
    mod_dir.mkdir(parents=True, exist_ok=True)

    # Ensure ai_bridge directory exists
    bridge_dir.mkdir(parents=True, exist_ok=True)

    # Create junction/symlink to mod folder
    if not mod_target.exists():
        print(f"  Linking mod: {mod_source} → {mod_target}")
        try:
            if sys.platform == "win32":
                # Use junction (doesn't require admin on most Windows configs)
                import subprocess
                result = subprocess.run(
                    ["cmd", "/c", "mklink", "/J", str(mod_target), str(mod_source)],
                    capture_output=True, text=True,
                )
                if not mod_target.exists():
                    # Junction failed — fall back to copy
                    print("  Junction failed — copying mod files instead")
                    import shutil
                    shutil.copytree(str(mod_source), str(mod_target))
            else:
                mod_target.symlink_to(mod_source)
        except Exception as exc:
            print(f"  WARNING: Could not link mod: {exc}")
            print(f"  Please manually copy {mod_source} to {mod_target}")
            return False

        if mod_target.exists():
            print("  Mod linked successfully")
        else:
            print("  ERROR: Mod link/copy failed")
            return False
    else:
        print("  Mod already installed")

    # Write .mod descriptor with absolute path
    abs_path = str(mod_target).replace("\\", "/")
    descriptor = (
        f'name="Stellaris Overmind"\n'
        f'path="{abs_path}"\n'
        f'tags={{\n'
        f'\t"AI"\n'
        f'\t"Gameplay"\n'
        f'}}\n'
        f'picture="thumbnail.png"\n'
        f'supported_version="v4.*"\n'
    )
    mod_desc_target.write_text(descriptor, encoding="utf-8")
    print(f"  Mod descriptor written: {mod_desc_target}")

    return True


def write_config(config: dict, path: Path | None = None) -> Path:
    """Write config dict to config.toml."""
    if path is None:
        path = _PROJECT_ROOT / "config.toml"

    if config["provider"] == "openai-compat" and config.get("mode") == "online":
        llm_mode = "online"
    else:
        llm_mode = "local"

    lines = [
        '# Stellaris Overmind — Configuration',
        '# Generated by setup wizard',
        '',
        'log_level = "INFO"',
        'max_retries = 2',
        '',
        '[stellaris]',
        f'install_dir = "{config["install_dir"]}"',
        f'user_data_dir = "{config["user_data_dir"]}"',
        'mod_name = "stellaris_overmind"',
        '',
        '[llm]',
        f'provider = "{config["provider"]}"',
        f'mode = "{llm_mode}"',
        f'base_url = "{config.get("base_url", "http://localhost:11434")}"',
        f'model = "{config.get("model", "qwen2.5:latest")}"',
        'max_tokens = 50',
        'temperature = 0.3',
        'timeout_s = 30.0',
        'compact_json = true',
        'prompt_cache = true',
    ]

    if config.get("api_key"):
        lines.append(f'api_key = "{config["api_key"]}"')

    lines.extend([
        '',
        '[bridge]',
        f'save_dir = "{config["save_dir"]}"',
        f'bridge_dir = "{config["bridge_dir"]}"',
        'poll_interval_s = 2.0',
        '',
        '[empire]',
        'auto_detect = true',
        '',
        '[target]',
        f'mode = "{config["target_mode"]}"',
        'ai_exclude_fallen = true',
        f'fast_decisions = {str(config["fast_decisions"]).lower()}',
        '',
        '[multi_agent]',
        f'enabled = {str(config["multi_agent"]).lower()}',
        'parallel = true',
        'arbiter_uses_llm = false',
        '',
        '[planner]',
        f'enabled = {str(config["planner"]).lower()}',
    ])

    if config.get("planner_model"):
        planner_url = config.get("planner_base_url", config.get("base_url", ""))
        lines.extend([
            'provider = "separate"',
            f'base_url = "{planner_url}"',
            f'model = "{config["planner_model"]}"',
        ])
    else:
        lines.append('provider = "same"')

    lines.extend([
        'interval_years = 5',
        'max_tokens = 512',
        'temperature = 0.4',
        '',
        '[training]',
        f'replay_dir = "{config["replay_dir"]}"',
        'sft_threshold = 0.3',
        'dpo_margin = 0.2',
        'quantize_method = "gptq"',
        'quantize_bits = 4',
    ])

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\n  Config saved to: {path}")

    # Install the mod into Stellaris
    print("\n  Installing Stellaris mod...")
    install_mod(config["user_data_dir"])

    print("\n  Setup complete! Next steps:")
    print("    1. Enable 'Stellaris Overmind' in the Stellaris launcher → Mods")
    print("    2. Set autosave frequency to Monthly (Settings → Game)")
    print("    3. Start a game, then run: python -m engine --console")

    return path


def ensure_config() -> Path:
    """Check for config.toml; run wizard if missing. Returns config path."""
    config_path = _PROJECT_ROOT / "config.toml"
    if config_path.exists():
        return config_path

    print("\n  No config.toml found — starting setup wizard...")
    config = run_wizard()
    return write_config(config, config_path)


# Allow running standalone
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    config = run_wizard()
    write_config(config)
