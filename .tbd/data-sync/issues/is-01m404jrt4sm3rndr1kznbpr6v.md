---
type: is
id: is-01m404jrt4sm3rndr1kznbpr6v
title: Separate cache and configuration storage using uv/fdu conventions
kind: epic
status: in_progress
priority: 2
version: 7
delegate: codex@spud10.local
labels: []
dependencies: []
parent_id: is-01m402dbhn3zsc1h896f3xnrsq
child_order_hints:
  - is-01m404yq5wyjd4tha1p66x5y9a
  - is-01m404yqhz92wqk3x2dfea9251
  - is-01m404yqx2zybbd9789dsb98q8
hold: null
hold_until: null
created_at: 2026-10-03T05:42:51.965Z
updated_at: 2026-10-03T05:49:24.257Z
started_at: 2026-10-03T05:49:23.081Z
---
Approved v0.12 clean break: use ~/.cache/metabrowser and ~/.config/metabrowser on Linux/macOS, honoring app-specific and XDG overrides. Remove METABROWSER_HOME and the combined home layout; no backward compatibility aliases, migration, or fallback. Update architecture, runtime paths, safety checks, CLI/UI contracts, test fixtures, goldens, runbook, and release notes. Existing user files remain untouched. Parent release-stability epic tracks overall acceptance.

## Notes

Comparison: current uv official storage docs use XDG on both Linux and macOS: ~/.cache/uv, ~/.config/uv, ~/.local/share/uv; cache override via --cache-dir or UV_CACHE_DIR or configuration. Local fdu checkout 31241be6 uses --cache-dir > FDU_CACHE_DIR > XDG_CACHE_HOME/fdu > ~/.cache/fdu on Linux/macOS; docs/usage.md and crates/fdu-core/src/lib.rs agree. fdu deliberately moved macOS from Library/Caches/fdu. Recommend same cache resolution pattern for Metabrowser, with config outside disposable cache and legacy METABROWSER_HOME compatibility/migration defined. Current Metabrowser config.yml is user-owned (cache/layout.py); moving the entire home into ~/.cache would misclassify config. Sources: https://docs.astral.sh/uv/reference/storage/ and https://docs.astral.sh/uv/concepts/cache/ . Decision pending; no implementation/default changes.
