---
type: is
id: is-01m774rqptvx1mb6nfr5xye33a
title: "Layer 2: view keys as route data"
kind: task
status: closed
priority: 2
version: 7
spec_path: docs/project/specs/done/plan-2026-11-11-shift-key-reveal-and-keymap.md
delegate: claude-code@spud10
labels:
  - layer-2
dependencies:
  - type: blocks
    target: is-01m774rrky1bpnkwshfqy4vqrz
parent_id: is-01m76jgfxbadse383jypkzwpm9
hold: null
hold_until: null
created_at: 2026-11-12T05:47:53.946Z
updated_at: 2026-11-13T16:45:47.514Z
started_at: 2026-11-12T07:33:56.260Z
closed_at: 2026-11-12T08:13:58.003Z
close_reason: "Layer 2 done on claude/keys-2-view-keys (82f97455, 24ab1761, 2e4dc430; not pushed). keymap.py holds the reserved table (t j k u w x y a and digits always; n p for pull-request) and check_view_keys(); ViewSpec.key validated; /api/file serves views[].key; --show, --plugin, --doctor report keys. Tests: tests/test_keymap.py (keymap check over every served kind, multi-view kinds key every view, first-wins, contextual, malformed), tests/test_plugin_loader.py (non-letter, reserved, lowercase, refused at discovery), tests/test_api_file_plugin_views.py (envelope keys, runtime first-wins), tests/test_plugins_cli.py (--doctor duplicate across two manifests). Goldens regenerated: cli-show, cli-api, cli-api-hidden-folder, cli-git-pin-show, cli-git-pin-files, cli-plugins, cli-untrusted, cli-github-pull, cli-github-url-open. Reserved table lives in keymap.py per the spec, not file_kinds.py; METABROWSER_SETTINGS serving is phase 2. Reveal-golden comparison is layer 3."
resolution: null
duplicate_of: null
---
Design > Where View Keys Are Declared. key on every built-in manifest [[view]] of a multi-view kind; views[].key in /api/file; keys on the metab --show views line; loader validation; merged-list uniqueness first-wins with a --doctor report; reserved shell key table (always and contextual) in file_kinds.py, served in METABROWSER_SETTINGS; Python keymap check; regenerate cli-show, cli-api, cli-api-hidden-folder goldens.
