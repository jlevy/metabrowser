---
type: is
id: is-01m7p8e0d30md4n29d9q7r5taw
title: "macOS app: File > Open URL… that opens a pasted GitHub repository, pull request, or file URL as the web UI and metab would, and refuses any other URL with a clean message"
kind: feature
status: in_progress
priority: 1
version: 4
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m7ksbn803jhw15qjc6beg7qf
hold: null
hold_until: null
created_at: 2026-11-18T02:40:33.186Z
updated_at: 2026-11-18T02:57:43.927Z
started_at: 2026-11-18T02:41:29.510Z
---
Owner, 2026-11-18 in chat: 'let's have it support an Open URL... that initially, only opens GitHub URLs and gives a clean error message if it's not a supported GitHub URL, but otherwise it should open repos, files, or PRs just like the web or CLI app would'. Builds on #539 (mb-87j0: the app opens GitHub links through metab --present, #540). Owned by the Local build review session's lane.

## Notes

2026-11-18 owner direction (via the coordinator): the File menu is "Open Folder…" (works for GitHub folders already checked out), "Open URL…" (supported GitHub URLs only, for now), and "Open Recent" (any recent item, GitHub targets included; the recents plan mb-40k4 drops #539 rule that repository windows stay out of Open Recent). Open modes are explicit (mb-wup3): folder mode = an existing checkout, mirror mode = Metabrowser cached copy, with a small indicator of which is in use. Which mode a GitHub URL opens in when a local checkout exists follows plan-2026-11-02-pr-review-mirror-and-checkout.md as the recents agent writes it; wait for that branch before building the mode choice.
2026-11-18 recents plan (branch claude/recent-folders 0e0a5cd8c; arch-recent-targets.md, app plan Phase 4, mirror-and-checkout plan "Open Modes"): Open URL… is always mirror mode, never the checkout; Open Folder… on a checkout is folder mode. Open URL… may offer recent mirror entries (`metab --recent --json`, shown only when Info.plist has MetabrowserOpensURLs). This lane also records each entry canonical target URL (PR, ref or file) via ProviderUrlReducer.web_url from #540: a few lines in run_serve_pin plus one store field. Entry = {mode, root, opened_at}, key (mode, root) = SessionRoot.key; no ref/PR/pin in the key.
