---
type: is
id: is-01m3zcr1v9pb3jw5mbeyr990m4
title: "Root overview: a below-the-fold README image is fetched earlier than on 0.11.0"
kind: bug
status: closed
priority: 3
version: 3
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m36k3w9vgwy97c9hcj2sqrs5
hold: null
hold_until: null
created_at: 2026-10-02T22:46:19.240Z
updated_at: 2026-11-01T17:32:56.912Z
started_at: 2026-11-01T16:21:31.694Z
closed_at: 2026-11-01T17:32:56.911Z
close_reason: "Not a product change. Established on 2026-11-01: on v0.11.0 and v0.12.0 alike, whether collapsing File Overview fetches a README image just past Chrome's 1,250 px lazy margin depends on whether two zero-height images land within one frame, and whether the README paints before File Overview depends on rollup timing. Fetched matched a frame showing the photo within the margin in 136 of 136 runs; forcing the timing gives the same rates on both builds. The old 5-of-6 asymmetry is attributed to load at capture time, which is inferred, not measured. The harness rule F4-lazy-image-fetched-earlier in browser/rules.mjs still flags this race and should be reclassified."
resolution: canceled
duplicate_of: null
---
Browser differential finding F4 (tip f62c16b1): with File Overview collapsed, images/photo.jpg about 1,300 px below the viewport was fetched by the stack and not by 0.11.0 in 5 of 6 captures; an isolated probe fetched it on neither build. Related: the README panel painted before File Overview and was pushed down 7 of 90 root loads against 2 of 90. No mechanism established. Reproduce with the browser harness: run.sh <main> <tip> --only '^3\.view-folders@' --skip-step9, step 04-panel-collapsed (harness in metabrowser-landing-gate-evidence/browser beside the checkout).
