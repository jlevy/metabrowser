---
type: is
id: is-01m7p8hjk6jd7ckmr0fnjmpqca
title: "Open modes: say plainly whether a view is folder mode (the reader's existing checkout) or mirror mode (Metabrowser's own cached copy), with a small indicator in the UI and the app, and the behaviors that differ"
kind: feature
status: open
priority: 1
version: 3
labels: []
dependencies: []
parent_id: is-01m7ksbn803jhw15qjc6beg7qf
created_at: 2026-11-18T02:42:30.117Z
updated_at: 2026-11-18T04:41:18.687Z
---
Owner, 2026-11-18 in chat: 'we should have clarity on the mode that something is opened in, either folder mode (an existing checkout) or a mirror mode (metabrowser's own cached copy). In both cases, Metabrowser may maintain a cached copy, but some behaviors are different. If we want to know that the actual files are changed, having two modes would be best. And we could indicate with a small indicator which it is.' Also the File menu the owner specified: Open Folder… (works for GitHub folders already checked out), Open URL… (supported GitHub URLs only, mb-m4mg), Open Recent (any recent item, mb-40k4). Design lives in the recents plan text (mb-40k4) and plan-2026-11-02-pr-review-mirror-and-checkout.md.

## Notes

2026-11-18 owner (chat): indicator icons: mirror mode = the GitHub icon, perhaps overlaid with a cloud if a good icon can be made; folder mode = a folder icon. Relayed to the recents/design agent (mb-40k4) for the plan's indicator section.
2026-11-18 owner: folder mode is a superset of mirror mode (any ref viewed as a mirror would) plus the true working directory, where folder-only features (local modified files etc.) activate. See mb-8ob8.
