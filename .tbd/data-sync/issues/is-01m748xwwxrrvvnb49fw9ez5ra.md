---
type: is
id: is-01m748xwwxrrvvnb49fw9ez5ra
title: "Agent front door: metab TARGET --present"
kind: feature
status: open
priority: 2
version: 5
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
updated_at: 2026-11-11T22:28:39.793Z
---
Phase 3. Resolves a target to the most specific registered root; hands off to the app when installed and preferred, else presents on a live root, else starts a detached server with an idle exit and opens the browser, else prints a link or the command; reports which and exits with a distinct code when blocked. The client mode must not import the server (metab --version took 0.36-0.52 s).

## Notes

2026-11-11, from review A on jlevy/metabrowser#352 (fixed in 083af6f8): a declined in-app confirmation is reported as blocked, with its own exit code.
