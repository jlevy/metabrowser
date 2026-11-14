---
type: is
id: is-01m76h3hxc44pkpkv2k8syp145
title: Rebuild the v1 app and check it end to end
kind: task
status: in_progress
priority: 1
version: 10
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
labels: []
dependencies:
  - type: blocks
    target: is-01m76cd0j37s7vbfjfwtw1ey7n
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
child_order_hints:
  - is-01m78ajtjtaaygpsm948na1jn8
  - is-01m78fd7rt1t7eww5sqks2xgbn
  - is-01m7dnv78aff7tenytbdvs2dav
created_at: 2026-11-12T00:04:16.939Z
updated_at: 2026-11-14T18:41:47.784Z
---
After the review is addressed: rebuild the dev and release-rehearsal bundles and DMGs; with fresh app settings on the build Mac, run Flow 1 (uv tool install metabrowser, then the app from the DMG) and Flow 2 (the app with no metab, the copyable commands, continuing when metab appears), an old metab, a launch from the DMG, opening a file, recents, tabs, session restore, and crash recovery, plus every manual check the implementation beads recorded; record the results in the PR. Not covered, and named as v1's limitation: other macOS versions, standard accounts, and no Command Line Tools (mb-5fp7), and Developer ID and Gatekeeper checks (mb-e9fm).

## Notes

2026-11-11, the user: validate end to end with Metabrowser itself on this repository: the app opens the repo, and its Pulls tab shows #341 and each stacked v1 PR as open PRs, whose conversation, changes, and rendered diffs load and read correctly. Checked at bc6477a5: /pulls, /pull/341, and /pull/341/files answer 200 in the running app.

2026-11-12, at review build cd72c7b (stack top 84cf13f6 plus #367), installed to /Applications as dev 0.1.0 (2682), codesign verified. On launch the build could not decode the setup an older build saved (FileFingerprint gained mode), ran discovery, took ~/.local/bin/metab 0.12.1.dev38, and every window failed with 'No such option: --exit-on-eof': filed as mb-sugi, fixed on #377. With the runtime pointed at the review build's metab (METABROWSER_METAB, then saved as source environment), session restore reopened three windows, each with its own server; /api/identity names the window; the Pulls list shows 17 open PRs including #341 and every stacked v1 PR; a refresh of #341 brought its detail and files to head 2343e79d (128 files, 8 reviews, 8 comments, 10 checks); /pull/341/files renders the 128-file list with Rendered and Source toggles. Not yet run: Flow 1 and Flow 2 with fresh settings, a DMG launch, crash recovery.

2026-11-14, at main c098e6a8 (dev and release 0.1.0 build 3258, ad hoc signed, hardened runtime, not notarized): `make app`, `make dmg` and `make release NOTARIZE=0` built; both DMGs pass check-dmg; the release DMG's executable is byte-identical to build/release's. Tested a renamed copy of the release DMG's app ("Metabrowser E2E", release bundle id, defaults backed up, cleared and restored) so the dev app's session.json was never touched. Passed: Flow 1a (PyPI 0.12.0 rejected as designed; a real Flow 1 needs 0.12.1 published), Flow 1b (main's metab adopted ~3 s after install, waiting folder opened itself), Flow 1c (real HOME: the old ~/.local/bin/metab skipped, UV_TOOL_BIN_DIR copy used), Flow 2 (steps advance as uv then metab appear), old metab rejected (0.12.0 and 0.12.1.dev38; a /tmp metab refused as world-writable; 59 setup/version unit tests pass), DMG launch of the copy (diskImage detected, notice shown, restore ran behind it), opening files (same window, one server; a file outside opens its folder in a new window; /dev/null alert), tabs (newFolderPlacement tabs/windows), page discard (WebContent count flat), session restore (servers started one at a time, front first; after a crash; with restore off), protected location and folder-replaced-by-link (servers wait for their tabs), app SIGKILL (servers gone in ~100 ms), server crash and hang (5 s health check, SIGTERM then SIGKILL ~10.5 s), orderly quit with an alert or sheet open, stderr in the server log, restart offer after an upgrade (with corrected stand-ins), print and drops in the app's web-view class (webkit-gate --checks). Not runnable from a shell: Open Recent (macOS's recents folder is not readable here). Needs the user's eyes or clicks: the setup screen text, Copy buttons and Choose metab…, the old-metab message, the DMG notice's buttons, Merge All Windows and the system Prefer tabs setting, the visual reload of a discarded tab, close-every-window-then-quit restore, selecting waiting tabs, Retry and File > Restart Server, Restart Servers, print and drops on the built app, the About box and Dock icon, and one launch of the unmodified release DMG with the dev app quit. Scripts for those: the app-e2e-check worktree's attic/e2e/bin/manual-checks.sh (setup|old|dmg|upgrade|everyday) and attic/e2e/bin/planned-window.sh. Found: check-setup-flows.sh's old-metab stand-ins predate the --exit-on-eof probe (filed as its own bead), and the README's "Checking by Hand" step 3 expects INFO: lines metab no longer prints. mb-mc85 was this run's scratch HOME, not a bug.
