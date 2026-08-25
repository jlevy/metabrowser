---
type: is
id: is-01m0x69kd73kx9jyzc6ypf4hcn
title: Await readiness-aware render after text chunk fallback
kind: bug
status: closed
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-25-git-revision-navigation-performance.md
labels: []
dependencies: []
parent_id: is-01m0w542g2gzak7th85hx2bdz8
created_at: 2026-08-25T19:27:59.894Z
updated_at: 2026-08-25T19:31:06.551Z
closed_at: 2026-08-25T19:31:06.550Z
close_reason: Awaited the async renderFile fallback in loadMoreCurrentText and pinned the call site with a focused source-append assertion; focused tests and make verify pass.
resolution: null
duplicate_of: null
---
Pre-commit review finding. src/metabrowser/static/app.js loadMoreCurrentText() falls back to renderFile() when incremental source append cannot apply. renderFile() is now async and owns plugin readiness plus the paint boundary, so this caller must await it before textChunkLoadInFlight clears. Acceptance: await the fallback render, add or update a focused contract test that pins the async call, rerun focused tests and make verify, then close with a fixed disposition.
