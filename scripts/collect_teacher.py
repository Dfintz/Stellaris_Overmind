"""
Collect Teacher — Runs game scenarios through a large cloud model to collect
high-quality training data for distillation.

The teacher model (e.g. Qwen 72B via OpenRouter) produces decisions for
each game state.  These are saved as teacher_data/*.jsonl and used by
``training/distill.py`` to train a smaller student model.

Safety: All prompts go through ``build_prompt()`` which enforces fog-of-war
filtering.  The teacher never sees hidden game data.

Usage:
    # Collect from replay buffer states using online provider
    python scripts/collect_teacher.py \
        --replay-dir training/replay_buffer \
        --base-url https://openrouter.ai/api/v1 \
        --model qwen/qwen-2.5-72b-instruct \
        --api-key $OPENROUTER_KEY

    # Collect from eval scenarios (no replay data needed)
    python scripts/collect_teacher.py --from-eval \
        --base-url https://openrouter.ai/api/v1 \
        --model qwen/qwen-2.5-72b-instruct \
        --api-key $OPENROUTER_KEY
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from datetime import datetime
from pathlib import Path

log = logging.getLogger(__name__)


def collect_from_replays(
    replay_dir: Path,
    provider: object,
    output_dir: Path,
    max_samples: int = 500,
) -> Path:
    """Collect teacher decisions for states from the replay buffer."""
    from engine.decision_engine import build_prompt, parse_llm_response
    from engine.llm_provider import LLMProviderError
    from engine.personality_shards import build_personality
    from engine.ruleset_generator import generate_ruleset
    from engine.validator import validate_directive

    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"teacher_{datetime.now():%Y%m%d_%H%M%S}.jsonl"

    records = _load_replays(replay_dir)
    log.info("Loaded %d replay records", len(records))

    collected = 0
    with open(out_path, "w", encoding="utf-8") as f:
        for rec in records[:max_samples]:
            state = rec.get("state_before")
            if not state:
                continue

            empire = state.get("empire", {})
            ethics = empire.get("ethics", ["Militarist"])
            civics = empire.get("civics", [])
            origin = empire.get("origin", "Prosperous Unification")
            government = empire.get("government", "Oligarchy")

            ruleset = generate_ruleset(
                ethics=ethics, civics=civics, traits=[],
                origin=origin, government=government,
            )
            personality = build_personality(
                ethics=ethics, civics=civics, traits=[],
                origin=origin, government=government,
            )

            prompt = build_prompt(ruleset, personality, state, rec.get("event"))

            t0 = time.monotonic()
            try:
                response = provider.complete(prompt)
                raw = response.text
            except LLMProviderError as exc:
                log.warning("Teacher error: %s", exc)
                continue

            latency = (time.monotonic() - t0) * 1000

            try:
                directive = parse_llm_response(raw)
            except ValueError:
                log.warning("Teacher produced unparseable response, skipping")
                continue

            # Validate — skip if teacher violates FoW/origin/meta rules
            vresult = validate_directive(directive.to_dict(), ruleset, state)
            if not vresult.valid:
                log.warning("Teacher response failed validation: %s", vresult.errors)
                continue

            record = {
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are a Stellaris 4.3.4 strategic AI advisor. "
                            "Choose exactly ONE action and cite ruleset elements."
                        ),
                    },
                    {"role": "user", "content": prompt},
                    {"role": "assistant", "content": raw.strip()},
                ],
                "metadata": {
                    "teacher_model": provider.name,
                    "latency_ms": latency,
                    "action": directive.action,
                    "year": state.get("year", 0),
                    "game_id": rec.get("game_id", "?"),
                },
            }
            f.write(json.dumps(record) + "\n")
            collected += 1

            if collected % 50 == 0:
                log.info("Collected %d/%d teacher decisions", collected, max_samples)

    log.info("Collected %d teacher decisions → %s", collected, out_path)
    return out_path


def collect_from_eval(
    provider: object,
    output_dir: Path,
) -> Path:
    """Collect teacher decisions for the built-in eval scenarios."""
    from engine.decision_engine import build_prompt, parse_llm_response
    from engine.llm_provider import LLMProviderError
    from engine.personality_shards import build_personality
    from engine.ruleset_generator import generate_ruleset
    from training.evaluate import SCENARIOS

    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"teacher_eval_{datetime.now():%Y%m%d_%H%M%S}.jsonl"

    collected = 0
    with open(out_path, "w", encoding="utf-8") as f:
        for scenario in SCENARIOS:
            ruleset = generate_ruleset(**scenario.empire)
            personality = build_personality(**scenario.empire)
            prompt = build_prompt(ruleset, personality, scenario.state, None)

            try:
                response = provider.complete(prompt)
                raw = response.text
            except LLMProviderError as exc:
                log.warning("Teacher error on %s: %s", scenario.name, exc)
                continue

            try:
                directive = parse_llm_response(raw)
            except ValueError:
                continue

            record = {
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are a Stellaris 4.3.4 strategic AI advisor. "
                            "Choose exactly ONE action and cite ruleset elements."
                        ),
                    },
                    {"role": "user", "content": prompt},
                    {"role": "assistant", "content": raw.strip()},
                ],
                "metadata": {
                    "teacher_model": provider.name,
                    "action": directive.action,
                    "scenario": scenario.name,
                },
            }
            f.write(json.dumps(record) + "\n")
            collected += 1

    log.info("Collected %d teacher decisions from eval scenarios → %s", collected, out_path)
    return out_path


def _load_replays(replay_dir: Path) -> list[dict]:
    """Load replay buffer JSONL files."""
    records = []
    for path in sorted(replay_dir.glob("*.jsonl")):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
    return records


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Collect teacher model decisions for distillation",
    )
    parser.add_argument("--replay-dir", type=Path, default=Path("training/replay_buffer"))
    parser.add_argument("--output", type=Path, default=Path("training/teacher_data"))
    parser.add_argument("--base-url", required=True, help="Teacher API endpoint")
    parser.add_argument("--model", required=True, help="Teacher model name")
    parser.add_argument("--api-key", default="", help="API key")
    parser.add_argument("--max-samples", type=int, default=500)
    parser.add_argument("--from-eval", action="store_true",
                        help="Use eval scenarios instead of replay buffer")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

    from engine.qwen_provider import OpenAICompatProvider

    provider = OpenAICompatProvider(
        base_url=args.base_url,
        model=args.model,
        api_key=args.api_key,
        max_tokens=256,
        temperature=0.3,
        timeout_s=120.0,
    )

    if args.from_eval:
        collect_from_eval(provider, args.output)
    else:
        collect_from_replays(args.replay_dir, provider, args.output, args.max_samples)


if __name__ == "__main__":
    main()
