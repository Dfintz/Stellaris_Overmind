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
    try:
        import urllib.request
        req = urllib.request.Request(f"{base_url.rstrip('/')}/api/tags")
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode())
            models = [m["name"] for m in data.get("models", [])]
            return True, ", ".join(models) if models else "no models pulled"
    except Exception:
        return False, "not reachable"


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
    if ollama_ok:
        print(f"  Ollama detected locally: {ollama_info}")

    provider = _ask_choice(
        "LLM backend:",
        ["ollama — Local or network Ollama (recommended)",
         "openai-compat — Any OpenAI-compatible API (vLLM, LM Studio, cloud)",
         "stub — Offline testing (no LLM needed)"],
        default="ollama — Local or network Ollama (recommended)" if ollama_ok else "stub — Offline testing (no LLM needed)",
    )

    if provider.startswith("ollama"):
        config["provider"] = "ollama"
        default_url = "http://localhost:11434"
        url = _ask("Ollama URL (localhost or network ip:port)", default_url)
        config["base_url"] = url.rstrip("/")

        # Check if the specified endpoint is reachable
        if url != default_url:
            ok, info = check_ollama(url)
            if ok:
                print(f"  Connected to {url}: {info}")
                ollama_ok, ollama_info = True, info
            else:
                print(f"  Warning: could not reach {url} — check the address later")
                ollama_ok = False

        if ollama_ok and ollama_info != "no models pulled":
            first_model = ollama_info.split(",")[0].strip()
            config["model"] = _ask("Model name", first_model)
        else:
            config["model"] = _ask("Model name", "qwen2.5:latest")

    elif provider.startswith("openai"):
        config["provider"] = "openai-compat"
        print("  Enter any OpenAI-compatible endpoint (vLLM, LM Studio, OpenRouter, Azure, etc.)")
        config["base_url"] = _ask("API base URL", "https://openrouter.ai/api/v1")
        config["model"] = _ask("Model name", "qwen/qwen-2.5-72b-instruct")
        config["api_key"] = _ask("API key (leave empty if not needed)", "")

        # Detect if it's a local endpoint
        if any(x in config["base_url"] for x in ["localhost", "127.0.0.1", "192.168.", "10."]):
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
        'provider = "same"',
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
