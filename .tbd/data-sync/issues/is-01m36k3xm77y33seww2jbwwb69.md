---
type: is
id: is-01m36k3xm77y33seww2jbwwb69
title: "GitHub URL open: reducer plugin, HTTPS with gh helper, ref/path split, line anchors"
kind: task
status: open
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
labels:
  - release:v0.12.0
dependencies:
  - type: blocks
    target: is-01m36k3y0t6fvtqhskx3cqxx95
parent_id: is-01m36k3w9vgwy97c9hcj2sqrs5
created_at: 2026-09-23T07:36:38.789Z
updated_at: 2026-09-24T08:01:45.500Z
---
Delivery step 5 of the thin-mirror plan. GitHub reducer in builtin_plugins/github through classify_root_argument(reducers=), with the URL grammar, canonical identity and refusals from the plan and network-free goldens for every shape. HTTPS fetch with the scoped gh credential helper when gh is present; error classification; measured stall bound (mb-rati); ref and path split without rev-parse (branch, tag, commit ID precedence); line anchors; SIGHUP handling (mb-163x); size check before a first clone. Opt-in live smoke on a public repository. Independent review, make verify, green CI.

## Notes

2026-09-24: PR #231 at 247d584c, CI green on all nine checks, after three independent review rounds (reducer and HTTPS at efe0893c; integration at f34a62c2; fix round at 35df8f3c). Every finding is fixed, and the last round (fold judgment by broken refs with a casefold/NFC key, followed_outcome, per-miss fetch tracking, selection states in the browser, tryscript gh guard) is not yet re-reviewed. It will be covered by the final stack review before the bead closes. Known limit: a decomposed-Unicode branch name on macOS hits a Git-internal prune and fetch disagreement after the first refresh (recorded in the architecture doc).
