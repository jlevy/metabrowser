---
type: is
id: is-01m7k5rv09cpqqjzfdt2vk4qdp
title: "macOS app: a translocated-launch harness for a downloaded release (LAUNCH=1)"
kind: task
status: in_progress
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-11-16-macos-app-publishing.md
delegate: claude-code@vm
labels: []
dependencies:
  - type: blocks
    target: is-01m7k2xcrjxtgfe2mepxas1434
parent_id: is-01m7k1vctj6d370jg7hqdps4hk
hold: null
hold_until: null
created_at: 2026-11-16T21:56:19.080Z
updated_at: 2026-11-17T07:58:06.066Z
started_at: 2026-11-17T07:58:06.066Z
---
Phase 1 of the publishing plan, split from mb-xd4o (PR #485 A20). make macos-check-release TAG=macos-vX.Y.Z LAUNCH=1, after the automated download check passes: copy the app out of the downloaded image into a scratch Downloads folder, still quarantined; open it and wait for the person at the Mac to answer Gatekeeper; check that the process runs from an /AppTranslocation/ path and shows the launch notice; quit, relaunch, and record whether it is still translocated; move it and check a launch from the new place, recording whether a move from Terminal clears translocation as a move in Finder does. It runs the unmodified release bundle, whose identity is the installed release's, so it refuses while a release copy is running, backs up and restores that identity's defaults, the shared session.json and its recent-documents list, and unregisters each scratch copy with lsregister -u, as check-setup-flows.sh does (PR #485 A17). On a VM or a second account, preferred, it needs none of that. Interactive by design: it is never run in CI. Done when the owner has run it on the first draft release and its output is in the release record.
