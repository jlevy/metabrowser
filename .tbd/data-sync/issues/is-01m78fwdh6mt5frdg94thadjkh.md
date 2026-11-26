---
type: is
id: is-01m78fwdh6mt5frdg94thadjkh
title: Remote sessions forward --plugins, --doctor, and the trust mode
kind: task
status: open
priority: 3
version: 8
spec_path: docs/project/specs/active/plan-2026-11-12-plugin-sources.md
assignee: null
delegate: null
labels: []
dependencies: []
parent_id: is-01m78ftefp9ks9100ebsm7sm29
hold: null
hold_until: null
created_at: 2026-11-12T18:21:23.365Z
updated_at: 2026-11-26T08:37:20.292Z
started_at: 2026-11-26T08:35:34.395Z
---
Phase 5 (plan: Remote Sessions). A --remote session runs the remote host's metab, so the remote registry, discovery, and confinement backend apply; the local registry and per-command sources do not travel, and a short-lived remote host loses its decisions with it. The --remote wrapper gives the remote command /dev/null stdin and no terminal, so until this lands the page's bar names ssh -t HOST metab ROOT --plugins-trust. Forward --plugins and --doctor over the same SSH path, and run the trust mode over a terminal-allocating SSH session.

## Notes

Rewritten 2026-11-26 with the plan's second revision (review against main); supersedes the 2026-11-12 body.
