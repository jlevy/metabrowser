---
type: is
id: is-01m76xfmqcnsxjs3e6sw99a1h5
title: metab discovery runs only executables that pass ExecutableTrust
kind: bug
status: closed
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
labels: []
dependencies:
  - type: blocks
    target: is-01m76h3hdcp0ek254274recmn5
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
created_at: 2026-11-12T03:40:35.946Z
updated_at: 2026-11-12T08:50:43.716Z
closed_at: 2026-11-12T08:50:43.715Z
close_reason: "Fixed in 785e5f7b: RuntimeDiscovery.validate applies ExecutableTrust to every metab the app found by itself (discovery, a saved automatic runtime at launch and in discovery, and rechecks), records refusals as CandidateResult.untrusted for Settings, the log, and the first-run steps, and runs a file the user chose as chosen. Admin-group trust (mb-6d4r) unchanged."
resolution: null
duplicate_of: null
---
From #361's review fixes (the setup agent's escalation): RuntimeDiscovery runs metab --version on Homebrew and login-PATH candidates with no ownership or permission check. Apply the ExecutableTrust rule that #361 added for uv (owned by the user or root, no group- or world-writable component, no ACL write grant), with the refused candidates and reasons shown in Settings and the log. Decide admin-group trust together with that bead (Homebrew's /opt/homebrew is drwxrwxr-x user admin).
