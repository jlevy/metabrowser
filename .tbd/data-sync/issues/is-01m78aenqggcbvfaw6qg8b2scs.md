---
type: is
id: is-01m78aenqggcbvfaw6qg8b2scs
title: "PR #375 A4: first-wins across manifests and the --doctor key report have no golden"
kind: bug
status: in_progress
priority: 2
version: 2
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m78ae0p02ghts4vw9h2vrmhp
hold: null
hold_until: null
created_at: 2026-11-12T16:46:30.127Z
updated_at: 2026-11-12T16:46:41.667Z
started_at: 2026-11-12T16:46:41.666Z
---
Medium. PR #375 review A (https://github.com/jlevy/metabrowser/pull/375#pullrequestreview-5871448143). Only tests/test_plugins_cli.py and tests/test_api_file_plugin_views.py cover them; cli-plugins.tryscript.md pins only the passing --doctor run. Fix: a golden whose before: writes operator plugins, pinning two plugins sharing a key under --show, the pair under --doctor and --doctor --json with exit 1, a pull-request view keyed N, and a manifest with a key reserved everywhere refused at load.
