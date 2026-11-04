---
type: is
id: is-01m6hsvza8q7xmwa5q6m892kc9
title: Use catalog response identity without per-page authentication probes
kind: task
status: closed
priority: 2
version: 5
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m6hryve021ndx04tt967a6a9
hold: null
hold_until: null
created_at: 2026-11-03T22:53:22.630Z
updated_at: 2026-11-04T17:14:29.967Z
started_at: 2026-11-03T22:53:30.780Z
closed_at: 2026-11-04T17:14:29.967Z
close_reason: "Scoped implementation independently reviewed and tested; owning feature PRs are actually merged. Final main https://github.com/jlevy/metabrowser/commit/db52ec09cf839269da3a56fd396e44f3092995a9 includes account fix https://github.com/jlevy/metabrowser/pull/297 and documentation https://github.com/jlevy/metabrowser/pull/298, with final manual acceptance and per-issue qualifications checked. Individual source, test, review and merge evidence: ACTION-PLAN.json SHA-256 d0867a696ee055cc27911e83c4f70744b419a3ca4a7a1218f0eeaf419dc37589. Future scope and historical dependency relationships remain open or preserved as recorded."
resolution: null
duplicate_of: null
---
Keep one active-account check per catalog job and attribute every GraphQL page to its authoritative viewer.login and repository identity. Remove the redundant post-page gh auth status call, which official gh source shows performs HTTP work. Preserve page CAS, account-separated checkpoints, rate holds and cache-only reads. Explicitly accept a completed response under its original reader after local account settings change; reject a later page from a different viewer without mixing rows. Add focused ordered-call, retention and stale-publisher controls; retain the superseded external guard probe as evidence. No token/config parsing, wrapper, quota or latency claim. Coordinator owns commit and publication.

## Notes

2026-11-03 implementation ready above8a62f7ce, uncommitted for coordinator. Catalog keeps initial account selection and validates every response viewer; per-page auth removed. Source/tests/docs frozen in catalog-auth-efficiency/frozen-source-tests.json. Approved response-reader change is explicit: old guard passes before and fails unchanged afterward; successor attribution test is red before and green after. All76 catalog and13 affected check-only session/golden tests pass, plus6 actual recorder updates and2 UI transcript cases. Focused lint/types/format/public-hygiene/golden checks pass. Existing CLI responses unchanged, only25 redundant auth lines removed across four transcripts; cached phase traces remain empty. Official gh2.98 source proves HTTP work, but no latency/quota claim. Evidence REPORT.md, validation.json, final.patch and generated-output-proof.json. Independent review and coordinator commit/full gates remain.

2026-11-03 independent review clean: reviewer inspected all10 owned files, reconciled frozen hashes and ran86 existing catalog/CLI/session cases plus2 provider-trace golden cases. No remaining correctness/security findings. Coordinator commit and full integration gates remain.
