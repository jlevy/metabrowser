---
type: is
id: is-01m76cd0j37s7vbfjfwtw1ey7n
title: "Native app v1: a usable app that meets the tbd coding guidelines"
kind: feature
status: open
priority: 1
version: 6
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
labels: []
dependencies: []
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
created_at: 2026-11-11T22:42:03.958Z
updated_at: 2026-11-12T01:05:15.513Z
---
Milestone for apps/macos on claude/macos-app-spike (jlevy/metabrowser#341, merged only when the user says so). Done when every bead this depends on is closed, an independent review of the upgraded app is addressed, and the app is rebuilt and checked end to end. Out of scope here, with reasons: warm folders (mb-e7im, blocked on mb-z46o), host mode and the agent front door (Phase 3), roots and MCP (Phase 4), the optional app-private runtime (mb-lrcd), and a Developer ID release (needs the owner's certificate).

## Notes

2026-11-11: the user asked for the remaining work to run in parallel ("continue with all the other work in parallel"). Four agents work at once on branches cut from claude/macos-app-spike at 8b0603f7, each in its own worktree: claude/v1-robustness (mb-nns2, mb-1poj, mb-hwa9, mb-9xl0), claude/v1-setup (mb-su30, mb-895s, mb-3n79, mb-2hqz), claude/v1-everyday (mb-tssz, mb-cqxd, mb-ssed, mb-lc8c), and claude/v1-webkit-gate (mb-gvtw). The coordinator merges them into the app branch one at a time, robustness first; the recorded dependencies now give that merge order. mb-x4fy (CI) is in; the first run failed on a wrong uv checksum, fixed in b0310862.

2026-11-11: two user decisions to carry into the plan spec on main when the milestone lands: the app requires macOS 26 and Swift 6.3 (bc6477a5; CI runs macos-26 only), and the dev build is also named Metabrowser, with the canary icon and an About panel that names the build (mb-9xl0). The plan spec still says macOS 15 and "Metabrowser Dev" in places.

2026-11-11, the user: keep #341 open ("I want to see it as an open PR for now, but let's keep working as a stack") and "I want to be able to validate and test everything end-to-end on metabrowser itself on this repo including 341 as an open PR". So the v1 work lands as a native GitHub stack on #341, not merged into it: main <- #341 (claude/macos-app-spike) <- claude/v1-robustness <- claude/v1-webkit-gate <- claude/v1-setup <- claude/v1-everyday, each upper branch merging the one below, linked with gh stack link. Nothing merges until the user says so; the user earlier authorized landing everything as long as the CLI is not destabilized, then asked to hold.

2026-11-11, the user: "I want our build here to be the latest code so I can review and see how it looks accurately." The running dev app now comes from a local integration branch, claude/app-review-build (worktree .claude/worktrees/app-review-build, not a PR, not pushed): the app branch plus every stacked v1 layer as it lands plus other in-flight branches the user wants to see (now claude/overview-compact-type-summary). The app saved runtime points at that checkout metab. Re-merge and relaunch whenever any of those branches moves. PR branches stay clean.
