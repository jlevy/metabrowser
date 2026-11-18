---
type: is
id: is-01m7pf8zxej09pn6zygh242t14
title: "Checkout branch chooser: in folder mode (an existing checkout) show the same branch and tag chooser as a mirror; picking another ref views it read-only from the checkout's own .git as a pinned revision, without touching the working tree; picking the checkout's branch returns to the live working tree"
kind: feature
status: in_progress
priority: 1
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7ksbn803jhw15qjc6beg7qf
hold: null
hold_until: null
created_at: 2026-11-18T04:40:08.878Z
updated_at: 2026-11-18T04:41:02.678Z
started_at: 2026-11-18T04:41:02.677Z
---
Owner, 2026-11-18 in chat: 'Why do I still not see a branch chooser anymore? ... I'm looking at a local repo ~/wrk/aisw/tradekb'. The chooser (static/source-ref-selector.js, #236/mb-eezo) renders only for a pin served from a mirror (server.py: git_pin and mirror_session). Owner chose: view the picked ref read-only from the checkout's .git as a pinned revision; never git checkout. Coordinate with Open Modes (mb-wup3, plan-2026-11-02-pr-review-mirror-and-checkout.md) and the pin model (/api/source/pin, #511's View on branch).

## Notes

2026-11-18 owner (chat): 'In general, when running in mirror mode, the working copy should never have changes. When running in file or folder mode, we would want to be able to view all the other branches as if it's in mirror mode, but it would be all within the git directory or within our own cache for that directory.' Governing rule for both modes; relayed to the implementing agent.
