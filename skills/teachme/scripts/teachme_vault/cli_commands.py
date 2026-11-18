"""CLI subcommand handlers for vault-native Obsidian state isolation, multi-vault registry, and source resolution."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from .indexer import (
    build_or_update_index,
    load_or_build_index,
    resolve_sources,
    retrieve_note_sections,
    search_vault,
)
from .models import (
    MODE_AUTO,
    MODE_STANDALONE,
    MODE_VAULT_NATIVE,
    detect_vault_mode,
    expand_path,
    get_active_vault_entry,
    get_registered_vaults,
    load_config,
    read_text_safe,
    register_vault,
    resolve_state_dir,
    save_config,
    select_active_vault,
    unregister_vault,
)
from .state_store import list_vault_native_sessions, resolve_session_dir


def _dump_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def _resolve_target_vault(raw_path: str | None, vault_ref: str | None = None) -> Path:
    cfg = load_config()
    if raw_path:
        entry = get_active_vault_entry(cfg, explicit_vault=raw_path)
        p = Path(entry["path"]) if entry else expand_path(raw_path)
        if not p.is_dir():
            raise FileNotFoundError(f"Vault directory not found: {p}")
        return p
    if vault_ref:
        entry = get_active_vault_entry(cfg, explicit_vault=vault_ref)
        if entry is None:
            raise FileNotFoundError(f"Vault '{vault_ref}' not found")
        p = Path(entry["path"])
        if not p.is_dir():
            raise FileNotFoundError(f"Vault directory not found: {p}")
        return p
    active = get_active_vault_entry(cfg)
    if active is not None:
        p = Path(active["path"])
        if p.is_dir():
            return p
        raise FileNotFoundError(f"Configured active Obsidian vault is inaccessible: {p}")
    raise FileNotFoundError(
        "No Obsidian vault path provided and no active vault configured in ~/.teachme-config.json"
    )


def _opt_state_dir(vault: Path, args: argparse.Namespace) -> Path:
    raw = getattr(args, "state_dir", None)
    return resolve_state_dir(vault, explicit_state_dir=raw)


def cmd_connect(args: argparse.Namespace) -> int:
    """Connect and register an existing Obsidian vault for isolated learning state and read-only search."""
    vault = expand_path(args.vault_path)
    if not vault.is_dir():
        raise FileNotFoundError(f"Vault directory does not exist: {vault}")

    mode_info = detect_vault_mode(vault, explicit_mode=args.mode)
    eff_mode = args.mode if args.mode != MODE_AUTO else mode_info["mode"]
    explicit_sd = expand_path(args.state_dir) if getattr(args, "state_dir", None) else None
    activate = not bool(getattr(args, "no_activate", False))

    reg = register_vault(
        vault,
        name=getattr(args, "name", None),
        state_dir=explicit_sd,
        activate=activate,
        mode=eff_mode,
    )
    sdir = _opt_state_dir(vault, args)
    idx = build_or_update_index(vault, full=False, state_dir=sdir)
    sessions = list_vault_native_sessions(vault)

    print(
        _dump_json(
            {
                "ok": True,
                "config_file": reg["config_file"],
                "vault_name": reg["vault"]["name"],
                "vault_path": str(vault),
                "active": reg["active"],
                "total_vaults": reg["total_vaults"],
                "detected_mode": mode_info,
                "active_mode": eff_mode,
                "state_dir": str(sdir),
                "indexed_notes": idx.get("doc_count", 0),
                "sessions": sessions,
            }
        )
    )
    return 0


def cmd_vaults(args: argparse.Namespace) -> int:
    """List registered Obsidian vaults, active selection, and accessibility status."""
    cfg = load_config()
    vaults = get_registered_vaults(cfg)
    active = get_active_vault_entry(cfg)
    active_name = active["name"] if active else ""

    items: list[dict[str, Any]] = []
    for name, entry in vaults.items():
        vp = Path(entry["path"])
        try:
            accessible = vp.is_dir()
            if accessible:
                os.listdir(vp)
        except OSError:
            accessible = False
        sdir = resolve_state_dir(vp, explicit_state_dir=entry.get("state_dir"), config=cfg)
        sessions = list_vault_native_sessions(vp, config=cfg) if accessible else []
        items.append(
            {
                "name": name,
                "path": str(vp),
                "active": name == active_name,
                "accessible": accessible,
                "state_dir": str(sdir),
                "has_index": (sdir / "index.json").is_file(),
                "sessions_count": len(sessions),
            }
        )

    print(
        _dump_json(
            {
                "ok": True,
                "active_vault": active_name,
                "obsidian_vault": cfg.get("obsidian_vault", ""),
                "vaults": items,
            }
        )
    )
    return 0


def cmd_use_vault(args: argparse.Namespace) -> int:
    """Switch active registered Obsidian vault by name or path."""
    res = select_active_vault(args.vault_ref)
    vp = Path(res["obsidian_vault"])
    try:
        accessible = vp.is_dir()
        if accessible:
            os.listdir(vp)
    except OSError:
        accessible = False
    print(
        _dump_json(
            {
                "ok": True,
                "config_file": res["config_file"],
                "active_vault": res["active_vault"],
                "obsidian_vault": res["obsidian_vault"],
                "accessible": accessible,
            }
        )
    )
    return 0


def cmd_remove_vault(args: argparse.Namespace) -> int:
    """Unregister a vault from TeachMe config without modifying any files on disk."""
    res = unregister_vault(args.vault_ref)
    print(
        _dump_json(
            {
                "ok": True,
                "config_file": res["config_file"],
                "removed": res["removed"],
                "was_active": res["was_active"],
                "remaining_vaults": res["remaining_vaults"],
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
                    "active_vault": cfg.get("active_vault", ""),
                    "obsidian_vault": cfg.get("obsidian_vault", ""),
                    "notes_root": cfg.get("notes_root", ""),
                }
            )
        )
        return 0

    active = get_active_vault_entry(cfg)
    obs = active["path"] if active else str(cfg.get("obsidian_vault", "")).strip()
    target = expand_path(obs) if obs else None
    detected = detect_vault_mode(target, config=cfg)
    print(
        _dump_json(
            {
                "configured_mode": cfg.get("mode", MODE_AUTO),
                "effective_mode": detected["mode"],
                "reason": detected["reason"],
                "active_vault": active["name"] if active else "",
                "obsidian_vault": obs,
                "notes_root": cfg.get("notes_root", ""),
            }
        )
    )
    return 0


def cmd_reindex(args: argparse.Namespace) -> int:
    """Refresh the read-only vault search index incrementally or from scratch."""
    vault = _resolve_target_vault(args.vault_path, getattr(args, "vault", None))
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
    vault = _resolve_target_vault(args.vault_path, getattr(args, "vault", None))
    sdir = _opt_state_dir(vault, args)
    index = load_or_build_index(vault, refresh=False, state_dir=sdir)
    res = search_vault(
        vault,
        args.query,
        limit=args.limit,
        index=index,
    )
    if getattr(args, "sections", False):
        for item in res.get("results", []):
            try:
                sec_data = retrieve_note_sections(vault, item["rel_path"], query=args.query, max_sections=2, max_section_chars=900)
                item["matched_sections"] = sec_data["sections"]
            except FileNotFoundError:
                item["matched_sections"] = []
    print(_dump_json(res))
    return 0


def cmd_resolve_sources(args: argparse.Namespace) -> int:
    """Deterministically resolve permitted sources into vault, hybrid, or web teaching mode."""
    objectives: list[Any] = list(getattr(args, "objective", None) or [])
    obj_file = getattr(args, "objectives_file", None)
    if obj_file:
        p = expand_path(obj_file)
        if not p.is_file():
            raise FileNotFoundError(f"Objectives JSON not found: {p}")
        data = json.loads(read_text_safe(p))
        if isinstance(data, dict) and isinstance(data.get("objectives"), list):
            data = data["objectives"]
        if isinstance(data, list):
            objectives.extend(data)

    sess_dir: Path | None = None
    sess_slug = getattr(args, "session", None)
    if sess_slug:
        try:
            sess_dir = resolve_session_dir(None, session_slug=sess_slug)
        except FileNotFoundError:
            sess_dir = None

    explicit_sd = expand_path(args.state_dir) if getattr(args, "state_dir", None) else None
    result = resolve_sources(
        args.topic,
        vault_path=args.vault_path,
        vault_ref=getattr(args, "vault", None),
        objectives=objectives or None,
        session_dir=sess_dir,
        state_dir=explicit_sd,
        web_available=not bool(getattr(args, "no_web", False)),
        max_notes=args.max_notes,
        max_sections_per_note=args.max_sections,
        max_total_chars=args.max_chars,
    )
    print(_dump_json(result))
    return 0


def register_vault_native_subcommands(subparsers: Any) -> None:
    """Register vault-native state isolation, multi-vault registry, and source-resolution commands."""
    p_conn = subparsers.add_parser(
        "connect", help="Connect and register an existing Obsidian vault for isolated learning state and read-only search."
    )
    p_conn.add_argument("vault_path", help="Path to existing Obsidian vault.")
    p_conn.add_argument("--name", default=None, help="Optional friendly alias for this vault.")
    p_conn.add_argument("--mode", choices=[MODE_AUTO, MODE_VAULT_NATIVE, MODE_STANDALONE], default=MODE_AUTO)
    p_conn.add_argument("--state-dir", default=None, help="Optional isolated TeachMe state directory.")
    p_conn.add_argument("--no-activate", action="store_true", help="Register vault without switching active selection.")
    p_conn.set_defaults(func=cmd_connect)

    p_vaults = subparsers.add_parser("vaults", help="List registered Obsidian vaults and active selection.")
    p_vaults.set_defaults(func=cmd_vaults)

    p_use = subparsers.add_parser("use-vault", help="Select the active Obsidian vault by name or path.")
    p_use.add_argument("vault_ref", help="Registered vault name or path.")
    p_use.set_defaults(func=cmd_use_vault)

    p_rm = subparsers.add_parser("remove-vault", help="Unregister a vault from TeachMe config without deleting any files.")
    p_rm.add_argument("vault_ref", help="Registered vault name or path.")
    p_rm.set_defaults(func=cmd_remove_vault)

    p_mode = subparsers.add_parser("mode", help="View or switch operating mode.")
    p_mode.add_argument("set_mode", nargs="?", choices=[MODE_AUTO, MODE_STANDALONE, MODE_VAULT_NATIVE], default=None)
    p_mode.set_defaults(func=cmd_mode)

    p_reidx = subparsers.add_parser("reindex", help="Refresh read-only vault search index.")
    p_reidx.add_argument("vault_path", nargs="?", default=None, help="Path to Obsidian vault.")
    p_reidx.add_argument("--vault", default=None, help="Registered vault name or path.")
    p_reidx.add_argument("--full", action="store_true", help="Rebuild index from scratch.")
    p_reidx.add_argument("--state-dir", default=None)
    p_reidx.set_defaults(func=cmd_reindex)

    p_search = subparsers.add_parser("search", help="Search existing vault notes read-only as learning sources.")
    p_search.add_argument("vault_path", nargs="?", default=None, help="Path to Obsidian vault.")
    p_search.add_argument("--vault", default=None, help="Registered vault name or path.")
    p_search.add_argument("--query", required=True, help="Search query.")
    p_search.add_argument("--limit", type=int, default=8)
    p_search.add_argument("--state-dir", default=None)
    p_search.add_argument("--sections", action="store_true", help="Include bounded matched sections.")
    p_search.set_defaults(func=cmd_search)

    p_res = subparsers.add_parser(
        "resolve-sources",
        help="Resolve permitted sources into vault, hybrid, or web mode with bounded sections and provenance.",
    )
    p_res.add_argument("vault_path", nargs="?", default=None, help="Optional explicit Obsidian vault path or name.")
    p_res.add_argument("--topic", required=True, help="Requested topic or query.")
    p_res.add_argument("--vault", default=None, help="Registered vault name or path.")
    p_res.add_argument("--session", default=None, help="Optional session slug to load objectives from.")
    p_res.add_argument("--objective", action="append", default=None, help="Learning objective to verify coverage (repeatable).")
    p_res.add_argument("--objectives-file", default=None, help="Optional JSON file listing learning objectives.")
    p_res.add_argument("--state-dir", default=None, help="Optional isolated state directory for vault index.")
    web_grp = p_res.add_mutually_exclusive_group()
    web_grp.add_argument("--web-available", action="store_true", default=True, help="Host agent has web/browsing tools (default).")
    web_grp.add_argument("--no-web", action="store_true", default=False, help="Host agent has no web/browsing tools.")
    p_res.add_argument("--max-notes", type=int, default=5, help="Max primary matched vault notes.")
    p_res.add_argument("--max-sections", type=int, default=4, help="Max matched sections per note.")
    p_res.add_argument("--max-chars", type=int, default=10000, help="Total character budget for retrieved sections.")
    p_res.set_defaults(func=cmd_resolve_sources)
