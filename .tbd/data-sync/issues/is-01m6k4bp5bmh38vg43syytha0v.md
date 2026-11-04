---
type: is
id: is-01m6k4bp5bmh38vg43syytha0v
title: Keep the installed CLI and preview servers on verified stack builds
kind: task
status: closed
priority: 1
version: 6
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
hold: null
hold_until: null
created_at: 2026-11-04T11:15:57.733Z
updated_at: 2026-11-04T17:21:04.018Z
started_at: 2026-11-04T11:22:51.935Z
closed_at: 2026-11-04T17:21:04.018Z
close_reason: Completed against actual final main https://github.com/jlevy/metabrowser/commit/db52ec09cf839269da3a56fd396e44f3092995a9; final independent integration review and all nine main CI jobs passed. Original evidence retains its execution pins; genuine future and release scope remains separate.
resolution: null
duplicate_of: null
---
Replace the installed metab/metabrowser CLI only with an exact verified wheel; restart the managed-repository and existing-checkout previews on ports8863/8864 after checking their actual process identities. Preserve source, auth, dependency versions and final acceptance receipts. Confirm package hashes, both aliases, readiness and served assets; retain failed attempts and recover the known previous previews on failure. Repeat after final landing/documentation so the installed build matches the final reviewed main.

## Notes

Current verified install is 0.11.1.dev1136+a4e9db6a, exact fd6c38bf wheel. Both metab/metabrowser aliases, all341 installed files, unchanged runtime pins/entrypoints, source_checkout=None, served assets and readiness passed. Managed port8863 PID28360 and checkout port8864 PID28521 are the exclusive listeners; original55898/55935 and recovered15498/15635 are gone. Root's built-in browser observed the new version, a real cached page surviving transient GitHub500 and recovery via Refresh, native12 navigation, and checkout63-file rendering.

The first offline attempt lacked annotated-doc registry metadata and stopped the two authorized old previews before resolution failed. The global048 CLI stayed unchanged; its previews were restored and verified. Attempt2 pre-resolved the same pinned requirements with documented nonmutating uv pip dry-run, then installed with normal official-registry access and no dependency/Python/source-build upgrades. All failed/recovery/success evidence is retained. FINAL acceptance b21a4cfb remained immutable. Success: coordination/installed-a4e9db6a/install-attempt2/INSTALL-ACCEPTANCE.json and POSTINSTALL-CENSUS.json.

Keep open through feature landing and postlanding documentation: the final installed CLI/previews must match the final verified main artifact, with all superseded task servers stopped. No release tag or PyPI publication is implied.

2026-11-04 completion: all 21 feature PRs and follow-ups #297/#298 are merged at https://github.com/jlevy/metabrowser/commit/db52ec09cf839269da3a56fd396e44f3092995a9. Final integration review https://github.com/jlevy/metabrowser/pull/298#pullrequestreview-5772391263 is clean; all nine actual-main CI jobs passed at https://github.com/jlevy/metabrowser/actions/runs/41868009781. Full make verify and normal push each passed 4,786 Python tests, nine expected skips and 378 golden commands at tree-identical commit 3f5bd2d3. Fresh final wheel passed eight public live tests, six installed regressions and 21 UI checks; root seven-image visual and actual installed-server manual checks passed. Both global aliases and previews use verified 0.11.1.dev1154+db52ec09, all 341 package bytes match, old servers are stopped, portable/host skill is current, and production cache admission passed after volume permissions were restored. Maintained documentation, all 37 plans, 124 mapped pointers, six historical pointer retirements and 25 current-status notes are reconciled. 107 scoped delivered tasks are closed. Genuine partial/future, quiet-performance and release work stays open; draft #247, both WIPs, issue relationships and protected config are preserved. No release tag or publication is implied.
