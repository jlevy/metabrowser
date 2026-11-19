---
type: is
id: is-01m75r1xshbawtvcvdw389y3hq
title: Find the app by bundle id from metab
kind: task
status: closed
priority: 3
version: 6
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
labels: []
dependencies:
  - type: blocks
    target: is-01m75r1wvvdpmyaeqcp4my33zb
  - type: blocks
    target: is-01m748xwwxrrvvnb49fw9ez5ra
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
created_at: 2026-11-11T16:46:29.169Z
updated_at: 2026-11-19T16:49:55.017Z
closed_at: 2026-11-19T16:49:55.016Z
close_reason: "Shipped on main (checked at 169496f05). src/metabrowser/cli/present.py:550 _launch_services_bundle is a read-only LaunchServices lookup by bundle id (LSCopyApplicationURLsForBundleIdentifier, the database open -b reads); is_installed (:702) filters it to APP_INSTALL_LOCATIONS, the system's and the user's Applications folders (:133-136), so build-folder copies are refused; find_app (:778) and look_up_app (:800) serve --present's decision (:891) and metab --doctor's doctor_open_in (:1455). Tests: tests/test_present.py:188-368. Landed in 8f8cc2a9a and 495301a95 (mb-d9tu, #540) and 35bf406e0 (mb-gh6l, mb-kze0). The install mode (mb-92d9) can reuse look_up_app."
resolution: null
duplicate_of: null
---
Phase 5. A read-only LaunchServices lookup by bundle id (measured about 0.09 s), filtered to Applications folders because it also returns build-folder copies; shared with the agent front door (mb-idri) and the install mode (research-2026-11-11-uv-and-macos-app-install.md).

## Notes

2026-11-11: Still useful before the install mode: the --present front door (mb-idri) needs it to find the app.

2026-11-19: closed after checking origin/main at 169496f05. It shipped as find_app in src/metabrowser/cli/present.py; the close reason cites the code. Reviewed while restructuring the host-mode beads under host mode plan HM-1 A.
