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


def _compact_moc_summary(moc_dec: dict[str, Any]) -> dict[str, Any]:
    return {
        "action": moc_dec.get("action"),
        "selected_moc": moc_dec.get("selected_moc"),
        "target_section": moc_dec.get("target_section"),
        "new_moc_path": moc_dec.get("new_moc_path"),
        "confidence": moc_dec.get("confidence"),
        "needs_confirmation": moc_dec.get("needs_confirmation", False),
        "query_satisfaction": moc_dec.get("query_satisfaction"),
        "reason": moc_dec.get("reason"),
    }


def _compact_diagram_summary(diag_dec: dict[str, Any]) -> dict[str, Any]:
    val = diag_dec.get("validation") or {}
    return {
        "include_diagram": diag_dec.get("include_diagram", False),
        "diagram_type": diag_dec.get("diagram_type"),
        "fallback_used": diag_dec.get("fallback_used", False),
        "validation_mode": val.get("validation_mode"),
        "valid": val.get("valid"),
        "reason": diag_dec.get("reason"),
    }


def _format_plan_output(plan: dict[str, Any], output_mode: str) -> dict[str, Any]:
    if output_mode == "full":
        out = dict(plan)
        out["affected_files"] = [
            {k: v for k, v in af.items() if k != "new_text"}
            for af in plan.get("affected_files", [])
        ]
        return out

    td = plan.get("tag_decisions", {})
    decs = td.get("decisions", [])
    compact_af = []
    for af in plan.get("affected_files", []):
        entry: dict[str, Any] = {
            "rel_path": af.get("rel_path"),
            "role": af.get("role"),
            "action": af.get("action"),
            "conflict": af.get("conflict", False),
            "expected_sha256": af.get("expected_sha256"),
        }
        if af.get("conflict_reason"):
            entry["conflict_reason"] = af["conflict_reason"]
        if output_mode == "diff" and af.get("diff"):
            entry["diff"] = af["diff"]
        compact_af.append(entry)

    plan_id = plan.get("plan_id", "")
    plan_file = plan.get("plan_file", "")
    dest = plan.get("destination", {})
    tpl = plan.get("template", {})

    out: dict[str, Any] = {
        "plan_id": plan_id,
        "plan_hash": plan.get("plan_hash"),
        "plan_file": plan_file,
        "topic": plan.get("topic"),
        "recommended_action": plan.get("recommended_action"),
        "unresolved": plan.get("unresolved", False),
        "resolution_options": plan.get("resolution_options", []),
        "destination": {
            "folder": dest.get("folder"),
            "filename": dest.get("filename"),
            "proposed_rel_path": dest.get("proposed_rel_path"),
            "confidence": dest.get("confidence"),
            "needs_confirmation": dest.get("needs_confirmation", False),
        },
        "template": {
            "selected": tpl.get("selected"),
            "confidence": tpl.get("confidence"),
        },
        "tags": plan.get("tags", []),
        "tag_decisions": {
            "placement": td.get("placement"),
            "reused": [d["tag"] for d in decs if d.get("decision") == "reuse"],
            "created": [d["tag"] for d in decs if d.get("decision") == "create"],
            "rejected": [d["tag"] for d in decs if d.get("decision") == "reject"][:8],
        },
        "relevant_notes": [
            {"rel_path": r.get("rel_path"), "wikilink": r.get("wikilink"), "score": r.get("score")}
            for r in plan.get("relevant_notes", [])[:6]
        ],
        "moc_decisions": _compact_moc_summary(plan.get("moc_decisions", {})),
        "diagram_decisions": _compact_diagram_summary(plan.get("diagram_decisions", {})),
        "affected_files": compact_af,
        "expected_hashes": plan.get("expected_hashes", {}),
        "evidence": plan.get("evidence", [])[:5],
        "warnings": plan.get("warnings", []),
        "confidence": plan.get("confidence"),
        "detail_commands": [
            f"vault_cli.py apply --plan {plan_id} --plan-hash {plan.get('plan_hash', '')}",
            f"vault_cli.py plan --topic \"{plan.get('topic', '')}\" --output full",
        ],
    }
    if plan.get("existing_note"):
        out["existing_note"] = {
            "rel_path": plan["existing_note"].get("rel_path"),
            "title": plan["existing_note"].get("title"),
            "score": plan["existing_note"].get("score"),
        }
    return out


def _format_audit_output(report: dict[str, Any], output_mode: str) -> dict[str, Any]:
    errors = report.get("errors", [])
    warnings = report.get("warnings", [])
    pre = report.get("pre_existing_issues", [])
    if output_mode == "full":
        out = dict(report)
        out["ok"] = len(errors) == 0
        return out

    max_pre = 10
    out: dict[str, Any] = {
        "ok": len(errors) == 0,
        "vault_path": report.get("vault_path"),
        "mode": report.get("mode"),
        "counts": {
            "audited_files": len(report.get("audited_files", [])),
            "audited_moc_updates": len(report.get("audited_moc_updates", [])),
            "errors": len(errors),
            "warnings": len(warnings),
            "pre_existing_issues": len(pre),
        },
        "audited_files": report.get("audited_files", []),
        "audited_moc_updates": report.get("audited_moc_updates", []),
        "errors": errors,  # Never omit blocking errors
        "warnings": warnings,
        "user_notes_untouched": report.get("user_notes_untouched", True),
    }
    if pre:
        out["pre_existing_issues"] = pre[:max_pre]
        if len(pre) > max_pre:
            out["pre_existing_truncated"] = True
            out["detail_commands"] = ["vault_cli.py audit --output full"]
    return out


def _format_generate_output(res: dict[str, Any], output_mode: str) -> dict[str, Any]:
    if output_mode == "full":
        out = dict(res)
        if isinstance(out.get("plan"), dict):
            out["plan"] = _format_plan_output(out["plan"], "full")
        return out

    plan = res.get("plan") if isinstance(res.get("plan"), dict) else {}
    compact_af = [
        {
            "rel_path": af.get("rel_path"),
            "role": af.get("role"),
            "action": af.get("action"),
            "conflict": af.get("conflict", False),
            "expected_sha256": af.get("expected_sha256"),
        }
        for af in res.get("affected_files", [])
    ]

    if res.get("conflict"):
        return {
            "ok": False,
            "status": "conflict",
            "conflict": True,
            "applied": False,
            "writes_committed": False,
            "audit_passed": None,
            "target_rel_path": res.get("target_rel_path"),
            "reason": res.get("reason"),
            "resolution_options": res.get("resolution_options", []),
            "plan_id": res.get("plan_id"),
            "plan_hash": res.get("plan_hash"),
        }

    out: dict[str, Any] = {
        "ok": res.get("ok", True),
        "status": res.get("status"),
        "applied": res.get("applied", False),
        "dry_run": res.get("dry_run", False),
        "writes_committed": res.get("writes_committed", False),
        "transaction_status": res.get("transaction_status"),
        "audit_passed": res.get("audit_passed"),
        "mode": res.get("mode"),
        "plan_id": res.get("plan_id"),
        "plan_hash": res.get("plan_hash"),
        "plan_file": res.get("plan_file", ""),
        "target_rel_path": res.get("target_rel_path"),
        "backup_rel_path": res.get("backup_rel_path", ""),
        "affected_files": compact_af,
        "moc_decisions": _compact_moc_summary(plan.get("moc_decisions", {})),
        "diagram_decisions": _compact_diagram_summary(plan.get("diagram_decisions", {})),
        "warnings": plan.get("warnings", []),
        "post_commit_errors": res.get("post_commit_errors", []),
    }

    if res.get("applied"):
        tx = res.get("transaction")
        if tx:
            out["transaction"] = {
                "tx_id": tx.get("tx_id"),
                "status": tx.get("status"),
                "written_files": tx.get("written_files", []),
                "backups": tx.get("backups", {}),
                "atomicity": tx.get("atomicity"),
            }
        if res.get("audit"):
            out["audit"] = _format_audit_output(res["audit"], "summary")
        if output_mode == "diff" and res.get("diff"):
            out["diff"] = res["diff"]
        out["detail_commands"] = ["vault_cli.py audit --output full"]
    else:
        if output_mode == "diff" and res.get("diff"):
            out["diff"] = res["diff"]
        out["detail_commands"] = [
            f"vault_cli.py apply --plan {res.get('plan_id', '')} --plan-hash {res.get('plan_hash', '')}",
        ]

    return out


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
    full = getattr(args, "output", "summary") == "full"
    print(_dump_json(summarize_profile_for_display(profile, full=full)))
    return 0


def cmd_profile(args: argparse.Namespace) -> int:
    """Display the persisted or freshly inferred vault profile."""
    vault = _resolve_target_vault(args.vault_path)
    sdir = _opt_state_dir(vault, args)
    profile = load_or_discover_profile(vault, refresh=False, state_dir=sdir)
    full = getattr(args, "output", "summary") == "full"
    print(_dump_json(summarize_profile_for_display(profile, full=full)))
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

    output_mode = getattr(args, "output", "summary")
    print(_dump_json(_format_plan_output(plan, output_mode)))
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

    raw_output = getattr(args, "output", None)
    eff_output = raw_output or ("summary" if apply_write else "diff")
    print(_dump_json(_format_generate_output(res, eff_output)))
    return 0 if res.get("ok", True) else 1


def cmd_apply(args: argparse.Namespace) -> int:
    """Apply a previously previewed/saved plan exactly (or reject if stale/tampered)."""
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

    output_mode = getattr(args, "output", "summary")
    print(_dump_json(_format_generate_output(res, output_mode)))
    return 0 if res.get("ok", True) else 1


def cmd_audit(args: argparse.Namespace) -> int:
    """Audit TeachMe-managed vault-native notes without touching user-authored notes."""
    vault = _resolve_target_vault(args.vault_path)
    sdir = _opt_state_dir(vault, args)
    files = [args.file] if args.file else None
    report = audit_vault_native(vault, target_files=files, state_dir=sdir)
    output_mode = getattr(args, "output", "summary")
    print(_dump_json(_format_audit_output(report, output_mode)))
    return 1 if report.get("errors") else 0


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
    p_disc.add_argument("--output", choices=["summary", "full"], default="summary")
    p_disc.add_argument("--state-dir", default=None)
    p_disc.set_defaults(func=cmd_discover)

    p_prof = subparsers.add_parser("profile", help="Display persisted vault profile.")
    p_prof.add_argument("vault_path", nargs="?", default=None, help="Path to Obsidian vault.")
    p_prof.add_argument("--output", choices=["summary", "full"], default="summary")
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
    p_plan.add_argument("--output", choices=["summary", "diff", "full"], default="summary")
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
    p_gen.add_argument("--output", choices=["summary", "diff", "full"], default=None)
    p_gen.add_argument("--state-dir", default=None)
    p_gen.set_defaults(func=cmd_generate)

    p_apply = subparsers.add_parser("apply", help="Execute a previously previewed/saved plan (or reject if stale).")
    p_apply.add_argument("vault_path", nargs="?", default=None, help="Path to Obsidian vault.")
    p_apply.add_argument("--plan", required=True, help="Reviewed plan ID or JSON file path.")
    p_apply.add_argument("--plan-hash", default=None, help="Optional expected plan_hash verification.")
    p_apply.add_argument("--output", choices=["summary", "diff", "full"], default="summary")
    p_apply.add_argument("--state-dir", default=None)
    p_apply.set_defaults(func=cmd_apply)

    p_audit = subparsers.add_parser("audit", help="Audit TeachMe-managed vault-native notes safely.")
    p_audit.add_argument("vault_path", nargs="?", default=None, help="Path to Obsidian vault.")
    p_audit.add_argument("--file", default=None, help="Optional specific relative file path to audit.")
    p_audit.add_argument("--output", choices=["summary", "full"], default="summary")
    p_audit.add_argument("--state-dir", default=None)
    p_audit.set_defaults(func=cmd_audit)
