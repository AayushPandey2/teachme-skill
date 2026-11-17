"""Configuration, operating mode detection, and filesystem safety utilities."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any, Iterator

MODE_AUTO = "auto"
MODE_STANDALONE = "standalone"
MODE_VAULT_NATIVE = "vault-native"
VALID_MODES = {MODE_AUTO, MODE_STANDALONE, MODE_VAULT_NATIVE}

DEFAULT_IGNORED_DIRS = frozenset(
    {
        ".obsidian",
        ".git",
        ".hg",
        ".svn",
        ".trash",
        ".teachme",
        "node_modules",
        ".venv",
        "__pycache__",
        ".makemd",
        ".space",
    }
)

SENSITIVE_KEY_RE = re.compile(
    r"(?:token|secret|api[_-]?key|password|passwd|auth|credential|private[_-]?key|bearer)",
    re.IGNORECASE,
)


def utc_now_iso() -> str:
    """Return current UTC timestamp in ISO-8601 format."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def today_iso() -> str:
    """Return current UTC date in YYYY-MM-DD format."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def config_path() -> Path:
    """Return path to ~/.teachme-config.json (or TEACHME_CONFIG_PATH override)."""
    env_cfg = os.environ.get("TEACHME_CONFIG_PATH", "").strip()
    if env_cfg:
        return Path(os.path.expandvars(env_cfg)).expanduser()
    return Path.home() / ".teachme-config.json"


def load_config(cfg_file: Path | None = None) -> dict[str, Any]:
    """Load ~/.teachme-config.json safely, returning an empty dict on failure."""
    path = cfg_file or config_path()
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_config(updates: dict[str, Any], cfg_file: Path | None = None) -> Path:
    """Merge updates into ~/.teachme-config.json atomically."""
    path = cfg_file or config_path()
    current = load_config(path)
    current.update(updates)
    current["updated_at"] = today_iso()
    atomic_write_text(path, json.dumps(current, indent=2, ensure_ascii=False) + "\n")
    return path


def expand_path(raw_path: str) -> Path:
    """Expand environment variables and ~ without requiring target existence."""
    return Path(os.path.expandvars(raw_path)).expanduser().resolve()


def is_within_root(candidate: Path, root: Path) -> bool:
    """Return True iff candidate resolves inside root (prevents symlink escape)."""
    try:
        resolved_root = root.resolve()
        resolved_cand = candidate.resolve()
        resolved_cand.relative_to(resolved_root)
        return True
    except (OSError, ValueError):
        return False


def read_text_safe(path: Path, max_bytes: int | None = None) -> str:
    """Read UTF-8 text safely with optional byte cap for large files."""
    if max_bytes is None:
        return path.read_text(encoding="utf-8-sig", errors="replace")
    with path.open("rb") as fh:
        raw = fh.read(max_bytes)
    text = raw.decode("utf-8", errors="replace")
    return text.lstrip("\ufeff")


def atomic_write_text(path: Path, content: str) -> None:
    """Write UTF-8 text atomically via a temporary file in the target directory."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=".teachme-tmp-", suffix=".tmp", dir=str(path.parent)
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(content)
        os.replace(str(tmp_path), str(path))
    except Exception:
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except OSError:
            pass
        raise


def sha256_text(text: str) -> str:
    """Return short SHA-256 hex digest of UTF-8 text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def redact_sensitive(obj: Any) -> Any:
    """Recursively redact sensitive keys in plugin configurations."""
    if isinstance(obj, dict):
        cleaned: dict[str, Any] = {}
        for k, v in obj.items():
            key_str = str(k)
            if SENSITIVE_KEY_RE.search(key_str) and isinstance(v, (str, int, float)):
                cleaned[key_str] = "<redacted>" if str(v).strip() else ""
            else:
                cleaned[key_str] = redact_sensitive(v)
        return cleaned
    if isinstance(obj, list):
        return [redact_sensitive(item) for item in obj]
    return obj


def _compile_user_ignore_filters(vault_root: Path) -> list[re.Pattern[str]]:
    """Read Obsidian userIgnoreFilters from .obsidian/app.json if present."""
    app_json = vault_root / ".obsidian" / "app.json"
    if not app_json.is_file() or not is_within_root(app_json, vault_root):
        return []
    try:
        data = json.loads(read_text_safe(app_json))
    except (OSError, json.JSONDecodeError):
        return []
    raw_filters = data.get("userIgnoreFilters", [])
    if not isinstance(raw_filters, list):
        return []
    patterns: list[re.Pattern[str]] = []
    for item in raw_filters:
        pat = str(item).strip()
        if not pat:
            continue
        # Obsidian treats /.../ as regex or plain prefix/substring
        if len(pat) >= 2 and pat.startswith("/") and pat.endswith("/"):
            try:
                patterns.append(re.compile(pat[1:-1]))
            except re.error:
                continue
        else:
            patterns.append(re.compile(re.escape(pat)))
    return patterns


def is_ignored_relpath(
    rel_posix: str,
    ignored_dirs: frozenset[str] | set[str],
    user_filters: list[re.Pattern[str]] | None = None,
) -> bool:
    """Return True if any path segment is ignored or matches Obsidian ignore filters."""
    parts = rel_posix.split("/")
    if any(part in ignored_dirs for part in parts[:-1]):
        return True
    if parts[-1] in ignored_dirs:
        return True
    if user_filters:
        for pat in user_filters:
            if pat.search(rel_posix):
                return True
    return False


def safe_iter_files(
    vault_root: Path,
    extensions: tuple[str, ...] = (".md",),
    ignored_dirs: frozenset[str] | set[str] = DEFAULT_IGNORED_DIRS,
    respect_obsidian_ignores: bool = True,
) -> Iterator[Path]:
    """Yield files inside vault_root without following symlinks outside the vault."""
    root = vault_root.resolve()
    if not root.is_dir():
        return
    user_filters = _compile_user_ignore_filters(root) if respect_obsidian_ignores else []
    ext_lower = tuple(e.lower() for e in extensions)
    visited_dirs: set[Path] = set()

    for dirpath, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
        current_dir = Path(dirpath)
        try:
            resolved_dir = current_dir.resolve()
        except OSError:
            dirnames[:] = []
            continue
        if not is_within_root(resolved_dir, root) or resolved_dir in visited_dirs:
            dirnames[:] = []
            continue
        visited_dirs.add(resolved_dir)

        kept_dirs: list[str] = []
        for d in sorted(dirnames):
            if d in ignored_dirs or d.startswith(".teachme"):
                continue
            cand_dir = current_dir / d
            if cand_dir.is_symlink() and not is_within_root(cand_dir, root):
                continue
            rel_d = cand_dir.relative_to(root).as_posix()
            if user_filters and any(pat.search(rel_d + "/") or pat.search(rel_d) for pat in user_filters):
                continue
            kept_dirs.append(d)
        dirnames[:] = kept_dirs

        for fname in sorted(filenames):
            if ext_lower and not fname.lower().endswith(ext_lower):
                continue
            fpath = current_dir / fname
            if fpath.is_symlink() and not is_within_root(fpath, root):
                continue
            if not is_within_root(fpath, root):
                continue
            rel_f = fpath.relative_to(root).as_posix()
            if is_ignored_relpath(rel_f, ignored_dirs, user_filters):
                continue
            yield fpath


def resolve_state_dir(
    vault_path: Path,
    explicit_state_dir: str | Path | None = None,
    config: dict[str, Any] | None = None,
) -> Path:
    """Resolve isolated TeachMe state directory for a vault-native Obsidian vault.

    Defaults to <vault_path>/.teachme, or <state_root>/<vault-slug>-<hash> if
    configured in ~/.teachme-config.json or --state-dir.
    """
    if explicit_state_dir:
        return Path(os.path.expandvars(str(explicit_state_dir))).expanduser().resolve()

    cfg = config if config is not None else load_config()
    vault_map = cfg.get("vault_state_dirs", {})
    vault_key = str(vault_path.resolve())
    if isinstance(vault_map, dict) and vault_key in vault_map:
        return expand_path(str(vault_map[vault_key]))

    state_root = str(cfg.get("state_root", "")).strip()
    if state_root:
        slug = re.sub(r"[^a-z0-9-]+", "-", vault_path.name.lower()).strip("-") or "vault"
        digest = hashlib.sha256(vault_key.encode("utf-8")).hexdigest()[:10]
        return expand_path(state_root) / f"{slug}-{digest}"

    return vault_path.resolve() / ".teachme"


def detect_vault_mode(
    target_path: Path | None,
    explicit_mode: str | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Detect whether a target directory is standalone TeachMe or vault-native Obsidian."""
    cfg = config if config is not None else load_config()
    requested = (explicit_mode or "").strip().lower()
    if requested in (MODE_STANDALONE, MODE_VAULT_NATIVE):
        return {
            "mode": requested,
            "reason": "explicit_argument",
            "has_obsidian": bool(target_path and (target_path / ".obsidian").is_dir()),
            "has_teachme_state": bool(target_path and (target_path / "00-SESSION-STATE.md").is_file()),
        }

    if target_path is None:
        cfg_mode = str(cfg.get("mode", MODE_AUTO)).strip().lower()
        if cfg_mode in (MODE_STANDALONE, MODE_VAULT_NATIVE):
            return {
                "mode": cfg_mode,
                "reason": "config_default",
                "has_obsidian": False,
                "has_teachme_state": False,
            }
        if cfg.get("obsidian_vault"):
            return {
                "mode": MODE_VAULT_NATIVE,
                "reason": "configured_obsidian_vault",
                "has_obsidian": True,
                "has_teachme_state": False,
            }
        return {
            "mode": MODE_STANDALONE,
            "reason": "legacy_default",
            "has_obsidian": False,
            "has_teachme_state": False,
        }

    has_obsidian = (target_path / ".obsidian").is_dir()
    has_teachme_state = (target_path / "00-SESSION-STATE.md").is_file() or (
        target_path / "00-GRAPH.json"
    ).is_file()
    has_teachme_dirs = (
        (target_path / "topics").is_dir()
        or (target_path / "00-MOC-INDEX.md").is_file()
        or (target_path / "learning-records").is_dir()
        or (target_path / "scratchpad").is_dir()
    )
    has_vault_profile = (target_path / ".teachme" / "profile.json").is_file() or (
        target_path / ".teachme" / "index.json"
    ).is_file() or (target_path / ".teachme" / "sessions").is_dir()

    if has_obsidian:
        return {
            "mode": MODE_VAULT_NATIVE,
            "reason": "obsidian_config_detected",
            "has_obsidian": True,
            "has_teachme_state": has_teachme_state,
        }

    if has_vault_profile and not has_teachme_state:
        return {
            "mode": MODE_VAULT_NATIVE,
            "reason": "teachme_vault_profile_detected",
            "has_obsidian": False,
            "has_teachme_state": False,
        }

    if has_teachme_state and (has_teachme_dirs or not has_obsidian):
        return {
            "mode": MODE_STANDALONE,
            "reason": "standalone_teachme_layout_detected",
            "has_obsidian": False,
            "has_teachme_state": True,
        }

    cfg_mode = str(cfg.get("mode", MODE_AUTO)).strip().lower()
    if cfg_mode in (MODE_STANDALONE, MODE_VAULT_NATIVE):
        return {
            "mode": cfg_mode,
            "reason": "config_default",
            "has_obsidian": False,
            "has_teachme_state": has_teachme_state,
        }

    # Safe fallback: if the directory already contains arbitrary user markdown notes
    # without TeachMe scaffolding, treat it as vault-native so legacy fix/verify
    # never touch user notes.
    if target_path.is_dir():
        for p in safe_iter_files(target_path, extensions=(".md",)):
            return {
                "mode": MODE_VAULT_NATIVE,
                "reason": "existing_non_teachme_markdown_detected",
                "has_obsidian": False,
                "has_teachme_state": has_teachme_state,
            }

    return {
        "mode": MODE_STANDALONE,
        "reason": "empty_or_new_target_default",
        "has_obsidian": False,
        "has_teachme_state": has_teachme_state,
    }
