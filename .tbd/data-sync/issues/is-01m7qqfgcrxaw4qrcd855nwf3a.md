---
type: is
id: is-01m7qqfgcrxaw4qrcd855nwf3a
title: "present --dry-run: take the link on stdin, so the process table never shows a link as sent"
kind: task
status: open
priority: 3
version: 2
spec_path: docs/project/specs/active/plan-2026-11-17-open-anything-from-cli-and-app.md
labels: []
dependencies: []
parent_id: is-01m7nnxhaqce1g2ewec3wbaf7e
created_at: 2026-11-18T16:22:45.395Z
updated_at: 2026-11-20T17:22:42.662Z
---
From review C11 on PR #539: the app runs metab LINK --present --dry-run --format json with the link as sent, so a raw.githubusercontent.com link's ?token= is in the process table (readable by another account through setuid /bin/ps) for the dry run's lifetime, about 0.3 s and at most PresentDryRun.timeout. The server's arguments and log carry only the canonical handoff. PR #539 corrected the two sentences that said the process table never shows it (PresentPlan.swift, arch-macos-app.md Trust Boundary). Closing the gap needs --present to read its target from stdin (or a file descriptor), and the app to pass it there.
