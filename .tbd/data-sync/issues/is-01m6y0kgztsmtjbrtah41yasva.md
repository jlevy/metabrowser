---
type: is
id: is-01m6y0kgztsmtjbrtah41yasva
title: Refresh release QA after the final product merges
kind: task
status: in_progress
priority: 2
version: 5
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m6wdjwawp9g1bvnefz2hxze3
hold: null
hold_until: null
created_at: 2026-11-08T16:41:59.028Z
updated_at: 2026-11-08T17:56:57.722Z
started_at: 2026-11-08T16:42:12.287Z
---
The public release QA record still describes PR #334's prefetch ownership fix as awaiting review and names an older installation as current. Refresh this dated checkpoint with merged #334/#335, exact gated426/default installation, green nine-job PR/main CI, accepted Part A delta, the current 55-file CLI pass and blocked manual cells, ongoing functional comparisons and deferred quiet performance. Preserve historical identities, unresolved observations and the paused mb-itzy scope. Change documentation only, then obtain independent review, required verification/CI and merge; no release or publication.

## Notes

November 8, 17:55 UTC: PR336 CI complete

All nine CI jobs passed at exact110a3ae2aad54f8e1da2038d0c26e05ccefdc6f4, workflow42505866893; watch47654 completedexit0 and a fresh job API check confirmed completed/success for allnine. The PR body records this. It remains draft for final qualification reconciliation rather than treating the earlier running/blocked snapshot as final. No main merge or release approval claimed. Installed product remains426, with no runtime changes in the QA-only branch.

November 8, 17:50 UTC: QA checkpoint published as draft #336

Branch110a3ae2aad54f8e1da2038d0c26e05ccefdc6f4 passed complete makeverify through normal prepush:4917 tests/9 expected skips,386 goldens, lint/types/parity/hygiene, both audits, distribution and installed-wheel smoke; filesystem observer0bytes. Gate1475.51s, pytest1111.24s, goldens285.84s. Exact QA wheel/sdist preserved under qa-evidence-mckq-20261108/gated-110a3ae2a; runtime qualification and installed aliases remain frozen426.

Draft https://github.com/jlevy/metabrowser/pull/336 targets main e1cf; independent A round1/2 published as reviews5818906340 and5818907214. CI42505866893 is still running under watch47654. The PR remains draft until latest manual/data/browser/C receipts and findings are incorporated; don't merge the earlier capture-status snapshot as final qualification. Source stays clean with one QA-only changed file. Initial hygiene and private-observer setup failures are preserved and not counted as test runs. Installed app discovered #336 automatically (Open1→2, total321→322), without manualReload and with PR335 Changes selection preserved; functional proof only, no latency measurement.

November 8, 17:09 UTC: QA follow-up at 110a3ae2a

The one-file QA reconciliation is committed on codex/v012-qa-evidence-20261108. Independent review A approved blob 4a35e9f1; the initial normal pre-push gate stopped before tests at two generic public PR references. Both now use explicit public repository links in a forward commit; normal formatting/codespell hooks passed, focused public hygiene passes, and complete exact-head make verify is running at 110a3ae2aad54f8e1da2038d0c26e05ccefdc6f4. No push/CI/merge success is claimed. All failed-gate logs remain in the private QA evidence directory. No runtime or lock changes.
