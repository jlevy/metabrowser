---
type: is
id: is-01m7kh4k0qtd75277xcq14dt1b
title: CI takes ~20-25 minutes per push; assess end to end and design how to get the PR gate to 3-5 minutes with the same coverage
kind: task
status: in_progress
priority: 1
version: 29
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
hold: null
hold_until: null
created_at: 2026-11-17T01:14:58.454Z
updated_at: 2026-11-17T07:17:00.392Z
started_at: 2026-11-17T01:15:52.976Z
---
Owner, 2026-11-16: 'investigate why CI is taking so long. This is unacceptably slow for CI. CI should be something like 3 to 5 minutes, or else we should figure out ways to avoid extraneous checks except when they're appropriate. ... properly assess this end-to-end and what the proper engineering solution is to maintain the same levels of coverage but speed up our development velocity.' Deliverable: a research brief and plan PR with implementation beads; workflow-file changes need the owner's OK (no grant covers workflow files).

## Notes

2026-11-17: the research brief and plan merged in PR #496 (c906ff5cb) after Reviews A, B, C, all dispositioned. Phases 1 and 2 are being implemented (claude/ci-parallel-tests and a stacked Phase 2 PR); close this when Phase 2 merges.
