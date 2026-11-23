---
type: is
id: is-01m83qdh00bp69n8xc05yz2gv8
title: "CI: a slow PyPI download times out stack-integration goldens+serial"
kind: bug
status: in_progress
priority: 2
version: 2
delegate: claude-code@spud10
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-23T08:12:33.660Z
updated_at: 2026-11-23T08:13:34.039Z
started_at: 2026-11-23T08:13:34.033Z
---
Run 45134271894 (PR #744, head aebb11f90): the 'stack-integration (-k test-goldens test-serial)' job hit its 7-minute timeout-minutes and was cancelled, failing ci-ok. Mechanism: uv sync printed 'Prepared 67 packages in 2m 45s' where sibling runs on the same main SHA and same setup-uv cache key took 1.5-2.05 s (runs 45134272552, 45131639897). setup-uv restores a pruned cache (key ...-pruned-...), so every job downloads ~100 MB of wheels (nodejs-wheel-binaries 57.9 MiB, basedpyright, ruff...) from PyPI; one slow download cost ~2m43s. The job now routinely takes 5-6 min (goldens 180-245 s for 135 files, serial ~85 s) against a 7 min timeout whose comment cites 1.2-4.3 min measurements, so ~1.5 min headroom absorbs no network stall. Fix candidates: keep wheels in the Actions cache (setup-uv prune-cache: false, measuring cache size and restore time), and/or re-measure and reset the timeout with the new numbers beside it. Done: a PR from main with measurements in the ci.yml comment.
