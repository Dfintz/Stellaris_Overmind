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
    fast_decisions: bool = True


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


def _open_log_tail(log_file: str) -> None:
    """Open a new terminal window tailing the log file."""
    import subprocess
    import sys

    path = str(log_file)
    try:
        if sys.platform == "win32":
            # PowerShell in a new window, tailing the log file
            subprocess.Popen(
                ["powershell", "-NoExit", "-Command",
                 f"Write-Host 'Overmind Log Viewer — {path}' -ForegroundColor Cyan; "
                 f"Get-Content '{path}' -Wait -Tail 50"],
                creationflags=subprocess.CREATE_NEW_CONSOLE,
            )
        else:
            # Unix: try to open a new terminal
            subprocess.Popen(["tail", "-f", "-n", "50", path])
        log.info("Opened log viewer: %s", path)
    except Exception as exc:
        log.warning("Could not open log viewer: %s", exc)


def run_console(
    metrics_collector: object,
    console_config: ConsoleConfig,
    stop_event: threading.Event,
    provider_name: str = "unknown",
    target_mode: str = "player",
    log_file: str | None = None,
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
        \"player\" or \"ai\".
    log_file : str | None
        Path to log file for parallel tail view.
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

        # Header — compact for narrow terminals
        short_provider = provider_name
        if "(" in short_provider and ")" in short_provider:
            short_provider = short_provider.split("(")[1].rstrip(")")

        year_str = str(m.game_year) if m.game_year > 0 else "---"

        header = Text()
        header.append("OVERMIND", style="bold cyan")
        header.append(f" Y:{year_str}", style="bold yellow")
        header.append(f" {target_mode.upper()}", style="bold")
        header.append(f" {short_provider}", style="")
        header.append(f" {_format_uptime(m.uptime_s)}", style="dim")

        # Token rates — 2 columns for narrow terminals
        tok_table = Table(show_header=False, expand=True, box=None, padding=(0, 1))
        tok_table.add_column(ratio=1)
        tok_table.add_column(ratio=1)
        tok_table.add_row(
            f"Tok/s:[bold]{m.tokens_per_second:.0f}[/bold] Avg:[bold]{m.avg_latency_ms:.0f}ms[/bold]",
            f"Calls:{m.local_calls} Err:{m.llm_errors} Tok:{total_tokens:,}",
        )

        # Decisions — use Text objects to avoid markup issues
        from rich.markup import escape
        safe_last = escape(m.last_action) if m.last_action else "none"
        dec_line1 = Text()
        dec_line1.append(f"Ok:{m.decisions_made}", style="bold green")
        dec_line1.append(f" Fail:{m.decisions_failed}", style="bold red")
        dec_line1.append(f" ValErr:{m.validation_errors}")
        dec_line2 = Text()
        dec_line2.append("Last: ")
        dec_line2.append(safe_last, style="bold")

        dec_table = Table(show_header=False, expand=True, box=None, padding=(0, 1))
        dec_table.add_column(ratio=1)
        dec_table.add_column(ratio=1)
        dec_table.add_row(dec_line1, dec_line2)

        # Outcomes panel (only if scoring has started)
        outcomes_text = None
        if m.scored_count > 0:
            sign = "+" if m.avg_composite_score >= 0 else ""
            parts = [f"Scored: {m.scored_count}  Avg: {sign}{m.avg_composite_score:.3f}"]
            for act, avg in sorted(m.action_scores.items()):
                s = "+" if avg >= 0 else ""
                parts.append(f"{act}={s}{avg:.2f}")
            outcomes_text = "  ".join(parts)

        # Empire status board — shows each empire and their current action
        from rich.markup import escape
        empire_table = None
        if m.empire_status:
            empire_table = Table(
                show_header=True, expand=True, box=None, padding=(0, 1),
            )
            empire_table.add_column("Empire", ratio=2, no_wrap=True)
            empire_table.add_column("Action", ratio=2, no_wrap=True)

            for name, action in sorted(m.empire_status.items()):
                empire_table.add_row(escape(name), escape(action))

        # Log panel — last 8 lines only (compact)
        log_lines = list(log_capture.records)
        visible = log_lines[-8:] if log_lines else []
        while len(visible) < 4:
            visible.append("")
        log_text = "\n".join(visible)

        # Suggestion panel (player mode only)
        suggestion_panel = None
        if target_mode == "player" and m.last_suggestion:
            suggestion_panel = Panel(
                m.last_suggestion,
                title="Suggestion",
                border_style="yellow",
            )

        # Controls — avoid [] brackets entirely (Rich interprets them as markup)
        controls = Text()
        controls.append("M:", style="bold cyan")
        controls.append(f"{console_config.llm_mode.upper()} ", style="")
        for label, on in [
            ("C:", console_config.council_enabled),
            ("P:", console_config.planner_enabled),
            ("R:", console_config.recording_enabled),
            ("F:", console_config.fast_decisions),
        ]:
            controls.append(label, style="bold cyan")
            controls.append("ON " if on else "off ", style="green" if on else "dim")
        if log_file:
            controls.append("L:", style="bold cyan")
            controls.append("log ", style="")
        controls.append("Q:", style="bold red")
        controls.append("quit", style="")

        # Assemble layout
        layout = Layout()
        panels = [
            Layout(Panel(header, style="bold"), size=3, name="header"),
            Layout(Panel(tok_table, title="Stats"), size=3, name="tokens"),
            Layout(Panel(dec_table, title="Decisions"), size=3, name="decisions"),
        ]
        if suggestion_panel is not None:
            panels.append(Layout(suggestion_panel, size=8, name="suggestion"))
        if outcomes_text is not None:
            panels.append(Layout(
                Panel(outcomes_text, title="Outcomes", border_style="magenta"),
                size=3, name="outcomes",
            ))
        if empire_table is not None:
            panels.append(Layout(
                Panel(empire_table, title="Empires"),
                name="empires",
            ))
        panels.extend([
            Layout(Panel(log_text, title="Log"), size=6, name="log"),
            Layout(Panel(controls), size=3, name="controls"),
        ])
        layout.split_column(*panels)
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
        elif key == "f":
            console_config.fast_decisions = not console_config.fast_decisions
            log.info("Fast decisions: %s", "ON" if console_config.fast_decisions else "OFF")
        elif key == "l":
            if log_file:
                _open_log_tail(log_file)
            else:
                log.info("No log file configured — restart with --log-file <path>")

    # Start key listener thread
    key_thread = threading.Thread(target=_key_listener, daemon=True)
    key_thread.start()

    # Main display loop
    try:
        with Live(build_display(), console=console, refresh_per_second=1, screen=True) as live:
            while not stop_event.is_set():
                live.update(build_display())
                stop_event.wait(1.0)
    except KeyboardInterrupt:
        stop_event.set()
    finally:
        logging.getLogger().removeHandler(log_capture)
