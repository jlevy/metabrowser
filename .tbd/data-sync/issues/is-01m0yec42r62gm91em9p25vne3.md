---
type: is
id: is-01m0yec42r62gm91em9p25vne3
title: Keep retained file content through async plugin readiness
kind: bug
status: closed
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-08-25-git-revision-navigation-performance.md
labels: []
dependencies:
  - type: blocks
    target: is-01m0w542g2gzak7th85hx2bdz8
parent_id: is-01m0w52mbqvhdj9r2et2eh9p55
created_at: 2026-08-26T07:08:25.558Z
updated_at: 2026-08-26T07:43:12.127Z
closed_at: 2026-08-26T07:43:12.126Z
close_reason: Implemented connected transparent inert staging with atomic child/disposer transfer and immediate stale-stage cancellation at the shared preview-claim boundary. Exact 4d45e0d file-views covers cold source, structured JSON, Markdown, and cached source with zero blank frames, exact selection/route/view convergence, one mount, bounded requests, and zero exceptions; git-revisions also has zero blank frames/exceptions and exact convergence. Rapid exact installed-build selection ends on AGENTS.md with one mount, zero pending stages, and no stuck busy state. make verify passes 1,562 tests plus 48 golden scenarios.
resolution: null
duplicate_of: null
---
Files/functions: src/metabrowser/static/app.js renderFile, mountPluginView, disposal ownership, and preview replacement helpers; tests/test_browser_loading_delay.py and focused browser lifecycle tests; explorations/performance-loop/capture-browser.js file-view candidate/gate coverage; active performance plan and CHANGELOG. Reproduced on exact ad7c8b7: file-views selected lefthook.yml, the structured active view awaited /api/plugin/structured/parsed after preview.innerHTML replaced the prior useful surface, and the hard gate observed 1-2 blank frames (8.3-16.7 ms). Preserve the connected-container contract for plugins that require layout while keeping the previous useful surface visible until the next active plugin render and optional ready promise complete; then swap atomically, transfer disposal ownership, animate only incoming content, and reject stale claims without leaks. Make file-view coverage deterministic enough to exercise an async structured view as well as synchronous/cached views. Acceptance: focused lifecycle tests fail before/pass after for async readiness, stale replacement, disposal, errors, and one active mount; exact headed file-views and git-revisions record zero blank frames, exact convergence, bounded requests, no exceptions; make format and make verify pass.
