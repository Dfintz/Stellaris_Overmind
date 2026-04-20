"""
Console — Rich TUI dashboard for live Overmind monitoring.

Displays token rates, decision stats, scrolling logs, and provides
keyboard controls for toggling settings (mode, council, planner, etc.).

Requires: pip install rich  (or:  pip install stellaris-overmind[console])

If ``rich`` is not installed, the console gracefully degrades to standard
logging — the engine still works, just without the fancy dashboard.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from dataclasses import dataclass

log = logging.getLogger(__name__)

# Mode cycle order
_MODE_CYCLE = ["local", "online", "hybrid"]


@dataclass
class ConsoleConfig:
    """What the console can toggle at runtime."""

    llm_mode: str = "local"
    council_enabled: bool = False
    planner_enabled: bool = False
    recording_enabled: bool = False


class LogCapture(logging.Handler):
    """Captures log records into a deque for display in the TUI."""

    def __init__(self, maxlen: int = 30) -> None:
        super().__init__()
        self.records: deque[str] = deque(maxlen=maxlen)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            self.records.append(msg)
        except Exception:
            pass


def _format_uptime(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def _format_histogram(hist: dict[str, int], max_items: int = 6) -> str:
    if not hist:
        return "none yet"
    sorted_items = sorted(hist.items(), key=lambda x: x[1], reverse=True)
    parts = [f"{k}={v}" for k, v in sorted_items[:max_items]]
    return " ".join(parts)


def run_console(
    metrics_collector: object,
    console_config: ConsoleConfig,
    stop_event: threading.Event,
    provider_name: str = "unknown",
    target_mode: str = "player",
) -> None:
    """Run the Rich TUI dashboard.  Blocks until ``stop_event`` is set.

    Parameters
    ----------
    metrics_collector : MetricsCollector
        The metrics aggregator to read from.
    console_config : ConsoleConfig
        Mutable config object — keyboard handlers modify this.
    stop_event : threading.Event
        Set to signal shutdown (also set by pressing Q).
    provider_name : str
        Display name of the LLM provider.
    target_mode : str
        "player" or "ai".
    """
    try:
        from rich.console import Console
        from rich.layout import Layout
        from rich.live import Live
        from rich.panel import Panel
        from rich.table import Table
        from rich.text import Text
    except ImportError:
        log.warning("Rich not installed — console disabled. pip install rich")
        # Block until stop
        while not stop_event.is_set():
            stop_event.wait(1.0)
        return

    # Set up log capture
    log_capture = LogCapture(maxlen=25)
    log_capture.setFormatter(logging.Formatter("%(asctime)s %(message)s", datefmt="%H:%M:%S"))
    logging.getLogger().addHandler(log_capture)

    console = Console()

    def build_display() -> Layout:
        m = metrics_collector.snapshot()
        total_tokens = m.local_tokens + m.online_tokens
        cache_total = m.cache_hits + m.cache_misses
        cache_rate = (
            f"{m.cache_hits / cache_total * 100:.0f}%"
            if cache_total > 0 else "N/A"
        )

        # Header
        header = Text.assemble(
            ("STELLARIS OVERMIND", "bold cyan"),
            ("  │  ", "dim"),
            (f"Mode: {target_mode.upper()}", "bold"),
            ("  │  ", "dim"),
            (f"Provider: {provider_name}", ""),
            ("  │  ", "dim"),
            (f"Year: {m.game_year}", "bold yellow"),
            ("  │  ", "dim"),
            (f"Uptime: {_format_uptime(m.uptime_s)}", "dim"),
        )

        # Token rates table
        tok_table = Table(show_header=False, expand=True, box=None, padding=(0, 1))
        tok_table.add_column(ratio=1)
        tok_table.add_column(ratio=1)
        tok_table.add_column(ratio=1)
        tok_table.add_row(
            f"Tok/s: [bold]{m.tokens_per_second:.0f}[/bold]",
            f"Avg latency: [bold]{m.avg_latency_ms:.0f}ms[/bold]",
            f"Last: [bold]{m.last_latency_ms:.0f}ms[/bold]",
        )
        tok_table.add_row(
            f"Local calls: {m.local_calls}",
            f"Online calls: {m.online_calls}",
            f"Fallbacks: {m.fallbacks}",
        )
        tok_table.add_row(
            f"Total tokens: {total_tokens:,}",
            f"Cache: {cache_rate}",
            f"LLM errors: {m.llm_errors}",
        )

        # Decisions table
        dec_table = Table(show_header=False, expand=True, box=None, padding=(0, 1))
        dec_table.add_column(ratio=1)
        dec_table.add_column(ratio=1)
        dec_table.add_row(
            f"Total: [bold green]{m.decisions_made}[/bold green]",
            f"Failed: [bold red]{m.decisions_failed}[/bold red]",
        )
        dec_table.add_row(
            f"Validated: {m.decisions_made - m.validation_errors}",
            f"Val errors: {m.validation_errors}",
        )
        dec_table.add_row(
            f"Last: [bold]{m.last_action or 'none'}[/bold]",
            f"Actions: {_format_histogram(m.actions_histogram)}",
        )

        # Log panel
        log_lines = list(log_capture.records)
        log_text = "\n".join(log_lines[-15:]) if log_lines else "[dim]Waiting for events...[/dim]"

        # Controls
        mode_display = console_config.llm_mode.upper()
        controls = Text.assemble(
            ("[M]", "bold cyan"), (f" Mode: {mode_display}  ", ""),
            ("[C]", "bold cyan"), (" Council: ", ""),
            ("ON" if console_config.council_enabled else "OFF",
             "green" if console_config.council_enabled else "dim"),
            ("  ", ""),
            ("[P]", "bold cyan"), (" Planner: ", ""),
            ("ON" if console_config.planner_enabled else "OFF",
             "green" if console_config.planner_enabled else "dim"),
            ("  ", ""),
            ("[R]", "bold cyan"), (" Record: ", ""),
            ("ON" if console_config.recording_enabled else "OFF",
             "green" if console_config.recording_enabled else "dim"),
            ("  ", ""),
            ("[Q]", "bold red"), (" Quit", ""),
        )

        # Assemble layout
        layout = Layout()
        layout.split_column(
            Layout(Panel(header, style="bold"), size=3, name="header"),
            Layout(Panel(tok_table, title="Token Rates"), size=5, name="tokens"),
            Layout(Panel(dec_table, title="Decisions"), size=5, name="decisions"),
            Layout(Panel(log_text, title="Log"), name="log"),
            Layout(Panel(controls), size=3, name="controls"),
        )
        return layout

    # Key input thread
    def _key_listener() -> None:
        """Listen for single keystrokes (Windows-compatible)."""
        try:
            import msvcrt
            while not stop_event.is_set():
                if msvcrt.kbhit():
                    key = msvcrt.getch().decode("utf-8", errors="ignore").lower()
                    _handle_key(key)
                time.sleep(0.1)
        except ImportError:
            # Unix: use termios
            try:
                import sys
                import termios
                import tty

                fd = sys.stdin.fileno()
                old = termios.tcgetattr(fd)
                try:
                    tty.setcbreak(fd)
                    while not stop_event.is_set():
                        key = sys.stdin.read(1).lower()
                        _handle_key(key)
                finally:
                    termios.tcsetattr(fd, termios.TCSADRAIN, old)
            except Exception:
                # No keyboard input available (e.g. piped stdin)
                while not stop_event.is_set():
                    stop_event.wait(1.0)

    def _handle_key(key: str) -> None:
        if key == "q":
            stop_event.set()
        elif key == "m":
            try:
                idx = _MODE_CYCLE.index(console_config.llm_mode)
            except ValueError:
                idx = -1
            console_config.llm_mode = _MODE_CYCLE[(idx + 1) % len(_MODE_CYCLE)]
            log.info("LLM mode switched to: %s", console_config.llm_mode)
        elif key == "c":
            console_config.council_enabled = not console_config.council_enabled
            log.info("Council: %s", "ON" if console_config.council_enabled else "OFF")
        elif key == "p":
            console_config.planner_enabled = not console_config.planner_enabled
            log.info("Planner: %s", "ON" if console_config.planner_enabled else "OFF")
        elif key == "r":
            console_config.recording_enabled = not console_config.recording_enabled
            log.info("Recording: %s", "ON" if console_config.recording_enabled else "OFF")

    # Start key listener thread
    key_thread = threading.Thread(target=_key_listener, daemon=True)
    key_thread.start()

    # Main display loop
    try:
        with Live(build_display(), console=console, refresh_per_second=2, screen=True) as live:
            while not stop_event.is_set():
                live.update(build_display())
                stop_event.wait(0.5)
    except KeyboardInterrupt:
        stop_event.set()
    finally:
        logging.getLogger().removeHandler(log_capture)
