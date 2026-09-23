---
type: is
id: is-01m2zvdh0wgdt6c9qx38dz52xw
title: Acquire HTTPS and SSH Git URLs into the shared store
kind: task
status: open
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
labels:
  - release:v0.12.0
dependencies: []
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
child_order_hints:
  - is-01m3617625k6h6qq4dq2hyxytb
created_at: 2026-09-20T16:47:01.143Z
updated_at: 2026-09-23T02:26:01.029Z
---
Track complete HTTPS and SSH acquisition into the shared worktree-free Git store. Current #217 supports file:// only and remote transports remain refused. Child mb-s1lt owns HTTPS acquisition within the Phase 2A PR and gates repository URL opening/publication. This parent retains SSH transport, prompt suppression, safe diagnostics, identity/credential isolation and its separate live/automated acceptance; it stays open after HTTPS is complete until SSH is also accepted. No implementation started in the planning handoff.
