---
type: is
id: is-01m7pf8zxej09pn6zygh242t14
title: "Checkout branch chooser: in folder mode (an existing checkout) show the same branch and tag chooser as a mirror; picking another ref views it read-only from the checkout's own .git as a pinned revision, without touching the working tree; picking the checkout's branch returns to the live working tree"
kind: feature
status: in_progress
priority: 1
version: 6
delegate: claude-code@spud10
labels: []
dependencies:
  - type: blocks
    target: is-01m6wpacpj9wtx02rt1g8kx49m
parent_id: is-01m7ksbn803jhw15qjc6beg7qf
hold: null
hold_until: null
created_at: 2026-11-18T04:40:08.878Z
updated_at: 2026-11-18T06:18:19.167Z
started_at: 2026-11-18T04:41:02.677Z
---
Owner, 2026-11-18 in chat: 'Why do I still not see a branch chooser anymore? ... I'm looking at a local repo ~/wrk/aisw/tradekb'. The chooser (static/source-ref-selector.js, #236/mb-eezo) renders only for a pin served from a mirror (server.py: git_pin and mirror_session). Owner chose: view the picked ref read-only from the checkout's .git as a pinned revision; never git checkout. Coordinate with Open Modes (mb-wup3, plan-2026-11-02-pr-review-mirror-and-checkout.md) and the pin model (/api/source/pin, #511's View on branch).

## Notes

2026-11-18 owner (chat): 'In general, when running in mirror mode, the working copy should never have changes. When running in file or folder mode, we would want to be able to view all the other branches as if it's in mirror mode, but it would be all within the git directory or within our own cache for that directory.' Governing rule for both modes; relayed to the implementing agent.
2026-11-18 owner (chat): 'when we're browsing main or a main branch (whether it's the mirrored main branch or the actual local file), a local folder is like a mirror in all cases, or it can be, as the most simple version. It also has the true working directory, as we may wish to have additional features like local modified files and so on only activate for folder mode.' Model: folder mode = mirror behavior for every ref (current branch included, as a committed revision) + a separate working-directory view where folder-only features live.
2026-11-18 origin: this implements bead mb-itzy (recorded 2026-11-07: 'Files should make both a live working tree and read-only cached branch snapshots accessible'). The model it builds is docs/project/architecture/arch-open-modes.md (mb-lsx1, PR #558); mb-itzy now depends on this bead. The title's last clause is stale: the checked-out branch, chosen as a ref, shows its commit, and the Working tree row returns to the live files.
