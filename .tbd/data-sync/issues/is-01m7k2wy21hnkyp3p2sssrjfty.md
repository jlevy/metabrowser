---
type: is
id: is-01m7k2wy21hnkyp3p2sssrjfty
title: "macOS app: Gatekeeper checks in check-dmg.sh (runtime flag, timestamp, Team ID, syspolicy_check, notarization)"
kind: task
status: in_progress
priority: 2
version: 8
spec_path: docs/project/specs/active/plan-2026-11-16-macos-app-publishing.md
delegate: claude-code@vm
labels: []
dependencies:
  - type: blocks
    target: is-01m7k2wz25n92m141a2c6rzj3m
  - type: blocks
    target: is-01m7k2xcrjxtgfe2mepxas1434
  - type: blocks
    target: is-01m7k2xdgr9b8sra4vrd372fe2
parent_id: is-01m7k1vctj6d370jg7hqdps4hk
hold: null
hold_until: null
created_at: 2026-11-16T21:06:07.552Z
updated_at: 2026-11-17T08:57:34.710Z
started_at: 2026-11-17T07:58:05.256Z
---
Phase 1 of the publishing plan. For a Developer ID build, check-dmg.sh also checks the hardened runtime flag and a secure timestamp (codesign -dvvv), the Team ID against EXPECTED_TEAM_ID when set, the full chain to Apple Root CA, syspolicy_check distribution on the app, and codesign -R=notarized --check-notarization on the app and the image, beside the existing stapler and spctl checks; with NOTARIZE=1 each is required and any miss exits nonzero. DTS gives --check-notarization for other code, so its use on an app and an image is the plan's extension, proven by the first signed build (PR #485 A13). A quarantine attribute, when present, is decoded (flags, time, agent) and printed as information only, never as a pass or fail, since its format is not API (PR #485 A14). make-dmg.sh builds at hdiutil's default zlib level instead of zlib-level=9, after measuring both, and says why beside the command (PR #485 A15). Done when scripts/test-scripts.sh covers the new readers on ad hoc copies with and without --options runtime, macos-app.yml runs the extended script on both images, and the zlib measurements are recorded in make-dmg.sh.

## Notes

2026-11-17: implemented in #510 (stack #512, top; head 170f9fae3): gatekeeper-lib.sh readers; check-dmg.sh requires the runtime flag on every app, and for Developer ID a secure timestamp, Team ID (EXPECTED_TEAM_ID), the chain on app and image, and once notarized syspolicy_check distribution and codesign --check-notarization on both; quarantine decoded for information only. Linux tests on codesign-form output; test-scripts.sh reads real ad hoc signatures with and without --options runtime; macos-app.yml already runs check-dmg.sh on both images (no workflow change). Left in progress: (1) the zlib change was NOT made: make-dmg.sh still uses zlib-level=9, since hdiutil cannot run here and nothing was measured; measure default vs 9 on a Mac (size, convert time) and record it beside the command; (2) the Developer ID branch is proven by the first signed build; (3) confirm macOS CI on #510.

2026-11-17: review A on #510 addressed in 3d9a3b6be: describe_quarantine decodes the \xHH that macOS stores in the agent name (CI capture is a Linux case); chain-without-root, chain-without-intermediate, and image Signed Time= cases added. Still open: the zlib measurement, and the Developer ID branch on the first signed build.
