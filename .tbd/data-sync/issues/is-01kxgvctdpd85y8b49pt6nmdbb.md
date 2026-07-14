---
type: is
id: is-01kxgvctdpd85y8b49pt6nmdbb
title: Normalize plugin paths on direct server import
kind: bug
status: closed
priority: 2
version: 2
spec_path: docs/specs/metabrowser-v0.1.0.md
labels: []
dependencies: []
created_at: 2026-07-14T17:39:32.406Z
updated_at: 2026-07-14T17:41:06.097Z
closed_at: 2026-07-14T17:41:06.096Z
close_reason: Canonicalized METABROWSER_PLUGINS_DIRS paths during direct server import, added a subprocess regression for tilde expansion without CLI bootstrap, updated the extraction spec, and passed the full 599-test release gate plus clean npm audit.
---
Address PR #1 review finding: direct imports of metabrowser.server must expand and canonicalize METABROWSER_PLUGINS_DIRS even when callers do not enter through the CLI helper. Add a subprocess regression for a tilde path, rerun the release gate, and preserve the explicit opt-in trust boundary.
