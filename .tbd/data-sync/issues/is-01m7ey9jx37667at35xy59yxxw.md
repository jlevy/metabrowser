---
type: is
id: is-01m7ey9jx37667at35xy59yxxw
title: CLI option defaults duplicate settings constants as literals
kind: bug
status: open
priority: 3
version: 1
spec_path: docs/project/specs/active/plan-2026-11-14-documentation-from-first-principles.md
labels: []
dependencies: []
parent_id: is-01m7ey9fq9v53mp3c974mg2d89
created_at: 2026-11-15T06:28:41.506Z
updated_at: 2026-11-15T06:28:41.506Z
---
cli/main.py hard-codes --max-depth, --max-files, and --index-timeout defaults that copy INVENTORY_MAX_DEPTH, INVENTORY_MAX_FILES, and INDEX_READY_TIMEOUT_S; --zone has an unexplained default. Use the constants.
