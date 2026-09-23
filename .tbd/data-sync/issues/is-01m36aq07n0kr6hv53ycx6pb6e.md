---
type: is
id: is-01m36aq07n0kr6hv53ycx6pb6e
title: Acquisition Git in its own session survives a terminal hangup
kind: bug
status: open
priority: 3
version: 3
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
labels:
  - release:v0.12.0
dependencies:
  - type: blocks
    target: is-01m3617625k6h6qq4dq2hyxytb
  - type: blocks
    target: is-01m36k3xm77y33seww2jbwwb69
parent_id: is-01m2yxd3tnr1s2zf0h0jat1ey2
created_at: 2026-09-23T05:09:46.868Z
updated_at: 2026-09-23T07:37:25.309Z
---
From the independent review of PR #226 (2026-09-22). mb-lp89 starts acquisition and fetch Git with start_new_session so a timeout or cancellation can kill the whole process group. A side effect: SIGHUP from closing the terminal reaches metab but not that Git group. Python's default SIGHUP action exits without running cancellation, so the Git group keeps running and a later staging sweep deletes the directory underneath it. Verified by the reviewer with a stand-in: the helper survived a SIGHUP to the parent's group under ACQUISITION_POLICY but not READ_POLICY. Impact is small for file:// and grows with HTTPS in Phase 2A. Options: install a SIGHUP handler in the CLI that cancels the main task, the same path as Ctrl-C, or forward SIGHUP to live acquisition groups. Decide before or with mb-s1lt.
