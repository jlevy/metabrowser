---
type: is
id: is-01m7hhr43k5rc7ytbxg1vx031s
title: "Release 0.13: app PR B (isReleased, floor 0.13.0, docs), WebKit gate rerun, signed+notarized DMG, macos-v0.1.0"
kind: task
status: open
priority: 1
version: 6
labels: []
dependencies: []
parent_id: is-01m7hgpc9550w78kmwqsvv64xh
created_at: 2026-11-16T06:47:09.682Z
updated_at: 2026-11-23T05:13:29.469Z
---

## Notes

2026-11-17 owner decisions in chat: (1) build the publishing plan's Phase 1 tooling beads (mb-qu6j, mb-4hwg, mb-tfap, mb-xd4o, mb-u36j, mb-63cx) now, before macos-v0.1.0, as the plan's rollout requires; (2) Q8: the agent creates the macos-v0.1.0 tag after the owner approves the image's SHA-256 and notes. Q6 (arm64 only) and Q7 (notarize twice) take the plan's recommendations. PR B (floor 0.13.0, isReleased) merges after the PyPI publish is verified.

2026-11-17 coordinator: Q8 timing. The owner chose who (the agent), not when, so the plan's order stands: after the owner approves RELEASE_COMMIT and the notes, the agent creates macos-v0.1.0 on that commit before the build, because gh release create --verify-tag needs the tag; the owner approves the image's SHA-256 before the draft is published. Tooling is in the stacked PRs #509 (mb-qu6j, mb-tfap) and #510 (mb-4hwg, mb-xd4o, mb-u36j, mb-63cx).

2026-11-20 audit: absorbs mb-0wqe (set MetabRequirement.isReleased when the release publishing the app's floor is out; closed as a duplicate). The floor has since moved from 0.12.1 to 0.13.0 (skills/metabrowser/SKILL.md), so this bead's PR B owns isReleased (apps/macos/Sources/ShellCore/Setup/MetabVersion.swift) and its docs.

2026-11-22 state: still blocked on the 0.13.0 PyPI release (mb-b246, which waits on mb-d515, which waits on the owner merging and releasing jlevy/kpress#80 per mb-tbq9) and on the owner's signing setup (mb-21t6, mb-0msg). MetabRequirement.isReleased is false and minimumRelease is 0.13.0 on main 3b2cfe142. Release-path bug mb-im90 (ARCHES normalization) is being fixed now. The test matrix before publishing is mb-5fp7 and the WebKit rerun is mb-76nv (both under mb-1apq).

2026-11-22 walkthrough: the CLI release is first and has a separate changelog PR #727. The arm64 development DMG rehearsal verified the mounted app, architecture, source/version stamp, and checksum. The first public Mac image still needs the PyPI runtime, exact source approval, the owner signing setup, the WebKit rerun, and download/launch checks. Kerm's check_mac_dmg.sh uses the same mount, codesign, and Gatekeeper checks now exercised by Metabrowser's release scripts, which also enforce team, notarization tickets and checksum.
