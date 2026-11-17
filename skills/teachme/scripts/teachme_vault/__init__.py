"""Operational learning-state and read-only Obsidian source indexing for TeachMe."""

from .indexer import build_or_update_index, load_or_build_index, search_vault
from .models import (
    DEFAULT_IGNORED_DIRS,
    MODE_AUTO,
    MODE_STANDALONE,
    MODE_VAULT_NATIVE,
    atomic_write_text,
    detect_vault_mode,
    load_config,
    resolve_state_dir,
    save_config,
)
from .state_store import (
    HANDOFF_SCHEMA_VERSION,
    build_handoff_envelope,
    import_legacy_vault,
    init_session_state,
    list_vault_native_sessions,
    rebuild_curriculum_graph,
    resolve_session_dir,
    validate_session_state,
)

__all__ = [
    "DEFAULT_IGNORED_DIRS",
    "HANDOFF_SCHEMA_VERSION",
    "MODE_AUTO",
    "MODE_STANDALONE",
    "MODE_VAULT_NATIVE",
    "atomic_write_text",
    "build_handoff_envelope",
    "build_or_update_index",
    "detect_vault_mode",
    "import_legacy_vault",
    "init_session_state",
    "list_vault_native_sessions",
    "load_config",
    "load_or_build_index",
    "rebuild_curriculum_graph",
    "resolve_session_dir",
    "resolve_state_dir",
    "save_config",
    "search_vault",
    "validate_session_state",
]
