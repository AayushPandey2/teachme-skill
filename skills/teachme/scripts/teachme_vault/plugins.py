"""Read-only Obsidian plugin capability detection and convention extraction."""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any

from .models import is_within_root, read_text_safe, redact_sensitive, safe_iter_files

CORE_PLUGIN_DESCRIPTIONS = {
    "templates": "Core Templates",
    "daily-notes": "Core Daily Notes",
    "canvas": "Obsidian Canvas",
    "bases": "Obsidian Bases",
    "backlinks": "Backlinks",
    "outgoing-link": "Outgoing Links",
}

COMMUNITY_PLUGIN_CATALOG = {
    "templater-obsidian": {
        "name": "Templater",
        "capability_level": "supported_safe_render",
        "notes": "Reads template folder and folder_templates mappings; preserves <% ... %> dynamic tags without executing JS/shell.",
    },
    "dataview": {
        "name": "Dataview",
        "capability_level": "supported_schema_aware",
        "notes": "Detects inline fields and inspects read-only DQL queries to preserve queried YAML/inline properties; never executes dataviewjs.",
    },
    "obsidian-spaced-repetition": {
        "name": "Spaced Repetition",
        "capability_level": "supported_syntax_matching",
        "notes": "Matches configured flashcard tags and :: / ? / cloze card syntax.",
    },
    "obsidian-tasks-plugin": {
        "name": "Tasks",
        "capability_level": "supported_syntax_preserving",
        "notes": "Preserves task global filter, status markers, and emoji/dataview date metadata.",
    },
    "obsidian-excalidraw-plugin": {
        "name": "Excalidraw",
        "capability_level": "protected_non_destructive",
        "notes": "Detects drawing folder and .excalidraw.md files; excludes them from Markdown rewriting.",
    },
    "quickadd": {
        "name": "QuickAdd",
        "capability_level": "limited_discovery",
        "notes": "Extracts template paths from choices when configured; macros/scripts are never executed.",
    },
    "metadata-menu": {
        "name": "Metadata Menu",
        "capability_level": "limited_schema_aware",
        "notes": "Extracts fileClass folder/property conventions where configured.",
    },
    "obsidian-folder-notes": {
        "name": "Folder Notes",
        "capability_level": "supported_convention_aware",
        "notes": "Recognizes folder note naming conventions (index vs folder-name).",
    },
    "folder-notes": {
        "name": "Folder Notes",
        "capability_level": "supported_convention_aware",
        "notes": "Recognizes folder note naming conventions.",
    },
    "periodic-notes": {
        "name": "Periodic Notes",
        "capability_level": "supported_folder_exclusion",
        "notes": "Identifies daily/weekly/monthly periodic folders and date formats.",
    },
    "calendar": {
        "name": "Calendar",
        "capability_level": "detected_metadata",
        "notes": "Indicates daily/periodic journaling workflow.",
    },
}


def _read_json_safe(path: Path, vault_root: Path) -> Any:
    if not path.is_file() or not is_within_root(path, vault_root):
        return None
    try:
        return json.loads(read_text_safe(path))
    except (OSError, json.JSONDecodeError):
        return None


def _parse_dql_signals(queries: list[str]) -> dict[str, Any]:
    """Extract queried folders, tags, and fields from Dataview DQL blocks safely."""
    from_folders: list[str] = []
    from_tags: list[str] = []
    fields: list[str] = []
    for q in queries:
        for line in q.splitlines():
            s = line.strip()
            low = s.lower()
            if low.startswith("from "):
                for m in re.finditer(r'"([^"]+)"', s):
                    folder = m.group(1).strip("/")
                    if folder and folder not in from_folders:
                        from_folders.append(folder)
                for m in re.finditer(r"#([A-Za-z0-9_/-]+)", s):
                    tag = m.group(1)
                    if tag not in from_tags:
                        from_tags.append(tag)
            elif low.startswith(("table ", "list ", "task ")):
                rest = s.split(" ", 1)[1] if " " in s else ""
                for part in rest.split(","):
                    col = part.strip().split(" as ")[0].strip()
                    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*", col) and col.lower() not in {"without", "id"}:
                        if col not in fields:
                            fields.append(col)
            elif low.startswith(("where ", "sort ")):
                for m in re.finditer(r"\b([a-zA-Z_][a-zA-Z0-9_-]*)\b", s[5:]):
                    tok = m.group(1)
                    if tok.lower() not in {"and", "or", "not", "contains", "file", "asc", "desc", "null", "true", "false"}:
                        if tok not in fields:
                            fields.append(tok)
    return {"folders": from_folders[:20], "tags": from_tags[:20], "fields": fields[:30]}


def inspect_obsidian_plugins(
    vault_root: Path,
    dataview_queries: list[str] | None = None,
) -> dict[str, Any]:
    """Inspect .obsidian/ configuration read-only and build a capability report."""
    obs_dir = vault_root / ".obsidian"
    has_obsidian = obs_dir.is_dir() and is_within_root(obs_dir, vault_root)

    app_cfg = redact_sensitive(_read_json_safe(obs_dir / "app.json", vault_root) or {})
    core_raw = _read_json_safe(obs_dir / "core-plugins.json", vault_root)
    community_raw = _read_json_safe(obs_dir / "community-plugins.json", vault_root)
    templates_cfg = redact_sensitive(_read_json_safe(obs_dir / "templates.json", vault_root) or {})
    daily_cfg = redact_sensitive(_read_json_safe(obs_dir / "daily-notes.json", vault_root) or {})

    core_enabled: list[str] = []
    if isinstance(core_raw, list):
        core_enabled = [str(x) for x in core_raw]
    elif isinstance(core_raw, dict):
        core_enabled = [str(k) for k, v in core_raw.items() if v]

    community_enabled: list[str] = (
        [str(x) for x in community_raw] if isinstance(community_raw, list) else []
    )

    capabilities: list[dict[str, Any]] = []
    template_folders: list[str] = []
    folder_templates: dict[str, str] = {}
    periodic_folders: list[str] = []
    protected_folders: list[str] = []
    conventions: dict[str, Any] = {
        "link_format": app_cfg.get("newLinkFormat", "shortest"),
        "use_markdown_links": bool(app_cfg.get("useMarkdownLinks", False)),
        "new_file_location": app_cfg.get("newFileLocation", "root"),
        "new_file_folder": str(app_cfg.get("newFileFolderPath", "")).strip("/"),
        "attachment_folder": str(app_cfg.get("attachmentFolderPath", "")).strip("/"),
        "flashcard_tags": [],
        "task_global_filter": "",
        "dataview_inline_syntax": False,
        "dataview_queried_fields": [],
        "dataview_queried_folders": [],
        "excalidraw_folder": "",
    }

    if conventions["attachment_folder"]:
        protected_folders.append(conventions["attachment_folder"])

    # Core plugin capabilities
    if "templates" in core_enabled or templates_cfg:
        tfolder = str(templates_cfg.get("folder", "")).strip("/")
        if tfolder and tfolder not in template_folders:
            template_folders.append(tfolder)
        capabilities.append(
            {
                "id": "templates",
                "name": "Core Templates",
                "kind": "core",
                "enabled": "templates" in core_enabled or bool(templates_cfg),
                "status": "supported",
                "conventions": {
                    "folder": tfolder,
                    "date_format": templates_cfg.get("dateFormat", "YYYY-MM-DD"),
                    "time_format": templates_cfg.get("timeFormat", "HH:mm"),
                },
                "affects_generation": True,
            }
        )

    if "daily-notes" in core_enabled or daily_cfg:
        dfolder = str(daily_cfg.get("folder", "")).strip("/")
        dtemplate = str(daily_cfg.get("template", "")).strip("/")
        if dfolder and dfolder not in periodic_folders:
            periodic_folders.append(dfolder)
        capabilities.append(
            {
                "id": "daily-notes",
                "name": "Core Daily Notes",
                "kind": "core",
                "enabled": "daily-notes" in core_enabled or bool(daily_cfg),
                "status": "supported",
                "conventions": {
                    "folder": dfolder,
                    "format": daily_cfg.get("format", "YYYY-MM-DD"),
                    "template": dtemplate,
                },
                "affects_generation": False,
            }
        )

    # Non-markdown structural file awareness (Canvas, Bases, Excalidraw)
    canvas_files = [
        p.relative_to(vault_root).as_posix()
        for p in safe_iter_files(vault_root, extensions=(".canvas",))
    ]
    base_files = [
        p.relative_to(vault_root).as_posix()
        for p in safe_iter_files(vault_root, extensions=(".base",))
    ]
    excalidraw_files = [
        p.relative_to(vault_root).as_posix()
        for p in safe_iter_files(vault_root, extensions=(".excalidraw.md", ".excalidraw"))
    ]

    if canvas_files or "canvas" in core_enabled:
        capabilities.append(
            {
                "id": "canvas",
                "name": "Obsidian Canvas",
                "kind": "core",
                "enabled": "canvas" in core_enabled or bool(canvas_files),
                "status": "protected_read_only",
                "conventions": {"canvas_count": len(canvas_files), "sample": canvas_files[:5]},
                "affects_generation": False,
            }
        )

    if base_files or "bases" in core_enabled:
        capabilities.append(
            {
                "id": "bases",
                "name": "Obsidian Bases",
                "kind": "core",
                "enabled": "bases" in core_enabled or bool(base_files),
                "status": "protected_read_only",
                "conventions": {"base_count": len(base_files), "sample": base_files[:5]},
                "affects_generation": False,
            }
        )

    # Community plugins
    plugins_dir = obs_dir / "plugins"
    discovered_ids: list[str] = list(community_enabled)
    if plugins_dir.is_dir() and is_within_root(plugins_dir, vault_root):
        for child in sorted(plugins_dir.iterdir()):
            if child.is_dir() and child.name not in discovered_ids:
                discovered_ids.append(child.name)

    for pid in discovered_ids:
        is_enabled = pid in community_enabled
        pdir = plugins_dir / pid
        manifest = redact_sensitive(_read_json_safe(pdir / "manifest.json", vault_root) or {})
        data = redact_sensitive(_read_json_safe(pdir / "data.json", vault_root) or {})
        meta = COMMUNITY_PLUGIN_CATALOG.get(pid)
        plugin_name = manifest.get("name") or (meta["name"] if meta else pid)

        plugin_conv: dict[str, Any] = {}
        affects_gen = False
        status = meta["capability_level"] if meta else "detected_unsupported"
        notes = meta["notes"] if meta else "Detected community plugin without specialized integration; using safe Markdown fallback."

        if pid == "templater-obsidian" and is_enabled:
            affects_gen = True
            tfolder = str(data.get("templates_folder", "")).strip("/")
            if tfolder and tfolder not in template_folders:
                template_folders.append(tfolder)
            raw_ft = data.get("folder_templates", [])
            if isinstance(raw_ft, list):
                for entry in raw_ft:
                    if isinstance(entry, dict):
                        fld = str(entry.get("folder", "")).strip("/")
                        tpl = str(entry.get("template", "")).strip("/")
                        if fld and tpl:
                            folder_templates[fld] = tpl
            plugin_conv = {
                "templates_folder": tfolder,
                "folder_templates": folder_templates,
                "trigger_on_file_creation": bool(data.get("trigger_on_file_creation", False)),
            }

        elif pid == "dataview" and is_enabled:
            affects_gen = True
            conventions["dataview_inline_syntax"] = True
            dql_info = _parse_dql_signals(dataview_queries or [])
            conventions["dataview_queried_fields"] = dql_info["fields"]
            conventions["dataview_queried_folders"] = dql_info["folders"]
            plugin_conv = {
                "enable_dataview_js": bool(data.get("enableDataviewJs", False)),
                "inline_query_prefix": data.get("inlineQueryPrefix", "="),
                "queried_fields": dql_info["fields"],
                "queried_folders": dql_info["folders"],
                "queried_tags": dql_info["tags"],
            }

        elif pid == "obsidian-spaced-repetition" and is_enabled:
            affects_gen = True
            sr_tags = data.get("flashcardTags", ["#flashcards"])
            if isinstance(sr_tags, list):
                conventions["flashcard_tags"] = [str(t).lstrip("#") for t in sr_tags if str(t).strip()]
            plugin_conv = {
                "flashcard_tags": conventions["flashcard_tags"],
                "inline_separator": data.get("singleLineCardSeparator", "::"),
                "multiline_separator": data.get("multilineCardSeparator", "?"),
                "convert_highlights_to_clozes": bool(data.get("convertHighlightsToClozes", True)),
                "convert_curly_brackets_to_clozes": bool(data.get("convertCurlyBracketsToClozes", False)),
            }

        elif pid == "obsidian-tasks-plugin" and is_enabled:
            affects_gen = True
            gf = str(data.get("globalFilter", "")).strip()
            conventions["task_global_filter"] = gf
            plugin_conv = {
                "global_filter": gf,
                "task_format": data.get("taskFormat", "tasksPluginEmoji"),
            }

        elif pid == "obsidian-excalidraw-plugin":
            ex_folder = str(data.get("folder", "")).strip("/")
            conventions["excalidraw_folder"] = ex_folder
            if ex_folder and ex_folder not in protected_folders:
                protected_folders.append(ex_folder)
            plugin_conv = {
                "excalidraw_folder": ex_folder,
                "excalidraw_files_count": len(excalidraw_files),
            }

        elif pid == "quickadd" and is_enabled:
            choices = data.get("choices", [])
            choice_templates: list[str] = []
            if isinstance(choices, list):
                for ch in choices:
                    if isinstance(ch, dict):
                        tp = str(ch.get("templatePath", "")).strip("/")
                        if tp:
                            choice_templates.append(tp)
            plugin_conv = {"template_paths": choice_templates[:15]}

        elif pid == "periodic-notes" and is_enabled:
            for period in ("daily", "weekly", "monthly", "quarterly", "yearly"):
                pcfg = data.get(period, {})
                if isinstance(pcfg, dict) and pcfg.get("enabled"):
                    pf = str(pcfg.get("folder", "")).strip("/")
                    if pf and pf not in periodic_folders:
                        periodic_folders.append(pf)
            plugin_conv = {"periodic_folders": periodic_folders}

        elif pid in ("obsidian-folder-notes", "folder-notes") and is_enabled:
            affects_gen = True
            plugin_conv = {
                "folder_note_method": data.get("folderNoteType", "inside"),
                "index_filename": data.get("indexName", "index"),
            }

        elif pid == "metadata-menu" and is_enabled:
            affects_gen = True
            fc_folder = str(data.get("classFilesPath", "")).strip("/")
            plugin_conv = {"class_files_path": fc_folder}

        capabilities.append(
            {
                "id": pid,
                "name": plugin_name,
                "kind": "community",
                "enabled": is_enabled,
                "version": manifest.get("version", ""),
                "status": status if is_enabled else "disabled",
                "conventions": plugin_conv,
                "notes": notes,
                "affects_generation": affects_gen if is_enabled else False,
            }
        )

    return {
        "has_obsidian": has_obsidian,
        "core_plugins_enabled": core_enabled,
        "community_plugins_enabled": community_enabled,
        "capabilities": capabilities,
        "template_folders": template_folders,
        "folder_templates": folder_templates,
        "periodic_folders": periodic_folders,
        "protected_folders": protected_folders,
        "non_markdown_assets": {
            "canvas_files": canvas_files[:50],
            "canvas_count": len(canvas_files),
            "base_files": base_files[:50],
            "base_count": len(base_files),
            "excalidraw_files": excalidraw_files[:50],
            "excalidraw_count": len(excalidraw_files),
        },
        "conventions": conventions,
    }
