---
type: is
id: is-01kxh84ay64vb6ezrxr4w85s47
title: Fix logical size passed to KPress render
kind: bug
status: closed
priority: 1
version: 2
spec_path: docs/specs/metabrowser-v0.1.0.md
labels: []
dependencies: []
parent_id: is-01kxh6nz7zzeerc5xgd3enrev2
created_at: 2026-07-14T21:22:05.893Z
updated_at: 2026-07-14T21:27:36.713Z
closed_at: 2026-07-14T21:27:36.712Z
close_reason: Fixed the final gzip logical-size finding in 38e78af, replied and resolved it, verified all 29 review threads are resolved, and completed the final CI watch with Cursor and all five Actions jobs passing.
---
For gzip-backed content, api_kpress_render validates logical_size but passes disk_size to render_kpress_view. Pass the decompressed logical size and add regression coverage for compressed Markdown.
