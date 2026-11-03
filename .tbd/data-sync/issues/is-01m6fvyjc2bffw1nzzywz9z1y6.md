---
type: is
id: is-01m6fvyjc2bffw1nzzywz9z1y6
title: Strong-tier pass owed on reviews run on Opus while Fable credits were exhausted
kind: task
status: closed
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
labels: []
dependencies: []
parent_id: is-01m6f39t9zax1nbajkkasya6st
created_at: 2026-11-03T04:51:15.969Z
updated_at: 2026-11-03T20:17:10.243Z
closed_at: 2026-11-03T20:17:10.243Z
close_reason: "Completed by forward commits in the PR-support stack; independent reviews, rechecks and dispositions are published on the owning PRs. Final integration ea771741211193a387c1771e04df29b5a9698100 passed make verify (4712 Python, 9 expected skips, 373 transcripts), 8 public live tests, installed-wheel Chrome (22 actions, 25 unchanged checkout/Git fingerprints), and all 171 CI jobs across 19 current-head runs on 14 PRs. Final clean review: https://github.com/jlevy/metabrowser/pull/288#pullrequestreview-5758664799 . No PR merged."
resolution: null
duplicate_of: null
---
2026-11-03: the strong tier (claude-fable-5-1) ran out of usage credits mid-run. Reviews from then on run on claude-opus-5-5 at xhigh and say so in their reviewer line ('moderate tier (strong tier unavailable: usage credits exhausted)'). First affected: PR 285 round 2, letter C. When credits return, rerun a strong-tier senior pass over each such review's scope, or record the user's decision to accept the moderate tier.

## Notes

2026-11-03 HANDOFF (paused for another agent): also owed: a light follow-up review of #285's 2cfed240 after mb-kstl and mb-qjpa are fixed; it can be the strong-tier pass.

2026-11-03 review-debt clarification: the owed independent strong-tier follow-up is complete. PR285 Review D at54d7c9f7 explicitly rechecks the full follow-up scope after Review C, preserves C1-C7 dispositions and C8 decline, verifies the two later landing fixes mb-kstl/mb-qjpa, and states that it completes the strong-tier debt. Subsequent strong reviews include PR281 G at1e2bc237 and final PR288 E at2bd58827700e951c3cd7359efd6fd20bfe33f96d; the final integration has no remaining review finding in that scope. These reviews used requested gpt-6-astra at xhigh. Exact-head full verification, review publication and successor CI are separate coordinator gates. This bead has no explicit merge-only rule and is a direct child of mb-8rpp, not of mb-lnkl or mb-4nju; it is eligible for disposition closure after those gates are recorded. Status is unchanged by this note; no sync or PR merge is performed.
