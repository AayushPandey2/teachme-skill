"""Terminal and host capability detection for cross-platform TeachMe CLI behavior."""

from __future__ import annotations

import importlib.util
import os
import shutil
import sys
from typing import Any, Mapping

VALID_IMAGE_PROTOCOLS = ("none", "kitty", "iterm2", "sixel")


def _parse_positive_int(raw: str | None) -> int | None:
    if raw is None:
        return None
    try:
        val = int(str(raw).strip())
        return val if val > 0 else None
    except ValueError:
        return None


def _clamp(val: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, val))


def detect_terminal_capabilities(
    env: Mapping[str, str] | None = None,
    *,
    width: int | None = None,
    height: int | None = None,
    is_tty: bool | None = None,
    interactive: bool | None = None,
    stdout_encoding: str | None = None,
) -> dict[str, Any]:
    """Detect terminal dimensions, interactivity, color, Unicode, and image protocol support.

    Never emits escape sequences or assumes rich terminal features when unconfirmed.
    """
    environ = env if env is not None else os.environ

    term_size = shutil.get_terminal_size(fallback=(80, 24))
    env_cols = _parse_positive_int(environ.get("COLUMNS"))
    env_rows = _parse_positive_int(environ.get("LINES"))

    eff_width = width if width is not None else (env_cols or term_size.columns or 80)
    eff_height = height if height is not None else (env_rows or term_size.lines or 24)
    eff_width = _clamp(int(eff_width), 20, 300)
    eff_height = _clamp(int(eff_height), 10, 120)

    if is_tty is None:
        try:
            eff_tty = bool(sys.stdout.isatty())
        except Exception:
            eff_tty = False
    else:
        eff_tty = bool(is_tty)

    if interactive is None:
        try:
            stdin_tty = bool(sys.stdin.isatty())
        except Exception:
            stdin_tty = False
        non_int_flag = str(environ.get("TEACHME_NON_INTERACTIVE", "")).strip().lower() in ("1", "true", "yes")
        ci_flag = bool(str(environ.get("CI", "")).strip())
        eff_interactive = bool(eff_tty and stdin_tty and not non_int_flag and not ci_flag)
    else:
        eff_interactive = bool(interactive)

    term_val = str(environ.get("TERM", "")).strip().lower()
    term_prog = str(environ.get("TERM_PROGRAM", "")).strip()
    lc_terminal = str(environ.get("LC_TERMINAL", "")).strip()
    colorterm = str(environ.get("COLORTERM", "")).strip().lower()

    no_color = (
        bool(str(environ.get("NO_COLOR", "")).strip())
        or str(environ.get("TEACHME_NO_COLOR", "")).strip().lower() in ("1", "true", "yes")
        or term_val == "dumb"
    )

    if no_color or not eff_tty:
        color_support = "none"
    elif colorterm in ("truecolor", "24bit"):
        color_support = "truecolor"
    elif "256color" in term_val:
        color_support = "ansi256"
    elif environ.get("WT_SESSION") or term_val not in ("", "dumb"):
        color_support = "ansi16"
    else:
        color_support = "none"

    enc = (stdout_encoding or getattr(sys.stdout, "encoding", None) or "utf-8").lower()
    unicode_override = str(environ.get("TEACHME_UNICODE", "")).strip().lower()
    if unicode_override in ("0", "false", "no", "ascii"):
        unicode_support = False
    elif unicode_override in ("1", "true", "yes"):
        unicode_support = True
    else:
        unicode_support = "utf" in enc

    proto_override = str(environ.get("TEACHME_IMAGE_PROTOCOL", "")).strip().lower()
    if not eff_tty:
        inline_protocol = "none"
    elif proto_override in VALID_IMAGE_PROTOCOLS:
        inline_protocol = proto_override
    elif environ.get("KITTY_WINDOW_ID") or term_val == "xterm-kitty":
        inline_protocol = "kitty"
    elif term_prog == "iTerm.app" or lc_terminal.lower() == "iterm2":
        inline_protocol = "iterm2"
    else:
        inline_protocol = "none"

    pil_available = importlib.util.find_spec("PIL") is not None

    return {
        "width": eff_width,
        "height": eff_height,
        "is_tty": eff_tty,
        "interactive": eff_interactive,
        "no_color": no_color,
        "color_support": color_support,
        "unicode_support": unicode_support,
        "stdout_encoding": enc,
        "inline_image_protocol": inline_protocol,
        "pil_available": pil_available,
        "os_platform": sys.platform,
    }


def detect_host_capabilities(
    available_tools: Mapping[str, bool] | None = None,
    terminal_caps: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Summarize host-exposed capabilities honestly without inventing tools."""
    t_caps = dict(terminal_caps) if terminal_caps is not None else detect_terminal_capabilities()
    tools = dict(available_tools or {})
    return {
        "web_search": bool(tools.get("web_search", False)),
        "source_fetch": bool(tools.get("source_fetch", False)),
        "image_search": bool(tools.get("image_search", False)),
        "image_inspect": bool(tools.get("image_inspect", False)),
        "python_exec": bool(tools.get("python_exec", True)),
        "browser": bool(tools.get("browser", False)),
        "terminal": t_caps,
    }
