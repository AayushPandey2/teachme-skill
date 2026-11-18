"""Bounded, portable, terminal-native educational simulations for TeachMe.

Uses Python standard library only (no curses, no browser, no eval/exec).
Supports interactive TTY loops and deterministic non-interactive step-throughs.
"""

from __future__ import annotations

import math
import random
import re
import sys
from typing import Any, Callable, Mapping, TextIO

from .terminal_caps import detect_terminal_capabilities
from .terminal_graph import render_optimization_trace, render_xy_graph

MAX_STEPS_PER_RUN = 50
MAX_TOTAL_STEPS = 200
MAX_HISTORY_LEN = 120
MAX_INTERACTIVE_TURNS = 200
MAX_SORT_ITEMS = 20
MAX_PROB_BATCH = 500
MAX_PROB_TOTAL_TRIALS = 10000
MAX_C_STATEMENTS = 25


class BaseSimulation:
    """Base class for bounded, inspectable terminal teaching simulations."""

    template_name: str = "base"
    title: str = "Simulation"
    description: str = ""
    parameters_spec: dict[str, str] = {}

    def __init__(self, **params: Any) -> None:
        self.step_count: int = 0
        self.done: bool = False
        self.pending_prediction: str | None = None
        self.last_prediction_feedback: dict[str, Any] | None = None
        self.history: list[dict[str, Any]] = []
        self._init_params = dict(params)
        self.reset(**params)

    def reset(self, **params: Any) -> dict[str, Any]:
        self.step_count = 0
        self.done = False
        self.pending_prediction = None
        self.last_prediction_feedback = None
        self.history = []
        if params:
            self._init_params.update(params)
        self._reset_impl()
        return self.inspect_state()

    def _reset_impl(self) -> None:
        raise NotImplementedError

    def set_param(self, key: str, value: Any) -> dict[str, Any]:
        raise NotImplementedError

    def predict(self, prediction_text: str) -> dict[str, Any]:
        clean = str(prediction_text or "").strip()
        if not clean:
            raise ValueError("Prediction cannot be empty")
        self.pending_prediction = clean[:160]
        return {"ok": True, "recorded_prediction": self.pending_prediction}

    def step(self) -> dict[str, Any]:
        if self.done:
            return self.inspect_state()
        if self.step_count >= MAX_TOTAL_STEPS:
            self.done = True
            return self.inspect_state()
        self._step_impl()
        self.step_count += 1
        if self.step_count >= MAX_TOTAL_STEPS:
            self.done = True
        return self.inspect_state()

    def _step_impl(self) -> None:
        raise NotImplementedError

    def run(self, steps: int = 5) -> dict[str, Any]:
        n = max(1, min(MAX_STEPS_PER_RUN, int(steps)))
        for _ in range(n):
            if self.done or self.step_count >= MAX_TOTAL_STEPS:
                break
            self.step()
        return self.inspect_state()

    def inspect_state(self) -> dict[str, Any]:
        raise NotImplementedError

    def render(
        self,
        *,
        width: int | None = None,
        no_color: bool | None = None,
        charset: str = "auto",
    ) -> str:
        raise NotImplementedError

    def _base_state_dict(self) -> dict[str, Any]:
        return {
            "template": self.template_name,
            "title": self.title,
            "step_count": self.step_count,
            "done": self.done,
            "pending_prediction": self.pending_prediction,
            "last_prediction_feedback": self.last_prediction_feedback,
            "counts_as_independent_mastery": False,
        }


# ---------------------------------------------------------------------------
# 1. Gradient Descent Simulation
# ---------------------------------------------------------------------------

_GD_FUNCTIONS: dict[str, tuple[str, Callable[[float], float], Callable[[float], float], str]] = {
    "quadratic": ("x^2", lambda w: w * w, lambda w: 2.0 * w, "f(w) = w^2 (min at w=0, stable for 0 < lr < 1)"),
    "shifted_quadratic": (
        "(x - 3)^2 + 1",
        lambda w: (w - 3.0) ** 2 + 1.0,
        lambda w: 2.0 * (w - 3.0),
        "f(w) = (w - 3)^2 + 1 (min at w=3, stable for 0 < lr < 1)",
    ),
    "steep_quadratic": (
        "5 * x^2",
        lambda w: 5.0 * w * w,
        lambda w: 10.0 * w,
        "f(w) = 5w^2 (min at w=0, oscillates/diverges for lr >= 0.2)",
    ),
    "double_well": (
        "0.25 * x^4 - x^2 + 0.5 * x",
        lambda w: 0.25 * (w ** 4) - (w ** 2) + 0.5 * w,
        lambda w: (w ** 3) - 2.0 * w + 0.5,
        "f(w) = 0.25w^4 - w^2 + 0.5w (non-convex with two wells)",
    ),
}


class GradientDescentSimulation(BaseSimulation):
    template_name = "gradient_descent"
    title = "1D Gradient Descent Explorer"
    description = "Adjust learning rate (lr) and starting parameter (w0), predict the update, and observe convergence or divergence."
    parameters_spec = {
        "fn": "quadratic | shifted_quadratic | steep_quadratic | double_well",
        "lr": "float in [0.0001, 2.0]",
        "w0": "float in [-100.0, 100.0]",
        "tol": "float in [1e-6, 1.0]",
    }

    def _reset_impl(self) -> None:
        fn_name = str(self._init_params.get("fn") or "quadratic").strip().lower()
        if fn_name not in _GD_FUNCTIONS:
            raise ValueError(f"Unknown gradient descent function {fn_name!r}; expected {tuple(_GD_FUNCTIONS)}")
        lr = float(self._init_params.get("lr", 0.2))
        w0 = float(self._init_params.get("w0", 4.0))
        tol = float(self._init_params.get("tol", 1e-3))
        if not (1e-4 <= lr <= 2.0) or not math.isfinite(lr):
            raise ValueError("lr must be finite and within [0.0001, 2.0]")
        if not (-100.0 <= w0 <= 100.0) or not math.isfinite(w0):
            raise ValueError("w0 must be finite and within [-100.0, 100.0]")
        if not (1e-6 <= tol <= 1.0) or not math.isfinite(tol):
            raise ValueError("tol must be finite and within [1e-6, 1.0]")

        self.fn_name = fn_name
        self.lr = lr
        self.w0 = w0
        self.tol = tol
        self.w = w0
        _, f, g, _ = _GD_FUNCTIONS[self.fn_name]
        self.loss = f(self.w)
        self.grad = g(self.w)
        self.status = "running"
        self.history = [{"step": 0, "w": round(self.w, 6), "loss": round(self.loss, 6), "grad": round(self.grad, 6)}]

    def set_param(self, key: str, value: Any) -> dict[str, Any]:
        k = key.strip().lower()
        if k == "fn":
            val = str(value).strip().lower()
            if val not in _GD_FUNCTIONS:
                raise ValueError(f"Unknown fn {val!r}")
            self._init_params["fn"] = val
        elif k in ("lr", "eta"):
            val = float(value)
            if not (1e-4 <= val <= 2.0) or not math.isfinite(val):
                raise ValueError("lr must be within [0.0001, 2.0]")
            self._init_params["lr"] = val
        elif k in ("w0", "w"):
            val = float(value)
            if not (-100.0 <= val <= 100.0) or not math.isfinite(val):
                raise ValueError("w0 must be within [-100.0, 100.0]")
            self._init_params["w0"] = val
        elif k == "tol":
            val = float(value)
            if not (1e-6 <= val <= 1.0) or not math.isfinite(val):
                raise ValueError("tol must be within [1e-6, 1.0]")
            self._init_params["tol"] = val
        else:
            raise ValueError(f"Unsupported parameter {key!r} for gradient_descent")
        self.reset()
        return self.inspect_state()

    def _evaluate_prediction(self, pred: str, old_w: float, new_w: float, grad: float) -> dict[str, Any]:
        p = pred.strip().lower()
        delta = new_w - old_w
        actual_dir = "zero" if abs(delta) < 1e-9 else ("decrease" if delta < 0 else "increase")
        try:
            num = float(p)
            err = abs(num - new_w)
            ok = err <= max(0.05, 0.1 * abs(new_w))
            return {
                "predicted": pred,
                "observed_w": round(new_w, 4),
                "matched": ok,
                "explanation": (
                    f"Exact update: w_new = {old_w:.4g} - ({self.lr:.4g})*({grad:.4g}) = {new_w:.4g}."
                ),
            }
        except ValueError:
            pass

        alias_map = {
            "left": "decrease",
            "down": "decrease",
            "smaller": "decrease",
            "decrease": "decrease",
            "-": "decrease",
            "right": "increase",
            "up": "increase",
            "larger": "increase",
            "increase": "increase",
            "+": "increase",
            "stay": "zero",
            "same": "zero",
            "zero": "zero",
        }
        norm_p = alias_map.get(p, p)
        matched = norm_p == actual_dir
        sign_note = (
            "gradient is positive, so subtracting lr*grad moves w left (decreases)."
            if grad > 0
            else "gradient is negative, so subtracting lr*grad moves w right (increases)."
            if grad < 0
            else "gradient is zero, so w does not move."
        )
        return {
            "predicted": pred,
            "observed_direction": actual_dir,
            "observed_w": round(new_w, 4),
            "matched": matched,
            "explanation": f"At w={old_w:.4g}, {sign_note} New w={new_w:.4g}.",
        }

    def _step_impl(self) -> None:
        _, f, g, _ = _GD_FUNCTIONS[self.fn_name]
        old_w = self.w
        grad = g(old_w)
        try:
            new_w = old_w - self.lr * grad
            new_loss = f(new_w)
            new_grad = g(new_w)
        except OverflowError:
            new_w = math.inf
            new_loss = math.inf
            new_grad = math.nan

        if self.pending_prediction is not None:
            if math.isfinite(new_w):
                self.last_prediction_feedback = self._evaluate_prediction(self.pending_prediction, old_w, new_w, grad)
            else:
                self.last_prediction_feedback = {
                    "predicted": self.pending_prediction,
                    "matched": False,
                    "explanation": "Update overflowed/diverged due to large step size.",
                }
            self.pending_prediction = None

        if not (math.isfinite(new_w) and math.isfinite(new_loss)) or abs(new_w) > 1e6:
            self.status = "diverged"
            self.done = True
            return

        self.w = new_w
        self.loss = new_loss
        self.grad = new_grad
        if abs(self.grad) <= self.tol or abs(new_w - old_w) <= self.tol * 1e-2:
            self.status = "converged"
            self.done = True
        elif len(self.history) >= 2 and abs(self.loss) > abs(self.history[0]["loss"]) * 100.0 + 1e3:
            self.status = "diverged"
            self.done = True

        self.history.append(
            {
                "step": self.step_count + 1,
                "w": round(self.w, 6),
                "loss": round(self.loss, 6),
                "grad": round(self.grad, 6),
            }
        )
        if len(self.history) > MAX_HISTORY_LEN:
            self.history = self.history[-MAX_HISTORY_LEN:]

    def inspect_state(self) -> dict[str, Any]:
        out = self._base_state_dict()
        out.update(
            {
                "fn": self.fn_name,
                "fn_description": _GD_FUNCTIONS[self.fn_name][3],
                "lr": self.lr,
                "w0": self.w0,
                "w": round(self.w, 6),
                "loss": round(self.loss, 6),
                "grad": round(self.grad, 6),
                "status": self.status,
                "history": list(self.history[-15:]),
            }
        )
        return out

    def render(self, *, width: int | None = None, no_color: bool | None = None, charset: str = "auto") -> str:
        expr, _, _, desc = _GD_FUNCTIONS[self.fn_name]
        iterates = [(h["w"], h["loss"]) for h in self.history]
        graph = render_optimization_trace(
            expr,
            iterates,
            title=f"Gradient Descent: {desc} | lr={self.lr}",
            x_label="w",
            y_label="L(w)",
            width=width,
            height=12,
            charset=charset,
            no_color=no_color,
        )
        lines = [graph["text"]]
        lines.append(
            f"Step {self.step_count} | w = {self.w:.4g} | L(w) = {self.loss:.4g} | "
            f"grad = {self.grad:.4g} | status = {self.status}"
        )
        if self.last_prediction_feedback:
            fb = self.last_prediction_feedback
            tag = "MATCH" if fb.get("matched") else "MISMATCH"
            lines.append(f"Prediction [{tag}]: {fb.get('explanation', '')}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# 2. Sorting Algorithms Simulation
# ---------------------------------------------------------------------------


class SortingSimulation(BaseSimulation):
    template_name = "sorting"
    title = "Step-by-Step Sorting Visualizer"
    description = "Step through selection, bubble, or insertion sort and inspect comparisons, swaps, and array states."
    parameters_spec = {
        "algorithm": "selection | bubble | insertion",
        "array": "comma-separated ints/floats (2..20 items)",
    }

    def _reset_impl(self) -> None:
        alg = str(self._init_params.get("algorithm") or "selection").strip().lower()
        if alg not in ("selection", "bubble", "insertion"):
            raise ValueError(f"Unsupported sorting algorithm {alg!r}; expected selection|bubble|insertion")
        raw_arr = self._init_params.get("array", [5, 2, 8, 1, 4])
        if isinstance(raw_arr, str):
            raw_arr = [int(x.strip()) if re.fullmatch(r"-?\d+", x.strip()) else float(x.strip()) for x in raw_arr.split(",") if x.strip()]
        if not isinstance(raw_arr, (list, tuple)) or not (2 <= len(raw_arr) <= MAX_SORT_ITEMS):
            raise ValueError(f"array must contain between 2 and {MAX_SORT_ITEMS} numbers")
        arr = [int(x) if isinstance(x, int) and not isinstance(x, bool) else float(x) for x in raw_arr]
        if any(not math.isfinite(float(x)) for x in arr):
            raise ValueError("array values must be finite")

        self.algorithm = alg
        self.initial_array = list(arr)
        self.array = list(arr)
        self.comparisons = 0
        self.swaps = 0
        self.last_action = "initialized"
        self.active_indices: tuple[int, ...] = ()
        self._steps_gen = self._build_stepper()
        self.history = [{"step": 0, "array": list(self.array), "action": "initialized"}]

    def _build_stepper(self):
        arr = self.array
        n = len(arr)
        if self.algorithm == "selection":
            for i in range(n - 1):
                min_idx = i
                for j in range(i + 1, n):
                    self.comparisons += 1
                    self.active_indices = (min_idx, j)
                    if arr[j] < arr[min_idx]:
                        min_idx = j
                        self.last_action = f"compare arr[{j}] < arr[{self.active_indices[0]}]: new min at idx {min_idx}"
                    else:
                        self.last_action = f"compare arr[{j}] >= arr[{min_idx}]: keep min idx {min_idx}"
                    yield
                if min_idx != i:
                    arr[i], arr[min_idx] = arr[min_idx], arr[i]
                    self.swaps += 1
                    self.active_indices = (i, min_idx)
                    self.last_action = f"swap idx {i} and {min_idx}"
                    yield
        elif self.algorithm == "bubble":
            for i in range(n - 1):
                swapped = False
                for j in range(0, n - 1 - i):
                    self.comparisons += 1
                    self.active_indices = (j, j + 1)
                    if arr[j] > arr[j + 1]:
                        arr[j], arr[j + 1] = arr[j + 1], arr[j]
                        self.swaps += 1
                        swapped = True
                        self.last_action = f"compare & swap idx {j} and {j + 1}"
                    else:
                        self.last_action = f"compare idx {j} <= {j + 1}: no_swap"
                    yield
                if not swapped:
                    self.last_action = "early stop (pass made 0 swaps)"
                    break
        elif self.algorithm == "insertion":
            for i in range(1, n):
                j = i
                while j > 0:
                    self.comparisons += 1
                    self.active_indices = (j - 1, j)
                    if arr[j - 1] > arr[j]:
                        arr[j - 1], arr[j] = arr[j], arr[j - 1]
                        self.swaps += 1
                        self.last_action = f"shift/swap idx {j - 1} and {j}"
                        j -= 1
                        yield
                    else:
                        self.last_action = f"compare idx {j - 1} <= {j}: position found"
                        yield
                        break

    def set_param(self, key: str, value: Any) -> dict[str, Any]:
        k = key.strip().lower()
        if k in ("algorithm", "alg"):
            self._init_params["algorithm"] = str(value).strip().lower()
        elif k == "array":
            self._init_params["array"] = value
        else:
            raise ValueError(f"Unsupported parameter {key!r} for sorting")
        self.reset()
        return self.inspect_state()

    def _step_impl(self) -> None:
        try:
            next(self._steps_gen)
        except StopIteration:
            self.done = True
            self.active_indices = ()
            self.last_action = "sorted"

        if self.pending_prediction is not None:
            pred = self.pending_prediction.strip().lower()
            is_swap_act = "swap" in self.last_action and "no_swap" not in self.last_action
            matched = (
                ("swap" in pred and "no" not in pred and is_swap_act)
                or (("no_swap" in pred or "no swap" in pred or "keep" in pred) and not is_swap_act)
            )
            self.last_prediction_feedback = {
                "predicted": self.pending_prediction,
                "observed_action": self.last_action,
                "matched": matched,
                "explanation": f"Observed action: {self.last_action}. Array is now {self.array}.",
            }
            self.pending_prediction = None

        self.history.append({"step": self.step_count + 1, "array": list(self.array), "action": self.last_action})
        if len(self.history) > MAX_HISTORY_LEN:
            self.history = self.history[-MAX_HISTORY_LEN:]

    def inspect_state(self) -> dict[str, Any]:
        out = self._base_state_dict()
        out.update(
            {
                "algorithm": self.algorithm,
                "array": list(self.array),
                "comparisons": self.comparisons,
                "swaps": self.swaps,
                "active_indices": list(self.active_indices),
                "last_action": self.last_action,
            }
        )
        return out

    def render(self, *, width: int | None = None, no_color: bool | None = None, charset: str = "auto") -> str:
        caps = detect_terminal_capabilities()
        eff_charset = ("unicode" if caps["unicode_support"] else "ascii") if charset == "auto" else charset
        bar_ch = "█" if eff_charset in ("braille", "unicode") else "#"
        max_v = max(abs(float(x)) for x in self.array) or 1.0
        lines = [
            f"Sorting ({self.algorithm}) | step={self.step_count} | comparisons={self.comparisons} | swaps={self.swaps} | done={self.done}",
            f"Action: {self.last_action}",
        ]
        for idx, val in enumerate(self.array):
            mark = "*" if idx in self.active_indices else " "
            n_bars = max(1, int(round((abs(float(val)) / max_v) * 18))) if val != 0 else 0
            lines.append(f"{mark} [{idx:2d}] {val:>6} | {bar_ch * n_bars}")
        if self.last_prediction_feedback:
            fb = self.last_prediction_feedback
            tag = "MATCH" if fb.get("matched") else "MISMATCH"
            lines.append(f"Prediction [{tag}]: {fb.get('explanation', '')}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# 3. C Pointers Conceptual Trace Simulation
# ---------------------------------------------------------------------------

_C_SCENARIOS: dict[str, list[str]] = {
    "basic_deref": [
        "int x = 10;",
        "int *p = &x;",
        "*p = 25;",
    ],
    "pointer_reassignment": [
        "int a = 5;",
        "int b = 12;",
        "int *p = &a;",
        "*p = 7;",
        "p = &b;",
        "*p = 20;",
    ],
    "swap_via_pointers": [
        "int x = 3;",
        "int y = 9;",
        "int *px = &x;",
        "int *py = &y;",
        "int tmp = *px;",
        "*px = *py;",
        "*py = tmp;",
    ],
    "null_guard": [
        "int x = 4;",
        "int *p = NULL;",
        "*p = 99;",
    ],
}

_RE_DECL_INT = re.compile(r"^int\s+([a-zA-Z_]\w*)\s*=\s*(-?\d+)\s*;?$")
_RE_DECL_INT_DEREF = re.compile(r"^int\s+([a-zA-Z_]\w*)\s*=\s*\*([a-zA-Z_]\w*)\s*;?$")
_RE_DECL_PTR_ADDR = re.compile(r"^int\s*\*\s*([a-zA-Z_]\w*)\s*=\s*&([a-zA-Z_]\w*)\s*;?$")
_RE_DECL_PTR_NULL = re.compile(r"^int\s*\*\s*([a-zA-Z_]\w*)\s*=\s*NULL\s*;?$")
_RE_ASSIGN_PTR_ADDR = re.compile(r"^([a-zA-Z_]\w*)\s*=\s*&([a-zA-Z_]\w*)\s*;?$")
_RE_ASSIGN_PTR_NULL = re.compile(r"^([a-zA-Z_]\w*)\s*=\s*NULL\s*;?$")
_RE_DEREF_WRITE_LIT = re.compile(r"^\*([a-zA-Z_]\w*)\s*=\s*(-?\d+)\s*;?$")
_RE_DEREF_WRITE_DEREF = re.compile(r"^\*([a-zA-Z_]\w*)\s*=\s*\*([a-zA-Z_]\w*)\s*;?$")
_RE_DEREF_WRITE_VAR = re.compile(r"^\*([a-zA-Z_]\w*)\s*=\s*([a-zA-Z_]\w*)\s*;?$")


class CPointersSimulation(BaseSimulation):
    template_name = "c_pointers"
    title = "C Pointers Conceptual Variable/Address/Target Trace"
    description = (
        "Trace named variables, symbolic addresses, pointer targets, and dereferencing safely "
        "(conceptual model; not physical OS memory addresses)."
    )
    parameters_spec = {
        "scenario": "basic_deref | pointer_reassignment | swap_via_pointers | null_guard",
        "program": "optional semicolon-separated safe C pointer statements (max 25)",
    }

    def _reset_impl(self) -> None:
        custom_prog = self._init_params.get("program")
        if custom_prog:
            if isinstance(custom_prog, str):
                stmts = [s.strip() + ";" for s in custom_prog.split(";") if s.strip()]
            elif isinstance(custom_prog, list):
                stmts = [str(s).strip() for s in custom_prog if str(s).strip()]
            else:
                raise ValueError("program must be a string or list of statements")
            if not (1 <= len(stmts) <= MAX_C_STATEMENTS):
                raise ValueError(f"program must contain 1..{MAX_C_STATEMENTS} statements")
            self.scenario = "custom"
            self.statements = stmts
        else:
            scen = str(self._init_params.get("scenario") or "basic_deref").strip().lower()
            if scen not in _C_SCENARIOS:
                raise ValueError(f"Unknown scenario {scen!r}; expected {tuple(_C_SCENARIOS)}")
            self.scenario = scen
            self.statements = list(_C_SCENARIOS[scen])

        self.pc = 0
        self._next_addr = 0x1000
        # vars: name -> {"type": "int"|"int*", "addr": "0x1000", "value": int|None, "target": str|None}
        self.variables: dict[str, dict[str, Any]] = {}
        self.fault: str | None = None
        self.last_statement = ""
        self.history = []

    def _alloc_addr(self) -> str:
        addr = f"0x{self._next_addr:04x}"
        self._next_addr += 4
        return addr

    def set_param(self, key: str, value: Any) -> dict[str, Any]:
        k = key.strip().lower()
        if k == "scenario":
            self._init_params.pop("program", None)
            self._init_params["scenario"] = str(value).strip().lower()
        elif k == "program":
            self._init_params["program"] = value
        else:
            raise ValueError(f"Unsupported parameter {key!r} for c_pointers")
        self.reset()
        return self.inspect_state()

    def _exec_statement(self, stmt: str) -> None:
        s = stmt.strip()
        m = _RE_DECL_INT.match(s)
        if m:
            name, val = m.group(1), int(m.group(2))
            self.variables[name] = {"type": "int", "addr": self._alloc_addr(), "value": val, "target": None}
            return

        m = _RE_DECL_INT_DEREF.match(s)
        if m:
            name, ptr = m.group(1), m.group(2)
            val = self._deref_read(ptr)
            if self.fault is None:
                self.variables[name] = {"type": "int", "addr": self._alloc_addr(), "value": val, "target": None}
            return

        m = _RE_DECL_PTR_ADDR.match(s)
        if m:
            ptr, target = m.group(1), m.group(2)
            if target not in self.variables:
                self.fault = f"Undefined target variable {target!r}"
                return
            self.variables[ptr] = {
                "type": "int*",
                "addr": self._alloc_addr(),
                "value": self.variables[target]["addr"],
                "target": target,
            }
            return

        m = _RE_DECL_PTR_NULL.match(s)
        if m:
            ptr = m.group(1)
            self.variables[ptr] = {"type": "int*", "addr": self._alloc_addr(), "value": "NULL", "target": None}
            return

        m = _RE_ASSIGN_PTR_ADDR.match(s)
        if m:
            ptr, target = m.group(1), m.group(2)
            if ptr not in self.variables or self.variables[ptr]["type"] != "int*":
                self.fault = f"{ptr!r} is not a declared pointer"
                return
            if target not in self.variables:
                self.fault = f"Undefined target variable {target!r}"
                return
            self.variables[ptr]["target"] = target
            self.variables[ptr]["value"] = self.variables[target]["addr"]
            return

        m = _RE_ASSIGN_PTR_NULL.match(s)
        if m:
            ptr = m.group(1)
            if ptr not in self.variables or self.variables[ptr]["type"] != "int*":
                self.fault = f"{ptr!r} is not a declared pointer"
                return
            self.variables[ptr]["target"] = None
            self.variables[ptr]["value"] = "NULL"
            return

        m = _RE_DEREF_WRITE_LIT.match(s)
        if m:
            ptr, val = m.group(1), int(m.group(2))
            self._deref_write(ptr, val)
            return

        m = _RE_DEREF_WRITE_DEREF.match(s)
        if m:
            dst_ptr, src_ptr = m.group(1), m.group(2)
            val = self._deref_read(src_ptr)
            if self.fault is None and val is not None:
                self._deref_write(dst_ptr, val)
            return

        m = _RE_DEREF_WRITE_VAR.match(s)
        if m:
            ptr, var_name = m.group(1), m.group(2)
            if var_name not in self.variables or self.variables[var_name]["type"] != "int":
                self.fault = f"{var_name!r} is not an int variable"
                return
            self._deref_write(ptr, int(self.variables[var_name]["value"]))
            return

        self.fault = f"Unsupported statement syntax in bounded C pointer model: {s!r}"

    def _deref_read(self, ptr: str) -> int | None:
        info = self.variables.get(ptr)
        if not info or info["type"] != "int*":
            self.fault = f"{ptr!r} is not a declared pointer"
            return None
        target = info.get("target")
        if not target or target not in self.variables:
            self.fault = f"Null/uninitialized pointer dereference on *{ptr}"
            return None
        return int(self.variables[target]["value"])

    def _deref_write(self, ptr: str, val: int) -> None:
        info = self.variables.get(ptr)
        if not info or info["type"] != "int*":
            self.fault = f"{ptr!r} is not a declared pointer"
            return
        target = info.get("target")
        if not target or target not in self.variables:
            self.fault = f"Null/uninitialized pointer dereference on *{ptr} = {val}"
            return
        self.variables[target]["value"] = val

    def _step_impl(self) -> None:
        if self.pc >= len(self.statements):
            self.done = True
            return
        stmt = self.statements[self.pc]
        self.last_statement = stmt
        self.pc += 1
        self._exec_statement(stmt)
        if self.fault is not None or self.pc >= len(self.statements):
            self.done = True

        if self.pending_prediction is not None:
            pred = self.pending_prediction.strip().lower()
            matched = False
            if self.fault and ("null" in pred or "fault" in pred or "error" in pred or "crash" in pred):
                matched = True
            elif "=" in pred:
                vname, vval = [x.strip() for x in pred.split("=", 1)]
                if vname in self.variables and str(self.variables[vname]["value"]).lower() == vval:
                    matched = True
            else:
                for info in self.variables.values():
                    if str(info["value"]).lower() == pred:
                        matched = True
                        break
            obs = f"FAULT: {self.fault}" if self.fault else ", ".join(
                f"{k}={v['value']}" for k, v in self.variables.items()
            )
            self.last_prediction_feedback = {
                "predicted": self.pending_prediction,
                "observed": obs,
                "matched": matched,
                "explanation": f"After `{stmt}` -> {obs}.",
            }
            self.pending_prediction = None

        self.history.append({"step": self.step_count + 1, "stmt": stmt, "fault": self.fault})

    def inspect_state(self) -> dict[str, Any]:
        out = self._base_state_dict()
        out.update(
            {
                "conceptual_model_note": "Symbolic addresses only; does not represent physical OS RAM layout.",
                "scenario": self.scenario,
                "pc": self.pc,
                "total_statements": len(self.statements),
                "next_statement": self.statements[self.pc] if self.pc < len(self.statements) else None,
                "last_statement": self.last_statement,
                "variables": {k: dict(v) for k, v in self.variables.items()},
                "fault": self.fault,
            }
        )
        return out

    def render(self, *, width: int | None = None, no_color: bool | None = None, charset: str = "auto") -> str:
        caps = detect_terminal_capabilities()
        arrow = "──▶" if (charset != "ascii" and caps["unicode_support"]) else "-->"
        lines = [
            f"C Pointers Conceptual Trace ({self.scenario}) | step={self.step_count}/{len(self.statements)}",
            "Note: Symbolic addresses are pedagogical labels, not physical memory addresses.",
        ]
        if self.last_statement:
            lines.append(f"Executed: {self.last_statement}")
        if self.pc < len(self.statements) and not self.fault:
            lines.append(f"Next:     {self.statements[self.pc]}")
        lines.append("Name     | Type | SymAddr | Value / Target")
        lines.append("---------+------+---------+-----------------------")
        for name, info in self.variables.items():
            if info["type"] == "int*":
                tgt = info["target"]
                if tgt and tgt in self.variables:
                    desc = f"{info['value']} {arrow} {tgt} ({self.variables[tgt]['value']})"
                else:
                    desc = "NULL (no valid target)"
            else:
                desc = str(info["value"])
            lines.append(f"{name:<8} | {info['type']:<4} | {info['addr']}  | {desc}")
        if self.fault:
            lines.append(f"SAFETY FAULT: {self.fault}")
        if self.last_prediction_feedback:
            fb = self.last_prediction_feedback
            tag = "MATCH" if fb.get("matched") else "MISMATCH"
            lines.append(f"Prediction [{tag}]: {fb.get('explanation', '')}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# 4. Bernoulli Probability & Law of Large Numbers Simulation
# ---------------------------------------------------------------------------


class ProbabilitySimulation(BaseSimulation):
    template_name = "probability"
    title = "Bernoulli Trials & Empirical Frequency Convergence"
    description = "Explore repeated Bernoulli(p) trials and observe empirical frequency vs. sample size."
    parameters_spec = {
        "p": "float in [0.0, 1.0]",
        "batch_size": "int in [1, 500]",
        "seed": "int",
    }

    def _reset_impl(self) -> None:
        p = float(self._init_params.get("p", 0.5))
        batch = int(self._init_params.get("batch_size", 20))
        seed = int(self._init_params.get("seed", 42))
        if not (0.0 <= p <= 1.0) or not math.isfinite(p):
            raise ValueError("p must be finite and within [0.0, 1.0]")
        if not (1 <= batch <= MAX_PROB_BATCH):
            raise ValueError(f"batch_size must be within [1, {MAX_PROB_BATCH}]")

        self.p = p
        self.batch_size = batch
        self.seed = seed
        self._rng = random.Random(seed)
        self.total_trials = 0
        self.successes = 0
        self.empirical_freq = 0.0
        self.history = []

    def set_param(self, key: str, value: Any) -> dict[str, Any]:
        k = key.strip().lower()
        if k == "p":
            val = float(value)
            if not (0.0 <= val <= 1.0) or not math.isfinite(val):
                raise ValueError("p must be within [0.0, 1.0]")
            self._init_params["p"] = val
        elif k in ("batch_size", "batch", "n"):
            val = int(value)
            if not (1 <= val <= MAX_PROB_BATCH):
                raise ValueError(f"batch_size must be within [1, {MAX_PROB_BATCH}]")
            self._init_params["batch_size"] = val
        elif k == "seed":
            self._init_params["seed"] = int(value)
        else:
            raise ValueError(f"Unsupported parameter {key!r} for probability")
        self.reset()
        return self.inspect_state()

    def _step_impl(self) -> None:
        remaining = MAX_PROB_TOTAL_TRIALS - self.total_trials
        if remaining <= 0:
            self.done = True
            return
        n_batch = min(self.batch_size, remaining)
        batch_succ = sum(1 for _ in range(n_batch) if self._rng.random() < self.p)
        prev_err = abs(self.empirical_freq - self.p) if self.total_trials > 0 else None
        self.total_trials += n_batch
        self.successes += batch_succ
        self.empirical_freq = self.successes / self.total_trials
        cur_err = abs(self.empirical_freq - self.p)

        if self.total_trials >= MAX_PROB_TOTAL_TRIALS:
            self.done = True

        if self.pending_prediction is not None:
            pred = self.pending_prediction.strip().lower()
            matched = False
            try:
                num = float(pred)
                matched = abs(num - self.empirical_freq) <= 0.1
            except ValueError:
                if prev_err is not None and ("closer" in pred or "shrink" in pred or "converge" in pred):
                    matched = cur_err <= prev_err + 0.05
            self.last_prediction_feedback = {
                "predicted": self.pending_prediction,
                "observed_freq": round(self.empirical_freq, 4),
                "matched": matched,
                "explanation": (
                    f"After {self.total_trials} trials: {self.successes} successes, "
                    f"empirical p_hat = {self.empirical_freq:.4f} vs true p = {self.p:.4f}."
                ),
            }
            self.pending_prediction = None

        self.history.append(
            {
                "step": self.step_count + 1,
                "n": self.total_trials,
                "successes": self.successes,
                "empirical_freq": round(self.empirical_freq, 5),
                "abs_error": round(cur_err, 5),
            }
        )
        if len(self.history) > MAX_HISTORY_LEN:
            self.history = self.history[-MAX_HISTORY_LEN:]

    def inspect_state(self) -> dict[str, Any]:
        out = self._base_state_dict()
        out.update(
            {
                "p": self.p,
                "batch_size": self.batch_size,
                "seed": self.seed,
                "total_trials": self.total_trials,
                "successes": self.successes,
                "failures": self.total_trials - self.successes,
                "empirical_freq": round(self.empirical_freq, 5),
                "abs_error": round(abs(self.empirical_freq - self.p), 5) if self.total_trials else None,
                "history": list(self.history[-15:]),
            }
        )
        return out

    def render(self, *, width: int | None = None, no_color: bool | None = None, charset: str = "auto") -> str:
        if not self.history:
            return (
                f"Bernoulli Simulation (p={self.p}, batch_size={self.batch_size}, seed={self.seed}) | "
                "No trials run yet. Use `step` or `run <k>`."
            )
        pts_emp = [(float(h["n"]), float(h["empirical_freq"])) for h in self.history]
        pts_true = [(float(self.history[0]["n"]), self.p), (float(self.history[-1]["n"]), self.p)]
        graph = render_xy_graph(
            [
                {"name": "empirical_freq", "points": pts_emp},
                {"name": f"true_p={self.p}", "points": pts_true},
            ],
            kind="line",
            title=f"Empirical Frequency vs Sample Size (p={self.p})",
            x_label="n trials",
            y_label="p_hat",
            width=width,
            height=11,
            charset=charset,
            no_color=no_color,
        )
        err = abs(self.empirical_freq - self.p)
        lines = [
            graph["text"],
            f"Trials={self.total_trials} | Successes={self.successes} | p_hat={self.empirical_freq:.4f} | |p_hat - p|={err:.4f}",
        ]
        if self.last_prediction_feedback:
            fb = self.last_prediction_feedback
            tag = "MATCH" if fb.get("matched") else "MISMATCH"
            lines.append(f"Prediction [{tag}]: {fb.get('explanation', '')}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Registry & Execution Runners
# ---------------------------------------------------------------------------

SIMULATION_REGISTRY: dict[str, type[BaseSimulation]] = {
    "gradient_descent": GradientDescentSimulation,
    "sorting": SortingSimulation,
    "c_pointers": CPointersSimulation,
    "probability": ProbabilitySimulation,
}


def list_simulation_templates() -> list[dict[str, Any]]:
    return [
        {
            "name": name,
            "title": cls.title,
            "description": cls.description,
            "parameters": dict(cls.parameters_spec),
        }
        for name, cls in SIMULATION_REGISTRY.items()
    ]


def create_simulation(template: str, **params: Any) -> BaseSimulation:
    key = str(template or "").strip().lower()
    cls = SIMULATION_REGISTRY.get(key)
    if cls is None:
        raise ValueError(f"Unknown simulation template {template!r}; expected {tuple(SIMULATION_REGISTRY)}")
    return cls(**params)


def run_non_interactive_demo(
    template: str,
    *,
    steps: int = 5,
    params: Mapping[str, Any] | None = None,
    prediction: str | None = None,
    width: int | None = None,
    no_color: bool | None = None,
    charset: str = "auto",
) -> dict[str, Any]:
    """Run a deterministic bounded step-through demonstration without waiting for stdin."""
    sim = create_simulation(template, **(dict(params or {})))
    n_steps = max(1, min(MAX_STEPS_PER_RUN, int(steps)))
    snapshots: list[dict[str, Any]] = []
    if prediction:
        sim.predict(prediction)
    for _ in range(n_steps):
        if sim.done:
            break
        state = sim.step()
        snapshots.append(state)
    rendered = sim.render(width=width, no_color=no_color, charset=charset)
    return {
        "ok": True,
        "mode": "non_interactive_demo",
        "template": sim.template_name,
        "steps_executed": sim.step_count,
        "final_state": sim.inspect_state(),
        "snapshots": snapshots,
        "rendered": rendered,
        "counts_as_independent_mastery": False,
    }


def run_interactive_cli(
    template: str,
    *,
    params: Mapping[str, Any] | None = None,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
    terminal_caps: Mapping[str, Any] | None = None,
    force_non_interactive: bool = False,
    demo_steps: int = 5,
) -> dict[str, Any]:
    """Run an interactive simulation loop when TTY is interactive, else render deterministic demo safely."""
    out_stream = stdout or sys.stdout
    in_stream = stdin or sys.stdin
    caps = dict(terminal_caps) if terminal_caps is not None else detect_terminal_capabilities()

    if force_non_interactive or not caps.get("interactive", False):
        demo = run_non_interactive_demo(
            template,
            steps=demo_steps,
            params=params,
            width=caps.get("width"),
            no_color=caps.get("no_color"),
            charset="auto" if caps.get("unicode_support", True) else "ascii",
        )
        out_stream.write(demo["rendered"] + "\n")
        return demo

    sim = create_simulation(template, **(dict(params or {})))
    w = caps.get("width")
    nc = caps.get("no_color")
    cs = "auto" if caps.get("unicode_support", True) else "ascii"

    out_stream.write(f"=== {sim.title} ===\n")
    out_stream.write("Commands: show | step | run <n> | set <k> <v> | predict <val> | inspect | reset | help | quit\n")
    out_stream.write(sim.render(width=w, no_color=nc, charset=cs) + "\n")

    turns = 0
    while turns < MAX_INTERACTIVE_TURNS:
        turns += 1
        out_stream.write("sim> ")
        out_stream.flush()
        try:
            raw = in_stream.readline()
        except (EOFError, KeyboardInterrupt):
            break
        if not raw:
            break
        cmd_line = raw.strip()
        if not cmd_line:
            continue
        parts = cmd_line.split()
        cmd = parts[0].lower()
        try:
            if cmd in ("quit", "exit", "q"):
                break
            if cmd == "help":
                out_stream.write("Commands: show | step | run <n> | set <k> <v> | predict <val> | inspect | reset | quit\n")
            elif cmd in ("show", "state"):
                out_stream.write(sim.render(width=w, no_color=nc, charset=cs) + "\n")
            elif cmd in ("step", "next", "s"):
                sim.step()
                out_stream.write(sim.render(width=w, no_color=nc, charset=cs) + "\n")
            elif cmd == "run":
                cnt = int(parts[1]) if len(parts) > 1 else 5
                sim.run(cnt)
                out_stream.write(sim.render(width=w, no_color=nc, charset=cs) + "\n")
            elif cmd == "set" and len(parts) >= 3:
                sim.set_param(parts[1], " ".join(parts[2:]))
                out_stream.write(sim.render(width=w, no_color=nc, charset=cs) + "\n")
            elif cmd == "predict" and len(parts) >= 2:
                res = sim.predict(" ".join(parts[1:]))
                out_stream.write(f"Recorded prediction: {res['recorded_prediction']}\n")
            elif cmd == "inspect":
                out_stream.write(str(sim.inspect_state()) + "\n")
            elif cmd == "reset":
                sim.reset()
                out_stream.write(sim.render(width=w, no_color=nc, charset=cs) + "\n")
            else:
                out_stream.write(f"Unknown command: {cmd_line}. Type 'help'.\n")
        except Exception as exc:
            out_stream.write(f"Error: {exc}\n")

    return {
        "ok": True,
        "mode": "interactive",
        "template": sim.template_name,
        "steps_executed": sim.step_count,
        "final_state": sim.inspect_state(),
        "counts_as_independent_mastery": False,
    }
