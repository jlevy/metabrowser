---
type: is
id: is-01m7p8a5sz6cwk826efzzwfhpy
title: "Drawn from disk: exercise the repository_labels fallback with a label named without a color"
kind: task
status: open
priority: 3
version: 1
labels: []
dependencies: []
parent_id: is-01m7n6v8n050erzeb13c5tasar
created_at: 2026-11-18T02:38:27.646Z
updated_at: 2026-11-18T02:38:27.646Z
---
Review of #528 (A2). tests/test_github_drawn_from_disk.py's label row reads the labels route, which only the CLI asks for; the page colors a chip from its record and, for a label a record names without a color (records cached before label colors), from the pull envelope's repository_labels. No fixture record names an uncolored label, so a regression in labels_for or repository_labels passes the module. Give a fixture record or core an uncolored label and assert repository_labels with no gh or Git spawned.
