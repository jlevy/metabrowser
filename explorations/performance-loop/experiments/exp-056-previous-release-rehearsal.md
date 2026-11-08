---
title: Previous-Release Rehearsal
softschema:
  contract: metabrowser.loadtime:Experiment/v1
  schema: experiment.schema.yaml
  envelope: experiment
  status: enforced
experiment:
  id: exp-056
  title: Previous-Release Rehearsal
  date: "2026-11-07"
  hypotheses:
    - H85
  subject:
    corpus: Frozen project-10 dependency corpus, shape 2, canonical identity tree-421a46c7.
    corpus_files: 120640
    host_system: MacIntel browser platform; exact OS build is not recorded in the canonical rows.
    browser: Visible Chrome 152, fresh origin and visible profile for each recorded capture.
    viewport: 1600x900
  method:
    runs_per_condition: 1
    interleaved: true
    record: ../results/runs.jsonl
    control: Published 0.11.0 at 6c278f3f9e10aebcb34a207035aee7768a1bba0e; one admitted browser capture.
    candidate: 0.11.1.dev1272+68534af93 at 68534af933f0fcb38a5d81d62691bb42732d58ab; two admitted captures, with the second unpaired and failed.
  results:
    - metric: first_row_ms_completed_pair_01_singletons
      control_median: 130
      candidate_median: 114
      control_range: [130, 130]
      candidate_range: [114, 114]
      overlapping: false
  verdict:
    decision: unresolved
    primary_metric: first_row_ms
    reason: The valid second candidate capture measured 444 ms against the 350 ms hard gate. Only one browser pair completed; its matching second control and all backend pairs were not run. This incomplete rehearsal establishes neither release acceptance nor a speedup.
---
**Status:** Incomplete, with a valid candidate hard-gate failure retained.
The declared five browser pairs and five backend pairs did not complete.

## Declared Release Checks

The protocol was declared before measurement on November 7, 2026. H85 combines three
release checks:

1. Ordered navigation rows and tally answers remain equivalent to published 0.11.0
   except for documented changes.
   Any unexplained difference blocks acceptance.
2. Every candidate browser capture meets the committed responsiveness and correctness
   hard gates. A faster primary metric cannot compensate for a missed gate.
3. Release metrics have no repeatable wrong-way paired ratio above 1.3 under the stated
   rerun policy. This is a rough sanity check, not a quiet-host speedup claim.

The intended sequence was five browser pairs in alternating control/candidate and
candidate/control order, followed by five interleaved backend pairs.
An unrecorded opening serve/fingerprint cycle preceded the captures.
Browser conditions changed only the wheel in one environment, using fresh origins and
visible profiles. Backend conditions were to use separate compiled environments with
shared dependency versions constrained by the candidate lock; those backend runs never
started.

The declared policy allowed one pair above the rough paired tolerance to be repeated
once; two offending pairs or a failed repeat would block release acceptance.
That ratio policy does not relax an individual candidate hard gate.

## Frozen Identities

| Condition | Application source | Wheel SHA-256 |
| --- | --- | --- |
| Control, `metab 0.11.0` | `6c278f3f9e10aebcb34a207035aee7768a1bba0e` | `b099786f84408968df10296fdf7226218dd8853faf1cdb02a25787c5ab396e7f` |
| Candidate, `metab 0.11.1.dev1272+68534af93` | `68534af933f0fcb38a5d81d62691bb42732d58ab` | `9b5ebaad3c6271acbc15795a7651c1fc4524777f24e1d2ce0213025cd92100c7` |

The harness source was `c67371c2ead80e0db76098d77e77738b670e8ce6`, including the
linked-install-root corpus correction.
It did not change the measured application or dependency files.
The state-location driver relocated only ignored pending, port and server-log files; the
committed probe, budgets, identity checks and measurement algorithms remained in use.

All three canonical rows report corpus shape 2 and fingerprint
`e5f58e2555ca0d99ea35b782a375156512ccafef2c5fecf36e961956490563e2`, with 120,640 files
in the browser inventory.
The generator’s separate raw traversal reported 244,342 files and 30,081 directories;
these counts describe different projections.
The recorded browser environment identity is
`0688ce1b5d0231061aff3c7d4dbe6579b2c089cfd428bc3bf872d77132901706`. Both builds report
provider `python` and contract `inventory-provider-v1`.

## Admitted Observations

The [canonical ledger](../results/runs.jsonl) retains exactly these three exp-056
records. Labels and measurement run IDs identify them without local paths.

| Sequence | Label | Measurement run ID | First row | Outcome |
| --- | --- | --- | ---: | --- |
| Pair 1, control | `exp056-release-v0110` | `6fe78db3cf4f6b4b75dc76dbaf92f63c` | 130 ms | Capture exited 0 |
| Pair 1, candidate | `exp056-main-68534af93` | `ab6d5b436e84ed1f268dde0eeeea7abc` | 114 ms | Capture exited 0 |
| Pair 2, candidate first | `exp056-main-68534af93` | `2cd6ce926d560fbc79379253e72c6b7a` | 444 ms | Capture exited 1; hard gate failed |

The second candidate exceeded the committed `first_row_ms <= 350`
[hard gate](../performance-budgets.toml).
Its capture reported one hard-gate miss and three roadmap-target misses.
The driver retained the row and stopped before pair 2’s matching control; no backend
pair ran.

All three rows have `measurement_valid: true`. The 444 ms observation is valid
measurement evidence of a gate failure, not an invalid capture or a discarded outlier.
The schema’s median/range fields above contain only pair 1’s two single observations,
and `runs_per_condition: 1` counts that one completed pair.
They are not statistics over the planned series or over unequal control/candidate
samples. No overall paired median, tolerance decision, navigation-equivalence result or
speedup is established.

## Setup Rejection and Interpretation

Setup attempt `attempt-00-identity-declaration` was rejected before any canonical row
was appended. The driver had incorrectly declared that the published control lacked
inventory identity. Its walker log and debug endpoint actually report `python` /
`inventory-provider-v1`. The rejected capture and original driver were retained; the
admitted series used the observed identity for both builds.

A separate unrelated CPU-bound job occupied one core during this rehearsal.
Its presence limits a quiet-host interpretation, but no causal link to the 444 ms result
was established. It does not invalidate the observation or excuse the hard-gate miss.

Subsequent UI requests change the next application candidate.
Experiment `exp-057` will measure that final candidate separately; exp-056 remains an
incomplete rehearsal of the exact source and artifacts above.
It does not measure the later UI commit `24f3721c9`, establish a complete
previous-release comparison, or confer release acceptance.
[Exp-055](exp-055-progressive-pr-metadata-warming.md) retains its separate
PR-preparation subjects, measurements and limits.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
