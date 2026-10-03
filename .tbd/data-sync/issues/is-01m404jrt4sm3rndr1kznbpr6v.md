---
type: is
id: is-01m404jrt4sm3rndr1kznbpr6v
title: Decide cache/config directory conventions and environment variable migration
kind: task
status: open
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m402dbhn3zsc1h896f3xnrsq
created_at: 2026-10-03T05:42:51.965Z
updated_at: 2026-10-03T05:44:03.496Z
---
Evaluate XDG_CACHE_HOME/metabrowser (default ~/.cache/metabrowser) for disposable cache, separate durable configuration/data locations, and native platform conventions. Clarify or replace METABROWSER_HOME without breaking existing overrides. Inventory durable versus reconstructible records, define migration and precedence, and validate security checks and cleanup semantics. User raised this during release QA; design decision pending, no default-location change authorized yet.

## Notes

Comparison: current uv official storage docs use XDG on both Linux and macOS: ~/.cache/uv, ~/.config/uv, ~/.local/share/uv; cache override via --cache-dir or UV_CACHE_DIR or configuration. Local fdu checkout 31241be6 uses --cache-dir > FDU_CACHE_DIR > XDG_CACHE_HOME/fdu > ~/.cache/fdu on Linux/macOS; docs/usage.md and crates/fdu-core/src/lib.rs agree. fdu deliberately moved macOS from Library/Caches/fdu. Recommend same cache resolution pattern for Metabrowser, with config outside disposable cache and legacy METABROWSER_HOME compatibility/migration defined. Current Metabrowser config.yml is user-owned (cache/layout.py); moving the entire home into ~/.cache would misclassify config. Sources: https://docs.astral.sh/uv/reference/storage/ and https://docs.astral.sh/uv/concepts/cache/ . Decision pending; no implementation/default changes.
