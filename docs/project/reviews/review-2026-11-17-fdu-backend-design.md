# Review: fdu Backend Design, Two Rounds, 2026-11-17

**Date:** 2026-11-17

**Status:** A dated record of two review rounds of the
[revisited fdu backend research](../research/research-2026-11-17-fdu-backend-revisited.md),
its implementation plan, and the
[Linux spike](../../../explorations/fdu-provider-spike/README.md).
Round one’s findings were applied before round two; round two’s are applied in the same
pull request as this record, and the research holds the result.
Line references describe Metabrowser `79ee3697` and fdu `4450be7`.

## Scope and Method

Each round used independent reviewers on a separate model from the authors, given the
documents and code rather than the authors’ conclusions, with read-only access to both
repositories.
Every reviewer verified claims against code and evidence files and reported findings by
severity.

- **Round one, design:** the research brief and the plan’s rewritten Checkpoints 2C and
  2D, with 36 spot-checked claims (30 held, 4 did not, 2 were unsupported).
- **Round one, spike:** the spike’s adapter, harnesses, correctness classes, and
  measurement method, with every headline number recomputed from raw output and seven
  reruns.
- **Round two:** the revised design (decisions D12 to D19, the corrected evidence, the
  regrouped fdu change list as an upstream proposal, and the proposed order of the
  fdu-independent Metabrowser work).

## Round One

### Design

Verdict: the boundary, evidence base, and most decisions were sound; not ready to drive
implementation until three things changed.

| Finding | Disposition |
| --- | --- |
| Critical: 4,096-row pages make large assemblies multi-read while fdu keeps only its current version | Added D13 (paging under version movement); revised again in round two |
| Critical: the experimental provider was registered before an adapter existed and put index-sized fallbacks in `src/` | D12 rewritten: thin adapter in `src/`, fallbacks in a harness outside it |
| Major: the 3.5 to 5.4 times engine figure was the observation-off configuration | Performance results restated by configuration |
| Major: no decision on memory, native panics, GIL hold, admission order, case-insensitive filesystems, or version evolution | Added D14 to D19 |
| Major: fdu refuses work bounds above 1,000,000 | D11 lists every paired bound |
| Major: D9 and F1 overlapped | D9 rewritten; revised again in round two |
| Major: repository obligations (parity rows, map, CHANGELOG) unstated | Stated for every observable change |
| Major: macOS list incomplete | Expanded from the spike’s README |
| Minor: tally key, counts, ranges, sizes, links | Corrected |

### Spike

Verdict: the direction held and every recomputed number matched, but several specifics
did not.

| Finding | Disposition |
| --- | --- |
| Critical: “first useful tree” timed a rollup readiness gate, not the tree | Re-measured with a socket-only readiness check; the native tree answers as early as Python’s; R28 withdrawn |
| Major: page chaining ignored the work limit, and helper reads were charged to requests | Adapter bugs fixed; work bounds re-run half by half |
| Major: 161 of 168 route passes overstated coverage | 85 tests actually build an fdu backend |
| Major: invalid registries were refused only for their schema | Re-checked through the shim: 18 of 21 refused for their own defect |
| Major: the binding cost was one whole-read sample | Split by layer and repeated: native 3.5 to 4.2 µs, dataclass rebuild 5.6 to 9.6 µs, adapter 3.5 to 3.9 µs per row |
| Major: a flake attributed to Python came from an injection leaking into the Python baseline | Harness fixed; the recursive-removal test passes 32 of 32 for both providers |
| Major: reproduction failed on macOS and timed scripts were not committed | Harness fixed; `series.sh` refuses uncommitted scripts |

## Round Two

| Area | Verdict |
| --- | --- |
| Revisions (D12 to D19, corrected claims) | Not ready: D13 unsound for filtered and grouped trees, dependent on an unrequested fdu capability, and missing its dirty-path rules; D9’s premise false; several headlines still off the evidence. D12, D14, D17, and D19 sound in direction |
| fdu proposal | Not ready as written: four items contradict decisions fdu has recorded; one blocking item missing; one mis-grouped |
| Layer order | Ready with changes |

### Critical

| ID | Finding | Evidence |
| --- | --- | --- |
| C1 | D13 needs fdu to resume a continuation at a moved version, which fdu refuses and no F item requests | fdu `crates/fdu-core/src/opened/read.rs:133` returns `ContinuationStale`; its plan states a later page fails with a stale-version result |
| C2 | Re-reading dirty paths through lookups cannot repair filtered or grouped tree rows, whose directory totals are selection-specific | `python_inventory.py:529-602` (`_TreeSelection.listed_totals`); `tree_page_assembly.py:103-110` rejects total drift; fdu’s plan makes filtered trees complete-or-limit |
| C3 | Dirty-path semantics are undefined and differ: Python names only a removed directory, fdu records one change per entry and goes all-dirty past 256, and the host merge loses order | `python_inventory.py:4441-4452`; fdu `engine_contract.rs:1611`, `MAX_DIRTY_PATHS = 256`; `coordinator.py:780-812` |
| C4 | fdu’s schema 3 and 4 parser requires presentation fields, so a classification document with presentation removed is refused as surely as schema 5 | fdu `classify/file_rollup_manifest.rs:224` requires `hue` on every family |

### Major

| ID | Finding |
| --- | --- |
| M1 | “Provisional while coverage is partial” makes trees with an unreadable directory or a budget stop provisional forever; key it on discovery instead |
| M2 | D13 has no convergence argument under discovery or churn, and would regress Python, whose per-version memo always completes; both providers should satisfy the rule rather than implement one mechanism |
| M3 | The assembler has no source of paths dirtied since its first page; it needs a per-read dirty ledger in the coordinator, the same mechanism as R27, so bounds and paging depend on host consistency |
| M4 | Retained versions (F22) contradict an fdu non-goal; present them only as a fallback |
| M5 | D6’s hard bound contradicts fdu’s recorded soft tree budget and the spike’s evidence |
| M6 | Refresh-receipt coalescing likely misses watcher-driven changes, which pass through the same reconcile path in fdu; state a general rule that a transient freshness transition is not its own envelope, with a bounded hold |
| M7 | The typed unsupported-kind failure has no shape, and a whole-read failure breaks native companions; it needs a per-projection result, a shrink-only expected list, and an experimental CHANGELOG entry |
| M8 | No decision on observation over remote or unknown filesystems, where Python polls and fdu has no polling or detection |
| M9 | R31 must cover every multi-page assembly consumer, including the SSE snapshot and `--api`, not only `/api/rollup` |
| M10 | The spike’s Python engine floor polled `handle.read` every 2 ms and competed with the walker; unpolled, `project-10` discovery is 2.1 times faster with fdu, not 3.6, and a polling client doubles Python’s discovery |
| M11 | The server “settled” figure measures the fallback rollup, not the configuration that ships |
| M12 | The stated A/A bands do not match the evidence file |
| M13 | Only native object building is an uninterruptible GIL hold; the dataclass rebuild and adapter conversion are preemptible Python, and moving them into native code lengthens the hold unless it is chunked |
| M14 | D18 allowed two answers; on a case-insensitive volume a wrong-case refresh can create an alias entry |
| M15 | Reopening from inside the relay task would cancel and await itself; recovery needs a supervisor and fault seams |
| M16 | No fdu-independent test reproduces the host bugs fdu exposed; a test-only wrapper provider that perturbs granularity, identity, replay, relay timing, and faults makes them deterministic |

### Minor

Corrected counts and wording (failure tallies, extension checks, the conformance
failure list, the F13 ratio range, the open-time group’s size), lowering the priority
path bound to fdu’s 64, excluding budget-stopped corpora from the semantic precheck,
measuring page-size constants after row-cost work, and aligning the plan, bead table,
and layer order.

### fdu Proposal Changes

- Reframe F9 to F12 as properties of fdu’s planned report views (output-bounded work,
  portable paths, ignored demotion, exact-or-capped totals) rather than new projection
  variants, which fdu’s bead `fdu-a0cf` rejects.
- Make F13 a complete-or-limit selected tree, for one or several selections in one pass,
  and reverse D7.
- Present F22 as a fallback that contradicts a non-goal, and drop F4’s 1,024 paths and
  “inert once stopped”.
- Add resumable positions across versions, classification-profile registry parsing in
  the open-time group, a fault-injection seam, case and normalization aliasing on
  refresh and lookup, and observation on remote or unknown filesystems.
- Resize F2 (an adoption gate, not an open-time item), F6 (M), and F15 (likely L); state
  F15’s invariant rather than its mechanism; cite F17 to memory only; offer F21 as
  caller-supplied ancestor rules; make F25 a cancellable wait; file F23 separately.

### Layer Order

1. Test and benchmark seams, plus the wrapper provider and fault seam, in three pull
   requests.
2. The decisions record, recording only Metabrowser’s unilateral decisions as decided,
   and conformance neutrality.
3. Host consistency: relay and refresh, a recovery supervisor, and moved-version mapping
   for every assembly consumer.
4. Honest Python semantics, moved up because it needs no fdu input and defines the
   baseline: provider-level oracles, then `--walk` through the runtime, then
   unreadable directories, then watch scope alone.
5. Contract types after fdu answers on aggregate shape and the registry profile.
6. Bounds and paging, with change-batch facts and row cost first, and D13 only after
   fdu agrees.
7. The provider package move, remaining host costs, and the Python re-baseline.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
