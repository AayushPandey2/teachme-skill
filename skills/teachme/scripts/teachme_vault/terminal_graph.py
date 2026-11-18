"""Lightweight stdlib-only terminal graphing utility for TeachMe.

Supports Braille, Unicode, and pure ASCII rendering with NO_COLOR support,
safe AST-based mathematical expression evaluation, domain/clipping safety,
and zero external dependencies.
"""

from __future__ import annotations

import ast
import math
import operator
from typing import Any, Callable, Sequence

from .terminal_caps import detect_terminal_capabilities

# Braille bit mapping for a 2x4 subpixel grid per character cell:
# col 0: rows 0..3 -> bits 0x01, 0x02, 0x04, 0x40
# col 1: rows 0..3 -> bits 0x08, 0x10, 0x20, 0x80
_BRAILLE_DOTS = (
    (0x01, 0x08),
    (0x02, 0x10),
    (0x04, 0x20),
    (0x40, 0x80),
)

_SAFE_CONSTANTS: dict[str, float] = {
    "pi": math.pi,
    "e": math.e,
    "tau": math.tau,
}


def _sigmoid(val: float) -> float:
    if val >= 0:
        z = math.exp(-min(val, 700.0))
        return 1.0 / (1.0 + z)
    z = math.exp(max(val, -700.0))
    return z / (1.0 + z)


_SAFE_FUNCS: dict[str, Callable[[float], float]] = {
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "asin": math.asin,
    "acos": math.acos,
    "atan": math.atan,
    "sinh": math.sinh,
    "cosh": math.cosh,
    "tanh": math.tanh,
    "exp": math.exp,
    "log": math.log,
    "log10": math.log10,
    "log2": math.log2,
    "sqrt": math.sqrt,
    "abs": abs,
    "floor": math.floor,
    "ceil": math.ceil,
    "sigmoid": _sigmoid,
}

_BIN_OPS: dict[type[ast.operator], Callable[[float, float], float]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
}

_UNARY_OPS: dict[type[ast.unaryop], Callable[[float], float]] = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}

_SERIES_CHARS_ASCII = ("*", "o", "+", "#", "x")
_SERIES_CHARS_UNICODE = ("●", "◆", "▲", "■", "×")
_ANSI_PALETTE = ("\x1b[36m", "\x1b[33m", "\x1b[32m", "\x1b[35m", "\x1b[34m")
_ANSI_RESET = "\x1b[0m"


def compile_safe_math_expr(expr: str) -> Callable[[float], float]:
    """Compile a univariate math expression f(x) safely via AST whitelisting."""
    clean = str(expr or "").strip()
    if not clean:
        raise ValueError("Mathematical expression cannot be empty")
    if len(clean) > 256:
        raise ValueError("Mathematical expression exceeds 256 character limit")
    # Support caret ^ as exponentiation convenience in math expressions
    normalized = clean.replace("^", "**")
    try:
        tree = ast.parse(normalized, mode="eval")
    except SyntaxError as exc:
        raise ValueError(f"Invalid math expression {expr!r}: {exc.msg}") from exc

    def _eval_node(node: ast.AST, x_val: float) -> float:
        if isinstance(node, ast.Expression):
            return _eval_node(node.body, x_val)
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
                return float(node.value)
            raise ValueError(f"Unsupported constant in expression: {node.value!r}")
        if isinstance(node, ast.Name):
            if node.id == "x":
                return float(x_val)
            if node.id in _SAFE_CONSTANTS:
                return _SAFE_CONSTANTS[node.id]
            raise ValueError(f"Unknown symbol {node.id!r} in math expression (allowed: x, pi, e, tau)")
        if isinstance(node, ast.UnaryOp):
            fn = _UNARY_OPS.get(type(node.op))
            if fn is None:
                raise ValueError(f"Unsupported unary operator: {type(node.op).__name__}")
            return fn(_eval_node(node.operand, x_val))
        if isinstance(node, ast.BinOp):
            fn = _BIN_OPS.get(type(node.op))
            if fn is None:
                raise ValueError(f"Unsupported binary operator: {type(node.op).__name__}")
            left = _eval_node(node.left, x_val)
            right = _eval_node(node.right, x_val)
            if isinstance(node.op, ast.Pow) and abs(right) > 1000:
                return math.nan
            return fn(left, right)
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in _SAFE_FUNCS:
                name = getattr(node.func, "id", type(node.func).__name__)
                raise ValueError(f"Unsupported function {name!r} in math expression")
            if len(node.args) != 1 or node.keywords:
                raise ValueError(f"Function {node.func.id!r} expects exactly 1 positional argument")
            arg_val = _eval_node(node.args[0], x_val)
            return float(_SAFE_FUNCS[node.func.id](arg_val))
        raise ValueError(f"Disallowed expression node: {type(node).__name__}")

    # Validate AST structure eagerly at compile time with x=1.0 (ignoring domain math errors)
    def _validate_ast(node: ast.AST) -> None:
        if isinstance(node, ast.Expression):
            _validate_ast(node.body)
        elif isinstance(node, ast.Constant):
            if not (isinstance(node.value, (int, float)) and not isinstance(node.value, bool)):
                raise ValueError(f"Unsupported constant: {node.value!r}")
        elif isinstance(node, ast.Name):
            if node.id != "x" and node.id not in _SAFE_CONSTANTS:
                raise ValueError(f"Unknown symbol {node.id!r} in math expression (allowed: x, pi, e, tau)")
        elif isinstance(node, ast.UnaryOp):
            if type(node.op) not in _UNARY_OPS:
                raise ValueError(f"Unsupported unary operator: {type(node.op).__name__}")
            _validate_ast(node.operand)
        elif isinstance(node, ast.BinOp):
            if type(node.op) not in _BIN_OPS:
                raise ValueError(f"Unsupported binary operator: {type(node.op).__name__}")
            _validate_ast(node.left)
            _validate_ast(node.right)
        elif isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in _SAFE_FUNCS:
                name = getattr(node.func, "id", type(node.func).__name__)
                raise ValueError(f"Unsupported function {name!r} in math expression")
            if len(node.args) != 1 or node.keywords:
                raise ValueError(f"Function {node.func.id!r} expects exactly 1 positional argument")
            _validate_ast(node.args[0])
        else:
            raise ValueError(f"Disallowed expression node: {type(node).__name__}")

    _validate_ast(tree)

    def _fn(x_val: float) -> float:
        try:
            res = float(_eval_node(tree, float(x_val)))
            return res if math.isfinite(res) else math.nan
        except (ValueError, ZeroDivisionError, OverflowError, ArithmeticError):
            return math.nan

    return _fn


def _resolve_render_opts(
    width: int | None,
    height: int | None,
    charset: str,
    no_color: bool | None,
) -> tuple[int, int, str, bool]:
    caps = detect_terminal_capabilities()
    eff_w = max(30, min(120, int(width if width is not None else caps["width"])))
    eff_h = max(8, min(36, int(height if height is not None else min(18, max(10, caps["height"] - 6)))))
    eff_no_color = bool(caps["no_color"]) if no_color is None else bool(no_color)

    req_charset = (charset or "auto").strip().lower()
    if req_charset == "auto":
        eff_charset = "braille" if caps["unicode_support"] else "ascii"
    elif req_charset in ("braille", "unicode", "ascii"):
        eff_charset = req_charset
        if not caps["unicode_support"] and req_charset in ("braille", "unicode"):
            # Explicit override allowed if caller requests it, but respect explicit ascii too
            eff_charset = req_charset
    else:
        raise ValueError(f"Unsupported charset {charset!r}; expected auto|braille|unicode|ascii")

    return eff_w, eff_h, eff_charset, eff_no_color


def _fmt_num(val: float) -> str:
    if not math.isfinite(val):
        return "nan"
    if abs(val) >= 1e4 or (0 < abs(val) < 1e-2):
        return f"{val:.2e}"
    if abs(val - round(val)) < 1e-9:
        return str(int(round(val)))
    return f"{val:.3g}"


def _draw_bresenham(
    plot_fn: Callable[[int, int], None],
    x0: int,
    y0: int,
    x1: int,
    y1: int,
) -> None:
    dx = abs(x1 - x0)
    dy = -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    cx, cy = x0, y0
    steps = 0
    max_steps = dx + abs(dy) + 4
    while steps < max_steps:
        plot_fn(cx, cy)
        if cx == x1 and cy == y1:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            cx += sx
        if e2 <= dx:
            err += dx
            cy += sy
        steps += 1


def _colorize(text: str, idx: int, no_color: bool) -> str:
    if no_color or not text:
        return text
    code = _ANSI_PALETTE[idx % len(_ANSI_PALETTE)]
    return f"{code}{text}{_ANSI_RESET}"


def render_xy_graph(
    series_list: Sequence[dict[str, Any]],
    *,
    kind: str = "line",
    title: str = "",
    x_label: str = "x",
    y_label: str = "y",
    unit_x: str = "",
    unit_y: str = "",
    width: int | None = None,
    height: int | None = None,
    charset: str = "auto",
    no_color: bool | None = None,
    y_clip: tuple[float, float] | None = None,
    markers: Sequence[dict[str, Any]] | None = None,
    domain_warnings: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Render one or more (x, y) data series as a terminal line or scatter plot."""
    eff_w, eff_h, eff_charset, eff_no_color = _resolve_render_opts(width, height, charset, no_color)
    warnings = list(domain_warnings or [])

    cleaned_series: list[dict[str, Any]] = []
    all_x: list[float] = []
    all_y: list[float] = []
    points_plotted = 0
    points_skipped = 0

    for idx, raw_s in enumerate(series_list):
        name = str(raw_s.get("name") or f"series-{idx + 1}")
        pts: list[tuple[float, float] | None] = []
        for pt in raw_s.get("points", []):
            if pt is None or len(pt) < 2:
                pts.append(None)
                continue
            try:
                xv = float(pt[0])
                yv = float(pt[1])
            except (TypeError, ValueError):
                points_skipped += 1
                pts.append(None)
                continue
            if not (math.isfinite(xv) and math.isfinite(yv)):
                points_skipped += 1
                pts.append(None)
                continue
            if y_clip is not None:
                lo, hi = float(y_clip[0]), float(y_clip[1])
                if yv < lo or yv > hi:
                    yv = max(lo, min(hi, yv))
            pts.append((xv, yv))
            all_x.append(xv)
            all_y.append(yv)
            points_plotted += 1
        cleaned_series.append({"name": name, "points": pts})

    valid_markers: list[dict[str, Any]] = []
    for mk in markers or []:
        try:
            mx = float(mk["x"])
            my = float(mk["y"])
        except (KeyError, TypeError, ValueError):
            continue
        if math.isfinite(mx) and math.isfinite(my):
            valid_markers.append({"x": mx, "y": my, "label": str(mk.get("label") or "*"), "char": str(mk.get("char") or "@")[:1]})
            all_x.append(mx)
            all_y.append(my)

    if not all_x or not all_y:
        return {
            "ok": False,
            "kind": kind,
            "error": "No finite points to plot",
            "text": f"[Graph unavailable: no finite points in domain{'; ' + '; '.join(warnings) if warnings else ''}]",
            "width": eff_w,
            "height": eff_h,
            "charset": eff_charset,
            "no_color": eff_no_color,
            "points_plotted": 0,
            "points_skipped": points_skipped,
            "domain_warnings": warnings,
        }

    x_min, x_max = min(all_x), max(all_x)
    y_min, y_max = min(all_y), max(all_y)

    if math.isclose(x_min, x_max, rel_tol=1e-12, abs_tol=1e-12):
        pad = max(1.0, abs(x_min) * 0.1)
        x_min -= pad
        x_max += pad
        warnings.append("Zero-width x range expanded for display")

    if math.isclose(y_min, y_max, rel_tol=1e-12, abs_tol=1e-12):
        pad = max(1.0, abs(y_min) * 0.1)
        y_min -= pad
        y_max += pad
        warnings.append("Zero-width y range expanded for constant values")

    y_axis_labels = [_fmt_num(y_max), _fmt_num((y_max + y_min) / 2.0), _fmt_num(y_min)]
    y_label_w = max(len(lbl) for lbl in y_axis_labels) + 1
    plot_cols = max(16, eff_w - y_label_w - 2)
    plot_rows = max(6, eff_h - 4)

    use_braille = eff_charset == "braille"
    pix_w = plot_cols * (2 if use_braille else 1)
    pix_h = plot_rows * (4 if use_braille else 1)

    def _to_px(xv: float, yv: float) -> tuple[int, int]:
        nx = (xv - x_min) / (x_max - x_min)
        ny = (yv - y_min) / (y_max - y_min)
        px = max(0, min(pix_w - 1, int(round(nx * (pix_w - 1)))))
        py = max(0, min(pix_h - 1, int(round((1.0 - ny) * (pix_h - 1)))))
        return px, py

    lines: list[str] = []
    if title:
        lines.append(title[:eff_w])

    if use_braille:
        # Per cell bitmask + series owner index for optional coloring
        grid = [[0 for _ in range(plot_cols)] for _ in range(plot_rows)]
        owner = [[-1 for _ in range(plot_cols)] for _ in range(plot_rows)]

        def _set_px(px: int, py: int, s_idx: int) -> None:
            if 0 <= px < pix_w and 0 <= py < pix_h:
                cx, cy = px // 2, py // 4
                dx, dy = px % 2, py % 4
                grid[cy][cx] |= _BRAILLE_DOTS[dy][dx]
                if owner[cy][cx] == -1:
                    owner[cy][cx] = s_idx

        for s_idx, ser in enumerate(cleaned_series):
            pts = ser["points"]
            prev_px: tuple[int, int] | None = None
            for pt in pts:
                if pt is None:
                    prev_px = None
                    continue
                cur_px = _to_px(pt[0], pt[1])
                if kind == "scatter" or prev_px is None:
                    _set_px(cur_px[0], cur_px[1], s_idx)
                else:
                    _draw_bresenham(lambda x, y, i=s_idx: _set_px(x, y, i), prev_px[0], prev_px[1], cur_px[0], cur_px[1])
                prev_px = cur_px

        # Overlay explicit markers cleanly on character grid
        marker_cells: dict[tuple[int, int], str] = {}
        for mk in valid_markers:
            mpx, mpy = _to_px(mk["x"], mk["y"])
            marker_cells[(mpx // 2, mpy // 4)] = mk["char"]

        # Render zero axes lightly if 0 lies inside domain
        zero_x_col = int(round(((0.0 - x_min) / (x_max - x_min)) * (plot_cols - 1))) if x_min < 0 < x_max else None
        zero_y_row = int(round((1.0 - (0.0 - y_min) / (y_max - y_min)) * (plot_rows - 1))) if y_min < 0 < y_max else None

        border_v = "│"
        border_bl = "└"
        border_h = "─"
        mid_row = plot_rows // 2

        for r in range(plot_rows):
            if r == 0:
                lbl = y_axis_labels[0]
            elif r == mid_row:
                lbl = y_axis_labels[1]
            elif r == plot_rows - 1:
                lbl = y_axis_labels[2]
            else:
                lbl = ""
            prefix = f"{lbl:>{y_label_w - 1}} {border_v}"
            row_chars: list[str] = []
            for c in range(plot_cols):
                if (c, r) in marker_cells:
                    row_chars.append(_colorize(marker_cells[(c, r)], len(cleaned_series), eff_no_color))
                elif grid[r][c]:
                    ch = chr(0x2800 + grid[r][c])
                    row_chars.append(_colorize(ch, max(0, owner[r][c]), eff_no_color))
                elif zero_y_row is not None and r == zero_y_row and zero_x_col is not None and c == zero_x_col:
                    row_chars.append("┼")
                elif zero_y_row is not None and r == zero_y_row:
                    row_chars.append("┄")
                elif zero_x_col is not None and c == zero_x_col:
                    row_chars.append("┆")
                else:
                    row_chars.append(" ")
            lines.append(prefix + "".join(row_chars))

        lines.append((" " * (y_label_w)) + border_bl + (border_h * plot_cols))
    else:
        palette = _SERIES_CHARS_UNICODE if eff_charset == "unicode" else _SERIES_CHARS_ASCII
        cgrid = [[" " for _ in range(plot_cols)] for _ in range(plot_rows)]
        cowner = [[-1 for _ in range(plot_cols)] for _ in range(plot_rows)]

        zero_x_col = int(round(((0.0 - x_min) / (x_max - x_min)) * (plot_cols - 1))) if x_min < 0 < x_max else None
        zero_y_row = int(round((1.0 - (0.0 - y_min) / (y_max - y_min)) * (plot_rows - 1))) if y_min < 0 < y_max else None
        if zero_y_row is not None and 0 <= zero_y_row < plot_rows:
            for c in range(plot_cols):
                cgrid[zero_y_row][c] = "-"
        if zero_x_col is not None and 0 <= zero_x_col < plot_cols:
            for r in range(plot_rows):
                cgrid[r][zero_x_col] = "+" if (zero_y_row is not None and r == zero_y_row) else ":"

        def _set_cell(cx: int, cy: int, ch: str, s_idx: int) -> None:
            if 0 <= cx < plot_cols and 0 <= cy < plot_rows:
                cgrid[cy][cx] = ch
                if cowner[cy][cx] == -1:
                    cowner[cy][cx] = s_idx

        for s_idx, ser in enumerate(cleaned_series):
            ch = palette[s_idx % len(palette)]
            prev_px: tuple[int, int] | None = None
            for pt in ser["points"]:
                if pt is None:
                    prev_px = None
                    continue
                cur_px = _to_px(pt[0], pt[1])
                if kind == "scatter" or prev_px is None:
                    _set_cell(cur_px[0], cur_px[1], ch, s_idx)
                else:
                    _draw_bresenham(lambda x, y, c=ch, i=s_idx: _set_cell(x, y, c, i), prev_px[0], prev_px[1], cur_px[0], cur_px[1])
                prev_px = cur_px

        for mk in valid_markers:
            mx, my = _to_px(mk["x"], mk["y"])
            _set_cell(mx, my, mk["char"], len(cleaned_series))

        border_v = "│" if eff_charset == "unicode" else "|"
        border_bl = "└" if eff_charset == "unicode" else "+"
        border_h = "─" if eff_charset == "unicode" else "-"
        mid_row = plot_rows // 2

        for r in range(plot_rows):
            if r == 0:
                lbl = y_axis_labels[0]
            elif r == mid_row:
                lbl = y_axis_labels[1]
            elif r == plot_rows - 1:
                lbl = y_axis_labels[2]
            else:
                lbl = ""
            prefix = f"{lbl:>{y_label_w - 1}} {border_v}"
            rendered_row: list[str] = []
            for c in range(plot_cols):
                cell = cgrid[r][c]
                if cowner[r][c] >= 0:
                    rendered_row.append(_colorize(cell, cowner[r][c], eff_no_color))
                else:
                    rendered_row.append(cell)
            lines.append(prefix + "".join(rendered_row))
        lines.append((" " * y_label_w) + border_bl + (border_h * plot_cols))

    # X-axis tick row
    x_left = _fmt_num(x_min)
    x_mid = _fmt_num((x_min + x_max) / 2.0)
    x_right = _fmt_num(x_max)
    gap1 = max(1, (plot_cols // 2) - len(x_left) - (len(x_mid) // 2))
    gap2 = max(1, plot_cols - len(x_left) - gap1 - len(x_mid) - len(x_right))
    tick_line = (" " * (y_label_w + 1)) + x_left + (" " * gap1) + x_mid + (" " * gap2) + x_right
    lines.append(tick_line[:eff_w])

    # Axis labels + legend
    xu = f" ({unit_x})" if unit_x else ""
    yu = f" ({unit_y})" if unit_y else ""
    legend_parts: list[str] = [f"Axes: x={x_label}{xu}, y={y_label}{yu}"]
    if len(cleaned_series) > 1 or cleaned_series[0]["name"] != "series-1":
        for idx, ser in enumerate(cleaned_series):
            sym = "*" if use_braille else (_SERIES_CHARS_UNICODE if eff_charset == "unicode" else _SERIES_CHARS_ASCII)[idx % 5]
            legend_parts.append(f"[{sym}] {ser['name']}")
    for mk in valid_markers[:3]:
        legend_parts.append(f"[{mk['char']}] {mk['label']} ({_fmt_num(mk['x'])}, {_fmt_num(mk['y'])})")
    lines.append(" | ".join(legend_parts))

    if warnings:
        lines.append("Notes: " + "; ".join(warnings[:3]))

    return {
        "ok": True,
        "kind": kind,
        "text": "\n".join(lines),
        "width": eff_w,
        "height": eff_h,
        "charset": eff_charset,
        "no_color": eff_no_color,
        "x_range": [x_min, x_max],
        "y_range": [y_min, y_max],
        "points_plotted": points_plotted,
        "points_skipped": points_skipped,
        "domain_warnings": warnings,
        "key_coordinates": [
            {"label": mk["label"], "x": mk["x"], "y": mk["y"]} for mk in valid_markers
        ],
    }


def render_function_graph(
    expr_or_fn: str | Callable[[float], float],
    x_min: float,
    x_max: float,
    *,
    samples: int | None = None,
    title: str = "",
    x_label: str = "x",
    y_label: str = "y",
    unit_x: str = "",
    unit_y: str = "",
    width: int | None = None,
    height: int | None = None,
    charset: str = "auto",
    no_color: bool | None = None,
    y_clip: tuple[float, float] | None = None,
    markers: Sequence[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Sample a 2D mathematical function safely and render it in the terminal."""
    x0 = float(x_min)
    x1 = float(x_max)
    if not (math.isfinite(x0) and math.isfinite(x1)):
        raise ValueError("x_min and x_max must be finite numbers")
    if x0 > x1:
        raise ValueError(f"Invalid domain: x_min ({x0}) > x_max ({x1})")

    warnings: list[str] = []
    if math.isclose(x0, x1):
        x0 -= 1.0
        x1 += 1.0
        warnings.append("Zero-width domain expanded around x")

    if isinstance(expr_or_fn, str):
        fn = compile_safe_math_expr(expr_or_fn)
        series_name = expr_or_fn.strip()
        eff_title = title or f"y = {series_name}"
    else:
        fn = expr_or_fn
        series_name = y_label
        eff_title = title

    eff_w, _, eff_charset, _ = _resolve_render_opts(width, height, charset, no_color)
    n_samples = max(24, min(400, int(samples if samples is not None else eff_w * (2 if eff_charset == "braille" else 1))))

    pts: list[tuple[float, float] | None] = []
    skipped = 0
    for i in range(n_samples):
        xv = x0 + (x1 - x0) * (i / max(1, n_samples - 1))
        try:
            yv = float(fn(xv))
        except Exception:
            yv = math.nan
        if not math.isfinite(yv):
            skipped += 1
            pts.append(None)
        else:
            pts.append((xv, yv))

    if skipped > 0:
        warnings.append(f"Skipped {skipped} non-finite/out-of-domain sample(s)")

    res = render_xy_graph(
        [{"name": series_name, "points": pts}],
        kind="line",
        title=eff_title,
        x_label=x_label,
        y_label=y_label,
        unit_x=unit_x,
        unit_y=unit_y,
        width=width,
        height=height,
        charset=charset,
        no_color=no_color,
        y_clip=y_clip,
        markers=markers,
        domain_warnings=warnings,
    )
    res["points_skipped"] = int(res.get("points_skipped", 0)) + skipped
    return res


def render_bar_chart(
    items: Sequence[tuple[str, float] | dict[str, Any]],
    *,
    title: str = "",
    value_label: str = "value",
    unit: str = "",
    width: int | None = None,
    charset: str = "auto",
    no_color: bool | None = None,
) -> dict[str, Any]:
    """Render a compact horizontal bar chart suitable for any terminal width."""
    eff_w, _, eff_charset, eff_no_color = _resolve_render_opts(width, None, charset, no_color)
    parsed: list[tuple[str, float]] = []
    skipped = 0
    for item in items:
        if isinstance(item, dict):
            lbl = str(item.get("label") or "")
            raw_v = item.get("value")
        else:
            lbl = str(item[0])
            raw_v = item[1]
        try:
            val = float(raw_v)
        except (TypeError, ValueError):
            skipped += 1
            continue
        if not math.isfinite(val):
            skipped += 1
            continue
        parsed.append((lbl[:22], val))

    if not parsed:
        return {
            "ok": False,
            "kind": "bar",
            "error": "No finite values for bar chart",
            "text": "[Bar chart unavailable: no finite values]",
            "width": eff_w,
            "charset": eff_charset,
            "no_color": eff_no_color,
        }

    max_abs = max(abs(v) for _, v in parsed)
    if math.isclose(max_abs, 0.0):
        max_abs = 1.0
    lbl_w = max(len(lbl) for lbl, _ in parsed)
    val_strs = [_fmt_num(v) + (f" {unit}" if unit else "") for _, v in parsed]
    val_w = max(len(vs) for vs in val_strs)
    bar_w = max(8, eff_w - lbl_w - val_w - 6)
    fill_ch = "█" if eff_charset in ("braille", "unicode") else "#"

    lines: list[str] = []
    if title:
        lines.append(title[:eff_w])
    for idx, ((lbl, val), vstr) in enumerate(zip(parsed, val_strs)):
        n_chars = max(0, min(bar_w, int(round((abs(val) / max_abs) * bar_w))))
        bar = _colorize(fill_ch * n_chars, idx, eff_no_color)
        sign_note = "-" if val < 0 else " "
        lines.append(f"{lbl:>{lbl_w}} |{sign_note}{bar:<{bar_w}} {vstr}")

    if value_label:
        lines.append(f"Metric: {value_label}" + (f" ({unit})" if unit else ""))

    return {
        "ok": True,
        "kind": "bar",
        "text": "\n".join(lines),
        "width": eff_w,
        "charset": eff_charset,
        "no_color": eff_no_color,
        "bars_count": len(parsed),
        "points_skipped": skipped,
    }


def render_histogram(
    values: Sequence[float],
    *,
    bins: int = 10,
    title: str = "Histogram",
    x_label: str = "value",
    unit: str = "",
    width: int | None = None,
    charset: str = "auto",
    no_color: bool | None = None,
) -> dict[str, Any]:
    """Bin numeric values into a horizontal terminal histogram."""
    clean = [float(v) for v in values if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(float(v))]
    if not clean:
        return {
            "ok": False,
            "kind": "histogram",
            "error": "No finite numeric values for histogram",
            "text": "[Histogram unavailable: no finite values]",
        }
    n_bins = max(1, min(25, int(bins)))
    lo, hi = min(clean), max(clean)
    if math.isclose(lo, hi):
        items = [(f"[{_fmt_num(lo)}]", float(len(clean)))]
    else:
        step = (hi - lo) / n_bins
        counts = [0] * n_bins
        for v in clean:
            idx = min(n_bins - 1, max(0, int((v - lo) / step)))
            counts[idx] += 1
        items = [
            (f"[{_fmt_num(lo + i * step)}, {_fmt_num(lo + (i + 1) * step)})", float(c))
            for i, c in enumerate(counts)
        ]
    res = render_bar_chart(
        items,
        title=title,
        value_label=f"count (n={len(clean)}, {x_label})",
        unit=unit,
        width=width,
        charset=charset,
        no_color=no_color,
    )
    res["kind"] = "histogram"
    res["sample_count"] = len(clean)
    res["bins"] = len(items)
    return res


def render_optimization_trace(
    expr_or_fn: str | Callable[[float], float],
    iterates: Sequence[tuple[float, float]],
    *,
    x_min: float | None = None,
    x_max: float | None = None,
    title: str = "Optimization Trace",
    x_label: str = "w",
    y_label: str = "L(w)",
    width: int | None = None,
    height: int | None = None,
    charset: str = "auto",
    no_color: bool | None = None,
) -> dict[str, Any]:
    """Plot a loss curve together with optimization iterate points."""
    fn = compile_safe_math_expr(expr_or_fn) if isinstance(expr_or_fn, str) else expr_or_fn
    valid_iters = [(float(w), float(l)) for w, l in iterates if math.isfinite(float(w)) and math.isfinite(float(l))]
    xs = [w for w, _ in valid_iters]
    lo = x_min if x_min is not None else (min(xs) - 1.0 if xs else -5.0)
    hi = x_max if x_max is not None else (max(xs) + 1.0 if xs else 5.0)
    if math.isclose(lo, hi):
        lo -= 1.0
        hi += 1.0

    eff_w, _, eff_charset, _ = _resolve_render_opts(width, height, charset, no_color)
    n_samples = max(30, min(300, eff_w * (2 if eff_charset == "braille" else 1)))
    curve_pts: list[tuple[float, float] | None] = []
    for i in range(n_samples):
        xv = lo + (hi - lo) * (i / max(1, n_samples - 1))
        yv = fn(xv)
        curve_pts.append((xv, yv) if math.isfinite(yv) else None)

    markers: list[dict[str, Any]] = []
    if valid_iters:
        markers.append({"x": valid_iters[0][0], "y": valid_iters[0][1], "label": "start", "char": "S"})
        if len(valid_iters) > 1:
            markers.append({"x": valid_iters[-1][0], "y": valid_iters[-1][1], "label": "current", "char": "*"})

    series = [
        {"name": "loss_curve", "points": curve_pts},
        {"name": "iterates", "points": valid_iters},
    ]
    res = render_xy_graph(
        series,
        kind="line",
        title=title,
        x_label=x_label,
        y_label=y_label,
        width=width,
        height=height,
        charset=charset,
        no_color=no_color,
        markers=markers,
    )
    res["kind"] = "optimization_trace"
    return res
