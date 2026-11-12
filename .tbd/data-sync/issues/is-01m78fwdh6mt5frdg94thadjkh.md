---
type: is
id: is-01m78fwdh6mt5frdg94thadjkh
title: Remote sessions forward --plugins, --doctor, and the trust mode
kind: task
status: open
priority: 3
version: 4
spec_path: docs/project/specs/active/plan-2026-11-12-plugin-sources.md
labels: []
dependencies: []
parent_id: is-01m78ftefp9ks9100ebsm7sm29
created_at: 2026-11-12T18:21:23.365Z
updated_at: 2026-11-12T21:17:50.720Z
---
Phase 5 (plan: Remote Sessions). A --remote session runs the remote host's metab, so the remote registry and discovery apply; the local registry and per-command sources do not travel, and a short-lived remote host loses its decisions with it. The --remote wrapper gives the remote command /dev/null stdin and no terminal, so until this lands the page's bar names ssh -t HOST metab-plugins ROOT --trust. Forward --plugins and --doctor over the same SSH path, and run the trust mode over a terminal-allocating SSH session.

## Notes

Body rewritten 2026-11-12 after the Fable 5.2 design review; it supersedes the earlier review notes. The plan's Key Decisions are awaiting the owner.
