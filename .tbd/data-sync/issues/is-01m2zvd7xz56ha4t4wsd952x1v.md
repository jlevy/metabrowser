---
type: is
id: is-01m2zvd7xz56ha4t4wsd952x1v
title: "Phase 1B-a: run no-lazy-fetch acceptance against the lowest admitted Git in CI (runner Git is below the floor; tests monkeypatch it)"
kind: task
status: closed
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
delegate: claude-code@spud10
labels:
  - release:v0.12.0
dependencies: []
parent_id: is-01kzsb4jnyd56wy89xmztkmz2m
hold: null
hold_until: null
created_at: 2026-09-20T16:46:51.837Z
updated_at: 2026-09-23T05:32:20.350Z
started_at: 2026-09-23T03:31:07.871Z
closed_at: 2026-09-23T05:32:20.349Z
close_reason: "Done on codex/v012-foundation-stabilization (PR #226). make test-admitted-git runs the no-lazy-fetch acceptance, the real-subprocess acquire golden and the acquisition and pin suites against real Git 2.43.7 (the lowest admitted release) and 2.50.1. METABROWSER_REQUIRE_ADMITTED_GIT turns any skip or version mismatch into a failure. The first run found a real defect: Git 2.43.7 dies instead of answering missing on a refused lazy fetch. That is fixed in a5339d8b. Both legs green: https://github.com/jlevy/metabrowser/actions/runs/35820742829"
resolution: null
duplicate_of: null
---
Phase 1B-a of docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md (heading at line 1774) still has this item unchecked: run the no-lazy-fetch acceptance tests against the lowest admitted Git release in CI, so that source reading behind the version floor is proven at runtime rather than simulated.
