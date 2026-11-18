---
type: is
id: is-01m7p8c8jxvvb9qgs08wea9nk3
title: "Recent folders: persist them in Metabrowser's own configuration, shared by metab and the macOS app, so Open Recent shows every recent folder"
kind: feature
status: in_progress
priority: 1
version: 5
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7ksbn803jhw15qjc6beg7qf
hold: null
hold_until: null
created_at: 2026-11-18T02:39:36.028Z
updated_at: 2026-11-18T03:38:01.662Z
started_at: 2026-11-18T02:50:57.554Z
---
Owner, 2026-11-18 in chat: 'Why do I not see all the recent folders in Open recent in the menu on the macos app? Can we save these in our configurations somewhere? It should be compatible with both the CLI and the native app so that the logic can be reused, e.g. for other shells in the future, around the CLI, or for features in the CLI where recently open folders are useful, even if right now it will primarily be a native app feature. Let's have a sub-agent design this out and implement end-to-end to make sure it's consistent.'

## Notes

2026-11-18: PR jlevy/metabrowser#546 (branch claude/recent-folders) holds the design (docs/project/architecture/arch-recent-targets.md, plan Phase 4, Open Modes), the store (recent-targets.yml, format mf01, in the configuration directory), metab --recent / --recent-add / --recent-forget / --recent-clear with a golden, the serve-start record, and the app's Open Recent drawn from metab --recent --json. Owner decisions recorded: configuration directory, no route yet, YAML with mfNN. Left for other beads: the mirror target (needs web_url from #540; mb-m4mg), the mode indicator (mb-wup3), the route and switcher (mb-a5ru, mb-9lf4), mfNN for layout.yml and config.yml (mb-3x6y). Not verified live in a running app. Awaiting review; do not close until merged.
