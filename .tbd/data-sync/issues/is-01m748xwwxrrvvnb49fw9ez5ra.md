---
type: is
id: is-01m748xwwxrrvvnb49fw9ez5ra
title: "Agent front door: metab TARGET --present"
kind: feature
status: open
priority: 2
version: 7
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
labels: []
dependencies:
  - type: blocks
    target: is-01m748xxadyc5tfdj366df1ag0
  - type: blocks
    target: is-01m748xxr130p68h0zbjbb6k9f
  - type: blocks
    target: is-01m748xykvszgd0b8x0ws7k6j7
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
created_at: 2026-11-11T03:02:54.108Z
updated_at: 2026-11-19T16:49:33.673Z
---
Phase 3. Resolves a target to the most specific registered root; hands off to the app when installed and preferred, else presents on a live root, else starts a detached server with an idle exit and opens the browser, else prints a link or the command; reports which and exits with a distinct code when blocked. The client mode must not import the server (metab --version took 0.36-0.52 s).

## Notes

2026-11-17: the release-scoped slice (LaunchServices delivery, the open_in preference, --dry-run) is mb-fb5k under mb-jl8o (plan-2026-11-17-open-anything-from-cli-and-app.md); this bead keeps the rendezvous transport, live-page present, and the reply.

2026-11-19: dependencies restructured under host mode plan HM-1 A (docs/project/specs/active/plan-2026-11-18-host-mode.md, step H5). This bead now waits on discovery (mb-baee), the find-or-start lock (mb-5xi4), --live's resolution (mb-77x9, H4, which the plan orders before H5), and idle exit for its detached server (mb-k3yz), and no longer on the control socket (mb-1zyp). mb-56nq, the app lookup, is closed: it shipped as find_app in src/metabrowser/cli/present.py.
