---
type: is
id: is-01m7k2wy21hnkyp3p2sssrjfty
title: "macOS app: Gatekeeper checks in check-dmg.sh (runtime flag, timestamp, Team ID, syspolicy_check, notarization)"
kind: task
status: open
priority: 2
version: 5
spec_path: docs/project/specs/active/plan-2026-11-16-macos-app-publishing.md
labels: []
dependencies:
  - type: blocks
    target: is-01m7k2wz25n92m141a2c6rzj3m
  - type: blocks
    target: is-01m7k2xcrjxtgfe2mepxas1434
  - type: blocks
    target: is-01m7k2xdgr9b8sra4vrd372fe2
parent_id: is-01m7k1vctj6d370jg7hqdps4hk
created_at: 2026-11-16T21:06:07.552Z
updated_at: 2026-11-16T22:07:18.456Z
---
Phase 1 of the publishing plan. For a Developer ID build, check-dmg.sh also checks the hardened runtime flag and a secure timestamp (codesign -dvvv), the Team ID against EXPECTED_TEAM_ID when set, the full chain to Apple Root CA, syspolicy_check distribution on the app, and codesign -R=notarized --check-notarization on the app and the image, beside the existing stapler and spctl checks; with NOTARIZE=1 each is required and any miss exits nonzero. DTS gives --check-notarization for other code, so its use on an app and an image is the plan's extension, proven by the first signed build (PR #485 A13). A quarantine attribute, when present, is decoded (flags, time, agent) and printed as information only, never as a pass or fail, since its format is not API (PR #485 A14). make-dmg.sh builds at hdiutil's default zlib level instead of zlib-level=9, after measuring both, and says why beside the command (PR #485 A15). Done when scripts/test-scripts.sh covers the new readers on ad hoc copies with and without --options runtime, macos-app.yml runs the extended script on both images, and the zlib measurements are recorded in make-dmg.sh.
