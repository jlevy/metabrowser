---
title: A backend-only comparison finds v0.11.0 equivalent and does not clear it for release
softschema:
  contract: metabrowser.loadtime:Experiment/v1
  schema: experiment.schema.yaml
  envelope: experiment
  status: enforced
experiment:
  id: exp-036
  title: A backend-only comparison finds v0.11.0 equivalent and does not clear it for release
  date: "2026-09-21"
  hypotheses: []
  subject:
    corpus: >-
      repository-shaped project-10 tree-705e090a, built fresh on this host by
      build_project_corpus. It is the documented project-10 shape but not exp-034's
      tree-8cf3e743: the installs it copies have moved since, so absolute numbers do not
      carry across the two rounds and nothing here is compared to them. This round is
      self-contained, control against candidate on one tree that did not change between
      them
    corpus_files: 119980
    corpus_dirs: 6850
    host_cpu: Intel Xeon @ 2.10GHz, 4 vCPU
    host_system: Linux 6.18.44-fc-v37, CPython 3.12.3
    browser: none; no captures were taken, which is why this round resolves nothing
    cold: false
  method:
    runs_per_condition: 5
    interleaved: true
    control: the v0.10.0 wheel, built from tag c97de624 in a detached worktree
    candidate: the 726a7858 wheel, the commit proposed for the v0.11.0 tag
    record: >-
      devtools.compare_builds over installed console scripts from two environments
      created outside every work tree, five interleaved pairs, corpus fingerprinted
      before and after
  results:
    - metric: backend_first_row_s
      control_median: 0.013
      candidate_median: 0.012
      control_range: [0.011, 0.013]
      candidate_range: [0.011, 0.015]
      change_pct: -7.7
      overlapping: true
    - metric: index_done_s
      control_median: 6.555
      candidate_median: 6.663
      control_range: [6.397, 6.724]
      candidate_range: [6.507, 6.832]
      change_pct: 1.6
      overlapping: true
    - metric: peak_rss_mb
      control_median: 187.1
      candidate_median: 187.1
      control_range: [186.9, 187.4]
      candidate_range: [187.0, 187.4]
      change_pct: 0.0
      overlapping: true
    - metric: tally_overlap_progress_max_ms
      control_median: 71.6
      candidate_median: 78.1
      control_range: [68.7, 77.3]
      candidate_range: [70.9, 81.9]
      change_pct: 9.1
      overlapping: true
  verdict:
    decision: unresolved
    primary_metric: project10_browser_first_row_ms
    reason: >-
      The primary metric was not measured. Time to first directory rows is a required
      release metric and comes from headed browser captures; this host has no Chromium
      and this round took none. What the backend half does establish is equivalence:
      valid is true, the corpus fingerprint is identical before and after, and ordered
      rows and tallies match the control exactly, so the candidate returns the same
      answers. Every timing moved less than the 1.1x careful tolerance with overlapping
      ranges. That is consistent with the release being harmless on this path and is not
      the same statement as clearing it. The obligation exp-035 created - that a change
      touching a measured path needs the captures taken again, and v0.11.0 contains one
      in _catalog_content_identity - is carried forward, not discharged.
    commit: 726a7858
---
# exp-036: a backend-only comparison finds v0.11.0 equivalent and does not clear it for release

## The question

v0.11.0 is ready on every other gate.
The release checklist asks for a comparison with the previous published release, and
exp-035 set a sharper version of the same requirement: it deferred the catalog content
hash to the first change after the v0.10.0 tag precisely because
`_catalog_content_identity` sits on the path exp-034’s captures measured, and it wrote
down that “a change that touched a measured path … would need the captures taken again”.

That change is in this release.
So is a new pair of ASGI middlewares that run on every request.
The question this round can answer is narrower than the one the checklist asks: does the
candidate still return the same answers, and does anything on the backend path move
enough to see?

## What was run, and what was not

Five interleaved pairs of `compare_builds` over installed console scripts, both built as
wheels the way `make build` builds a release — the control from tag `c97de624` in a
detached worktree, the candidate from `726a7858`. Environments were created outside
every work tree, and each `metab --version` was asserted against its own wheel before a
timing was taken.

No browser captures.
This host has no Chromium, and `record` refuses a headless capture because the
responsiveness gates depend on a visible tab.
That is the whole reason the verdict below is `unresolved` rather than `accepted`: the
release metric is `project10_browser_first_row_ms` and it was not measured.

## Equivalence, which is the part that did resolve

`valid: true`. The corpus fingerprint — 256,023 files across 31,561 directories — is
identical before and after the ten runs, so nothing wrote into the tree between
conditions. Ordered rows: zero differences.
Tallies: zero differences.
No errors and no validation errors.

This is worth stating plainly because it is the guard that matters most for a release
carrying a hashing change.
The candidate computes the catalog content identity by joining each page once instead of
updating the digest four times per record, and the claim attached to that change is that
the digest is byte-identical.
Nothing here contradicts it, and the equivalence check is a stronger reading of it than
the unit tests alone: it compares the actual responses two installed builds serve from
one tree.

## Timings, and why none of them is a finding

| metric | control | candidate | change | ranges |
| --- | --- | --- | --- | --- |
| backend `first_row` | 0.013 s | 0.012 s | −7.7% | 0.011–0.013 vs 0.011–0.015 |
| `index_done` | 6.555 s | 6.663 s | +1.6% | 6.397–6.724 vs 6.507–6.832 |
| peak RSS | 187.1 MB | 187.1 MB | 0.0% | 186.9–187.4 vs 187.0–187.4 |
| `tally_overlap_progress_max_ms` | 71.6 ms | 78.1 ms | +9.1% | 68.7–77.3 vs 70.9–81.9 |

Every range overlaps its counterpart, and every median moves less than the 1.1x careful
tolerance. The largest mover, `tally_overlap_progress_max_ms`, is a maximum over samples
rather than a central statistic, which is the shape that moves most on a shared host;
its candidate range sits inside 1.1x of the control’s and the two overlap across most of
their span.

Reading a 2% improvement in one run set and a 1.6% regression in another as signal would
be reading the noise floor.
The honest summary is that the backend path did not move enough for five pairs on this
host to see, in either direction.

## What this does not say

It does not say v0.11.0 is faster.
The catalog hashing change was measured at 62 ms to 41 ms at 300,000 rows, which is
about 8 ms at this corpus’s row count, against an `index_done` whose own spread here is
330 ms. This round could not resolve that change even in principle, and did not set out
to.

It does not say the new middlewares are free.
They run on every request and were not isolated here; the whole-load cost was estimated
by microbenchmark at under half a millisecond, and an estimate is what it remains.

Most of all it does not clear the release.
A backend comparison is half of a release round by construction, and the half it omits
is the one the checklist names.
v0.11.0 ships, if it ships, with the browser captures outstanding and this file as the
record of that choice.

## Carried forward

The 300k re-measurement that
[the flat-tree plan](../../../docs/project/specs/active/plan-2026-09-15-flat-tree-delivery-cost.md)
lists as step 4 is still owed, and exp-035’s standard means it is owed to this release’s
evidence and not only to the tier-1 work.
A later round on a host with a browser should take the project-10 captures and the 300k
flat-stress pass together, and lower the flat-stress ratchet in whichever change earns
it.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
