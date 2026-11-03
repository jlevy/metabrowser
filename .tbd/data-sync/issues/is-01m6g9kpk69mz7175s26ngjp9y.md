---
type: is
id: is-01m6g9kpk69mz7175s26ngjp9y
title: "PR #288 B2: attach companions adopted during store upgrade"
kind: bug
status: closed
priority: 2
version: 4
labels: []
dependencies: []
parent_id: is-01m6g5eqdtdmc5pj1eb9ryy6s1
created_at: 2026-11-03T08:49:59.909Z
updated_at: 2026-11-03T20:17:09.692Z
closed_at: 2026-11-03T20:17:09.692Z
close_reason: "Completed by forward commits in the PR-support stack; independent reviews, rechecks and dispositions are published on the owning PRs. Final integration ea771741211193a387c1771e04df29b5a9698100 passed make verify (4712 Python, 9 expected skips, 373 transcripts), 8 public live tests, installed-wheel Chrome (22 actions, 25 unchanged checkout/Git fingerprints), and all 171 CI jobs across 19 current-head runs on 14 PRs. Final clean review: https://github.com/jlevy/metabrowser/pull/288#pullrequestreview-5758664799 . No PR merged."
resolution: null
duplicate_of: null
---
Independent strong review: companion threaded read can start with ListedRepository, store attaches while it awaits, then newly adopted companion remains metadata-only forever although group git_dir is attached. Rebind/version-check current published source before _keep; deterministic different-PR barrier test.

## Notes

2026-11-03 independent-review integration at final tip 58270d69. Review C independently verifies B2 fixed: a companion adopted during store attachment is rebound to the current published source, preserving comparison access. Deterministic different-PR barriers and integration probes pass. Retained at final #288 58270d69. Final full verification, publication and remote CI are coordinator gates still pending; no PR merged.
