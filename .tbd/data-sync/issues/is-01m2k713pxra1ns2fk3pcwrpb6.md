---
type: is
id: is-01m2k713pxra1ns2fk3pcwrpb6
title: "v0.12 thin-mirror stack: coordinate landing"
kind: task
status: in_progress
priority: 1
version: 67
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
refs:
  - kind: other
    url: https://github.com/jlevy/metabrowser/stack/218
    at: 2026-09-19T17:24:56.130Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/125
    at: 2026-09-19T17:24:56.131Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/134
    at: 2026-09-19T17:24:56.131Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/136
    at: 2026-09-19T17:24:56.131Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/139
    at: 2026-09-19T17:24:56.131Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/140
    at: 2026-09-19T17:24:56.131Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/217
    at: 2026-09-19T17:24:56.131Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/216
    at: 2026-09-19T17:24:56.131Z
delegate: claude-code@spud10.local
labels:
  - stack:pr125
  - stack:pr134
  - stack:pr136
  - stack:pr140
  - stack:pr139
  - stack:pr217
  - stack:pr216
  - release:v0.12.0
dependencies: []
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
hold: blocked
hold_until: null
created_at: 2026-09-15T18:59:49.596Z
updated_at: 2026-10-02T04:28:51.805Z
started_at: 2026-09-16T21:24:51.532Z
---
Coordinate landing of the v0.12 stack: one linear chain of open PRs, main <- #125 ... #244 (#241 is the draft acceptance record), plus the PRs above #244 that finish stabilization. Keep exact base/head relationships, per-layer review dispositions, green per-layer CI and top integration evidence against current main, and keep beads and specs aligned. Gates: mb-hall and mb-gnr9. SSH, the PR list and panel, inline review anchors, checkout attachment and rebind are deferred by the user's 2026-09-23 decision and do not gate landing. Hold every layer until the user explicitly approves; then land the tip as one fast-forward of main (merging lower layers one at a time would put retired-design states on main).

## Notes

2026-10-01 (late): the chain is ONE native GitHub stack. Until now it was split across three native stacks (#218: #125-#226; #245: #233-#244; #266: #253-#265) with twelve PRs in none; #245 and #266 were dissolved with 'gh stack unstack <n>' and their PRs, plus the twelve, appended with 'gh stack link 218 ...'. Stack #218 now holds all 44 PRs, #125 ... #265, in chain order, base main; no branch, base or head changed; verified with 'gh api repos/jlevy/metabrowser/stacks'. #241 marked ready (a draft blocks 'gh stack merge'). Owed on top, each appended with 'gh stack link 218 <pr>': the gate-fixes-2 layer (mb-55tr) and #260 (docs). Landing is 'gh stack merge' on stack 218 per 'tbd shortcut stacked-prs', only on the user's explicit approval; the merge method (merge commit or squash) is the user's open decision. Never retarget a chain PR to main (it flattens the stack). The earlier fast-forward-push plan is withdrawn.

2026-10-01: ready chain is main <- #125 ... <- #250 <- #252 (test isolation) <- #251 (missing tools loud, tiers, bounds) <- #253 (golden machinery), restacked by merges with bases set through gh; all green. In review: #254 (startup cost; folder shell 173 KB against the 175 KB gate; lint check for the budget), to be restacked above the test PRs. In progress on branches from #253: mb-79t3, mb-738k, mb-sqlv, mb-haxx+mb-jqbg. Owed on a quiet machine (this machine is loaded by unrelated jobs, load over 100): wall-clock startup pairs against main (explorations/performance-loop/startup_pairs.py) and the single-command make golden-update no-op on the merged tree. Decisions left for the user: macOS CI job; admitted-Git duplication across the test matrix; a line-coverage tool; landing approval.

2026-09-30 (evening): the stack above #244 is linear, restacked by merges with bases set through gh: #244 <- #246 (remove unused Hosted Review and capability SDK; ready) <- #248 (View file; ready) <- #249 (landing fixes; ready) <- #250 (docs reconciliation; draft until the acceptance rerun is recorded). Every head contains its base; all green. #247 (reference/v012-hosted-review, tag reference/v012-hosted-review-2026-09-30) hangs off #246 as a do-not-merge draft and is not part of the stack. In progress above #250: mb-l8c2 (startup cost, branch codex/v012-startup-cost). Regression check against main: no route, memory or output regression; make verify passes on the tip except the long-path bench test that fails on main too (mb-ghko). Remaining gates: mb-gnr9 rerun, mb-l8c2, mb-06up's labelled children, mb-myum; then the user's approval. Land the tip as one fast-forward.

2026-09-30 audit: SSH (mb-bi2c) is deferred and has no edge to this bead; the 2026-09-22 notes saying it gates final landing are superseded. mb-nhky closed as superseded; mb-gacf closed. Live 2026-09-30: all 27 PRs CLEAN and green, #241 draft, origin/main 6c278f3f is an ancestor of #244 a896d8fe; merge-tree of main and the tip equals the tip's tree. Remaining gates: mb-hall (mb-zb5t and the new landing beads) and mb-gnr9.

2026-09-22 planning-only handoff complete. PR #225 https://github.com/jlevy/metabrowser/pull/225 is at 7a3bd1de04589c38ccc203e79d78a1856ca0a90d, on codex/v012-alpha-test-plan above unchanged #216 b3c001a96eed64eb77961c2b7165b103af98b77c. Fresh CI passed all seven jobs: https://github.com/jlevy/metabrowser/actions/runs/35811262120 . Local make verify passed (3112 pytest tests, two skips; 147 CLI transcripts; audits and installed-distribution checks), final lint and pre-push passed. Working tree is clean; only four planning documents changed.

The user explicitly requested no implementation yet. No runtime code, feature branch, implementation PR, or feature claim was started. Current feature statuses/delegates were preserved. The durable handoff is docs/project/specs/active/plan-2026-09-22-v012-alpha-testing.md#next-prs-and-agent-handoff, linked from TODO.md. Next agent starts with a new foundation-stabilization PR on the live Stack 218 tip, resolves existing findings and review obligations through mb-k900/mb-tsdc/mb-hoae, and records mb-j439 acceptance. Foundation evidence uses current CLI/content routes; acquired HTTP/browser acceptance starts in 2A.

Then publish one new PR per phase: 2A reducers mb-12cz, HTTPS mb-s1lt and URL/serving mb-ew38 -> mb-innz; 2B jobs mb-jlon and convergence mb-bgn8 -> mb-bf94; 2C selection mb-2xq7 -> mb-9aku on the exact green 2B head. HTTPS gates 2A publication. Parent mb-bi2c retains SSH and gates final mb-n2ro landing without blocking the first HTTPS test milestone. No tbd release or cleanup is a prerequisite. Astra checked scope/dependency boundaries and Sol checked live stack, links, statuses and dependency ordering. Keep the whole stack for stabilization and explicit landing approval; no merge or release occurred.

Earlier status history:
Planning handoff: the complete v0.12 transport scope includes SSH under mb-bi2c; this final landing coordinator now depends on that aggregate. HTTPS acquisition is the separate mb-s1lt child in Phase 2A. SSH does not block the first HTTPS repository/browser milestone, but passing T1/T2 or only the T3 browser rows does not complete the wider transport promise. No feature implementation or claims changed in this planning task.

2026-09-22 final follow-up: PR #225 is updated to ef334432dde5449d29a7f097a8dc2084fdb08f20 over unchanged #216 b3c001a96eed64eb77961c2b7165b103af98b77c. All eight Stack 218 PRs are OPEN, non-draft, contiguous, MERGEABLE/CLEAN, with seven successful checks each. Current main 6c278f3f is an ancestor of the integration tip. Fresh CI: https://github.com/jlevy/metabrowser/actions/runs/35808364944 . Final evidence and walkthrough: https://github.com/jlevy/metabrowser/pull/225#issuecomment-5787687825 . Full review ledger: https://github.com/jlevy/metabrowser/pull/216#issuecomment-5786877244 .

The expanded feature map distinguishes built, partial and planned scope and later work, with T0 available now, the first default-branch URL browser checkpoint after 2A, full T1 after selected-ref/branch integration, direct PR T2 and discovery/navigation/anchors T3. The explicit Phase 2B background worker is mb-bgn8; M10b covers provider rebind. Local make verify and the pre-push gate passed (3112 pytest tests, two skips; 147 CLI transcript checks; audits and installed-wheel/distribution checks). The real CLI cold/warm/origin-absent T0 smoke passed; fixture-server startup/HTTP was checked, without claiming full manual visual acceptance or GitHub URL/PR E2E support. Astra checked feature/design boundaries and Sol verified fresh CI, ancestry, mergeability and documentation consistency.

No tbd release, upgrade or shortcut cleanup is a prerequisite for product implementation, testing, landing or release. mb-dbue/#219 are independent optional maintenance. This supersedes historical notes mentioning an upstream tbd release wait. Product acceptance findings including mb-sumg remain open; mb-gnr9 owns future installed/browser acceptance. Future work extends this same stack, and whole-stack landing awaits product stabilization and explicit user approval. No merge or release was performed.

Earlier history (superseded where noted):
2026-09-22 follow-up: no work is held on tbd. All eight current stack PRs are ready for review; #217/#216 draft flags were removed at the user’s request after live ancestry, mergeability and green-CI checks. This changes mechanical mergeability, not feature completion or landing authorization. GitHub reports all current layers mergeable/clean against main 6c278f3f and no required-review rule; draft flags are removed. Continue coordinating product stabilization and the user’s whole-stack landing decision. No tbd update/release/shortcut cleanup is a prerequisite.

Earlier history:
Do not merge. Do not imply landed.

GitHub stack #218: https://github.com/jlevy/metabrowser/stack/218
#125 → #134 (folded #130 #132 #133) → #136 (folded #135) → #139 (folded #138) → #140 → #217 (folds #208 #210) → #216 (folds #156 and #211–#215).

#140 Bugbot Mediums fixed in da73b878; both threads resolved.
#125 is 2 commits behind origin/main (#137 tbd 0.9.0). Internally consistent; do not restack unless asked.
#217 and #216 are drafts. #216 is large (~101 files).

Landing still requires explicit human approval, then bottom-to-top gh stack merge.

2026-09-20: an independent re-review found #217 and #216 not yet landable; stabilization is tracked in mb-gacf. #207 merged; the stack needs a restack onto main.

2026-09-20: scope narrowed by user decision to the current stack #125 → #134 → #136 → #139 → #140 → #217 → #216 plus PR #209, which lands before #217; later phases are owned by mb-nhky.
The nine future-phase review blockers (mb-innz, mb-9aku, mb-k7lc, mb-cpco, mb-bue2, mb-79sz, mb-r596, mb-mx8q, mb-bf94) moved to mb-nhky, which is also blocked by this bead. mb-gacf was added as a blocker here. Remaining open blockers on this bead: mb-hoae, mb-k900, mb-tsdc, mb-d658, mb-gacf.

2026-09-22 reconciliation: v0.11.0 is released; this is the v0.12 stack. Live GitHub Stack 218 has exact chain #125(ed370a4e) -> #134(10990158) -> #136(e0b713b3) -> #139(4e189c9b) -> #140(93f19061) -> #217(4d25dc9a, draft) -> #216(b3c001a9, draft), all seven checks green per layer. User directs future testing, stabilization, and feature PRs to extend the same stack; hold the whole stack for stabilization and explicit landing approval. mb-nhky coordinates later phase publication but no longer means a separate landing batch. Remaining direct review blockers: mb-k900, mb-tsdc, mb-hoae, mb-gacf. HTML trust mb-d658 is closed and on main through #209, with later hardening inherited through #224. Alpha acceptance is docs/project/specs/active/plan-2026-09-22-v012-alpha-testing.md; no merge or release authorized by this audit.

2026-09-22 dependency reconciliation: removed the obsolete edge making mb-nhky wait for mb-n2ro (an early landing). mb-n2ro now waits for mb-nhky, mb-gnr9 and mb-eegt as well as its existing publication/review gates. Later feature publication can proceed on the unmerged stack, while final whole-stack landing remains held until the planned publications, alpha acceptance, review and explicit approval. This reverses the superseded split-landing sequence; it closes no product work.

2026-09-22 completed review/publication: https://github.com/jlevy/metabrowser/pull/225 is the ready-for-review eighth layer of Stack 218, head ff94e3676bf0f7caab7a8bdfdbb18eb8b1f8e1c9 over #216 b3c001a96eed64eb77961c2b7165b103af98b77c. The original seven heads and exact chain are unchanged. All seven CI checks passed: https://github.com/jlevy/metabrowser/actions/runs/35803858717 . Local make verify passed (3112 pytest tests, two skips, 147 CLI transcript checks, dependency audits and installed-wheel/distribution checks); pre-push gate passed. Real unmodified Git 2.50.1 CLI T0 smoke passed for cold/warm acquisition, nested Markdown/JSON/tree/progress, origin-absent reuse, and local filesystem inspection. Independent Astra plan review found no actionable plan blocker: https://github.com/jlevy/metabrowser/pull/225#issuecomment-5787107670 . Full top-level review: https://github.com/jlevy/metabrowser/pull/216#issuecomment-5786877244 . #136/#139 later functional deltas received independent technical review; #217/#216 acceptance remains open. New finding mb-sumg and future installed/browser acceptance mb-gnr9 remain open. Specs, QA procedure, roadmap, active release labels, PR descriptions and dependency graph are reconciled. mb-xada historical handoff is closed; #219/mb-dbue remain open awaiting a released tbd replacement. All future work extends Stack 218 and the whole stack stays held for stabilization and explicit landing approval. No GitHub URL/PR end-to-end pass, merge or release is claimed.

2026-09-24: the v0.12 stack is linear, restacked by merges (no rebases or force pushes) and bases set with gh: main ← #125 ← #134 ← #136 ← #139 ← #140 ← #217 ← #216 ← #225 ← #226 ← #227 ← #228 ← #229 ← #230 ← #231 ← #232 ← #233 ← #234 ← #235 ← #239 ← #242 ← #236 ← #238 ← #237 ← #240 ← #241 ← #243 ← #244. Every head contains its base's tip. The tree at #241 equals the tested integration tree (948861c4) plus #242's deletion. Nothing merged; landing awaits the user's approval.
