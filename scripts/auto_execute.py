"""
Auto-Execute — Sends console commands to Stellaris automatically.

Watches for new ``ai_commands.txt`` files and sends keystrokes to
the Stellaris window to execute them via the in-game console.

Flow:
  1. Watches the Stellaris user data directory for ai_commands.txt changes
  2. When a new command file appears, activates the Stellaris window
  3. Sends: ` (open console) → run ai_commands.txt → Enter → ` (close console)
  4. Waits for the next directive

Usage:
    python scripts/auto_execute.py

    # With custom Stellaris data directory
    python scripts/auto_execute.py --stellaris-dir "C:/Users/.../Paradox Interactive/Stellaris"

Requirements:
    - Stellaris must be running (non-Ironman, non-multiplayer)
    - The game console must be accessible (` key)
    - Windows only (uses ctypes for window activation)

Note: This is optional — you can always run `run ai_commands.txt` manually
in the Stellaris console instead.
"""

from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes
import logging
import os
import time
from pathlib import Path

log = logging.getLogger(__name__)

# Windows API constants
SW_RESTORE = 9
KEYEVENTF_KEYUP = 0x0002
VK_RETURN = 0x0D
VK_OEM_3 = 0xC0  # backtick/tilde key (console toggle)


def find_stellaris_window() -> int:
    """Find the Stellaris game window handle."""
    user32 = ctypes.windll.user32

    hwnd = user32.FindWindowW(None, "Stellaris")
    if hwnd:
        return hwnd

    # Try alternate titles
    for title in ("Stellaris ", "stellaris"):
        hwnd = user32.FindWindowW(None, title)
        if hwnd:
            return hwnd

    return 0


def activate_window(hwnd: int) -> bool:
    """Bring Stellaris window to foreground."""
    user32 = ctypes.windll.user32

    # Restore if minimized
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, SW_RESTORE)

    # Bring to front
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.3)

    return user32.GetForegroundWindow() == hwnd


def send_key(vk: int, delay: float = 0.05) -> None:
    """Send a single key press + release."""
    user32 = ctypes.windll.user32
    user32.keybd_event(vk, 0, 0, 0)
    time.sleep(delay)
    user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
    time.sleep(delay)


def send_text(text: str, delay: float = 0.03) -> None:
    """Type a string using SendInput."""
    user32 = ctypes.windll.user32
    for char in text:
        # Use VkKeyScan to get virtual key for each character
        vk_result = user32.VkKeyScanW(ord(char))
        vk = vk_result & 0xFF
        shift = (vk_result >> 8) & 1

        if shift:
            user32.keybd_event(0x10, 0, 0, 0)  # Shift down

        user32.keybd_event(vk, 0, 0, 0)
        time.sleep(delay)
        user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)

        if shift:
            user32.keybd_event(0x10, 0, KEYEVENTF_KEYUP, 0)

        time.sleep(delay)


def execute_console_command(hwnd: int, command: str = "run ai_commands.txt") -> bool:
    """Open Stellaris console, type command, execute, close console."""
    if not activate_window(hwnd):
        log.warning("Could not activate Stellaris window")
        return False

    time.sleep(0.2)

    # Open console (backtick key)
    send_key(VK_OEM_3, delay=0.1)
    time.sleep(0.3)

    # Type command
    send_text(command)
    time.sleep(0.1)

    # Press Enter
    send_key(VK_RETURN, delay=0.1)
    time.sleep(0.3)

    # Close console (backtick key again)
    send_key(VK_OEM_3, delay=0.1)

    return True


def watch_and_execute(
    stellaris_dir: Path,
    poll_interval: float = 2.0,
) -> None:
    """Watch for new ai_commands.txt and auto-execute in Stellaris."""
    cmd_path = stellaris_dir / "ai_commands.txt"
    last_mtime: float = 0.0

    log.info("Auto-execute watching: %s", cmd_path)
    log.info("Make sure Stellaris is running and the console is accessible")
    log.info("Press Ctrl+C to stop")

    while True:
        try:
            if cmd_path.exists():
                mtime = os.path.getmtime(cmd_path)
                if mtime > last_mtime:
                    last_mtime = mtime

                    # Read command to log what we're executing
                    content = cmd_path.read_text(encoding="utf-8").strip()
                    action_line = next(
                        (l for l in content.splitlines() if l.startswith("#")),
                        "unknown",
                    )
                    log.info("New directive detected: %s", action_line)

                    # Find and activate Stellaris
                    hwnd = find_stellaris_window()
                    if hwnd == 0:
                        log.warning("Stellaris window not found — is the game running?")
                        time.sleep(poll_interval)
                        continue

                    # Execute
                    if execute_console_command(hwnd):
                        log.info("Console command sent successfully")
                    else:
                        log.warning("Failed to send console command")

            time.sleep(poll_interval)

        except KeyboardInterrupt:
            log.info("Shutting down auto-execute")
            break
        except Exception:
            log.exception("Error in auto-execute loop")
            time.sleep(poll_interval)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Auto-execute Overmind directives in Stellaris console",
    )
    parser.add_argument(
        "--stellaris-dir", type=Path,
        default=Path("C:/Users/Fintz/OneDrive/Documents/Paradox Interactive/Stellaris"),
        help="Stellaris user data directory",
    )
    parser.add_argument(
        "--poll", type=float, default=2.0,
        help="Polling interval in seconds",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [auto-exec] %(message)s",
        datefmt="%H:%M:%S",
    )

    if not args.stellaris_dir.exists():
        log.error("Stellaris directory not found: %s", args.stellaris_dir)
        raise SystemExit(1)

    watch_and_execute(args.stellaris_dir, args.poll)


if __name__ == "__main__":
    main()
