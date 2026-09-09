# Review: Inventory Stack Merge Readiness

**Date:** 2026-09-07

**Status:** Review and final fixes complete.
The full local `make verify` gate passes.
Check the top commit’s GitHub CI before merging the stack.

**Scope:** The complete stack ending at
[metabrowser#101](https://github.com/jlevy/metabrowser/pull/101): #74, #98, #91, #99,
and #101. Reviewed against `main` at `aeef188a`, starting from top-branch commit
`7190f21f`. Work is tracked by `mb-jqvz`; the fixes are on the top branch.

## Engineering Assessment

The refactor is a sound foundation for the shipped Python provider after the fixes
below.
The review found concrete concurrency and browser freshness defects, rather than a
reason to replace the provider boundary again.
The boundary has five operations, batches coherent reads, and keeps retained filesystem
facts with one owner.
The coordinator adds sparse host state without retaining another complete inventory.
Those properties leave room for a native implementation without requiring every browser
consumer to change with it.

The most consequential structural fix removes the coordinator lock from provider I/O
during multi-page assembly.
A root operation lease protects lifecycle ownership, and an immutable sparse overlay
snapshot protects page consistency while unrelated reads and host updates continue.
The Python provider can continue an already-retained page sequence after live mutations;
it does not need a second full inventory image to do so.

Native adoption still has explicit prerequisites.
Rollup and navigation projections contain browser wire models, and the exploratory fdu
adapter rebuilds a Python entry graph to answer aggregate queries.
That spike is evidence of the remaining cost, not a production adapter.
Native aggregate ownership, retained-page behavior under churn, and recovery after an
engine failure must be resolved and measured in `mb-hej8` and its related beads before
shipping a second provider.
The current merge should not be described as completing native-provider adoption.

## Fixed Findings

| Finding | Result | Tracking |
| --- | --- | --- |
| Cancelling the first coordinator close could let later callers return before shutdown joined | One owned shutdown task is shielded and joined by every close caller | `mb-98aj` |
| A delayed refresh could replace newer metadata or remove a newly updated entry | Refresh retains its write generation across filesystem observation | `mb-n7j0` |
| Refresh and priority hints could follow symlink ancestors outside the walker’s scope | Native ancestor checks are shared by refresh, priority, and subtree rewalk paths | `mb-rzta` |
| Page assembly held a host lock over provider I/O | Root lease plus sparse immutable overlay snapshot permits concurrent publication | `mb-vknc`, addressed portion |
| Immutable page memos were rejected after any live engine advance | Continuations use their retained version/state; eviction still fails explicitly | `mb-6elt` |
| Canonical percent escapes reached native filesystem joins and browser labels | Host readers use the inverse; URLs, links, search, breadcrumbs, and live rows preserve identity and readable names | `mb-efvg`, `mb-02sc` |
| Generic JSONL failed when opened before agent-log assets | Views register immediately and load the shared renderer through the SDK, with disposal guards | `mb-b6gy` |
| Collapsed or prefetched folders kept old children after a filesystem event | Affected cache variants and in-flight reads are invalidated; mounted hidden rows stay current | `mb-rg0h` |
| Reopening an edited inactive file served an indefinitely stale preview | Changed facts and ancestor events flag existing ETag revalidation, including invalidations during a request | `mb-1luh` |
| Recent queries constructed unused full-tree topology and repeated filter setup | Build only the topology a query consumes and fold extensions once | `mb-dva8` |
| Recent rebuilt full entries and unused host decorations for every returned file | Compact validated Recent records and distinct-ancestor traversal remove this work without a cache | `mb-ulzy` |
| The overlay-only test raced unrelated native watcher delivery | Isolate its watcher; retain separate real-watcher coverage | `mb-mibz` |
| Fast scans never satisfied the serving benchmark’s completion detector | Child processes explicitly enable the DEBUG completion log; a small-corpus regression covers it | `mb-gan6` |
| Index metadata omitted the served root and JSON/YAML walk ignored provider selection | Restore root-inclusive counts and honor the selected provider for model output | `mb-sb5b`, addressed portion of `mb-iyu7` |
| Planning and spike disposition contradicted unresolved work and reproducibility | State native gates explicitly and retain the adapter with its rerunnable historical harness | `mb-drw5`, `mb-uaiv` |

The observable path contract change bumps the hard plugin SDK gate to **0.6**, together
with every built-in manifest, fixtures, current authoring documentation, and CLI
goldens. See [plugin path identity](../../plugins.md#path-identity).

## Performance Evidence

**Correction, September 8:** the September 7 paired measurements below used a
free-threaded Python baseline and regular Python for the candidate.
They do not establish code-only startup, CPU, memory, or serving improvements or
regressions. The initial September 8 scratch rerun had the same flaw.
Retain these historical observations with that limitation; use the matching-runtime
comparison below for the file-navigation conclusion.

The [sanitized serving results](evidence/inventory-stack-serving-2026-09-07.json) retain
the full measurements and method notes.
Both builds used the same physical corpus and machine, with eight clients in the
concurrency phases.
These single diagnostic runs are not statistical performance budgets.
The candidate includes the provider fixes and Recent optimization, measured before the
subsequent browser cache fixes.

| Measurement | Main, synthetic | Candidate, synthetic | Main, project | Candidate, project |
| --- | --- | --- | --- | --- |
| Observed regular files | 60,000 | 60,000 | 11,727 | 11,727 |
| Scan completion, ms | 9,719 | 5,673 | 2,452 | 672 |
| Scan process CPU, s | 3.64 | 2.95 | 1.57 | 0.93 |
| Scan peak RSS, KiB | 128,736 | 120,448 | 88,992 | 75,504 |
| Scan with client attached, s | 16.5 | 6.2 | 2.5 | 1.9 |
| First folder count on wire, s | 0.90 | 0.77 | 0.77 | 0.58 |
| Rollup during scan p95, ms | 102.1 | 66.6 | 21.6 | 23.8 |
| Settled rollup, aggregated p50, ms | 25.6 | 46.8 | 5.9 | 8.4 |
| Navigation first pass, ms | 754.7 | 482.6 | 170.0 | 190.8 |
| Catalog first body, ms | 73.1 | 281.0 | 4.4 | 26.0 |
| Settled peak RSS, KiB | 175,792 | 131,568 | 97,600 | 78,448 |

The observed startup, CPU, memory, and serving differences combine code and interpreter
changes. `mb-5no9` tracks further scaling measurements with matched runtimes.
The 60,000-file Recent profile also fell from 613,017 calls and 223 ms to 127,551 calls
and 49 ms, with the same 61,105 rows visited and 50 results.
That is a provider profile, not browser latency.

The harness’s “cold scan” includes its readiness rollup request, so it is not a pure
filesystem scan with no client work.
The project corpus generates 25,296 physical files, but its hidden virtual environment
is outside inventory scope; only equal observed populations are compared.
Synthetic `top00` tree probes have no project counterpart and are omitted there.
Main predates provider diagnostics, so a scratch adapter only changed the completion log
parser and labeled its missing provider identity; HTTP probes remained shared.
The older 300,000-entry operational-tree result was not reproduced on that private
corpus and is not superseded by these synthetic measurements.

Reproduce the candidate using `devtools/bench_serving.py` with `--corpus synthetic` or
`--corpus project`, a shared `--corpus-dir`, and `--clients 8`. Use `--files 60000` for
the synthetic shape and `--projects 1` for the project shape.
The harness accepts `--metab` to select an independently installed build.
See [the performance model](../../engine-performance-model.md) for the measured phases.

### September 8 Controlled Navigation Comparison

The [controlled summaries](evidence/navigation-serving-2026-09-08.json) compare main
`aeef188a`, the reviewed branch at `96638a7a`, and that branch with the compact Recent
record fix. All use regular CPython 3.14.6 with identical dependency versions.
Each comparison ran fresh baseline/candidate/candidate/baseline processes over the same
13,709-file repository with gzip and 20 repetitions per warm/concurrent phase.
The two comparisons total 3,752 successful measured requests.
Indexed populations, complete catalog membership/extensions, file content/kind/path, and
the 5,000-row Recent selection/count matched.
The baseline’s native percent paths were explicitly normalized to the refactor’s
canonical identities.

| Median HTTP latency, ms | Main before pair | Branch before fix | Main after pair | Fixed branch |
| --- | --- | --- | --- | --- |
| Warm Markdown file | 2.23 | 2.52 | 2.17 | 2.02 |
| Warm Python file | 2.12 | 2.25 | 1.94 | 1.88 |
| Python file, seven clients without Recent | 10.81 | 11.56 | 10.35 | 10.76 |
| Python file, eight clients with Recent | 39.74 | 62.70 | 36.98 | 41.04 |
| Markdown file, eight clients with Recent | 39.07 | 61.24 | 37.49 | 41.25 |
| Recent, eight clients | 32.20 | 59.30 | 30.30 | 34.38 |
| Catalog, first body | 2.62 | 7.38 | 2.82 | 5.11 |

The fixed Python-file p95 with Recent was 60.96 ms versus main’s 60.47 ms; Markdown p95
was 66.03 versus 60.25 ms.
The Recent workload consumed 1.27–1.30 process CPU seconds before the fix and 0.82–0.83
after, across 20 bursts per process.
Main consumed 0.68–0.79 seconds.
Host one-minute load ranged roughly 8–10 on ten cores; wall-clock differences between
the two pairs still include host and cache variation.
No multi-second stalls occurred in either controlled comparison.

Matching-runtime thread CPU profiling isolated about 24.2 ms of Recent selection and
serialization before the fix versus 7.6 ms on main, for 5,000 returned rows.
Full `InventoryEntry` construction dominated the added work; coordinator composition
also built decorations the Recent route discarded.
`RecentRecord` keeps only the five consumed facts and validates the canonical identity
once. Traversal now visits each distinct ancestor once instead of rewalking every
selected file’s ancestor chain.
No cache, unchecked constructor, or new full-index mirror was added.
Existing ranking, cutoff, count, and coherence semantics remain.

This removes most of the measured regression, with about 4 ms of median overhead
remaining under eight-client contention.
Ordinary reads are comparable to main.
First catalog materialization on this repository adds about 2.3 ms; this experiment does
not establish its cost at larger sizes.
These residual costs stay visible in `mb-5no9`; they do not justify another structural
layer before merging the shipped Python provider.
Native adoption gates remain separate.
Reproduce using the
[CLI navigation comparison](../../engine-performance-model.md#comparing-file-navigation-without-a-browser),
then validate interaction and rendering in a real browser.

The full September 8 gate subsequently reported five new HTTPX2/HTTPCore2 advisories.
The development client and transport were upgraded to 2.12.0 under the existing
cool-off; see the
[dependency review](../../../SUPPLY-CHAIN-SECURITY.md#development-http-client-review-september-8-2026).
The paired performance measurements above retain their original, identical 2.5.0
development environments.
Neither package is an application runtime dependency, and the benchmark uses the
standard-library HTTP client.

## Verification

The top branch’s starting head had successful CI for lint, Python 3.12/3.13/3.14 tests,
distribution smoke tests, and stack integration.
Its description, comments, the lower PR context, and the
[earlier inventory review](review-2026-08-31-pluggable-inventory-engine.md) were read
before this pass. There were no formal submitted reviews or inline review comments at
that starting head. Those earlier green checks did not cover the interleavings and
first-open browser failures reproduced here.

The initial local full gate reproduced one flaky overlay test with 1,876 other tests
passing. After the fixes, all **1,893 Python and browser-harness tests pass** locally.
Deterministic regressions exercise cancelled shutdown, delayed refresh, symlink scope,
retained-page mutation and eviction, overlay publication during a paused read, lazy
JSONL disposal, stale subtree responses, and cached file invalidation.
The full `make verify` gate passes: formatting, strict browser typing, parity, public
hygiene, locked dependency audits, all **99 CLI golden scenarios**, distributions, and
isolated installed-wheel behavior.

Real-browser checks used a temporary public synthetic fixture directory and the
60,000-file corpus:

- Generic JSONL as the first file, Log and Raw JSON, then agent-log Log and Charts.
- Markdown Document/Source, gzip Markdown, structured JSON Tree/Source, SVG, a binary
  byte preview, source text, and a multi-file diff with a selected virtual child.
- Percent filenames and directories through direct URLs, Markdown links, breadcrumbs,
  keyboard Quick File search, reload, and browser back/forward.
- Empty-folder summaries, live insertion into collapsed folders, updated counts and
  labels, live deletion, and reopening a file after a filesystem edit.
- Large-folder expansion, aggregate Overview, Treemap, a Python filter yielding 2,994
  files, and Quick File search across all 60,000 catalog entries.

The final browser sessions reported no console warnings or errors.
macOS refused creation of an invalid UTF-8 filename; POSIX byte escapes and Windows
lone-surrogate URL behavior have codec and boundary tests, not a claimed real-filesystem
browser run on those platforms.

## Remaining Work and Merge Boundary

| Work | Disposition |
| --- | --- |
| First catalog and warm request overhead | `mb-5no9`: measured optimization follow-up; keep absolute latency and work counters |
| Native aggregate implementation and browser-wire coupling | `mb-hej8`: adoption gate; do not ship the exploratory Python graph adapter |
| Native session restart/recovery | `mb-6o0l`: require adapter-owned recovery or a supervised reopen contract before shipping native |
| Native pinned-page retention under churn | `mb-hej8`: prove useful completion and explicit eviction, using the now-stated contract semantics |
| Invalidation-only native transport costs | `mb-l2eh`: measure real binding cost before adding fact payloads |
| Remaining SSE/host debt | `mb-vknc`: resume, queue scope, history memory, and retry/validator cost remain; page-read lock ownership is fixed |
| Text and streaming walk diagnostics | `mb-iyu7`: still explicitly Python walker diagnostics; JSON/YAML model output honors provider selection |
| Provider-private module placement | `mb-ed9h`: organizational follow-up; avoid making it a reason to duplicate retained records |

Merge the stack only after the updated top commit’s full local gate and GitHub CI pass.
With the current base relationships, carry the fixes down through #101 → #99 → #91 → #98
→ #74, then into main, checking CI as the branches advance.
The intermediate refactor alone is not the reviewed release candidate.
This review prepares and validates the branch; it does not merge the stack into main.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
