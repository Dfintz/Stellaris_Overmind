"""
Fine-Tune — LoRA/QLoRA fine-tuning script for Qwen2.5-Omni on Stellaris data.

This script takes the SFT and DPO datasets produced by the curator and
fine-tunes a Qwen2.5 model using LoRA (Low-Rank Adaptation).

Usage:
    # SFT fine-tuning
    python -m training.fine_tune sft \
        --data training/sft_data/sft_latest.jsonl \
        --model Qwen/Qwen2.5-Omni-3B \
        --output models/overmind-sft-v1

    # DPO fine-tuning (requires SFT model as base)
    python -m training.fine_tune dpo \
        --data training/dpo_pairs/dpo_latest.jsonl \
        --model models/overmind-sft-v1 \
        --output models/overmind-dpo-v1

Requirements:
    pip install transformers peft trl datasets accelerate bitsandbytes

Note: This module defines the configuration and scripts but does NOT
import heavy ML libraries at module level — they are imported lazily
inside functions to keep the core engine lightweight.
"""

from __future__ import annotations

import argparse
import json
import logging
from dataclasses import dataclass

log = logging.getLogger(__name__)


@dataclass
class FineTuneConfig:
    """Configuration for LoRA fine-tuning."""

    # Model
    base_model: str = "Qwen/Qwen2.5-Omni-3B"
    output_dir: str = "models/overmind-sft-v1"

    # LoRA
    lora_r: int = 16
    lora_alpha: int = 32
    lora_dropout: float = 0.05
    lora_target_modules: list[str] | None = None  # None = auto-detect

    # Training
    num_epochs: int = 3
    batch_size: int = 4
    gradient_accumulation_steps: int = 4
    learning_rate: float = 2e-4
    warmup_ratio: float = 0.1
    max_seq_length: int = 2048
    bf16: bool = True

    # QLoRA (4-bit quantization for lower VRAM)
    use_qlora: bool = False
    bnb_4bit_compute_dtype: str = "bfloat16"
    bnb_4bit_quant_type: str = "nf4"

    # Integrations
    use_wandb: bool = False            # log to Weights & Biases
    use_unsloth: bool = False          # use Unsloth for 2x faster training


def run_sft(data_path: str, config: FineTuneConfig) -> None:
    """Run supervised fine-tuning with LoRA on SFT data.

    This trains the model to produce good (action, target, reason) outputs
    given (ruleset + state) prompts.
    """
    # Lazy imports — only needed when actually training
    try:
        from datasets import Dataset
        from peft import LoraConfig, TaskType, get_peft_model
        from transformers import (
            AutoModelForCausalLM,
            AutoTokenizer,
            TrainingArguments,
        )
        from trl import SFTTrainer
    except ImportError as exc:
        raise SystemExit(
            "Fine-tuning requires: pip install transformers peft trl datasets "
            "accelerate bitsandbytes"
        ) from exc

    log.info("Loading SFT data from %s", data_path)
    records = _load_jsonl(data_path)
    log.info("Loaded %d training examples", len(records))

    # Build HF dataset from chat messages
    dataset = Dataset.from_list(records)

    log.info("Loading base model: %s", config.base_model)
    tokenizer = AutoTokenizer.from_pretrained(
        config.base_model, trust_remote_code=True,
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model_kwargs = {
        "torch_dtype": "auto",
        "device_map": "auto",
        "trust_remote_code": True,
    }
    if config.use_qlora:
        from transformers import BitsAndBytesConfig

        model_kwargs["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_compute_dtype=config.bnb_4bit_compute_dtype,
            bnb_4bit_quant_type=config.bnb_4bit_quant_type,
        )

    model = AutoModelForCausalLM.from_pretrained(
        config.base_model, **model_kwargs,
    )

    # LoRA config
    lora_config = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=config.lora_r,
        lora_alpha=config.lora_alpha,
        lora_dropout=config.lora_dropout,
        target_modules=config.lora_target_modules,
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    # Training args
    training_args = TrainingArguments(
        output_dir=config.output_dir,
        num_train_epochs=config.num_epochs,
        per_device_train_batch_size=config.batch_size,
        gradient_accumulation_steps=config.gradient_accumulation_steps,
        learning_rate=config.learning_rate,
        warmup_ratio=config.warmup_ratio,
        bf16=config.bf16,
        logging_steps=10,
        save_strategy="epoch",
        report_to="wandb" if config.use_wandb else "none",
    )

    trainer = SFTTrainer(
        model=model,
        args=training_args,
        train_dataset=dataset,
        tokenizer=tokenizer,
        max_seq_length=config.max_seq_length,
    )

    log.info("Starting SFT training...")
    trainer.train()

    log.info("Saving model to %s", config.output_dir)
    trainer.save_model()
    tokenizer.save_pretrained(config.output_dir)
    log.info("SFT training complete")


def run_dpo(data_path: str, config: FineTuneConfig) -> None:
    """Run DPO (Direct Preference Optimization) on preference pairs.

    This teaches the model to prefer good decisions over bad ones
    for similar game states.
    """
    try:
        from datasets import Dataset
        from peft import LoraConfig, TaskType
        from transformers import AutoModelForCausalLM, AutoTokenizer
        from trl import DPOConfig, DPOTrainer
    except ImportError as exc:
        raise SystemExit(
            "DPO training requires: pip install transformers peft trl datasets "
            "accelerate bitsandbytes"
        ) from exc

    log.info("Loading DPO data from %s", data_path)
    records = _load_jsonl(data_path)
    log.info("Loaded %d preference pairs", len(records))

    dataset = Dataset.from_list(records)

    log.info("Loading model: %s", config.base_model)
    tokenizer = AutoTokenizer.from_pretrained(
        config.base_model, trust_remote_code=True,
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        config.base_model,
        torch_dtype="auto",
        device_map="auto",
        trust_remote_code=True,
    )

    lora_config = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=config.lora_r,
        lora_alpha=config.lora_alpha,
        lora_dropout=config.lora_dropout,
        target_modules=config.lora_target_modules,
    )

    dpo_config = DPOConfig(
        output_dir=config.output_dir,
        num_train_epochs=config.num_epochs,
        per_device_train_batch_size=config.batch_size,
        gradient_accumulation_steps=config.gradient_accumulation_steps,
        learning_rate=config.learning_rate / 10,  # DPO uses lower LR
        warmup_ratio=config.warmup_ratio,
        bf16=config.bf16,
        logging_steps=10,
        save_strategy="epoch",
        report_to="none",
        max_length=config.max_seq_length,
        max_prompt_length=config.max_seq_length - 256,
    )

    trainer = DPOTrainer(
        model=model,
        args=dpo_config,
        train_dataset=dataset,
        tokenizer=tokenizer,
        peft_config=lora_config,
    )

    log.info("Starting DPO training...")
    trainer.train()

    log.info("Saving model to %s", config.output_dir)
    trainer.save_model()
    tokenizer.save_pretrained(config.output_dir)
    log.info("DPO training complete")


def _load_jsonl(path: str) -> list[dict]:
    """Load a JSONL file into a list of dicts."""
    records = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="overmind-finetune",
        description="Fine-tune Qwen2.5 on Stellaris Overmind replay data",
    )
    sub = parser.add_subparsers(dest="mode", required=True)

    # SFT subcommand
    sft_p = sub.add_parser("sft", help="Supervised fine-tuning")
    sft_p.add_argument("--data", required=True, help="Path to SFT JSONL")
    sft_p.add_argument("--model", default="Qwen/Qwen2.5-Omni-3B", help="Base model")
    sft_p.add_argument("--output", default="models/overmind-sft-v1", help="Output dir")
    sft_p.add_argument("--epochs", type=int, default=3)
    sft_p.add_argument("--qlora", action="store_true", help="Use 4-bit QLoRA")

    # DPO subcommand
    dpo_p = sub.add_parser("dpo", help="DPO preference optimization")
    dpo_p.add_argument("--data", required=True, help="Path to DPO JSONL")
    dpo_p.add_argument("--model", default="models/overmind-sft-v1", help="SFT model")
    dpo_p.add_argument("--output", default="models/overmind-dpo-v1", help="Output dir")
    dpo_p.add_argument("--epochs", type=int, default=2)
    dpo_p.add_argument("--qlora", action="store_true", help="Use 4-bit QLoRA")

    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")

    config = FineTuneConfig(
        base_model=args.model,
        output_dir=args.output,
        num_epochs=args.epochs,
        use_qlora=args.qlora,
    )

    if args.mode == "sft":
        run_sft(args.data, config)
    elif args.mode == "dpo":
        run_dpo(args.data, config)


if __name__ == "__main__":
    main()
