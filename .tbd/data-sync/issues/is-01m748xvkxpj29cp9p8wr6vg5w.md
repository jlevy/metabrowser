---
type: is
id: is-01m748xvkxpj29cp9p8wr6vg5w
title: Live-server registry with a per-root find-or-start lock
kind: feature
status: open
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
labels: []
dependencies:
  - type: blocks
    target: is-01m748xwwxrrvvnb49fw9ez5ra
  - type: blocks
    target: is-01m748xsest94amc9cyx26j1zk
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
created_at: 2026-11-11T03:02:52.796Z
updated_at: 2026-11-11T22:28:37.998Z
---
Phase 3. One owner-only state file per live process listing its roots, URL, owner, version, and boot id; readers drop dead pids and failed identity probes; a per-root lock serializes find-or-start so a root has at most one live server. A listing mode with --json and a golden against a fixture runtime directory.
