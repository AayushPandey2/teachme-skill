"""Vault-aware, context-aware Obsidian integration engine for TeachMe.

Pure Python 3 standard-library package providing vault discovery, metadata/tag
indexing, style profiling, read-only plugin capability detection, template
resolution, destination placement, context retrieval, and non-destructive
vault-native note generation and auditing.
"""

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

__all__ = [
    "DEFAULT_IGNORED_DIRS",
    "MODE_AUTO",
    "MODE_STANDALONE",
    "MODE_VAULT_NATIVE",
    "detect_vault_mode",
    "load_config",
    "resolve_state_dir",
    "save_config",
]
