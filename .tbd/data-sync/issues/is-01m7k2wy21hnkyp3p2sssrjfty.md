---
type: is
id: is-01m7k2wy21hnkyp3p2sssrjfty
title: "macOS app: Gatekeeper checks in check-dmg.sh (runtime flag, timestamp, Team ID, syspolicy_check, notarization)"
kind: task
status: open
priority: 2
version: 4
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
updated_at: 2026-11-16T21:06:23.383Z
---
Phase 1 of the publishing plan. For a Developer ID build, check-dmg.sh also checks the hardened runtime flag and a secure timestamp (codesign -dvvv), the Team ID against EXPECTED_TEAM_ID when set, the full chain to Apple Root CA, syspolicy_check distribution on the app, and codesign -R=notarized --check-notarization on the app and the image, beside the existing stapler and spctl checks; with NOTARIZE=1 each is required and any miss exits nonzero. A quarantine attribute, when present, is decoded (flags, time, agent). Done when scripts/test-scripts.sh covers the new readers on ad hoc copies with and without --options runtime, and macos-app.yml runs the extended script on both images.
