"""
Quantize — Post-training quantization for Stellaris-specific models.

Converts a fine-tuned model (SFT, distilled, or DPO) to lower precision
for faster inference and reduced VRAM usage.

Supported methods:
  - **GPTQ (INT4)** — via AutoGPTQ.  Best for vLLM serving.
  - **AWQ (INT4)** — via AutoAWQ.  Good for llama.cpp/Ollama.
  - **BitsAndBytes (NF4)** — dynamic quantization at load time (no export).

Usage:
    # GPTQ quantization (for vLLM deployment)
    python -m training.quantize \
        --model models/overmind-distilled-v1 \
        --output models/overmind-stellaris-gptq \
        --method gptq

    # AWQ quantization (for Ollama/llama.cpp)
    python -m training.quantize \
        --model models/overmind-distilled-v1 \
        --output models/overmind-stellaris-awq \
        --method awq

    # Validate quantized model quality
    python -m training.quantize \
        --model models/overmind-stellaris-gptq \
        --validate-only

Requirements:
    GPTQ: pip install auto-gptq
    AWQ:  pip install autoawq
"""

from __future__ import annotations

import argparse
import json
import logging
from dataclasses import dataclass

log = logging.getLogger(__name__)


@dataclass
class QuantizeConfig:
    """Configuration for post-training quantization."""

    model_path: str = "models/overmind-distilled-v1"
    output_path: str = "models/overmind-stellaris-gptq"
    method: str = "gptq"                   # gptq | awq
    bits: int = 4
    group_size: int = 128
    desc_act: bool = True                  # activation order (slower but better quality)
    use_triton: bool = False               # use triton backend for GPTQ
    calibration_samples: int = 128         # number of samples for calibration


def build_calibration_data() -> list[str]:
    """Build calibration prompts from eval scenarios.

    Calibration data should be representative of real inference inputs.
    We use the built-in eval scenarios as they cover early/mid/late game
    with diverse empire configs.
    """
    from engine.decision_engine import build_prompt
    from engine.personality_shards import build_personality
    from engine.ruleset_generator import generate_ruleset
    from training.evaluate import SCENARIOS

    prompts = []
    for scenario in SCENARIOS:
        ruleset = generate_ruleset(**scenario.empire)
        personality = build_personality(**scenario.empire)
        prompt = build_prompt(ruleset, personality, scenario.state, None)
        prompts.append(prompt)

    return prompts


def run_gptq(config: QuantizeConfig) -> None:
    """Quantize a model using GPTQ (INT4).

    GPTQ produces a static quantized model that can be served directly
    by vLLM with ``--quantization gptq``.
    """
    try:
        from auto_gptq import AutoGPTQForCausalLM, BaseQuantizeConfig
        from transformers import AutoTokenizer
    except ImportError as exc:
        raise SystemExit(
            "GPTQ quantization requires: pip install auto-gptq"
        ) from exc

    log.info("Loading model: %s", config.model_path)
    tokenizer = AutoTokenizer.from_pretrained(
        config.model_path, trust_remote_code=True,
    )

    # Build calibration dataset
    log.info("Building calibration data from eval scenarios...")
    cal_prompts = build_calibration_data()
    cal_data = [
        tokenizer(p, return_tensors="pt", truncation=True, max_length=2048)
        for p in cal_prompts[:config.calibration_samples]
    ]
    log.info("Calibration samples: %d", len(cal_data))

    quant_config = BaseQuantizeConfig(
        bits=config.bits,
        group_size=config.group_size,
        desc_act=config.desc_act,
    )

    model = AutoGPTQForCausalLM.from_pretrained(
        config.model_path,
        quant_config,
        trust_remote_code=True,
    )

    log.info("Quantizing with GPTQ (INT%d, group_size=%d)...", config.bits, config.group_size)
    model.quantize(cal_data, use_triton=config.use_triton)

    log.info("Saving quantized model to %s", config.output_path)
    model.save_quantized(config.output_path)
    tokenizer.save_pretrained(config.output_path)
    log.info("GPTQ quantization complete")


def run_awq(config: QuantizeConfig) -> None:
    """Quantize a model using AWQ (INT4).

    AWQ models can be converted to GGUF for llama.cpp/Ollama.
    """
    try:
        from awq import AutoAWQForCausalLM
        from transformers import AutoTokenizer
    except ImportError as exc:
        raise SystemExit(
            "AWQ quantization requires: pip install autoawq"
        ) from exc

    log.info("Loading model: %s", config.model_path)
    tokenizer = AutoTokenizer.from_pretrained(
        config.model_path, trust_remote_code=True,
    )

    model = AutoAWQForCausalLM.from_pretrained(
        config.model_path,
        trust_remote_code=True,
    )

    log.info("Building calibration data...")
    cal_prompts = build_calibration_data()

    quant_config = {
        "zero_point": True,
        "q_group_size": config.group_size,
        "w_bit": config.bits,
        "version": "GEMM",
    }

    log.info("Quantizing with AWQ (INT%d)...", config.bits)
    model.quantize(
        tokenizer,
        quant_config=quant_config,
        calib_data=cal_prompts[:config.calibration_samples],
    )

    log.info("Saving quantized model to %s", config.output_path)
    model.save_quantized(config.output_path)
    tokenizer.save_pretrained(config.output_path)
    log.info("AWQ quantization complete")


def validate_quantized(model_path: str) -> dict:
    """Run a quick validation of a quantized model using eval scenarios.

    Returns eval summary dict.
    """

    log.info("Validating quantized model: %s", model_path)
    log.info("Note: model must be served (e.g. vLLM) before validation")

    return {"status": "requires_served_model", "model_path": model_path}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Quantize a fine-tuned model for faster inference",
    )
    parser.add_argument("--model", required=True, help="Input model path")
    parser.add_argument("--output", default="", help="Output path (default: model-{method})")
    parser.add_argument("--method", choices=["gptq", "awq"], default="gptq")
    parser.add_argument("--bits", type=int, default=4)
    parser.add_argument("--group-size", type=int, default=128)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

    if args.validate_only:
        result = validate_quantized(args.model)
        print(json.dumps(result, indent=2))
        return

    output = args.output or f"{args.model}-{args.method}"
    config = QuantizeConfig(
        model_path=args.model,
        output_path=output,
        method=args.method,
        bits=args.bits,
        group_size=args.group_size,
    )

    if args.method == "gptq":
        run_gptq(config)
    elif args.method == "awq":
        run_awq(config)


if __name__ == "__main__":
    main()
