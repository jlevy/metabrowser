---
type: is
id: is-01m7p8ghqfsdt3ya1hxjsbmxx6
title: "Diff summary brief line: show its whole words as a tooltip while cut short"
kind: task
status: open
priority: 3
version: 1
labels: []
dependencies: []
parent_id: is-01m7n6v8n050erzeb13c5tasar
created_at: 2026-11-18T02:41:56.462Z
updated_at: 2026-11-18T02:41:56.462Z
---
The PR page's cached brief line (pull-summary-brief.js, #536) is cut short at narrow widths like the Diff summary's header, but unlike the header (tipWhenCut) it has no tooltip with its whole words while cut. Found by review A on #536 (A7). Fix: reuse the header's cut-short tooltip for .github-pull-summary-brief; check in the Chrome summary-wait part at 360 px.
