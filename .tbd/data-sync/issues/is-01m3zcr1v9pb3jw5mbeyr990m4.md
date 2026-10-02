---
type: is
id: is-01m3zcr1v9pb3jw5mbeyr990m4
title: "Root overview: a below-the-fold README image is fetched earlier than on 0.11.0"
kind: bug
status: open
priority: 3
version: 1
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
labels: []
dependencies: []
parent_id: is-01m36k3w9vgwy97c9hcj2sqrs5
created_at: 2026-10-02T22:46:19.240Z
updated_at: 2026-10-02T22:46:19.240Z
---
Browser differential finding F4 (tip f62c16b1): with File Overview collapsed, images/photo.jpg about 1,300 px below the viewport was fetched by the stack and not by 0.11.0 in 5 of 6 captures; an isolated probe fetched it on neither build. Related: the README panel painted before File Overview and was pushed down 7 of 90 root loads against 2 of 90. No mechanism established. Reproduce with the browser harness: run.sh <main> <tip> --only '^3\.view-folders@' --skip-step9, step 04-panel-collapsed (harness in metabrowser-landing-gate-evidence/browser beside the checkout).
