"""CLI subcommand handlers for vault-native Obsidian state isolation and read-only search."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .indexer import build_or_update_index, load_or_build_index, search_vault
from .models import (
    MODE_AUTO,
    MODE_STANDALONE,
    MODE_VAULT_NATIVE,
    detect_vault_mode,
    expand_path,
    load_config,
    resolve_state_dir,
    save_config,
)
from .state_store import list_vault_native_sessions


def _dump_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def _resolve_target_vault(raw_path: str | None) -> Path:
    if raw_path:
        p = expand_path(raw_path)
        if not p.is_dir():
            raise FileNotFoundError(f"Vault directory not found: {p}")
        return p
    cfg = load_config()
    obs = str(cfg.get("obsidian_vault", "")).strip()
    if obs:
        p = expand_path(obs)
        if p.is_dir():
            return p
    raise FileNotFoundError(
        "No Obsidian vault path provided and no obsidian_vault configured in ~/.teachme-config.json"
    )


def _opt_state_dir(vault: Path, args: argparse.Namespace) -> Path:
    raw = getattr(args, "state_dir", None)
    return resolve_state_dir(vault, explicit_state_dir=raw)


def cmd_connect(args: argparse.Namespace) -> int:
    """Connect an existing Obsidian vault for isolated learning state and read-only search."""
    vault = expand_path(args.vault_path)
    if not vault.is_dir():
        raise FileNotFoundError(f"Vault directory does not exist: {vault}")

    mode_info = detect_vault_mode(vault, explicit_mode=args.mode)
    updates: dict[str, Any] = {
        "obsidian_vault": str(vault),
        "mode": args.mode if args.mode != MODE_AUTO else mode_info["mode"],
    }
    if getattr(args, "state_dir", None):
        cfg = load_config()
        vmap = dict(cfg.get("vault_state_dirs", {}))
        vmap[str(vault)] = str(expand_path(args.state_dir))
        updates["vault_state_dirs"] = vmap

    cfg_path = save_config(updates)
    sdir = _opt_state_dir(vault, args)
    idx = build_or_update_index(vault, full=False, state_dir=sdir)
    sessions = list_vault_native_sessions(vault)

    print(
        _dump_json(
            {
                "ok": True,
                "config_file": str(cfg_path),
                "vault_path": str(vault),
                "detected_mode": mode_info,
                "active_mode": updates["mode"],
                "state_dir": str(sdir),
                "indexed_notes": idx.get("doc_count", 0),
                "sessions": sessions,
            }
        )
    )
    return 0


def cmd_mode(args: argparse.Namespace) -> int:
    """View or switch operating mode (auto | standalone | vault-native)."""
    cfg = load_config()
    if args.set_mode:
        cfg_path = save_config({"mode": args.set_mode})
        print(
            _dump_json(
                {
                    "ok": True,
                    "mode": args.set_mode,
                    "config_file": str(cfg_path),
                    "obsidian_vault": cfg.get("obsidian_vault", ""),
                    "notes_root": cfg.get("notes_root", ""),
                }
            )
        )
        return 0

    obs = str(cfg.get("obsidian_vault", "")).strip()
    target = expand_path(obs) if obs else None
    detected = detect_vault_mode(target, config=cfg)
    print(
        _dump_json(
            {
                "configured_mode": cfg.get("mode", MODE_AUTO),
                "effective_mode": detected["mode"],
                "reason": detected["reason"],
                "obsidian_vault": obs,
                "notes_root": cfg.get("notes_root", ""),
            }
        )
    )
    return 0


def cmd_reindex(args: argparse.Namespace) -> int:
    """Refresh the read-only vault search index incrementally or from scratch."""
    vault = _resolve_target_vault(args.vault_path)
    sdir = _opt_state_dir(vault, args)
    idx = build_or_update_index(vault, full=args.full, state_dir=sdir)
    print(
        _dump_json(
            {
                "ok": True,
                "vault_path": str(vault),
                "doc_count": idx.get("doc_count", 0),
                "stats": idx.get("stats", {}),
                "ambiguous_titles_count": len(idx.get("ambiguous_titles", {})),
            }
        )
    )
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    """Read-only search of existing vault notes as optional learning sources."""
    vault = _resolve_target_vault(args.vault_path)
    sdir = _opt_state_dir(vault, args)
    index = load_or_build_index(vault, refresh=False, state_dir=sdir)
    res = search_vault(
        vault,
        args.query,
        limit=args.limit,
        index=index,
    )
    print(_dump_json(res))
    return 0


def register_vault_native_subcommands(subparsers: Any) -> None:
    """Register vault-native state isolation and read-only search commands."""
    p_conn = subparsers.add_parser(
        "connect", help="Connect an existing Obsidian vault for isolated learning state and read-only search."
    )
    p_conn.add_argument("vault_path", help="Path to existing Obsidian vault.")
    p_conn.add_argument("--mode", choices=[MODE_AUTO, MODE_VAULT_NATIVE, MODE_STANDALONE], default=MODE_AUTO)
    p_conn.add_argument("--state-dir", default=None, help="Optional isolated TeachMe state directory.")
    p_conn.set_defaults(func=cmd_connect)

    p_mode = subparsers.add_parser("mode", help="View or switch operating mode.")
    p_mode.add_argument("set_mode", nargs="?", choices=[MODE_AUTO, MODE_STANDALONE, MODE_VAULT_NATIVE], default=None)
    p_mode.set_defaults(func=cmd_mode)

    p_reidx = subparsers.add_parser("reindex", help="Refresh read-only vault search index.")
    p_reidx.add_argument("vault_path", nargs="?", default=None, help="Path to Obsidian vault.")
    p_reidx.add_argument("--full", action="store_true", help="Rebuild index from scratch.")
    p_reidx.add_argument("--state-dir", default=None)
    p_reidx.set_defaults(func=cmd_reindex)

    p_search = subparsers.add_parser("search", help="Search existing vault notes read-only as learning sources.")
    p_search.add_argument("vault_path", nargs="?", default=None, help="Path to Obsidian vault.")
    p_search.add_argument("--query", required=True, help="Search query.")
    p_search.add_argument("--limit", type=int, default=8)
    p_search.add_argument("--state-dir", default=None)
    p_search.set_defaults(func=cmd_search)
