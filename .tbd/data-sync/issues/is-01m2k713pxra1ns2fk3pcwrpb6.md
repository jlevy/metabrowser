---
type: is
id: is-01m2k713pxra1ns2fk3pcwrpb6
title: "v0.12 thin-mirror stack: coordinate landing"
kind: task
status: in_progress
priority: 1
version: 69
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
updated_at: 2026-10-02T20:47:23.013Z
started_at: 2026-09-16T21:24:51.532Z
---
Coordinate landing of the v0.12 stack: one linear chain of open PRs, main <- #125 ... #244 (#241 is the draft acceptance record), plus the PRs above #244 that finish stabilization. Keep exact base/head relationships, per-layer review dispositions, green per-layer CI and top integration evidence against current main, and keep beads and specs aligned. Gates: mb-hall and mb-gnr9. SSH, the PR list and panel, inline review anchors, checkout attachment and rebind are deferred by the user's 2026-09-23 decision and do not gate landing. Hold every layer until the user explicitly approves; then land the tip as one fast-forward of main (merging lower layers one at a time would put retired-design states on main).

## Notes

2026-10-02 HANDOFF (full text also as a comment on PR #260 and in metabrowser-landing-gate-evidence/HANDOFF.md beside the main checkout):
# Handoff: landing the v0.12 stack (written 2026-10-02, about 14:00 local)

This is the state of the v0.12 landing work for the next agent. The coordinating bead is
`mb-n2ro`; run `tbd show mb-n2ro` first.

## Where it stands

- **One native GitHub stack, #218**, base `main`, 46 PRs in order: #125 … #265, then #267
  (gate fixes 2) and #260 (docs, QA runbook, review ledger) at the top. Check it with
  `gh api 'repos/jlevy/metabrowser/stacks?per_page=100'`. Every base is the branch below,
  no drafts, all CLEAN, CI green on the top two heads: #267 `14fcdb85`, #260 `2b2fad34`.
- `main` is still v0.11.0 (`6c278f3f`). **Nothing is merged, tagged or released, and
  nothing may be without the owner's explicit approval.**
- Outside the stack on purpose: #247 (do-not-merge reference of removed code), #262
  (page-connection fix, held until after landing, `mb-tdmd`), #51, #87, #219 (unrelated,
  based on `main`).
- Every worktree is clean. Worktrees are siblings of the main checkout, named
  `metabrowser-v012-<name>`.

## In flight when this was written (may be lost with the session)

1. **Independent review of #267: not finished, no report recorded.** If `mb-55tr` has no
   review note, run it again: an agent that did not write #267 reviews
   `codex/v012-gate-fixes-2` against `codex/v012-release-check` (six fixes: structured
   cache size 0, diff document hook on any file name, `--show` dotenv reads, stray
   attribute on tree folder rows, 21 px line pitch for unhighlighted source, negative
   byte bounds), with its own mutation checks.
2. **Data differential and evidence audit on `14fcdb85`**, started 13:46 as a detached
   job. Progress is in `landing-gate/final/status.log` in the session scratchpad; if that
   directory is gone, re-run from this folder (below).

## What is left, in order

1. Finish the review of #267; fix findings on #267's branch (new commits, no rewrite),
   then merge that branch into `codex/v012-landing-docs` and push.
2. Add a CHANGELOG entry (on #260's branch) for negative byte-bound settings: v0.11.0
   read unbounded at -2 and answered `plugin_error` at -3 and below; the stack answers a
   typed empty result for every negative value.
3. On the final head, all three landing-gate checks against v0.11.0 on a regular folder
   (bead `mb-2g6f`; accept rule: zero unexplained differences):
   - data: `data/run.sh <v0.11.0 metab> <tip metab> --jobs 6` (about 90 minutes; run it
     detached, a 30-minute background limit killed the first attempt);
   - evidence audit: `audit/run.sh origin/<top product branch>`;
   - browser: `browser/run.sh <v0.11.0 metab> <tip metab>` (node 24, Chrome, ports
     8851–8858; about 45 minutes).
   The harness sources and the reports from the earlier head (`f62c16b1`) are in this
   folder. Corpora and builds were not copied: `data/build_corpora.py` and
   `browser/make_corpus.mjs` rebuild them; build the tip wheel with
   `uv --config-file uv.toml build --wheel`, export constraints with
   `uv --config-file uv.toml export --frozen --no-dev --no-emit-project --no-hashes`, and
   install both builds into fresh environments with bytecode compiled
   (`env -u PYTHONDONTWRITEBYTECODE <env>/bin/python -m compileall -q <env>/lib`).
4. `make verify` on the final head (it passed on `8879c4de`, #264: 3,952 Python and 266
   browser tests).
5. Release rehearsal step 3 on a quiet machine with no agents running (bead `mb-cf6y`):
   5 headed pairs and 5 `compare_builds` pairs, recorded as exp-039
   (`release-check/rerun.sh`; see `explorations/performance-loop/` and exp-038 on #265).
6. Update the review ledger and landing status on #260 with the results; close `mb-55tr`,
   `mb-2g6f`, `mb-cf6y`, `mb-65pn`.
7. On the owner's approval only: `gh stack merge 218 --yes` with the method the owner
   chooses, then confirm `git diff <tested head> origin/main` is empty and watch CI.

## Known findings and their state

- Fixed in #264: hover prefetch of compound `.jsonl` names; `size` and decoding in
  `/api/plugin/structured/parsed`.
- Fixed in #267: the six items above.
- Open, owner's call: a below-the-fold image fetched earlier on the root overview (5 of 6
  captures, no cause found); two extra module requests (Markdown and diff views); JSONL
  log rows no longer exposed as clickable in the accessibility tree.
- Deliberate changes with no CHANGELOG entry, listed in
  `docs/project/reviews/review-2026-10-01-v012-changes-to-existing-behavior.md` on #260:
  `--end-of-options` on `git rev-parse`; `base_policy` validation answering 400.
- Follow-ups, not blocking: `mb-hj9h` (long repository name cut in the heading), `mb-32y6`
  (math as raw TeX in a mirror), `mb-tdmd` (#262), `mb-mw0t`, and the Pulls tab plan
  (`docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md`, beads `mb-lnkl`,
  `mb-iw1v`, `mb-cbak`), which is planned only.

## Decisions waiting on the owner

1. Merge method for `gh stack merge`: merge commits or squash.
2. Whether to rehearse the stack merge on a two-PR scratch stack first.
3. Three local-only branches, committed but not on GitHub: `claude/v011-cache-measurements`,
   `claude/pr-74-review-merge-a180e7`, `test/git-pin-golden`. Pushing them means skipping
   the pre-push gate, which would run on old code.
4. Accept `--doctor` being about 250 ms slower (1.78x, by design).
5. Sign off the list of intended changes to v0.11.0 behavior (the record above).
6. Manual checks nobody has run: Safari, Firefox, a private repository, third-party
   plugins; and walking `docs/qa-v012-repository-library.md`.
7. The three open browser findings above.

## Rules this work has followed

- Never rewrite or reset a stack branch: new commits, restack by merge, group with
  `gh stack link 218 <pr>`. Never retarget a stacked PR to `main`. `gh stack sync` and
  `rebase` force-push; ask the owner before using them.
- Every PR gets an independent review by an agent that did not write it.
- Never bare `uv run`, `python` or `pip`; use Make targets or
  `uv --config-file uv.toml run --frozen …`.
- Push through the pre-push gate (about 13 minutes); do not use `--no-verify`.
- Never print credentials; live tests use public repositories and read-only `gh api`.
- Never kill processes by pattern; never use the real `~/.metabrowser` in tests.
- `tbd update --notes` overwrites: read and merge the existing notes first.
- The installed `metab` on this machine is `0.11.1.dev640+8879c4de` (#264), not the top
  of the stack.

2026-10-02: native stack #218 now holds all 46 PRs, #125 ... #265, #267 (gate fixes 2, mb-55tr), #260 (docs), verified through the stacks API: every base is the branch below, none is a draft, all CLEAN, each head contains its base. #267 head 9c758f6f and #260 head 0f7f6c2c are CI green. Every worktree is clean. Outside the stack by design: #247 (reference, do not merge), #262 (held, mb-tdmd), #51, #87, #219 (unrelated, on main). Running: the independent review of #267 and one more commit on it (negative byte bounds answer as 0.11.0). Then owed on the final head: merge #267 into #260's branch, the three landing-gate checks, make verify, the quiet-machine performance pairs (exp-039). Local-only branches not on GitHub, awaiting the user's word on pushing past the pre-push gate: claude/v011-cache-measurements, claude/pr-74-review-merge-a180e7, test/git-pin-golden.

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
