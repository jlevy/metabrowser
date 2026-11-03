---
type: is
id: is-01m6hrpg9zw9a8gxe6w7s3fqq2
title: Make GitHub dependency failures actionable across PR views and CLI
kind: bug
status: in_progress
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m6hr8f0x7hr7mhchrtx1sqb7
hold: null
hold_until: null
created_at: 2026-11-03T22:32:54.839Z
updated_at: 2026-11-03T22:47:58.808Z
started_at: 2026-11-03T22:34:22.444Z
---
Severity: Low setup UX. Read-only runtime audit at6b93a964 reproduced actual missing-gh and signed-out refresh outcomes across catalog, PR detail, and changed files, preserving cached data. PR detail only displays The last refresh failed: GitHub CLI (gh) is not on PATH beside Fetch or Refresh; catalog/files say Install GitHub CLI and sign in but offer neither a direct official install link nor a concrete install command. Backend/CLI gh_missing also has no setup action; gh_too_old recommends a bare capability minimum rather than a current maintained release. User explicitly requests clear descriptive setup messages and standard manageable dependencies. Propose consistent install/auth/update guidance plus official cli.github.com link, retaining Retry/Fetch/Refresh, cached/local availability, typed errors, and ordinary local browsing. No installer wrapper, version probe, new admission policy, or host-tool changes. External actual-envelope/model evidence and proposed patch under gh-availability-6b93a964. Production frozen until root review/authorization.

## Notes

Implemented coordinator-approved runtime setup guidance on codex/gh-setup-01a1a051; no source commit by writer. Exact official install/update/auth command text and clickable links in catalog/PR detail/changed-files tree; setup-only local/cached availability sentence. Preserves explicit401 and permission/network/rate distinctions, safe null-message fallbacks and existing Retry/Fetch/Refresh. Removed unused GH_MIN_VERSION as coordinator requested. Runtime audit45 actual scenarios plus12 corrected controls and neither-Git-nor-gh folder/managed-missingGit probes found no local/cached functional block. Two initial invalid/api/children diagnostics retained and excluded from defect findings. Checks:280 affected tests,5 nonupdating CLI golden tests,6 UI goldens,2 actual recorders,both TS configs,check_goldens,Ruff/Biome/diff pass. Exact source hashes/raw evidence in gh-availability-6b93a964/runtime-writer-report.json. Panel files handed to checkout_design for separately reviewed small phase trace. Await root independent/final gate and closure.
