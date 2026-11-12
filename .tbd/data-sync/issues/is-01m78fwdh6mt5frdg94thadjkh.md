---
type: is
id: is-01m78fwdh6mt5frdg94thadjkh
title: Remote sessions forward --plugins, --doctor, and the trust modes
kind: task
status: open
priority: 3
version: 3
spec_path: docs/project/specs/active/plan-2026-11-12-plugin-sources.md
labels: []
dependencies: []
parent_id: is-01m78ftefp9ks9100ebsm7sm29
created_at: 2026-11-12T18:21:23.365Z
updated_at: 2026-11-12T18:47:20.142Z
---
Phase 5 (plan: Remote Sessions). A --remote session runs the remote host's metab, so the remote registry and repository discovery apply and the local registry does not travel. Forward --plugins, --doctor, and ROOT --plugins-trust/--plugins-deny/--plugins-untrust over the same SSH path (with a terminal for the confirmation), and have the page's repository bar name the forwarded command; document syncing the remote repository's environment on the remote host.

## Notes

Review (2026-11-12, independent design review; plan updated to match): The --remote wrapper gives the remote command /dev/null stdin and no PTY, so forwarded modes cannot prompt: fetch the remote plugin set through forwarded --plugins --json, confirm locally, send --plugins-trust --yes --expect SHA256. Until then the bar names ssh -t HOST metab ROOT --plugins-trust.
