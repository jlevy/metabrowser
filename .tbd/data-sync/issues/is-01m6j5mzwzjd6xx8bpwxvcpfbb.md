---
type: is
id: is-01m6j5mzwzjd6xx8bpwxvcpfbb
title: Make the gh timeout child-cleanup fixture wait for readiness
kind: bug
status: in_progress
priority: 2
version: 3
labels: []
dependencies: []
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
created_at: 2026-11-04T02:19:16.762Z
updated_at: 2026-11-04T02:23:08.682Z
---
The exact 224e32aa full verification run reported the expected one-second GhError timeout, then failed reading the child PID marker because the fake gh had not yet spawned its child on the loaded external filesystem. Preserve the real timeout and parent/child cleanup assertions, add bounded fixture readiness with deterministic delayed startup, and keep product code unchanged. Evidence: make-verify-224e32aa.log; 4724 passed, 9 expected skips, one fixture failure.

## Notes

2026-11-03: Confirmed a fixture startup race, not a provider defect. An original-test control with 1.25-second startup reproduces missing child PID after the correct one-second timeout. The fixture now signals parent/child readiness; the test checks both exist, invokes unchanged real _finish with timeout_s=1, and verifies both are gone before emergency cleanup. Immediate and delayed controls pass in the 22-test provider module (9.16s). Deliberately omitting termination fails the parent-running assertion; emergency cleanup leaves both owned PIDs absent. Check-only Make lint/types/parity/goldens/docs passed using installed frozen external dependencies. Only tests/test_github_provider.py changed; no source/Make/lock edits. Evidence label: gh-timeout-readiness-224e32aa/HANDOFF.json, with original full-gate hash and negative-control logs. Await coordinator commit and final full verification; no full-suite rerun or publication by this agent.
