---
type: is
id: is-01m3617625k6h6qq4dq2hyxytb
title: "Repository Phase 2A: acquire HTTPS Git sources for URL opening"
kind: feature
status: open
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
labels:
  - release:v0.12.0
dependencies:
  - type: blocks
    target: is-01kzsb4k9hwrt25jj9j6svkvaf
  - type: blocks
    target: is-01m2kw2b66x74xxjjtdp3wrsr4
  - type: blocks
    target: is-01m2zvdh0wgdt6c9qx38dz52xw
parent_id: is-01m2zvdh0wgdt6c9qx38dz52xw
created_at: 2026-09-23T02:23:51.363Z
updated_at: 2026-09-23T02:26:04.295Z
---
Own the HTTPS portion of mb-bi2c in the Phase 2A PR. Extend the existing bounded Git acquisition and publication path to credential-free HTTPS Git sources, preserving environment isolation, prompt suppression, safe diagnostics, version gates and no implicit fetch on content reads. Prove a cold public repository URL can acquire, publish and open its default full OID, and a valid warm/read-only/offline hit uses no network or provider credential lookup. Include transport failure/cancellation and interrupted publication coverage. The GitHub API, provider-principal credential bridge, selected-ref jobs and SSH are outside this subtask. SSH remains tracked by parent mb-bi2c, which must stay open until both transports meet their acceptance. Planning only: do not begin implementation until the next implementation task is explicitly started.
