---
type: is
id: is-01m7p8c8jxvvb9qgs08wea9nk3
title: "Recent folders: persist them in Metabrowser's own configuration, shared by metab and the macOS app, so Open Recent shows every recent folder"
kind: feature
status: closed
priority: 1
version: 8
delegate: claude-code@spud10
labels:
  - linear
dependencies: []
parent_id: is-01m7ksbn803jhw15qjc6beg7qf
hold: null
hold_until: null
created_at: 2026-11-18T02:39:36.028Z
updated_at: 2026-11-20T17:00:12.362Z
started_at: 2026-11-18T02:50:57.554Z
closed_at: 2026-11-18T18:02:30.400Z
close_reason: "Merged in #546 (4e7759c51); owner hand checks 2, 11 and 18 pending on the rebuilt app."
resolution: null
duplicate_of: null
---
Owner, 2026-11-18 in chat: 'Why do I not see all the recent folders in Open recent in the menu on the macos app? Can we save these in our configurations somewhere? It should be compatible with both the CLI and the native app so that the logic can be reused, e.g. for other shells in the future, around the CLI, or for features in the CLI where recently open folders are useful, even if right now it will primarily be a native app feature. Let's have a sub-agent design this out and implement end-to-end to make sure it's consistent.'

## Notes

2026-11-18: PR jlevy/metabrowser#546 (branch claude/recent-folders) holds the design (docs/project/architecture/arch-recent-targets.md, plan Phase 4, Open Modes), the store (recent-targets.yml, format mf01, in the configuration directory), metab --recent / --recent-add / --recent-forget / --recent-clear with a golden, the serve-start record, and the app's Open Recent drawn from metab --recent --json. Owner decisions recorded: configuration directory, no route yet, YAML with mfNN. Later the same day, three more owner decisions implemented on the PR: a restore is not an open (FolderServer starts every server that is not an open's first start with METABROWSER_RECORD_RECENT=0), the Dock menu lists the same targets (applicationDockMenu; NSDocumentController no longer fed), and the opt-out variable METABROWSER_RECORD_RECENT, set by the test run, the serving golden, make macos-run, the WebKit gate, the devtools benchmarks and the performance-loop harnesses. Left for other beads: the mirror target (needs web_url from #540; mb-m4mg), the mode indicator (mb-wup3), the route and switcher (mb-a5ru, mb-9lf4), mfNN for layout.yml and config.yml (mb-3x6y). Neither menu verified in a running app. Awaiting review; do not close until merged.
