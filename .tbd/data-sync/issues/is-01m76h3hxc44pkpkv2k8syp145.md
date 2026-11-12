---
type: is
id: is-01m76h3hxc44pkpkv2k8syp145
title: Rebuild the v1 app and check it end to end
kind: task
status: open
priority: 1
version: 6
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
labels: []
dependencies:
  - type: blocks
    target: is-01m76cd0j37s7vbfjfwtw1ey7n
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
child_order_hints:
  - is-01m78ajtjtaaygpsm948na1jn8
created_at: 2026-11-12T00:04:16.939Z
updated_at: 2026-11-12T16:49:44.572Z
---
After the review is addressed: rebuild the dev and release-rehearsal bundles and DMGs; with fresh app settings on the build Mac, run Flow 1 (uv tool install metabrowser, then the app from the DMG) and Flow 2 (the app with no metab, the copyable commands, continuing when metab appears), an old metab, a launch from the DMG, opening a file, recents, tabs, session restore, and crash recovery, plus every manual check the implementation beads recorded; record the results in the PR. Not covered, and named as v1's limitation: other macOS versions, standard accounts, and no Command Line Tools (mb-5fp7), and Developer ID and Gatekeeper checks (mb-e9fm).

## Notes

2026-11-11, the user: validate end to end with Metabrowser itself on this repository: the app opens the repo, and its Pulls tab shows #341 and each stacked v1 PR as open PRs, whose conversation, changes, and rendered diffs load and read correctly. Checked at bc6477a5: /pulls, /pull/341, and /pull/341/files answer 200 in the running app.

2026-11-12, at review build cd72c7b (stack top 84cf13f6 plus #367), installed to /Applications as dev 0.1.0 (2682), codesign verified. On launch the build could not decode the setup an older build saved (FileFingerprint gained mode), ran discovery, took ~/.local/bin/metab 0.12.1.dev38, and every window failed with 'No such option: --exit-on-eof': filed as mb-sugi, fixed on #377. With the runtime pointed at the review build's metab (METABROWSER_METAB, then saved as source environment), session restore reopened three windows, each with its own server; /api/identity names the window; the Pulls list shows 17 open PRs including #341 and every stacked v1 PR; a refresh of #341 brought its detail and files to head 2343e79d (128 files, 8 reviews, 8 comments, 10 checks); /pull/341/files renders the 128-file list with Rendered and Source toggles. Not yet run: Flow 1 and Flow 2 with fresh settings, a DMG launch, crash recovery.
