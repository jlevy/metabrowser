---
type: is
id: is-01m1fg54k3nptzd10zqrjhm3tj
title: Reconcile MetaBrowser 0.9.1 registry identity fix onto main
kind: task
status: closed
priority: 1
version: 3
labels: []
dependencies: []
created_at: 2026-09-01T22:06:39.202Z
updated_at: 2026-09-01T22:16:14.251Z
closed_at: 2026-09-01T22:16:14.250Z
close_reason: "Merged PR #104 at 26f417f0 after full local verification, formal senior review, and green exact-head CI on Python 3.12-3.14."
resolution: null
duplicate_of: null
---
Cherry-pick the reviewed schema-4 file-type registry identity fix from release/0.9 onto current main, resolve only semantic conflicts, run the full gate, and land through an exact-head PR so future releases retain the 0.9.1 correction.
