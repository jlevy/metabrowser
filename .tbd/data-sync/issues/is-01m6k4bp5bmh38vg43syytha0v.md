---
type: is
id: is-01m6k4bp5bmh38vg43syytha0v
title: Keep the installed CLI and preview servers on verified stack builds
kind: task
status: open
priority: 1
version: 1
labels: []
dependencies: []
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
created_at: 2026-11-04T11:15:57.733Z
updated_at: 2026-11-04T11:15:57.733Z
---
Replace the installed metab/metabrowser CLI only with an exact verified wheel; restart the managed-repository and existing-checkout previews on ports8863/8864 after checking their actual process identities. Preserve source, auth, dependency versions and final acceptance receipts. Confirm package hashes, both aliases, readiness and served assets; retain failed attempts and recover the known previous previews on failure. Repeat after final landing/documentation so the installed build matches the final reviewed main. The current a4 offline attempt missed pinned annotated-doc registry metadata; the unchanged048 CLI and both previews were recovered as PIDs15498/15635. Normal official-registry resolution for unchanged pinned requirements is authorized. Revised pre-resolution and guarded retry are in preparation; no source changes are needed.
