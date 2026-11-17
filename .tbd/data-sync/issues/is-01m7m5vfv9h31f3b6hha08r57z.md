---
type: is
id: is-01m7m5vfv9h31f3b6hha08r57z
title: "CI speed 2.5: verify Phase 2 after the merge: 20 pull request runs, a red main, cancellation, the stack cases, and the nightly"
kind: task
status: open
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-11-16-fast-ci.md
labels: []
dependencies: []
parent_id: is-01m7kh4k0qtd75277xcq14dt1b
created_at: 2026-11-17T07:17:00.392Z
updated_at: 2026-11-17T17:02:10.817Z
---
After-merge acceptance of Fast CI Phase 2 (jlevy/metabrowser#504, branch claude/ci-split-jobs), from the accept criteria of mb-oz36, mb-r283, and mb-stg2 that need runs only a merged workflow can produce. plan-2026-11-16-fast-ci.md, Testing Strategy.

- Split jobs: over 20 pull request runs after the merge, median push to green at or under 5 minutes and 90th percentile at or under 6 (make ci-report), and unit, the serial tier, and chrome together collecting the tests the old test job collected on the same commit. If a unit leg's 90th percentile passes 4.5 minutes, add a third shard; measure the queue wait again (a main run is now 34 jobs, a pull request 22).
- ci-ok: a pull request with one deliberately failing shard, closed unmerged: ci-ok red and naming it, the other jobs finishing.
- A red main in CI: the first pull request run after main is next red, and a rerun of a run from before, both run the Chrome tier on all four; the first's verdict line says tested=yes with main's head, the rerun's tested=no.
- Cancellation: two pushes a minute apart cancel the first run; a main run is never cancelled.
- stack-integration: a stack behind main (needed; seen on #504's first run), one level with it (identical), and one that conflicts (conflict), each with its plan summary.
- Nightly soak: one workflow_dispatch run of nightly.yml (it needs the file on main): 5 serial jobs and 20 Chrome shard jobs run and report, and the time-limits job reads ci.yml's runs since the last change to ci.yml.
- Replace each new job's estimated timeout-minutes (plan, unit, chrome, ci-ok, nightly time-limits) with 1.5 times its measured 90th percentile once the runs exist.

## Notes

2026-11-17: after reviews A and B of #504, the stack cases are four: contained (a formal stack), and needed, identical, and conflict (an informal chain). Review A7 notes that a formal stack that conflicts with main may get no merge ref and so no pull_request run; check which. The unit, chrome, and stack-integration limits are now 7, from the slowest part's 90th percentile over runs 44037230262 to 44046843606.

2026-11-17 (review C of #504): one sample shows the limit includes checkout: in run 44125857838 attempt 1, unit (3.12, 2/2) hit its 7-minute limit because checkout's full-history fetch took about 6 minutes (16:27:23 to 16:33:15 UTC). When re-taking limits, measure checkout separately and consider a shallow fetch where the job does not need history. Run 44128706304 (at f34f656) took the formal-stack-after-main-moved path on GitHub: plan reported not read, narrow Chrome, needed, and the eight stack-integration jobs ran (review C7).
