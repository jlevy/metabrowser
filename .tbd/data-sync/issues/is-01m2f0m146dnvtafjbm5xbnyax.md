---
type: is
id: is-01m2f0m146dnvtafjbm5xbnyax
title: "PR #115 review R1: Benchmark environments inside the git checkout make serve refuse both conditions"
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
created_at: 2026-09-14T03:50:51.781Z
updated_at: 2026-09-14T04:48:09.889Z
started_at: 2026-09-14T03:50:58.552Z
closed_at: 2026-09-14T04:48:09.888Z
close_reason: "Fixed in bbd16783: environments under mktemp -d outside any work tree; require_version/use_wheel demand exact 'metab <wheel version>'; verified _build_provenance accepts both conditions outside and refuses both under .bench/"
resolution: null
duplicate_of: null
---
PR #115 review R1 (High). explorations/performance-loop/README.md:315, 331-352, 386-398, 896-901.

The release-comparison recipe creates the benchmark environments under $PWD/.bench/ inside the git checkout. metabrowser.build_version.source_checkout() runs git rev-parse --show-toplevel from the installed package, which succeeds inside ignored directories, so metab --version reports e.g. "metab 0.9.1 (+153 commits, 8d111f4a)". Control serve then refuses --build-ref (run.py _build_provenance), and candidate attestation fails (devtools/bench_serving.py:349 requires the last token to equal the wheel version). compare_builds environments carry the same annotation.

Fix: create environments outside any git work tree (mktemp -d), keep wheels and reports under .bench/, and make use_wheel fail unless metab --version prints exactly "metab <wheel version>". Verify the version check and install steps in a temp dir (no benchmarks).
