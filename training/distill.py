"""
Distill — Knowledge distillation from a teacher model to a student model.

Takes teacher data collected by ``scripts/collect_teacher.py`` and fine-tunes
a smaller student model to reproduce the teacher's decisions.  This is
standard SFT on teacher outputs — the key insight is that the teacher data
is higher quality than live play data.

Pipeline:
  1. Teacher (72B cloud) produces decisions → teacher_data/*.jsonl
  2. This script fine-tunes student (3B/7B local) on those decisions
  3. Optionally runs eval to compare student vs teacher quality

Usage:
    # Distill teacher data into student
    python -m training.distill \
        --teacher-data training/teacher_data/teacher_latest.jsonl \
        --student-model Qwen/Qwen2.5-Omni-3B \
        --output models/overmind-distilled-v1

    # With QLoRA for lower VRAM
    python -m training.distill \
        --teacher-data training/teacher_data/teacher_latest.jsonl \
        --student-model Qwen/Qwen2.5-Omni-7B \
        --output models/overmind-distilled-7b-v1 \
        --qlora

Requirements:
    pip install transformers peft trl datasets accelerate bitsandbytes
"""

from __future__ import annotations

import argparse
import json
import logging
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)


@dataclass
class DistillConfig:
    """Configuration for knowledge distillation."""

    # Models
    student_model: str = "Qwen/Qwen2.5-Omni-3B"
    output_dir: str = "models/overmind-distilled-v1"

    # LoRA
    lora_r: int = 16
    lora_alpha: int = 32
    lora_dropout: float = 0.05

    # Training
    num_epochs: int = 3
    batch_size: int = 4
    gradient_accumulation_steps: int = 4
    learning_rate: float = 2e-4
    warmup_ratio: float = 0.1
    max_seq_length: int = 2048
    bf16: bool = True

    # QLoRA
    use_qlora: bool = False


def validate_teacher_data(data_path: Path) -> dict:
    """Validate teacher data format and return summary stats."""
    records = _load_jsonl(data_path)

    valid = 0
    invalid = 0
    actions: dict[str, int] = {}

    for rec in records:
        messages = rec.get("messages", [])
        if len(messages) < 3:
            invalid += 1
            continue

        # Check assistant message has proper format
        assistant_msg = messages[-1].get("content", "")
        if "ACTION:" in assistant_msg:
            valid += 1
            # Extract action
            for line in assistant_msg.splitlines():
                if line.strip().upper().startswith("ACTION:"):
                    action = line.split(":", 1)[1].strip().upper()
                    actions[action] = actions.get(action, 0) + 1
                    break
        else:
            invalid += 1

    return {
        "total": len(records),
        "valid": valid,
        "invalid": invalid,
        "action_distribution": actions,
        "path": str(data_path),
    }


def run_distillation(data_path: str, config: DistillConfig) -> None:
    """Run distillation: fine-tune student on teacher data.

    This is identical to SFT — the difference is that the training data
    comes from a large teacher model rather than live play.
    """
    # Reuse the existing SFT infrastructure
    from training.fine_tune import FineTuneConfig, run_sft

    sft_config = FineTuneConfig(
        base_model=config.student_model,
        output_dir=config.output_dir,
        lora_r=config.lora_r,
        lora_alpha=config.lora_alpha,
        lora_dropout=config.lora_dropout,
        num_epochs=config.num_epochs,
        batch_size=config.batch_size,
        gradient_accumulation_steps=config.gradient_accumulation_steps,
        learning_rate=config.learning_rate,
        warmup_ratio=config.warmup_ratio,
        max_seq_length=config.max_seq_length,
        bf16=config.bf16,
        use_qlora=config.use_qlora,
    )

    log.info("Starting distillation: %s → %s", config.student_model, config.output_dir)

    # Validate teacher data first
    stats = validate_teacher_data(Path(data_path))
    log.info(
        "Teacher data: %d valid, %d invalid, actions=%s",
        stats["valid"], stats["invalid"], stats["action_distribution"],
    )
    if stats["valid"] < 10:
        log.error("Not enough valid teacher data (%d). Need at least 10.", stats["valid"])
        return

    run_sft(data_path, sft_config)
    log.info("Distillation complete: %s", config.output_dir)


def _load_jsonl(path: Path) -> list[dict]:
    records = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Distill a teacher model's decisions into a student model",
    )
    parser.add_argument("--teacher-data", required=True, help="Path to teacher JSONL")
    parser.add_argument("--student-model", default="Qwen/Qwen2.5-Omni-3B")
    parser.add_argument("--output", default="models/overmind-distilled-v1")
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--lr", type=float, default=2e-4)
    parser.add_argument("--qlora", action="store_true", help="Use QLoRA (4-bit)")
    parser.add_argument("--validate-only", action="store_true",
                        help="Only validate teacher data, don't train")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

    if args.validate_only:
        stats = validate_teacher_data(Path(args.teacher_data))
        print(json.dumps(stats, indent=2))
        return

    config = DistillConfig(
        student_model=args.student_model,
        output_dir=args.output,
        num_epochs=args.epochs,
        learning_rate=args.lr,
        use_qlora=args.qlora,
    )
    run_distillation(args.teacher_data, config)


if __name__ == "__main__":
    main()
