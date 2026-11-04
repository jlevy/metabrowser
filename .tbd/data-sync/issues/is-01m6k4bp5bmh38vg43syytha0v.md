---
type: is
id: is-01m6k4bp5bmh38vg43syytha0v
title: Keep the installed CLI and preview servers on verified stack builds
kind: task
status: in_progress
priority: 1
version: 3
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
hold: null
hold_until: null
created_at: 2026-11-04T11:15:57.733Z
updated_at: 2026-11-04T11:22:52.212Z
started_at: 2026-11-04T11:22:51.935Z
---
Replace the installed metab/metabrowser CLI only with an exact verified wheel; restart the managed-repository and existing-checkout previews on ports8863/8864 after checking their actual process identities. Preserve source, auth, dependency versions and final acceptance receipts. Confirm package hashes, both aliases, readiness and served assets; retain failed attempts and recover the known previous previews on failure. Repeat after final landing/documentation so the installed build matches the final reviewed main. The current a4 offline attempt missed pinned annotated-doc registry metadata; the unchanged048 CLI and both previews were recovered as PIDs15498/15635. Normal official-registry resolution for unchanged pinned requirements is authorized. Revised pre-resolution and guarded retry are in preparation; no source changes are needed.

## Notes

Current verified install is 0.11.1.dev1136+a4e9db6a, exact fd6c38bf wheel. Both metab/metabrowser aliases, all341 installed files, unchanged runtime pins/entrypoints, source_checkout=None, served assets and readiness passed. Managed port8863 PID28360 and checkout port8864 PID28521 are the exclusive listeners; original55898/55935 and recovered15498/15635 are gone. Root's built-in browser observed the new version, a real cached page surviving transient GitHub500 and recovery via Refresh, native12 navigation, and checkout63-file rendering.

The first offline attempt lacked annotated-doc registry metadata and stopped the two authorized old previews before resolution failed. The global048 CLI stayed unchanged; its previews were restored and verified. Attempt2 pre-resolved the same pinned requirements with documented nonmutating uv pip dry-run, then installed with normal official-registry access and no dependency/Python/source-build upgrades. All failed/recovery/success evidence is retained. FINAL acceptance b21a4cfb remained immutable. Success: coordination/installed-a4e9db6a/install-attempt2/INSTALL-ACCEPTANCE.json and POSTINSTALL-CENSUS.json.

Keep open through feature landing and postlanding documentation: the final installed CLI/previews must match the final verified main artifact, with all superseded task servers stopped. No release tag or PyPI publication is implied.
