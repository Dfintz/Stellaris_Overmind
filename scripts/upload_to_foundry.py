"""
Upload to Foundry — Uploads SFT training data to Azure AI Foundry for
managed fine-tuning.

Azure AI Foundry expects the OpenAI chat message format (JSONL), which
is exactly what our ``training/curate.py`` produces.

Usage:
    # Upload SFT data for managed fine-tuning
    python scripts/upload_to_foundry.py \
        --data training/sft_data/sft_latest.jsonl \
        --project https://your-project.services.ai.azure.com \
        --api-key $AZURE_AI_KEY

    # Upload teacher data for distillation fine-tuning
    python scripts/upload_to_foundry.py \
        --data training/teacher_data/teacher_latest.jsonl \
        --project https://your-project.services.ai.azure.com \
        --api-key $AZURE_AI_KEY

Requirements:
    pip install azure-ai-ml  (or use REST API directly — this script uses REST)

The script uploads the JSONL file and prints the file ID for use in
the Foundry fine-tuning UI or API.
"""

from __future__ import annotations

import argparse
import json
import logging
import urllib.error
import urllib.request
from pathlib import Path

log = logging.getLogger(__name__)


def validate_jsonl(path: Path) -> dict:
    """Validate JSONL format before upload."""
    valid = 0
    invalid = 0
    total_tokens_est = 0

    with open(path, encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                messages = record.get("messages", [])
                if len(messages) < 2:
                    invalid += 1
                    continue
                # Estimate tokens (~4 chars per token)
                text_len = sum(len(m.get("content", "")) for m in messages)
                total_tokens_est += text_len // 4
                valid += 1
            except json.JSONDecodeError:
                invalid += 1
                log.warning("Line %d: invalid JSON", i)

    return {
        "path": str(path),
        "valid": valid,
        "invalid": invalid,
        "estimated_tokens": total_tokens_est,
        "size_bytes": path.stat().st_size,
    }


def upload_to_foundry(
    data_path: Path,
    project_url: str,
    api_key: str,
    purpose: str = "fine-tune",
) -> dict:
    """Upload a JSONL file to Azure AI Foundry.

    Uses the OpenAI-compatible Files API that Foundry exposes.
    """
    url = f"{project_url.rstrip('/')}/openai/files?api-version=2024-10-21"

    # Read file content
    file_content = data_path.read_bytes()
    file_name = data_path.name

    # Build multipart form data
    boundary = "----OvermindUploadBoundary"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="purpose"\r\n\r\n'
        f"{purpose}\r\n"
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{file_name}"\r\n'
        f"Content-Type: application/jsonl\r\n\r\n"
    ).encode() + file_content + f"\r\n--{boundary}--\r\n".encode()

    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "api-key": api_key,
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode())
            log.info("Upload successful: file_id=%s", result.get("id"))
            return result
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode() if exc.fp else str(exc)
        log.error("Upload failed (HTTP %d): %s", exc.code, detail)
        raise SystemExit(f"Upload failed: {detail}") from exc
    except urllib.error.URLError as exc:
        log.error("Cannot reach Foundry: %s", exc.reason)
        raise SystemExit(f"Connection failed: {exc.reason}") from exc


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Upload training data to Azure AI Foundry",
    )
    parser.add_argument("--data", type=Path, required=True,
                        help="Path to JSONL training file")
    parser.add_argument("--project", required=True,
                        help="Foundry project URL")
    parser.add_argument("--api-key", default="",
                        help="Azure AI API key (or set AZURE_AI_KEY env var)")
    parser.add_argument("--validate-only", action="store_true",
                        help="Validate file format without uploading")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

    import os
    api_key = args.api_key or os.environ.get("AZURE_AI_KEY", "")

    # Validate first
    log.info("Validating %s...", args.data)
    stats = validate_jsonl(args.data)
    log.info(
        "Validation: %d valid, %d invalid, ~%d tokens, %.1f KB",
        stats["valid"], stats["invalid"],
        stats["estimated_tokens"],
        stats["size_bytes"] / 1024,
    )

    if stats["valid"] == 0:
        log.error("No valid training examples found")
        raise SystemExit(1)

    if args.validate_only:
        print(json.dumps(stats, indent=2))
        return

    if not api_key:
        log.error("No API key. Set --api-key or AZURE_AI_KEY env var")
        raise SystemExit(1)

    # Upload
    result = upload_to_foundry(args.data, args.project, api_key)
    print(json.dumps(result, indent=2))
    log.info("File uploaded. Use file_id '%s' in Foundry fine-tuning.", result.get("id"))


if __name__ == "__main__":
    main()
