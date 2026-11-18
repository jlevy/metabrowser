---
type: is
id: is-01m7pk99cegx2xz0sc5wwddsdj
title: "One canonical design for open modes: docs/project/architecture/arch-open-modes.md (plain folder, repository folder, mirror; working directory vs revision views; root resolution with guarded walk-up), and bring every drifting plan and guide into line with it (docs only)"
kind: task
status: open
priority: 1
version: 1
labels: []
dependencies: []
parent_id: is-01m7ksbn803jhw15qjc6beg7qf
created_at: 2026-11-18T05:50:12.878Z
updated_at: 2026-11-18T05:50:12.878Z
---
From the Fable design review of 2026-11-18 (attic/coord/design-review-open-modes.md in the coordinator worktree) and the owner's answers the same day: Q1 any Git repo; Q2 guarded walk-up (+ --exact-root; data modes exact); Q3 Pulls and toggle stay on a revision; Q4 Open URL = mirror, offer the checkout, switch an open window; Q5 View on branch = head as a revision, working-tree copy a separate action; Q6 indicator by the root name, cloud fallback; Q8 a file joins the most specific open folder, never above its repo root; Q9 revisions inert; terminology per Git (working tree / worktree). Implements mb-itzy's 2026-11-07 ask. Blocks mb-8ob8, #546's mode text, mb-m4mg, mb-wup3.
