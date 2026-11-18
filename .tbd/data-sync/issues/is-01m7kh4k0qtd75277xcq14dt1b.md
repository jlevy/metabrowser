---
type: is
id: is-01m7kh4k0qtd75277xcq14dt1b
title: CI takes ~20-25 minutes per push; assess end to end and design how to get the PR gate to 3-5 minutes with the same coverage
kind: task
status: in_progress
priority: 1
version: 36
delegate: claude-code@spud10.local
labels: []
dependencies: []
child_order_hints:
  - is-01m7kpmdd2sqmd8xdkp7nmef7k
  - is-01m7kpme30x5k8w9nvtdwam8r2
  - is-01m7kpmejx8xf1ymb22jnmjsfr
  - is-01m7kpmf2bmaqx2fy8f3ytp3yq
  - is-01m7kpmfhmfryhsb2eg3fg7jyp
  - is-01m7kpnbgvh17pnc0z229034gd
  - is-01m7kpnc003tcx5fa2qjt9pf8e
  - is-01m7kpncf08n8ckbdq6baayrxn
  - is-01m7kpncy9xzk6a0rhv0vxd4db
  - is-01m7kpnddkcadvetnzbrfy8hy9
  - is-01m7kpndww8wehzg3zya4x6wy5
  - is-01m7kpnebx9r14tv5m3e3wrfwj
  - is-01m7kpnew2rrszv4ekchm6c75z
  - is-01m7kpnfbtzejh3redbeppejmp
  - is-01m7ks84x8evd46whm3vmcgfjh
  - is-01m7ks85cztbqgy4bw9ntv7c7s
  - is-01m7ktycr1m7798eaqhyky3qnr
  - is-01m7kvt6zsgb9m5xpanazw7prr
  - is-01m7kwcymkyzy307gn8bvwhx18
  - is-01m7m3rn4x4ttt604xrtj32vff
  - is-01m7m5vfv9h31f3b6hha08r57z
  - is-01m7m7fshyv62ga8zqj1rc9xej
  - is-01m7m91x7qs2xbsz7kae1ch64n
  - is-01m7man9fyy31fp5mmq7xg7ake
  - is-01m7mby30w7w14nj5hhj6m9jx0
  - is-01m7mby7m1z850mwaf34qn4xfx
  - is-01m7pj8gve71bkvxyw96nqa4yn
hold: null
hold_until: null
created_at: 2026-11-17T01:14:58.454Z
updated_at: 2026-11-18T05:32:19.181Z
started_at: 2026-11-17T01:15:52.976Z
---
Owner, 2026-11-16: 'investigate why CI is taking so long. This is unacceptably slow for CI. CI should be something like 3 to 5 minutes, or else we should figure out ways to avoid extraneous checks except when they're appropriate. ... properly assess this end-to-end and what the proper engineering solution is to maintain the same levels of coverage but speed up our development velocity.' Deliverable: a research brief and plan PR with implementation beads; workflow-file changes need the owner's OK (no grant covers workflow files).

## Notes

2026-11-16: assessment and plan are jlevy/metabrowser#496 (branch claude/ci-speed-assessment): docs/project/research/research-2026-11-16-ci-speed.md and docs/project/specs/active/plan-2026-11-16-fast-ci.md. Documents only; no workflow, Makefile, dependency, or setting changed. Measured from the last 300 ci.yml runs; the xdist speedup (assumed 2.5 to 3.2 times) was NOT measured, and mb-dz35 measures it first. Implementation beads: mb-a1le, mb-dz35, mb-4ub2, mb-tjdq, mb-f0z9 (Phase 1); mb-oz36, mb-to1c, mb-r283, mb-stg2 (Phase 2); mb-nx36, mb-v719, mb-6nn3, mb-37dw, mb-pvyg (Phase 3). Raw run data and the analysis scripts are in the ci-speed worktree's gitignored attic/ci-speed/.

2026-11-16, owner decisions, relayed by the coordinating session and recorded in the plan at commit 1e6f437f4: Q1 approved (restructure ci.yml and add the nightly workflow, through reviewed pull requests); Q2 yes (pytest-xdist 3.8.0 and execnet 2.1.2 in the dev group); Q3 the serial tier on Python 3.13 for a pull request and on all four interpreters on main; Q5 yes, the owner sets a ruleset requiring ci-ok once the job exists. Q4, Q6, Q7, Q8 open. Phase 1 is implemented on branch claude/ci-parallel-tests and Phase 2 stacked on it.

2026-11-17: owner decisions recorded on #496 at 1e6f437f4. Phase 1 not started (branch claude/ci-parallel-tests has no commits, not pushed). Sub-agent stopped for handoff (PR #497).

2026-11-17 (2): #496 review A published (A1, A2 Medium); decisions in coordinator attic/coord/reviews/pr496-A-decisions.md; not addressed yet. Handoff PR #497.

2026-11-17: the research brief and plan merged in PR #496 (c906ff5cb) after Reviews A, B, C, all dispositioned. Phases 1 and 2 are being implemented (claude/ci-parallel-tests and a stacked Phase 2 PR); close this when Phase 2 merges.
