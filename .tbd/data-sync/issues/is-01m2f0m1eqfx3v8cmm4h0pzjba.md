---
type: is
id: is-01m2f0m1eqfx3v8cmm4h0pzjba
title: "PR #115 review R2: Recipe wheel builds use isolated build-dependency resolution"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m2f0m0sdxg3fe8v091zxkby8
hold: null
hold_until: null
created_at: 2026-09-14T03:50:52.118Z
updated_at: 2026-09-14T04:48:10.206Z
started_at: 2026-09-14T03:50:58.559Z
closed_at: 2026-09-14T04:48:10.205Z
close_reason: "Fixed in bbd16783 (option a): locked sync then uv build --clear --no-build-isolation, mirroring make build; verified with v0.9.1 and the branch"
resolution: null
duplicate_of: null
---
PR #115 review R2 (Medium). explorations/performance-loop/README.md:317-318, 896.

uv build --wheel uses default build isolation, re-resolving hatchling and uv-dynamic-versioning dependencies from the index at build time. SUPPLY-CHAIN-SECURITY.md requires building without isolated dependency re-resolution; releases use make build (uv build --clear --no-build-isolation).

Fix (pick one): (a) sync locked, then uv build --wheel --clear --no-build-isolation mirroring the Makefile build target; (b) use the published control wheel with a SHA-256 check.
