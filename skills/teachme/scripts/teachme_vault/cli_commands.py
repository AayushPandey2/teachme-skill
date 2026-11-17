"""CLI subcommand handlers for vault-native Obsidian integration."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

from .discovery import discover_vault, load_or_discover_profile, summarize_profile_for_display
from .indexer import build_or_update_index, load_or_build_index, search_vault
from .models import (
    MODE_AUTO,
    MODE_STANDALONE,
    MODE_VAULT_NATIVE,
    detect_vault_mode,
    expand_path,
    load_config,
    read_text_safe,
    resolve_state_dir,
    save_config,
)
from .planner import plan_note
from .writer import audit_vault_native, generate_vault_note


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


def _load_optional_json(raw_path: str | None) -> dict[str, Any] | None:
    if not raw_path:
        return None
    p = expand_path(raw_path)
    data = json.loads(read_text_safe(p))
    return data if isinstance(data, dict) else None


def cmd_connect(args: argparse.Namespace) -> int:
    """Connect an existing Obsidian vault and persist active vault/mode configuration."""
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
    profile = discover_vault(vault, refresh=False, state_dir=sdir)
    build_or_update_index(vault, full=False, state_dir=sdir)

    print(
        _dump_json(
            {
                "ok": True,
                "config_file": str(cfg_path),
                "vault_path": str(vault),
                "detected_mode": mode_info,
                "active_mode": updates["mode"],
                "state_dir": str(sdir),
                "total_notes": profile.get("total_notes", 0),
                "organization_pattern": profile.get("organization_pattern", {}),
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


def cmd_discover(args: argparse.Namespace) -> int:
    """Inspect and profile an Obsidian vault, persisting profile.json."""
    vault = _resolve_target_vault(args.vault_path)
    sdir = _opt_state_dir(vault, args)
    profile = discover_vault(vault, refresh=args.refresh, state_dir=sdir)
    print(_dump_json(summarize_profile_for_display(profile)))
    return 0


def cmd_profile(args: argparse.Namespace) -> int:
    """Display the persisted or freshly inferred vault profile."""
    vault = _resolve_target_vault(args.vault_path)
    sdir = _opt_state_dir(vault, args)
    profile = load_or_discover_profile(vault, refresh=False, state_dir=sdir)
    print(_dump_json(summarize_profile_for_display(profile)))
    return 0


def cmd_reindex(args: argparse.Namespace) -> int:
    """Refresh the vault knowledge index incrementally or from scratch."""
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
    """Retrieve ranked relevant existing notes for a query."""
    vault = _resolve_target_vault(args.vault_path)
    sdir = _opt_state_dir(vault, args)
    profile = load_or_discover_profile(vault, refresh=False, state_dir=sdir)
    index = load_or_build_index(vault, refresh=False, state_dir=sdir)
    res = search_vault(
        vault,
        args.query,
        limit=args.limit,
        index=index,
        exclude_roles={"templates", "attachments", "archive", "protected_assets"},
        profile=profile,
    )
    print(_dump_json(res))
    return 0


def _compact_plan_for_cli(plan: dict[str, Any]) -> dict[str, Any]:
    """Strip full file bodies from CLI stdout while preserving diffs, hashes, and decisions."""
    out = dict(plan)
    out["affected_files"] = [
        {k: v for k, v in af.items() if k != "new_text"}
        for af in plan.get("affected_files", [])
    ]
    return out


def cmd_plan(args: argparse.Namespace) -> int:
    """Preview placement, template, tags, MOC, Mermaid, and exact affected file edits."""
    vault = _resolve_target_vault(args.vault_path)
    sdir = _opt_state_dir(vault, args)
    keywords = [k.strip() for k in (args.keywords or "").split(",") if k.strip()]
    content_payload = _load_optional_json(getattr(args, "content_json", None))
    proposal_payload = _load_optional_json(getattr(args, "proposal_json", None))
    try:
        plan = plan_note(
            vault_root=vault,
            topic=args.topic,
            explicit_folder=args.folder,
            explicit_template=args.template,
            keywords=keywords or None,
            refresh=args.refresh,
            state_dir=sdir,
            content=content_payload,
            proposal=proposal_payload,
            extend_rel_path=getattr(args, "extend", None),
            mermaid_mode=getattr(args, "mermaid", "auto"),
            mindmap_supported=not bool(getattr(args, "no_mindmap", False)),
            min_moc_cluster_size=getattr(args, "min_moc_cluster_size", None),
            allow_moc=not bool(getattr(args, "no_moc", False)),
            save_plan=not bool(getattr(args, "no_save_plan", False)),
        )
    except (ValueError, RuntimeError, FileNotFoundError) as exc:
        print(_dump_json({"ok": False, "error": str(exc)}), file=sys.stderr)
        return 1

    print(_dump_json(_compact_plan_for_cli(plan)))
    return 0


def cmd_generate(args: argparse.Namespace) -> int:
    """Generate or non-destructively extend vault-native notes + MOCs + Mermaid (dry-run default)."""
    vault = _resolve_target_vault(args.vault_path)
    sdir = _opt_state_dir(vault, args)
    content_payload = _load_optional_json(getattr(args, "content_json", None))
    proposal_payload = _load_optional_json(getattr(args, "proposal_json", None))
    keywords = [k.strip() for k in (getattr(args, "keywords", "") or "").split(",") if k.strip()]

    apply_write = bool(args.apply) and not bool(args.dry_run)
    try:
        res = generate_vault_note(
            vault_root=vault,
            topic=args.topic or "",
            apply=apply_write,
            explicit_folder=args.folder,
            explicit_template=args.template,
            extend_rel_path=args.extend,
            content=content_payload,
            expected_hash=args.expected_hash,
            state_dir=sdir,
            keywords=keywords or None,
            proposal=proposal_payload,
            plan_ref=getattr(args, "plan", None),
            expected_plan_hash=getattr(args, "plan_hash", None),
            mermaid_mode=getattr(args, "mermaid", "auto"),
            mindmap_supported=not bool(getattr(args, "no_mindmap", False)),
            min_moc_cluster_size=getattr(args, "min_moc_cluster_size", None),
            allow_moc=not bool(getattr(args, "no_moc", False)),
        )
    except (ValueError, RuntimeError, FileNotFoundError) as exc:
        print(_dump_json({"ok": False, "error": str(exc)}), file=sys.stderr)
        return 1

    if "plan" in res and isinstance(res["plan"], dict):
        res = dict(res)
        res["plan"] = _compact_plan_for_cli(res["plan"])
    print(_dump_json(res))
    return 0 if res.get("ok", True) else 1


def cmd_apply(args: argparse.Namespace) -> int:
    """Apply a previously previewed/saved plan exactly (or reject if stale)."""
    vault = _resolve_target_vault(args.vault_path)
    sdir = _opt_state_dir(vault, args)
    try:
        res = generate_vault_note(
            vault_root=vault,
            apply=True,
            plan_ref=args.plan,
            expected_plan_hash=getattr(args, "plan_hash", None),
            state_dir=sdir,
        )
    except (ValueError, RuntimeError, FileNotFoundError) as exc:
        print(_dump_json({"ok": False, "error": str(exc)}), file=sys.stderr)
        return 1

    if "plan" in res and isinstance(res["plan"], dict):
        res = dict(res)
        res["plan"] = _compact_plan_for_cli(res["plan"])
    print(_dump_json(res))
    return 0 if res.get("ok", True) else 1


def cmd_audit(args: argparse.Namespace) -> int:
    """Audit TeachMe-managed vault-native notes without touching user-authored notes."""
    vault = _resolve_target_vault(args.vault_path)
    sdir = _opt_state_dir(vault, args)
    files = [args.file] if args.file else None
    report = audit_vault_native(vault, target_files=files, state_dir=sdir)
    print(_dump_json(report))
    return 0


def register_vault_native_subcommands(subparsers: Any) -> None:
    """Register vault-native Obsidian integration commands on argparse subparsers."""
    p_conn = subparsers.add_parser(
        "connect", help="Connect an existing Obsidian vault and initialize its profile/index."
    )
    p_conn.add_argument("vault_path", help="Path to existing Obsidian vault.")
    p_conn.add_argument("--mode", choices=[MODE_AUTO, MODE_VAULT_NATIVE, MODE_STANDALONE], default=MODE_AUTO)
    p_conn.add_argument("--state-dir", default=None, help="Optional isolated TeachMe state directory.")
    p_conn.set_defaults(func=cmd_connect)

    p_mode = subparsers.add_parser("mode", help="View or switch operating mode.")
    p_mode.add_argument("set_mode", nargs="?", choices=[MODE_AUTO, MODE_STANDALONE, MODE_VAULT_NATIVE], default=None)
    p_mode.set_defaults(func=cmd_mode)

    p_disc = subparsers.add_parser("discover", help="Inspect and profile an Obsidian vault.")
    p_disc.add_argument("vault_path", nargs="?", default=None, help="Path to Obsidian vault.")
    p_disc.add_argument("--refresh", action="store_true", help="Force full rescan.")
    p_disc.add_argument("--state-dir", default=None)
    p_disc.set_defaults(func=cmd_discover)

    p_prof = subparsers.add_parser("profile", help="Display persisted vault profile.")
    p_prof.add_argument("vault_path", nargs="?", default=None, help="Path to Obsidian vault.")
    p_prof.add_argument("--state-dir", default=None)
    p_prof.set_defaults(func=cmd_profile)

    p_reidx = subparsers.add_parser("reindex", help="Refresh vault search index.")
    p_reidx.add_argument("vault_path", nargs="?", default=None, help="Path to Obsidian vault.")
    p_reidx.add_argument("--full", action="store_true", help="Rebuild index from scratch.")
    p_reidx.add_argument("--state-dir", default=None)
    p_reidx.set_defaults(func=cmd_reindex)

    p_search = subparsers.add_parser("search", help="Search vault for relevant existing notes.")
    p_search.add_argument("vault_path", nargs="?", default=None, help="Path to Obsidian vault.")
    p_search.add_argument("--query", required=True, help="Topic or concept query.")
    p_search.add_argument("--limit", type=int, default=10)
    p_search.add_argument("--state-dir", default=None)
    p_search.set_defaults(func=cmd_search)

    p_plan = subparsers.add_parser("plan", help="Preview placement, template, tags, MOC, Mermaid, and link plan.")
    p_plan.add_argument("vault_path", nargs="?", default=None, help="Path to Obsidian vault.")
    p_plan.add_argument("--topic", required=True, help="Target topic title.")
    p_plan.add_argument("--folder", default=None, help="Optional explicit destination folder.")
    p_plan.add_argument("--template", default=None, help="Optional explicit template path/name.")
    p_plan.add_argument("--keywords", default="", help="Comma-separated extra keywords.")
    p_plan.add_argument("--extend", default=None, help="Optional relative path to extend.")
    p_plan.add_argument("--content-json", default=None, help="JSON file with structured educational fields.")
    p_plan.add_argument("--proposal-json", default=None, help="JSON file with semantic tag/diagram/link proposals.")
    p_plan.add_argument("--mermaid", choices=["auto", "mindmap", "flowchart", "none"], default="auto")
    p_plan.add_argument("--no-mindmap", action="store_true", help="Use flowchart fallback instead of mindmap.")
    p_plan.add_argument("--min-moc-cluster-size", type=int, default=None)
    p_plan.add_argument("--no-moc", action="store_true", help="Disable MOC creation/updates for this plan.")
    p_plan.add_argument("--no-save-plan", action="store_true", help="Do not persist plan snapshot to .teachme/plans/.")
    p_plan.add_argument("--refresh", action="store_true")
    p_plan.add_argument("--state-dir", default=None)
    p_plan.set_defaults(func=cmd_plan)

    p_gen = subparsers.add_parser("generate", help="Generate or extend a vault-native note (dry-run default).")
    p_gen.add_argument("vault_path", nargs="?", default=None, help="Path to Obsidian vault.")
    p_gen.add_argument("--topic", default="", help="Target topic title (optional if --plan is provided).")
    p_gen.add_argument("--apply", action="store_true", help="Write changes to disk.")
    p_gen.add_argument("--dry-run", action="store_true", help="Preview only (default).")
    p_gen.add_argument("--folder", default=None)
    p_gen.add_argument("--template", default=None)
    p_gen.add_argument("--keywords", default="", help="Comma-separated extra keywords.")
    p_gen.add_argument("--extend", default=None, help="Existing relative note path to extend non-destructively.")
    p_gen.add_argument("--content-json", default=None, help="JSON file with structured educational fields.")
    p_gen.add_argument("--proposal-json", default=None, help="JSON file with semantic tag/diagram/link proposals.")
    p_gen.add_argument("--plan", default=None, help="Reviewed plan ID or path to execute without recomputing.")
    p_gen.add_argument("--plan-hash", default=None, help="Expected plan_hash when applying a reviewed plan.")
    p_gen.add_argument("--expected-hash", default=None, help="Optional SHA-256 conflict check for --extend.")
    p_gen.add_argument("--mermaid", choices=["auto", "mindmap", "flowchart", "none"], default="auto")
    p_gen.add_argument("--no-mindmap", action="store_true")
    p_gen.add_argument("--min-moc-cluster-size", type=int, default=None)
    p_gen.add_argument("--no-moc", action="store_true")
    p_gen.add_argument("--state-dir", default=None)
    p_gen.set_defaults(func=cmd_generate)

    p_apply = subparsers.add_parser("apply", help="Execute a previously previewed/saved plan (or reject if stale).")
    p_apply.add_argument("vault_path", nargs="?", default=None, help="Path to Obsidian vault.")
    p_apply.add_argument("--plan", required=True, help="Reviewed plan ID or JSON file path.")
    p_apply.add_argument("--plan-hash", default=None, help="Optional expected plan_hash verification.")
    p_apply.add_argument("--state-dir", default=None)
    p_apply.set_defaults(func=cmd_apply)

    p_audit = subparsers.add_parser("audit", help="Audit TeachMe-managed vault-native notes safely.")
    p_audit.add_argument("vault_path", nargs="?", default=None, help="Path to Obsidian vault.")
    p_audit.add_argument("--file", default=None, help="Optional specific relative file path to audit.")
    p_audit.add_argument("--state-dir", default=None)
    p_audit.set_defaults(func=cmd_audit)
