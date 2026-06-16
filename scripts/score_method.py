"""Emit a numeric method score for harness experiment loops.

This uses the built-in evaluation harness with the stub provider,
then prints METHOD_SCORE=<value> for regex extraction.
"""

from __future__ import annotations

from engine.llm_provider import StubProvider
from training.evaluate import run_eval


def main() -> None:
    summary = run_eval(provider=StubProvider(), model_name="stub")
    score = summary.mean_composite * 100.0
    print(f"METHOD_SCORE={score:.2f}")


if __name__ == "__main__":
    main()
