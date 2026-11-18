---
type: is
id: is-01m7p8hjk6jd7ckmr0fnjmpqca
title: "Open modes: say plainly whether a view is folder mode (the reader's existing checkout) or mirror mode (Metabrowser's own cached copy), with a small indicator in the UI and the app, and the behaviors that differ"
kind: feature
status: open
priority: 1
version: 5
labels: []
dependencies: []
parent_id: is-01m7ksbn803jhw15qjc6beg7qf
created_at: 2026-11-18T02:42:30.117Z
updated_at: 2026-11-18T04:45:36.337Z
---
Owner, 2026-11-18 in chat: 'we should have clarity on the mode that something is opened in, either folder mode (an existing checkout) or a mirror mode (metabrowser's own cached copy). In both cases, Metabrowser may maintain a cached copy, but some behaviors are different. If we want to know that the actual files are changed, having two modes would be best. And we could indicate with a small indicator which it is.' Also the File menu the owner specified: Open Folder… (works for GitHub folders already checked out), Open URL… (supported GitHub URLs only, mb-m4mg), Open Recent (any recent item, mb-40k4). Design lives in the recents plan text (mb-40k4) and plan-2026-11-02-pr-review-mirror-and-checkout.md.

## Notes

2026-11-18 owner (chat): indicator icons: mirror mode = the GitHub icon, perhaps overlaid with a cloud if a good icon can be made; folder mode = a folder icon. Relayed to the recents/design agent (mb-40k4) for the plan's indicator section.
2026-11-18 owner: folder mode is a superset of mirror mode (any ref viewed as a mirror would) plus the true working directory, where folder-only features (local modified files etc.) activate. See mb-8ob8.
2026-11-18 owner (chat): three modes: pure folder (no repo; all Git features off), GitHub folder mode (a folder inside a repo: walk up to the nearest enclosing repo, which becomes the open repo), and mirror. A folder or file not in any repo opens as requested; a file with no repo anywhere opens its enclosing folder. Fable design review (in progress) folds this in.
2026-11-18 owner (chat): 'If it's a folder that's not a GitHub repo and not enclosed in anything, it should open the folder itself. And all Git features would just be disabled.' 'All of this should be carefully designed and reviewed to be thorough.' Process: (1) Fable design review + drift audit (running); (2) a docs-only design PR putting the model in one canonical home and fixing every drifting doc; (3) an independent Fable review of that PR; (4) only then do mb-8ob8, #546, mb-m4mg and the indicator implementations finalize against it.
