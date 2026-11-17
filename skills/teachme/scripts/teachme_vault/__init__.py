"""Vault-aware, context-aware Obsidian integration engine for TeachMe.

Pure Python 3 standard-library package providing vault discovery, metadata/tag
indexing, style profiling, read-only plugin capability detection, template
resolution, destination placement, context-aware tagging, MOC maintenance,
Mermaid diagram planning/validation, and transactional note generation/auditing.
"""

from .discovery import discover_vault, load_or_discover_profile
from .indexer import build_or_update_index, load_or_build_index, resolve_safe_wikilink, search_vault
from .mermaid import plan_mermaid_diagram, validate_mermaid_syntax
from .moc import plan_moc_integration
from .models import (
    DEFAULT_IGNORED_DIRS,
    MODE_AUTO,
    MODE_STANDALONE,
    MODE_VAULT_NATIVE,
    detect_vault_mode,
    load_config,
    resolve_state_dir,
    save_config,
)
from .planner import load_reviewed_plan, plan_note
from .tagging import select_and_plan_tags
from .writer import audit_vault_native, generate_vault_note

__all__ = [
    "DEFAULT_IGNORED_DIRS",
    "MODE_AUTO",
    "MODE_STANDALONE",
    "MODE_VAULT_NATIVE",
    "audit_vault_native",
    "build_or_update_index",
    "detect_vault_mode",
    "discover_vault",
    "generate_vault_note",
    "load_config",
    "load_or_build_index",
    "load_or_discover_profile",
    "load_reviewed_plan",
    "plan_mermaid_diagram",
    "plan_moc_integration",
    "plan_note",
    "resolve_safe_wikilink",
    "resolve_state_dir",
    "save_config",
    "search_vault",
    "select_and_plan_tags",
    "validate_mermaid_syntax",
]
