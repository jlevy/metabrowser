# Load-Time Explorations

A measured-improvement loop for how fast Metabrowser becomes usable.
Each round states a hypothesis before the change, measures it against the unchanged
build on the same corpus, and records the verdict — including when the answer is no.

The hypotheses this loop is working through are registered in
[the load-time plan](../../docs/project/specs/active/plan-2026-08-21-load-time-performance.md#hypotheses).
The write-ups are in [experiments/](experiments/), one file per round.

The backend half measures the inventory engine.
The rule about what may run once per entry is
[the engine performance model](../../docs/engine-performance-model.md), the measurement
discipline this bench enforces is
[Benchmarking Scan and Serve](../../docs/development.md#measurement-discipline), and the
reference engine’s measured costs are in
[the Python inventory engine](../../docs/project/architecture/arch-inventory-engine-python.md).

Measurements taken once to set a design-system rule, in WebKit and Chrome, are in
[Design Rule Measurements](design-rule-measurements.md).
What one scripted session of browsing pull requests asks of GitHub, live against this
repository, is in [GitHub Requests While Browsing](github-requests/README.md), with its
driver, [`github_browsing.py`](github_browsing.py), which the in-process benchmark
`tests/test_github_browsing_benchmark.py` runs against the stand-in.

The browser half is the Metabrowser adapter for the reusable
[Web Performance Framework](../../docs/web-performance-framework.md).
The navigation-time recorder supplies browser-standard loading and responsiveness
signals, `probe.js` adds application facts, `performance-budgets.toml` declares policy,
and `run.py` refuses invalid evidence or a candidate that crosses a hard gate.

This is deliberately smaller than
[`devtools/bench_serving.py`](../../devtools/bench_serving.py), which measures serving
and belongs in `make verify`’s world.
The one thing the two share is the corpus: its generators live in `bench_serving`, and
[Building the corpus](#building-the-corpus) is how this loop calls them.
Nothing here runs in CI. An exploration answers a question once; a benchmark defends an
answer forever, and only the second one earns a place in the release gate.

## The loop

```
1. HYPOTHESIS  Write down what you think is slow, why, and which metric would
               show it. Before the change. Register it in the plan.
2. MEASURE     The unchanged build, three or more cold runs.
3. CHANGE      The smallest diff that tests that one hypothesis.
4. MEASURE     The changed build, the same number of cold runs, same corpus.
5. DECIDE      The accept rule below. Write the verdict down either way.
6. RECORD      experiments/exp-NNN-<slug>.md, and update the hypothesis status.
```

Rejected rounds get the same write-up as accepted ones.
Record the change and its reason in the existing
[Experiment contract](experiments/experiment.schema.yaml).
Put chart annotations in `annotations`, using `change`, `finding`, or `limitation`. Keep
accepted, rejected, and superseded verdicts in the ledger.

A diagnostic round uses `verdict.decision: diagnostic` and records its readings as
`observations`, with the phase, scenario, condition, unit, statistic, and sample count.
Paired results keep their existing meaning and stay in `results`. A diagnostic has no
paired results or acceptance decision.
Its protocol states which runs, builds, and cache regimes were observed, and names any
limit on comparison.

### Short HTTP rounds

Use the development guide’s
[single-build command](../../docs/development.md#comparing-file-navigation-without-a-browser)
for a short diagnostic.
Run it against a clean, pinned checkout with a commit history.
The committed case exercises the same first page as the Commits tab.
Copy the case to scratch and change the route and checked fields when studying another
destination.
With `--baseline-metab`, the harness interleaves fresh control and candidate
servers. It still waits for inventory readiness, then times only the named GETs with
`--api-only`. Run the ordinary inventory and Files workload separately when it is a
guard.

Keep the protocol, both builds, and raw output for each round.
Start with a short diagnostic to prove the response and locate the bottleneck.
Take timings to the browser when the hypothesis is about useful paint or continuity, and
run the acceptance series when the relevant guards can pass.
If a retry cannot change a refusal, log the reason and advance to the next independent
hypothesis. Hosted checks can run while that experiment proceeds on its own branch.

A short diagnostic can start with the first checked response:

```shell
jq '.runs[] | {condition: .build, sample: .phases.first[]}' "$RESULT"
```

If the result passes the response checks, record the selected metrics as diagnostic
observations with their actual sample counts and units.
Keep the protocol and any limits under `method` and `annotations`. If the run fails a
guard, record the refusal before moving on.
For a worked record that separates preparation from later reads, see
[exp-104](experiments/exp-104-history-startup.md).

### GitHub and origin transport

Read the [GitHub request report](../../docs/realtime-debugging.md#github-requests) for
the server and time window that handled the trial.
Use its provider call durations, queue time, response status, duplicate calls, and
reported budget charges together.
Keep those separate from Git subprocess time and the browser’s useful-paint clock.
An authenticated quota snapshot describes the account and can include other callers.

[Exp-112](experiments/exp-112-selected-provider-handoff.md) tests a provider-slot
handoff with an exact ASGI response.
[Exp-113](experiments/exp-113-origin-fetch-order.md) and
[exp-114](experiments/exp-114-origin-negotiation-hints.md) compare Git transport in
isolated stores. Verify the origin ref digest and the intended diff before using timing
or storage differences to decide a round.

### Exporting the Ledger

```shell
uv --config-file uv.toml run --frozen python explorations/performance-loop/run.py report --format jsonl
```

Each line carries the repository-relative artifact, the complete YAML payload with its
verdict and annotations, and a `structurally_valid` flag.
Legacy records that fail the current contract are retained and flagged.
Filter on that flag and the verdict before charting paired improvements.
Chart diagnostic observations in their own series.
`report` without a format flag regenerates the Markdown ledger.

## Building the corpus

`.bench/` is gitignored and machine-local, so a fresh checkout has no corpus and every
command below fails until it is built.
This is the first step on a new machine:

```shell
uv --config-file uv.toml run --frozen python -c "
from pathlib import Path
from devtools.bench_serving import build_project_corpus
root = Path('.bench/project-10'); root.mkdir(parents=True, exist_ok=True)
print(build_project_corpus(root, 10))
"
```

It takes a few minutes and writes about 5 GB: 10 copies of this repository’s own locked
installs — the `node_modules` from `package-lock.json` and the `.venv` from `uv.lock`,
plus its own source as the tracked half — which comes to roughly 249k files across 31k
directories, about 113k of them visible to the walker once ignore rules apply.
See [The corpus](#the-corpus) for what that shape is and why it is copied rather than
generated.

`build_project_corpus` is called directly here rather than through `bench_serving`,
which builds the same tree on its way to running a benchmark when a release comparison
only wants the tree.
It needs `make install` to have run first: the installs it copies are this repository’s
own. Linked install roots are materialized as directories, preserving the installed
contents within the corpus instead of leaving dependency-root links outside it.

The build is deterministic and idempotent.
`.bench-corpus.json` records the project count and the shape version, so a rerun reuses
a matching tree and rebuilds a mismatched one rather than comparing across shapes.
Read the file count from that marker rather than counting by hand; `run.py count`
reports the walker’s own rule for any tree.

`project-10` is the name the rest of this document uses, and the directory name is not
derived — pass it explicitly, as above, or `bench_serving` will default to
`.bench/corpus-project-10` and nothing will find it.

## Resuming this loop from scratch

Everything needed to pick the loop up mid-stream is in three places, and nothing needed
is only in someone’s head:

1. **What to try next, and why** — the hypothesis registry in
   [the load-time plan](../../docs/project/specs/active/plan-2026-08-21-load-time-performance.md#hypotheses).
   Every row is stated so it can be wrong, names the metric that would show it, carries
   its status, and links its bead.
2. **What has already been tried** — [report.md](report.md), regenerated by
   `run.py report`, and the per-round artifacts in [experiments/](experiments/).
   Rejected rounds are written up like accepted ones; the point of the record is that
   nobody re-runs a refuted idea.
3. **How to run one** — this file, and `run.py --help`.

A round is: pick the top open hypothesis, run `serve` on the control build, measure,
make the smallest change that tests it, measure again, apply the accept rule, and write
the artifact either way.
Then `run.py report` and commit.

### Picking up a round as a fresh agent

Work the lanes in
[the campaign plan](../../docs/project/specs/active/plan-2026-11-14-performance-campaigns.md#order-of-work),
in its order, not `tbd ready`: the ready queue is priority-sorted across the whole
repository and gives no ranking between items of the same priority.
The plan says which hypothesis each lane runs next and what blocks it; the
[registry](../../docs/project/specs/active/plan-2026-08-21-load-time-performance.md#hypotheses)
defines each one.

Rounds can run in parallel.
Each takes one hypothesis, one branch, and one artifact, and the things that would
collide are few and named:

- `results/runs.jsonl` is append-only and merges cleanly, but two agents recording under
  the same `--label` will pool into one condition in `compare`. Label with the
  hypothesis, not with `before`/`after`.
- `report.md` is generated.
  Never hand-edit it; regenerate with `run.py report` after merging and let that be the
  conflict resolution.
  `run.py report` writes unformatted Markdown, so run `make format` after it or
  `make lint-check` fails on the file you just generated.
- The corpus at `.bench/project-10` must not change.
  It is what makes runs from different agents and different weeks comparable, and
  [re-running an old round](#re-running-an-old-round-against-todays-corpus) depends on
  it. If a round needs a different tree, serve it with `--tree` and leave the corpus
  alone. Rebuilding it is not a disaster — `record` stores a filesystem-state fingerprint
  on every run, so `compare` refuses to pool changed trees rather than mixing them
  silently. It does mean those rounds no longer compare against new ones.
- Take the next free `exp-NNN` and the next free `H` number by reading the plan, and say
  in the pull request which you took.

**Before claiming a round is done**, check it against the objective and not only against
the metric it named:

1. The metric the hypothesis predicted moved, with non-overlapping ranges at n≥3.
2. `run.py compare before after --expect-build before=<identity> --expect-build after=<identity>`
   exits successfully. Use both exact identities printed by `serve`; the comparator
   rejects stale, identical, or mixed builds even when an old run reused the same label.
   It requires at least three admissible runs per condition and checks every candidate
   run against the hard responsiveness budgets; a median cannot hide one freeze.
3. `long_task_max_ms` did not grow, and the run says it was measured visible.
   A round that improves its own metric by doing the same work in a shorter window
   raises `main_thread_blocked_pct` while improving every absolute — read the share
   against `long_task_window_ms` before calling either direction.
4. `reserved_region_shift_px` did not grow, and `tree_region_repaints` did not grow.
   Both are in `compare` for exactly this reason — the campaign regressed both without
   noticing, over nine rounds, because nothing looked.
5. The artifact says what did *not* move, in the same voice as what did.

A round that improves its own metric and quietly costs a paint or twenty pixels is not
an improvement, and exp-010 is the worked example of finding that out six rounds late.

### Where a round’s files live

Nothing a round depends on lives in a transient location, other than what rerunning a
command recreates, such as the `/tmp/mb-at-*` worktrees and `$ENVS` in the recipes
below. [Durable Storage](#durable-storage) says where each kind of file and the series
lock belong, and `tests/test_experiment_storage.py` checks the records.
For a round, that means:

- **The protocol is committed** beside the record as `exp-NNN-protocol.txt` before the
  first timed run, and each amendment, with its timestamp, before the measurement it
  governs.
- **The record names it** in `method.protocol` with its sha256. The file is not edited
  after the round is recorded; a later correction goes in the record.
- **Samples and analysis scripts are committed** beside the record, named in
  `method.record` or linked from the body.
- **The analysis is registered before any result is read.** The protocol names the
  exclusion and analysis scripts by sha256, committed before the first result is read.
  A change to either after that is a deviation.
  The record gives the change, which verdicts it moved, and the coordinator’s ruling,
  and both versions stay in the branch’s history (exp-079). Its `method.analysis` names
  each script with its sha256, which must be one the protocol registered.
  A script changed afterwards gives its new sha256 together with `registered_sha256` and
  a `deviation` reason, and the storage test then requires a Deviation section in the
  record.

## Durable Storage

An agent’s session scratchpad lives under `/private/tmp`, and the operating system
empties it, `/tmp`, and the `/var/folders` directories `$TMPDIR` names on restart and at
other times without warning.
A restart that empties them also takes every lock, coordination script, and protocol a
running campaign depends on, and ends every subagent and background loop.

**A transient location holds only output that rerunning a command recreates.** Anything
a later step, another session, a record, or a lock depends on goes somewhere durable:

| What | Where |
| --- | --- |
| An experiment’s protocol, criteria, and amendments | Committed beside its record as `exp-NNN-protocol.txt`, named in the record’s `method.protocol` |
| Samples, analysis, and figure scripts a record cites | Committed beside the record, and linked from it or named in `method.record` |
| Logs, drivers, and probe output that hold local paths | The worktree’s gitignored `attic/` |
| Raw bench output and corpora | The gitignored `.bench/` |
| A lock that serializes timed rounds across worktrees | `$(git rev-parse --path-format=absolute --git-common-dir)/metabrowser-series.lock`, which every worktree of the checkout shares |
| A series driver or analysis a later round reuses | Committed, without local paths, under `explorations/performance-loop/`; its per-round config, which holds them, in that round’s `attic/` |
| Coordination scripts for one campaign only | A worktree’s gitignored `attic/` |
| Rebuilt intermediates, such as a filtered sample file or a scratch worktree in a “Reproducing” recipe | `/tmp/` or `$TMPDIR`, inside the recipe’s fenced block |

**Write a protocol so it can be committed.** Name builds by their version line and
commit, and machine paths by placeholders such as `$CONTROL` and `$CORPUS`, so the
public-hygiene check accepts it.
It is plain text (`.txt`), not Markdown, so `make format` never rewrites it and its
sha256 holds, and so the records’ `exp-*.md` glob does not read it as a record.
Commit it before the first timed run, and commit each amendment, with its timestamp,
before the measurement it governs; the history then shows which version governed what.

**A lock outlives a crash.** A campaign’s driver takes the series lock; the transition
harness takes none.
The lock is a directory made with one atomic `mkdir`, with an `owner`
file naming the process and the start time, as [`wkprobe-lock.mjs`](wkprobe-lock.mjs)
makes the WKWebView probe’s. A lock whose owner is no longer running is reported as
stale and left for a person or the coordinating agent to remove, never removed
automatically, because a process id can be reused after a restart and an owner file can
be written some other way.

**After a restart,** expect every subagent, background loop, and timed series to have
ended. Check what a timed series recorded before it stopped, resume agents by message,
and re-arm any watcher from its durable copy.

`tests/test_experiment_storage.py` holds the rule for experiment records:

- no record points its evidence at a session scratchpad, or, outside a fenced recipe, at
  an operating system temporary directory;
- every file a record names is in the repository: its protocol, with the sha256 the
  record’s `method.protocol` gives, each script `method.analysis` registers, with its
  sha256, the files `method.record` names, and every relative link;
- a record that cites a pre-registration by sha256, or is dated from the rule on, names
  its committed protocol.

## Running a round

```shell
UV="uv --config-file uv.toml run --frozen python"

$UV explorations/performance-loop/run.py serve --exp exp-004 --label before --files 300000 --provider python
$UV explorations/performance-loop/run.py fingerprint                 # first run of a series: unrecorded warm-up
$UV explorations/performance-loop/run.py serve --exp exp-004 --label before --files 300000 --provider python
$UV explorations/performance-loop/run.py probe-server                # server-side metrics, no browser
# ... and the browser half, for anything a reader sees:
$UV explorations/performance-loop/run.py capture \
  --headed --output .bench/profile.json --record                    # trusted Chrome input
# Manual diagnostic fallback when headed capture is unavailable:
$UV explorations/performance-loop/run.py probe                       # prints committed probe.js
$UV explorations/performance-loop/run.py record --json '<paste>'
$UV explorations/performance-loop/run.py compare before after \
  --expect-build 'before=<identity printed by control serve>' \
  --expect-build 'after=<identity printed by candidate serve>'
$UV explorations/performance-loop/run.py report
```

`serve` remembers the experiment, label, port, corpus, commit, selected build, requested
inventory provider, provider contract, server spawn time, and unique measurement nonce.
The nonce travels in the page URL and in the output of both `probe.js` and
`probe-server`, so `record` cannot relabel a stale browser profile or route sample from
another port or build.
Each nonce is single-use: after `record` appends one row, take another capture only from
a fresh `serve` run.
`record` refuses a nonce already present in the ledger and checks again under an
exclusive lock on the ledger as it appends, so two recorders of one run cannot both
succeed. `compare` rejects duplicate nonces in existing evidence.

`serve` does not traverse the corpus.
On a corpus larger than the host’s vnode cache (`kern.maxvnodes` on macOS), the last
traversal before a launch decides which entries the measured walk finds cached.
Every recorded run therefore launches after the same sequence: the previous served run’s
completed walk, then one full traversal.
`record` runs that traversal after the measurement and stores its filesystem-state
fingerprint on the row.
The next `serve` of the same root carries that fingerprint into its pending run as the
launch baseline, provided a root-only marker shows the root unchanged since.
`record` refuses a run whose root marker moved between `serve` and `record`, and a run
whose fingerprint differs from its baseline.
The baseline check catches a change below the root, including one during a series’ first
recorded run.

The first run of a series has no recorded predecessor, so open every series with one
unrecorded cycle: `serve` the first condition, then run `fingerprint`, which waits for
that server’s walk to complete, takes the same traversal, and hands it to the next
`serve`. `serve` prints whether it carried a baseline.
`record`, and `capture --record` before it starts Chrome, refuse a run launched without
one; run `fingerprint` and serve again.
The same step resumes a series after a refused record.
It also starts a new series after a deliberate change to the tree, whose rows then do
not pool with the earlier ones.
This does not remove the traversal from a back-to-back series: consecutive measured runs
are still separated by one, as they were under harness 21. What the harness guarantees
is that no recorded run of any condition is an exception.

Each browser row records `spawn_to_profile_start_ms`, the offset from server spawn to
the profile’s time origin, and `compare` prints it beside `walk_elapsed_ms`. A walk that
is slower with a browser attached can then be read against when the browser arrived in
it.

Headed capture records directly; the manual fallback is accepted only from the pending
URL. Provenance is filled in automatically: timestamp, commit, whether the tree was
dirty, the selected build’s reported version, the provider identity read from the
running server, and — read back out of the server’s own log — how long that run’s walk
took.
A number nobody can trace is a number nobody can defend, so none of that is left to
whoever remembers.

When measuring an installed build instead of the current environment, select it and name
its immutable source explicitly:

```shell
$UV explorations/performance-loop/run.py serve \
  --metab /path/to/release/bin/metab --artifact /path/to/metabrowser.whl \
  --build-ref <full-40-character-source-commit> \
  --tree /path/to/tree --files <count> --exp exp-0NN --label release
```

The harness resolves the executable, verifies its reported version, hashes the supplied
wheel, and verifies that every wheel file is the byte installed behind the console
script before starting.
It rejects editable installs and launchers that do not invoke the wheel’s `metab` entry
point.
The wheel hash is the comparison identity; the launcher and dependency environment
are recorded separately.
`--build-ref` records the full source commit for auditability, but cannot make different
installed bytes compare as the same build.
When `metab --version` contains a commit token, the harness resolves that token to its
full commit and rejects a different `--build-ref`; a correct short prefix cannot conceal
an invented remainder.
An external build records `dirty` as null: nothing the harness can observe says whether
the tree the wheel was built from was clean, and null means unverified rather than
clean.

Phase 1 accepts `--provider python`. Phase 2 adds `fdu` to this same axis.
The server is started with `METABROWSER_INVENTORY_PROVIDER` and local diagnostics
enabled; the result records the provider requested, provider selected, contract,
lifecycle state, version, and cumulative work counters.
A missing or mismatched identity invalidates the run instead of silently comparing
different engines.

An exact external release that predates provider and contract diagnostics can declare
that evidence gap explicitly:

```shell
$UV explorations/performance-loop/run.py serve \
  --metab /absolute/path/to/v0.9.1/bin/metab \
  --artifact /absolute/path/to/metabrowser-0.9.1.whl \
  --build-ref 16211ccb6459836c9a0813f0c3b096eef38e17b3 \
  --declare-pre-contract-inventory-identity-missing \
  --tree /path/to/unchanged/tree --files <inventory-count> \
  --exp exp-0NN --label release-v0.9.1
```

This option is a measurement adapter, not production compatibility.
It is accepted only with `--metab`, an attested exact wheel, and a full source commit;
the pending and recorded evidence retain the declaration while leaving the unreported
provider and contract null.
`compare` binds the declaration to that condition instead of treating the missing data
as observed identity.
If either server diagnostic reports an identity, recording fails because that conflicts
with the declaration.
Such a release logs walk completion as
`inventory walker complete: status=… elapsed=…ms`, without a provider or contract.
`record` reads `walk_elapsed_ms` from that line only under this declaration, and refuses
it from a run that did not make one.
Do not use the option for a current build: current builds must report their provider and
contract directly.

### Comparing a candidate with the previous release

A release comparison is a complete loop, not a screenshot or one timing copied from a
terminal. It uses installed console scripts on both sides, at least three cold browser
runs and three backend runs per condition, immutable build references, one unchanged
corpus, semantic response comparison, and the full responsiveness gate.

Build the corpus first if this machine has none (see
[Building the corpus](#building-the-corpus)).

**Time to first directory rows is a required release metric, on a repository-shaped
corpus.** The first paint of the directory tree must be rapid, and a release comparison
has to be able to see it fail.
Run the release comparison on `project-10`, which has nested `.gitignore` files, ignored
installs, and about 31k directories.
The synthetic `build_corpus` can supplement that round but cannot replace it.
From a cold start of each condition, report:

- backend `first_row` from `compare_builds`: from the first answered request to the
  first nonempty root `/api/tree`, with `spawn_to_serving` for the start before it;
- browser `first_row_ms` from the headed captures.

A candidate whose first rows regress past the tolerance below, or cross the
`first_row_ms` hard gate in `performance-budgets.toml`, is not accepted.
exp-032 is why this is written down: it used the synthetic corpus, where first rows took
about 0.1 s, while a real repository waited 9-34 s for a whole-repository `.gitignore`
pre-walk, a delay present since v0.1.0. `tests/test_gitignore_hierarchical.py` pins the
structural half in `make verify`: root rows land while a deeper directory has not been
read.

**Label the round, not the side.** `--label release` or `--label v0.8.0` pools with
every earlier round that used the same word, and the ledger is append-only across rounds
and across corpora. `compare` refuses a label that spans more than one corpus, but the
cheap habit is a label carrying the experiment number — `exp-021-release`,
`exp-021-candidate`. The refusal exists because the pooled comparison looks ordinary: an
earlier round’s smaller tree reads as a first-row regression in the current one.

The control is the previous release, built from its tag rather than assumed, and both
conditions are the wheels users would install.
Do not measure a `uv sync` checkout: it installs Metabrowser editable, and the wheel
attestation refuses it.
Keep machine-specific reports under `.bench/`; they contain absolute executable and
corpus paths and therefore do not belong in the public repository.

Build both wheels the way `make build` builds a release: from the checkout’s locked
environment, without build isolation.
An isolated build resolves the build backend’s dependencies from the index at build
time, which [supply-chain security](../../SUPPLY-CHAIN-SECURITY.md) rules out, and the
control would no longer be built the way the release it stands for was.
Each synced `.venv` is used only to build and is never measured.
`--clear` empties the output directory, so each `ls` below matches exactly one wheel on
a rerun.

```shell
RESULTS="$PWD/.bench/release-comparisons/vX.Y.Z-to-candidate"
git worktree add --detach /tmp/mb-at-vX.Y.Z vX.Y.Z
(cd /tmp/mb-at-vX.Y.Z &&
  uv --config-file uv.toml sync --locked --all-extras --all-groups &&
  uv --config-file uv.toml build --clear --no-build-isolation --out-dir "$RESULTS/control")
uv --config-file uv.toml sync --locked --all-extras --all-groups
uv --config-file uv.toml build --clear --no-build-isolation --out-dir "$RESULTS/candidate"
CONTROL_WHEEL=$(ls "$RESULTS"/control/metabrowser-*.whl)
CANDIDATE_WHEEL=$(ls "$RESULTS"/candidate/metabrowser-*.whl)
```

The browser half runs both conditions from **one fresh environment that alternates only
the Metabrowser wheel**. `compare` refuses external conditions whose dependency
environments differ, and two separately created environments differ even when they
install the same packages.
Install one wheel with its dependencies once; every later switch replaces only
Metabrowser. exp-032’s admissible series was captured this way.
This recipe takes those dependencies from the candidate’s `uv.lock`, so a rerun on
another day installs the same versions rather than a fresh resolution.

**Create the environments outside every git work tree**, including the `/tmp/mb-at-*`
worktrees. The control is an earlier release, and releases 0.7.0 through 0.9.1 annotate
`metab --version` with the state of any work tree that contains the installed package,
even from an ignored directory such as `.bench/`. A v0.9.1 wheel installed there
reports, for example, `metab 0.9.1 (+153 commits, 8d111f4a)`. The harness reads that
line, so `serve` then refuses the control’s `--build-ref`. From 0.10.0, only a run from
Metabrowser’s own tracked source is annotated, and a wheel installed inside the checkout
reports its version correctly.
Until the control is 0.10.0 or later, it still needs an environment outside every work
tree, and the recipe installs the candidate the same way.
`use_wheel` and `require_version` stop on anything but the exact `metab <wheel version>`
line. Wheels and reports stay under `.bench/`.

```shell
ENVS="$(mktemp -d)"
uv --config-file uv.toml export --frozen --no-dev --no-emit-project \
  --output-file "$RESULTS/constraints.txt"
uv --config-file uv.toml venv "$ENVS/env"
uv --config-file uv.toml pip install --python "$ENVS/env/bin/python" \
  --constraints "$RESULTS/constraints.txt" "$CANDIDATE_WHEEL"
require_version() {   # <metab> <wheel>: exactly the wheel's version, with no annotation
  expected="metab $(basename "$2" | cut -d- -f2)"
  actual="$("$1" --version)" || return
  [ "$actual" = "$expected" ] || { echo "expected '$expected', got '$actual'" >&2; return 1; }
}
use_wheel() {
  uv --config-file uv.toml pip install --python "$ENVS/env/bin/python" \
    --no-deps --reinstall-package metabrowser "$1" &&
    uv --config-file uv.toml pip check --python "$ENVS/env/bin/python" &&
    require_version "$ENVS/env/bin/metab" "$1"
}
```

If `uv pip check` fails, the two wheels need different dependencies and cannot share one
environment. The comparison would then measure those dependencies too; say so in the
experiment rather than forcing the install.

The backend comparison runs both builds interleaved inside one invocation, so each needs
its own environment:

```shell
for side in control candidate; do
  uv --config-file uv.toml venv "$ENVS/backend-$side"
done
uv --config-file uv.toml pip install --python "$ENVS/backend-control/bin/python" \
  --constraints "$RESULTS/constraints.txt" "$CONTROL_WHEEL"
uv --config-file uv.toml pip install --python "$ENVS/backend-candidate/bin/python" \
  --constraints "$RESULTS/constraints.txt" "$CANDIDATE_WHEEL"
require_version "$ENVS/backend-control/bin/metab" "$CONTROL_WHEEL"
require_version "$ENVS/backend-candidate/bin/metab" "$CANDIDATE_WHEEL"

uv --config-file uv.toml run --frozen python -m devtools.compare_builds \
  /path/to/unchanged/tree \
  --baseline "$ENVS/backend-control/bin/metab" \
  --candidate "$ENVS/backend-candidate/bin/metab" \
  --runs 5 --corpus-name <opaque-corpus-label> \
  --output "$RESULTS/backend.json"
```

`compare_builds` does not yet attest those installs against the wheel bytes, so read the
`versions` and `resolved` fields before the timings.

Its `spawn_to_serving`, printed as `start=`, runs from spawn to the first answered
request, so it includes the build importing itself, and with it the bytecode trap that
[Start-Up Work, in Pairs](#start-up-work-in-pairs) describes: two environments in
different bytecode states differ about threefold there for that reason alone.
`compare_builds` does not check the state.
Read `start=` only when both environments were installed the same way, with
`--compile-bytecode` on both `uv pip install` lines for the state an installation runs
in.

The trap ends where the server starts answering.
For one wheel with and without bytecode, each of a server’s first requests for the
shell, the tree, a file, the catalog, a rollup, and a plugin’s data hook did the same
work to within 1%, and so did the scan of a 20,000-file tree, at 5,376M instructions
against 5,396M in the rounds that polled it equally often (2026-10-01, five rounds).
`first_row` and `index_done` are counted from the first answered request, and everything
the browser half records starts after it, so `run.py serve` and `capture` need no
bytecode step. Their `spawn_to_profile_start_ms` does span the imports; it is a
diagnostic, and no gate reads it.

Read `valid` before reading the timings.
It is true only when every run completed, the corpus fingerprint stayed fixed, required
response fields existed, and ordered rows and tallies were identical.

`valid: false` is not automatically a stop.
A release that deliberately changes a response says so there: a schema bump moves
`tallies`, and the comparison reports it as an equivalence difference because it cannot
know the change was intended.
Read `equivalence` and decide.
Rows differing is a regression until proven otherwise — the navigation tree is what the
reader sees. Tallies differing only where the changelog says they change is the release
working as described, and the experiment records it as an explicit acceptance rather
than as a pass.

For the browser half, first use `count` to obtain the inventory count, then alternate
the release and candidate in both orders.
Each `serve` creates a fresh process and origin; each `capture --record` creates a fresh
visible Chrome profile, applies the evidence and budget policy, and appends the
normalized record to the ledger.
Open the series with the unrecorded warm-up cycle: the first `serve` below, then
`run.py fingerprint` in place of its capture, then that `serve` again.

```shell
use_wheel "$CONTROL_WHEEL"
$UV explorations/performance-loop/run.py serve \
  --metab "$ENVS/env/bin/metab" --artifact "$CONTROL_WHEEL" \
  --build-ref <full-release-commit> \
  --tree /path/to/unchanged/tree --files <inventory-count> \
  --exp exp-0NN --label release-vX.Y.Z
$UV explorations/performance-loop/run.py capture --headed \
  --output "$RESULTS/browser-release-1.json" --record

use_wheel "$CANDIDATE_WHEEL"
$UV explorations/performance-loop/run.py serve \
  --metab "$ENVS/env/bin/metab" --artifact "$CANDIDATE_WHEEL" \
  --build-ref <full-candidate-commit> \
  --tree /path/to/unchanged/tree --files <inventory-count> \
  --exp exp-0NN --label candidate-<commit>
$UV explorations/performance-loop/run.py capture --headed \
  --output "$RESULTS/browser-candidate-1.json" --record
```

**Script the control’s capture with its exit status allowed.** `capture --record` keeps
the row and then exits 1 on any hard-gate miss, and it cannot tell a control from a
candidate: labels are free-form until `compare` names the candidate, which is its last
label. An older release can miss a gate by construction.
On a repository-shaped corpus, v0.1.0 through v0.9.1 miss `first_row_ms`, the gate that
exists to reject their `.gitignore` pre-walk, and v0.9.1 also reports
`inventory_delivery_attribution_missing`. So `set -e` stops a driver after its first
control run, as it did in exp-034. A refused record exits 1 as well, so read the
`recorded` line rather than ignoring the failure, and leave the verdict to `compare`:

```shell
$UV explorations/performance-loop/run.py capture --headed \
  --output "$RESULTS/browser-release-1.json" --record | tee "$RESULTS/capture.log" || true
grep -q '^recorded ' "$RESULTS/capture.log"
```

Wait for the `recorded` confirmation before switching the wheel or starting the next
server: `record` re-attests the installed bytes, so a switch before it refuses the run.
Repeat each condition at least three times for a large-effect experiment.
A release comparison or any claim about a change near five percent uses at least five
interleaved runs per side, keeps the tab visible, and exercises the complete
progressive-load window.
When ranges overlap, report hard-budget compliance and the absence of a repeatable
wrong-way result rather than claiming a precise percentage.

**Judge a tolerance on back-to-back pairs.** For each key metric, divide the candidate
run by the control run it was captured next to, and never compare one condition’s worst
run with the other’s. A load spike moves both halves of a pair and separates runs taken
minutes apart, so only the pair ratio shows how the builds differ under the same
conditions. The ratio a comparison may accept depends on what it claims:

- **Careful: 1.1x, or 1.05x for a fine claim.** Use it for a claim about a specific
  change, measured on a quiet machine.
- **Rough cut: 1.3x.** Use it for a sanity check that a release is about as fast as the
  previous one, when the machine cannot be kept quiet.
  It catches an order-of-magnitude regression, such as the pre-walk exp-032 missed, but
  not a small one, so its record must say it was a rough cut.
  [exp-033](experiments/exp-033-v0100-rough-cut-release-sanity-under-load.md) is the
  worked example.

When exactly one pair exceeds the tolerance on a metric, rerun that pair back to back
once and judge the rerun.
A metric that exceeds it in two pairs, or again on the rerun, stops the release until it
is explained.

Then run `compare`, write an `exp-NNN` document with the ranges and verdict, and
regenerate `report.md`:

```shell
$UV explorations/performance-loop/run.py compare \
  release-vX.Y.Z candidate-<commit> \
  --expect-build 'release-vX.Y.Z=<wheel identity printed by release serve>' \
  --expect-build 'candidate-<commit>=<wheel identity printed by candidate serve>'
$UV explorations/performance-loop/run.py report
```

The durable record has three levels:

- raw backend JSON and full browser profiles under `.bench/`, attached to a pull request
  or bug when the diagnostic detail matters;
- normalized browser records in `results/runs.jsonl`; and
- the committed experiment and generated `report.md`, which retain the comparison, its
  limits, and the decision without publishing local paths.

The v0.6.0 application predates the current profiler.
Comparing that release requires the measurement-only adapter recorded in
[exp-015](experiments/exp-015-merged-main-preserves-the-release-performance-win.md).
Do not turn that adapter into a production compatibility layer.
Releases containing the current recorder can be measured directly.

### Which probe to use

**`probe-server`** samples one route every second from the moment the socket answers
until the walk ends, then again once settled.
Use it when the question is about a route while the inventory is walking.
Use the [short HTTP driver](#short-http-rounds) for golden-backed first and repeated
requests after readiness.
It exists because the browser cannot measure a server-side hypothesis honestly: the pane
takes seconds to start, so whether a page load lands inside the walk or after it is
luck, and a route that costs 1,500 ms scanning and 15 ms settled will report whichever
the luck picked. Thirteen samples per run beats one draw.

**`probe.js`** measures what a reader gets: time to first row, render spans, request
count, transferred bytes.
Use it for anything above the wire.
Prefer `run.py capture --headed`, which evaluates the committed probe in a fresh Chrome
profile and records the result.
If headed capture is unavailable, use `run.py probe` and paste its exact output into the
visible page rather than retyping it.

**`server-time.mjs`** reports the time the server was busy over one landing, by phase,
to the end of every body, and a warm serial time for its assets; see
[Server Time over a Landing](#server-time-over-a-landing).
Use it to say where a landing’s server time went before choosing the next measurement.

Most rounds want both.
exp-003 is the worked example of why: the route got 40% faster server-side and time to
first row did not move at all, because the first request of a page load misses a cache
by construction.

### Git Revision Navigation Scenario

Use the built-in interaction scenario when the hypothesis concerns moving between commit
comparisons rather than initial page load:

```shell
$UV explorations/performance-loop/run.py capture --headed \
  --scenario git-revisions --output .bench/git-revisions.json
```

The scenario warms the on-demand diff assets, resets the navigation-time profiler, and
then uses trusted Chrome input for two cold selections and one pointer-prepared
selection. It then finds a revision with active and queued deferred files, scrolls that
comparison, and changes revision while hydration is active.
Before waiting for inventory completion, it also switches from Files to Git, opens a
comparison, waits for a nonempty folder to arrive in the inactive Files tree, returns,
and expands the folder with trusted input.
The preflight fails if collapsed class, ARIA, inline style, computed visibility, or the
first expanded state disagree.
It records `git_files_roundtrip.return_to_files_ms` and `folder_expand_ms`, then reloads
the application document so the established revision measurements start without
preflight cache or mount state.
The run fails if deferred requests exceed two in flight, old-revision file work succeeds
after selection, active work is not canceled, row/route/view state diverges, or more
than one comparison remains mounted.
The corpus must contain at least five revisions and one revision with three deferred
files among the first history rows; missing stress coverage is an error, not a skipped
check. Its `git-revision-navigation/v1` output separates request time reported by the
server from client data and rendering spans.
It also records time to a double-animation-frame ready boundary, frames without prior
commit content, Long Tasks, Long Animation Frames, page exceptions, retained heap, and
mounted comparison count.

### Git Route Pairs

`git-route-pairs.mjs` times Git routes back to back on two servers serving the same
corpus, the server half of a Git hypothesis:

```shell
node explorations/performance-loop/git-route-pairs.mjs \
  --control http://127.0.0.1:8910 --candidate http://127.0.0.1:8911 \
  --n 15 --out .bench/git-routes.json \
  --comparison <full commit ID> --comparison <another>
```

Start each server first with its own `--cache-dir` and `--config-dir`, and wait for
`/api/index/progress` to say done.
For each route there is one unrecorded warm-up request a server, then `n` pairs, odd
pairs asking the control first and even pairs the candidate.
Every request sends `accept-encoding: gzip` and reads the whole body.

The routes are `/api/git/log?limit=250`, `/api/git/summary`, and `/api/git/refs`. Each
`--comparison REV` adds `/api/plugin/diff/comparison?revision=REV`, the diff of a commit
with its first parent that a click in the Commits list asks for, and
`--comparisons-only` times those alone.
Before a comparison’s pairs, one unrecorded request to each build without gzip records
whether the two answer it byte for byte (`answer.answers_equal`). A comparison of a
folder is computed for every request; a store’s, named by full commit IDs, is kept after
the first, so on a store the pairs time the kept answer.

A sample records its client time, start offset, status, body bytes, whether an ETag came
back, and `Server-Timing`, and from that header’s `git` entry the `git` time (`git_ms`)
and the Git processes the request started (`git_processes`). The entry counts them in
its description, `git;dur=41.2;desc="2 processes"`, from H116 on; an older build’s
samples hold null. A process is counted in the request that started it: one that joins a
comparison another request is already listing counts none of that listing’s processes.
To count an older build’s processes, start each server with `GIT_TRACE2_EVENT` naming an
empty directory, where Git writes one file a process, and pass the directories as
`--control-trace` and `--candidate-trace`. A sample then records the files that appeared
while its request ran (`trace_processes`) and the commands they name (`trace_commands`),
which show any process the server started on its own in that window.
Only a folder’s reads are traced: a store’s Git runs with every inherited `GIT_*`
variable dropped.
Tracing writes as Git runs, so a traced pass counts and is never timed;
the timed round runs untraced and reads `git_processes`. The summary gives, per build,
each route’s median and range, the pair ratios, and the counts each build reported.

H116’s untimed count (2026-11-14) on a four-commit folder, the branch against the build
it was cut from: a commit within `MAX_LISTED_PATCH_BYTES` took 4 processes before and 2
after (`rev-parse`, `diff`), a 450 KB commit past it 4 and 3, and the root commit 6 and
6; every answer was byte-equal, and the candidate’s own count matched its trace on every
sample. Two counts differ from these by design, and `tests/test_diff_one_run.py` holds
them. A server’s first comparison of a folder or store also asks `git config` whether a
textconv driver is named, beside its listing run, so it counts one more process, and a
folder’s very first asks `git var` too, which system file Git reads; the warm-up request
of each route absorbs them.
The answer is kept only while every configuration file Git reads is unchanged, and not
at all where it cannot be sure which those are (`textconv.py`), so such a folder asks
every time. Where a driver is named, the page’s files are diffed in a run of their own,
with their drivers, as before: 3 processes, and 4 for the first.
`diff.submodule=diff` counts as a named driver, since Git diffs a changed submodule in a
child `git diff` that runs the submodule’s own drivers.
Git before 2.42 has no `git var GIT_CONFIG_SYSTEM`: a server’s very first comparison
asks it instead to list its system file alone, one process more (5), and its answers are
then kept as a newer Git’s are; a system file that holds no entry names itself nowhere,
so every comparison asks `git config` again, 3 processes.
A page whose files Git pairs otherwise in a run limited to their paths takes the whole
patch within `MAX_LISTED_PATCH_BYTES` in a run of its own, one process more, wherever
the listing run’s patch was not kept: from a kept manifest, from another request’s
listing, or from a pull request’s own loader.
The one run has half the read deadline; past it the listing and the page run apart, so a
commit only the one run is slow on still answers within one deadline.

What the pairs cannot see: they are serial requests from one client, so a cost that
falls on other requests, such as a parse that holds the GIL, does not show in them, and
the counts above depend on the Git version and on whether the served folder’s
configuration names a driver, neither of which a result records yet.
A round that times H116 records both beside its pairs.

`--check-repo` with `--check-control` and `--check-candidate` adds a correctness check
between pairs, untimed: a scratch clone the timed servers never serve, whose refs it
moves before asking both builds for the refs, the summaries, and the first log page,
which must agree. exp-061 is the round that used it.

### Pull Request View Pairs

[pr-view.mjs](pr-view.mjs) times a GitHub pull request’s page, or the Pulls tab, as a
reader landing on it sees it.
Each run starts its own server from an installed build, on a GitHub checkout, with a
cold or a warm cache, and its own headless Chrome.
It records the first animation frame at which each milestone holds: the title, the
description as rendered Markdown, the Diff summary’s loading box and summary, and each
Pulls row and change line.
It also keeps every `/api/` resource timing with its Server-Timing, and counts gh calls
through a logging shim.
Its header comment lists the milestones and selectors.
[pr-view-pairs.sh](pr-view-pairs.sh) runs back-to-back pairs of two builds from one
environment, swapping only the wheel and the KPress it pins.
[pr-view-wheel.sh](pr-view-wheel.sh) builds a commit’s wheel from `git archive`, with no
second worktree. [pr-view-stats.mjs](pr-view-stats.mjs) reads the samples: per step and
build, medians and ranges, and with `--control` and `--candidate` the ratio of each
pair. [pr-view-first-routes.mjs](pr-view-first-routes.mjs) asks a fresh server for a
page’s first GitHub routes without a browser.

```shell
explorations/performance-loop/pr-view-wheel.sh <commit> attic/pr-view/wheels attic/pr-view/build-venv/bin/python
ROOT=$PWD/attic/pr-view/root ENV=$PWD/attic/pr-view/env CHECKOUT=<github checkout> \
  OUT=$PWD/attic/pr-view/pairs.jsonl UV_CONFIG=$PWD/uv.toml \
  explorations/performance-loop/pr-view-pairs.sh 3 pr control <wheel-a> candidate <wheel-b>
node explorations/performance-loop/pr-view-stats.mjs attic/pr-view/pairs.jsonl --control control --candidate candidate
```

The header comments of `pr-view-wheel.sh` and `pr-view-pairs.sh` give the commands that
make the build and runtime environments from the committed locks.
A round runs against live GitHub, so the driver stops when the core budget or the disk
runs low. The scripts are macOS-only as written (`df -g`, `sysctl vm.loadavg`, and the
Chrome that `pr-cdp.mjs` finds, which `CHROME_BIN` overrides).
exp-099 is the round that found #369’s first-paint hold with it.

### File View Navigation Scenario

Use the parallel file scenario to measure ordinary connected plugin views rather than
commit comparisons:

```shell
$UV explorations/performance-loop/run.py capture --headed \
  --scenario file-views --output .bench/file-views.json
```

The scenario warms one regular source file, then uses trusted tree-row clicks for a cold
source file, a cold Markdown file, and a cached source revisit.
Each transition must converge on the exact selected row, navigation target, rendered
path, active view, and single mounted plugin container.
The prior useful surface must remain continuously visible; the shared pending modifier
must appear and clear with `aria-busy`; and the active view must contain useful content
at a double-animation-frame boundary.

The `file-view-navigation/v1` output separates `/api/file` and plugin requests from
response decoding, selected-kind assets, active-renderer readiness, and paint.
It also records pending onset and clearance, blank frames, Long Tasks, Long Animation
Frames, page exceptions, and retained heap.
A cold transition may issue at most one matching `/api/file` request, and a cached
revisit may issue none.
This gate catches selected requests that race the row-hover prefetch as well as ordinary
duplicate navigation.
The fixed corpus must expose one Markdown and two source-like file rows; missing
coverage is an error.

Scenario output stays under `.bench/` and is summarized in the corresponding experiment.
It is not accepted by `record`: the initial-load ledger and its budgets use a different
schema. Run at least three visible-Chrome captures for each condition, alternate
condition order, and keep the repository and selected subjects unchanged.

### Transition Navigation Scenario

Use this scenario when the hypothesis is about how a UI transition looks: whether a main
tab switch, a revisit, a pull request page, or a view tab paints its destination at
once, without a blank or loading frame, and without moving content that is already on
screen. It is the instrument for the transition campaign (`mb-mpo0`), and
[exp-058](experiments/exp-058-transition-baseline.md) is its baseline.

One series runs every journey on one or two builds of `metab` against a standalone clone
of this repository:

```shell
node explorations/performance-loop/transitions.mjs run --exp exp-NNN \
  --corpus /path/to/standalone-clone --runs 6 \
  --condition control=/envs/control/.venv/bin/metab \
  --condition candidate=/envs/candidate/.venv/bin/metab
node explorations/performance-loop/transitions.mjs summarize .bench/transitions/exp-NNN/runs.jsonl
node explorations/performance-loop/transitions.mjs compare .bench/transitions/exp-NNN/runs.jsonl \
  --control control --candidate candidate --expect TRANSITION:METRIC:lower
```

It needs Node 24 and Chrome (`CHROME_BIN` overrides the macOS default) and adds no
dependency. A run of every journey takes seven to ten minutes, about half of it the
warm-up pass, and a condition’s first run takes longer while its warm-up fills the
GitHub cache.

The corpus must be a clean Git checkout, and `run` refuses one that is not.
Use a standalone clone with its own refs, not a worktree of a checkout other work
commits to: the Commits list walks the corpus’s `HEAD` and trunk refs, and a ref that
moves under a series changes the list and resets the server’s caches.
Each run records the corpus’s commit, cleanliness, trunk, and a hash of all its refs at
its start and end, and refuses itself (`corpus_changed`) if any moved.

`--journeys` narrows a diagnostic run, `--headed` shows the window, `--no-warmup` skips
the journey warm-up pass, `--keep-going` continues past refusals to list them all, and
`--memory-after ID,...` reads retained memory after the named transitions (below).
`--no-warmup` still reuses condition storage and reads the Git history and Pulls catalog
before the browser pass.
Use `--first-visit` for a fresh application cache.
None of them is the standard regime: such a run says so when it starts, records
`regime_flags`, and writes to `diagnostic.jsonl` instead of `runs.jsonl` unless `--out`
names a file, and `compare` refuses to mix it with standard runs.

### First Visits After Repository Load

Use one journey per fresh server and one browser profile per journey.
For example, with `CORPUS` set to the pinned clone and `PULL_SUBJECTS` set to four
comma-separated merged PR numbers from the catalog.
Add `--changes-hunks` when examining when the first visible source line arrives in
Changes.

```shell
node explorations/performance-loop/transitions.mjs run --exp exp-NNN \
  --corpus "$CORPUS" --condition baseline="$PWD/.venv/bin/metab" \
  --journeys pulls --pull-subjects "$PULL_SUBJECTS" --first-visit --changes-hunks --runs 3
```

For `commits` and `maintabs`, pass `--expect-newest` with the full first commit ID from
the pinned corpus’s default Git history.
The recorder verifies it against the server after the journey.
Each run gets fresh application cache, config, and event log state.
Only ordinary product startup and setup within the journey can warm a target before
input. The run waits for server inventory, then loads a Files landing and gives
application startup work its setup interval.
Startup timings live in `server.ready_ms` and `journeys[].facts.startup`. The startup
facts report when the landing was observed ready, when browsing setup began, and the
number of instrumented browser fetches still in flight at that boundary.
This is a declared start of browsing, with any remaining preparation reported.
Later clicks retain state created by earlier clicks.
Report startup and after-startup click timings separately.

With `--changes-hunks`, each Changes transition also reports `prChangesHunk`. The
milestone waits for visible hunk text on the active Changes page for the requested pull
request. File-card readiness keeps its existing clock.
A pull request with no visible text diff records a missing milestone.
Compare runs with the same flag.

Keep first-visit timings apart from the reused-state `--no-warmup` diagnostic and the
standard warm-server comparison.
First visits use live GitHub, so compare paired runs under the same regime and disclose
catalog changes and machine load.
A smoke run helps find broken predicates and candidate bottlenecks.
A judged result also needs the recorded protocol, adequate samples, and the
[accept rule](#the-accept-rule).

### Standard Transition Regime

**The regime.** Each run starts a fresh server from the condition’s `metab` on a free
port in 8890–8899, waits for its inventory to complete, runs every journey once
unrecorded, then runs them again measured.
A refusal in the warm-up pass refuses the run (`warmup_…`) and skips the measured pass,
because it leaves the server in an unknown state.
A pass stops at its first refused transition: the run is invalid from there on.
Each journey opens its own fresh Chrome profile, so the browser is cold (empty HTTP
cache, new document) while the server is warm: whatever it caches in memory or in its
state directory holds what the warm-up pass asked for.
Each condition keeps one cache and configuration directory
(`.bench/transitions/<exp>/state/<label>/`, passed as `--cache-dir` and `--config-dir`)
across its runs, so GitHub records are read from cache and network variance stays out of
the measured pass. The server still refreshes the pull request catalog on its own
schedule, so that work can overlap a run, and two conditions can hold different catalog
snapshots; `compare` prints the catalog totals each condition saw.
Two conditions alternate within each pair: the first `--condition` leads odd pairs and
the second leads even ones (`--order fixed` keeps the given order).
The viewport is 1440×900 at device scale 1, headless by default, and input is trusted
CDP pointer and key events; driver-owned scrolling and the hit test happen before the
clock starts.

**Builds are identified by content.** A build is its `metab --version` line and, for an
editable checkout, its commit, whether it is dirty, and for a dirty tree a hash of its
diff against `HEAD` and of its untracked files, read without writing to the checkout.
A wheel is identified by the hash of its `RECORD`. Provenance is read again when a run
ends, and a build that changed during the run refuses it (`build_changed`), since an
editable install serves its files live.

**Subjects are named by identity.** `SUBJECTS` in `transitions-journeys.mjs` names every
file by path, every commit by full ID, and every pull request by number, and a subject
that is not listed refuses the run instead of measuring a neighbor.
The Pulls list follows GitHub, so newer pull requests push the merged subjects down the
Closed list, past the rows a virtualized list mounts.
A subject row that is not mounted is scrolled to, one screen at a time from the top of
the list and before the clock starts, and the journey records where it sat (`facts`: its
offset in the list and the screens scrolled), so a list that moved shows in the record.
For a diagnostic against a current catalog, pass `--pull-subjects PR,PR,PR,PR` to pin
four listed merged PRs.
The override is recorded as part of the regime, and the comparator keeps it apart from
the historical subjects.
The open pull request count still moves the list that `pulls.first_show` and the
main-tab Pulls rows land on.

| Journey | Transitions |
| --- | --- |
| `landing` | Cold landing on a Markdown file, then a reload |
| `files` | Eight cold file clicks across kinds, four revisits, history back and forward, hover then click |
| `keyboard` | ArrowDown to three cold neighbors, ArrowUp to two revisits |
| `views` | View tab first visit and two revisits for Markdown, JSON, and a folder’s Overview and Treemap |
| `maintabs` | Files, Commits, and Pulls round trips with nothing selected, then again with a commit and a pull request selected; each switch to Commits lands as the build does (below) |
| `commits` | Commits first show (landing as the build does), three cold commits, two revisits, hover then click |
| `pulls` | Pulls first show, list to pull request, its tabs first and again, pull request to pull request cold, revisit, and after a hover, history back, and Changes to another pull request |
| `tree` | Folder expand, collapse, re-expand, and a nested expand |
| `palette` | Quick Search opened with `t`, then a query typed that returns both files and pull requests |
| `skim` | ArrowDown held over six rows: one `keyDown`, five more flagged `autoRepeat`, 60 ms apart, then one `keyUp` |
| `reveal` | A landing on a file three folders down, its ancestors collapsed |
| `dwell` | A hover of each length in `SUBJECTS.dwell.ms` (0, 100, 200, and 450 ms) over its own cold Markdown file of 23 to 32 KB, then a click (H94, since revision 6) |

**The Commits landing.** Main’s `19a36c5b` made every switch to Commits select the
newest commit and show it, on that commit’s address.
Before it, a switch showed the tab’s prompt (“Select a commit to preview”) on a first
visit, and the last commit read after that.
Since revision 5 a switch to Commits is ready on either landing:

- `empty`: the list and the prompt, on an address that names no commit, which converge
  with no commit mounted.
  A prompt on a `/commit/` address is the newest landing’s own failure (“Could not load
  this commit.”) and is neither landing;
- `newest`: the list and the newest commit, shown as `commitReady` requires, which
  converge with that commit’s row the one selected;
- `restored`: a switch back to Commits after a commit was read (`main_subject.*`), shown
  as a build before `19a36c5b` restores it.

The newest commit is named by identity, the head of the server’s git log
(`facts.git_log_head`), the first commit of the history the panel selects from; another
commit satisfies neither landing, and an empty or failed history, which shows no rows,
is never ready. The landing that made a switch ready must be the one it settles on: the
ready predicate keeps the branch that held first (`landingAtReady`), and a switch that
was ready on one landing and converged on another is refused (`converged`: “ready on
empty, converged on newest”), so a build that paints the prompt, or the commit read
before, ahead of the newest commit is not timed at the first paint.
Each such transition records the landing it saw (`landing`), and each run records which
landing its build has (`commits_landing`): `newest` when every switch landed on the
newest commit, `empty` when every one landed as before `19a36c5b`, `mixed` otherwise,
and null when no switch to Commits was measured.

Under the newest landing these transitions measure something else than they did before
`19a36c5b`:

- `main.files_to_commits.first` and `commits.first_show` time a switch until the newest
  commit’s detail is ready, its comparison and detail requests counted as the subject’s,
  and they now pay the diff kind’s assets and the first commit view’s mount.
  On the standing corpus the newest commit is a merge whose first-parent diff is 32
  files;
- `main.files_to_commits.again`, `main.pulls_to_commits`, and both
  `main_subject.*_to_commits` are revisits of the newest commit, its detail already
  held; a `main_subject` row then names the newest commit as its `subject`, not the
  commit read before;
- `main.commits_to_files.*` and `main.commits_to_pulls` start from a mounted commit diff
  instead of the prompt, so their teardown differs and `blankFramesOriginPrompt` no
  longer applies, and `main_subject.commits_to_*` start from the newest commit’s diff
  instead of the commit read before;
- `commits.cold.1` starts from the newest commit’s view rather than the prompt, and is
  no longer the profile’s first commit view.
  `commits.cold.2` and `.3`, the revisits, and `commits.hover_click` already started
  from a selected commit and are unchanged.

`compare` refuses runs whose `commits_landing` differs, or in which any one transition
landed differently, since the same transition then measures a different subject on each
side; `--allow-mixed-landing` compares them anyway and notes which transitions differ.
A round that needs the flag registers which transitions it reports and does not judge.
Their results are listed but decide nothing, because a transition with a different
subject on each side is not the same measurement (exp-079 left six such transitions
out).
`summarize` names each condition’s landing and any transition whose landing drifted
between its runs.

**How a frame is read.** Every frame is read once, after its own style and layout and
before it paints: the recorder’s `requestAnimationFrame` callback creates a
ResizeObserver on the document element, and Chrome delivers a new observation in the
same frame’s rendering steps, after layout and after every ResizeObserver the page
created earlier. The read forces no layout, and a later task cannot change what a frame
was recorded as showing.
Since revision 6 each frame’s entry also records the read’s own duration and whether the
read came after the input reached the page, and a root asked about twice in one read, by
the frame’s state and by the ready predicate, is searched once.

**Useful content** is visible, laid-out content in the preview’s active view: a text
node on screen (its parent rendered, not at zero opacity or hidden, with a non-empty
text box that no clipping ancestor or the viewport cuts away) outside a placeholder,
prompt, or screen-reader-only label; or an `<img>` once it has loaded and its `decode()`
has resolved, a `<video>` with a current frame, or a canvas, iframe, or large SVG laid
out at a useful size.
A root that is, or is inside, a placeholder, prompt, or label (`.sr-only` and, since
revision 6, `.visually-hidden`) has none, so a pane-level placeholder with text of its
own reads `P`, not `UP`, and so has a root hidden by its own
`content-visibility: hidden`, which is not walked at all (revision 6). Canvas and iframe
pixels are not read.

**How content is found.** The search walks the root’s subtree in document order and
stops at the first hit (`hasUseful` in `transitions-recorder.mjs`). It does not enter
the subtree of a placeholder, prompt, or label (a source view’s line-number gutter,
`.source-line-numbers`, among them); of an element with `display: none`,
`content-visibility: hidden`, or zero opacity, none of whose descendants can show; or of
an element with an empty box that clips its descendants (overflow other than visible, or
paint containment), such as a block collapsed to height 0. A box-less element (an inline
whose only child is positioned) and an empty one that does not clip (a windowed list’s
zero-height anchor) are entered, so their descendants are tested by their own boxes.
An element wholly outside the viewport is not entered unless its scrollable overflow,
which holds content and positioned descendants laid out outside its box, reaches the
viewport. A text node is measured only over its runs of lines that hold a non-space
character, each trimmed to its first and last one, so blank lines on screen after text
that is not are not content; at most 32 runs of a node are measured, and a node whose
first 32 are not on screen sends the search on to the hit test.
Text under a hidden parent is visited but neither measured nor counted toward the 400.
The walk stops at 1,500 nodes visited, entered or not, or 400 text nodes measured.
A text node longer than 2,000 characters, such as a plain source view’s text, is
measured over its first 2,000 only, since its boxes cost in proportion to its lines (3
ms a call for the corpus’s `app.js` gutter of 41,000 characters, in every frame of that
view, before the bound); one whose start is not shown sends the search on to the hit
test. When the walk stops at a bound, or found nothing after passing over an element on
its own box, it hit-tests up to 60 points across the area where the root can paint (the
viewport, cut by the root and every ancestor that clips), at four columns: first the two
top rows of that area and of the root, where a view’s content starts, then as many rows
as the points left fill, coarse to fine and each level from its outer rows inward, so
the last level the 60 points reach still spans the area down to its bottom eighth.
It stops at the first point that finds content.
Its bound is counted in work, so the same page gives the same answer under any load:
each point is charged the child nodes of every element from the one it lands on up to
the root, and one per 8 characters of the text among that element’s first 32 children,
and no point starts once the charge reaches 80,000 (the first always runs).
A call that stops there marks the frame’s read `searchTruncated`; its time is only
reported, in the read’s cost.
A point whose topmost element (`elementFromPoint`) is outside the root, such as an
overlay, does not show the root.
Otherwise that element and its ancestors up to the root are tested as media and by the
text among their first 32 children (elements and blank text count toward the 32), and,
the first time a topmost element is met, so is the text the caret lands on there
(`caretPositionFromPoint`), which sees text under `pointer-events: none` and the text
nearest the point, so a lone line between the rows is found; that node is measured from
the line the caret lands on.
Media are tested as the walk reaches them, not by a separate pass over the whole
subtree.

The bounds come from [transitions-search-cost.mjs](transitions-search-cost.mjs), which
times one call on synthetic documents in headless Chrome, scrolled to the end of their
lines (dense), or past them onto a tail that shows a heading at the screen’s top, one
line at its bottom, lines under `pointer-events: none`, or nothing (blank), and prints
the search’s counts beside each time.
Median of 20 calls in ms, revision 5 / revision 6, at a load average falling from about
17 to 7 (read the ratios, not the values); `(cut)` marks a call that stopped at the
hit-test bound, and every other call found what is on screen:

| Document | Lines | Dense | Sparse top | Sparse bottom | `pointer-events: none` | Blank |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| one `<div>` per line | 10,000 | 13.5 / 1.9 | 14.0 / 1.7 | 13.0 / 1.7 | 12.7 / 1.8 | 13.3 / 2.7 (cut) |
| one `<div>` per line | 40,000 | 53.9 / 1.7 | 52.9 / 1.7 | 53.5 / 1.8 | 52.1 / 1.8 | 54.8 / 1.8 (cut) |
| lines of 8 highlighted spans | 10,000 | 14.6 / 2.0 | 14.6 / 1.9 | 16.2 / 1.9 | 16.5 / 2.0 | 19.9 / 3.3 (cut) |
| lines of 8 highlighted spans | 40,000 | 66.5 / 1.9 | 66.0 / 1.9 | 64.7 / 1.9 | 65.6 / 1.9 | 81.5 / 1.8 (cut) |
| table rows of 3 cells | 10,000 | 14.0 / 1.9 | 0.0 / 0.0 | 0.0 / 0.0 | 0.0 / 0.0 | 1.8 / 0.2 |
| table rows of 3 cells | 40,000 | 57.8 / 2.0 | 0.0 / 0.0 | 0.0 / 0.0 | 0.0 / 0.0 | 7.4 / 0.1 |
| sections of 50 lines | 10,000 | 0.3 / 0.3 | 0.3 / 0.3 | 0.3 / 0.3 | 0.3 / 0.3 | 0.7 / 0.5 |
| sections of 50 lines | 40,000 | 1.1 / 1.0 | 1.1 / 1.0 | 1.1 / 1.0 | 1.1 / 1.0 | 3.2 / 1.7 |

A long document of short lines now costs the search what a short one does, because the
walk is bounded and the first hit-test point finds the lines, the heading, the lone
line, or the text under `pointer-events: none`. Over blank space past a long flat list
the hit-test bound stops the call: after 8 points past 10,000 lines and 2 past 40,000,
each charged the list’s children, where all 60 points would cost 68 to 123 ms over
40,000 lines; such a frame reads blank, which it is.
The table rows and sections were charged little enough that every blank call tried all
60 points. On the product, a frame of the corpus’s `app.js` source view read in 2.4 ms
while the search still measured the first 2,000 characters of its gutter (5.1 ms with
the whole gutter), and of its Markdown files in under 1 ms; the search now passes over
the gutter, which has not been timed on the product.
That bound is the search’s alone, and the probe times the search alone.
The rest of a frame’s read, its state’s prompt and placeholder queries, the regions’
selectors, and the alert query, traverses the view in every frame: review B of #442
counted 15 such traversals a read, a million element visits on a highlighted source of
8,671 lines, against the search’s 3, so on a large view the read costs in proportion to
its DOM (`mb-gnh9`). A text node costs up to its 2,000 characters and their line boxes,
so a view of many long nodes, such as a large file’s 64 KiB chunks after Load more,
scrolled to its end, costs the search up to 400 of them (`mb-jg75`). Neither has been
measured on the product’s views; both wait on the A/A run of revision 6.

**Scenario revisions.** Each row carries `scenario_revision`, and `compare` refuses to
mix revisions but judges two sets of rows of one older revision against each other,
noting what that revision records differently (`REVISION_NOTES` in
`transitions-stats.mjs`). Revision 3 redefined the clocks and the frame accounting.
Revision 4 reads a 304 for a request a worker made as `revalidated` (revision 3 read it
as `network`, so its cache disposition counts are wrong for worker requests), takes a
region’s first rendered match rather than its first match, and skips hidden and
off-screen subtrees when it looks for useful content.
Revision 5 accepts a switch to Commits that lands on the newest commit as well as one
that lands on the prompt, and records the landing; revision 4 refused every build since
main’s `19a36c5b`, which lands on the newest commit (**The Commits landing**, above).
Revision 6 fixes three recorder defects and adds the readings Phases 2 and 3 need
(**Revision 6**, below).
**A round must not compare a revision 5 run with a revision 6 run**: `compare` refuses
to, and a series that spans the change is rerun on one revision.

**Revision 6.** What changed from revision 5, and why; everything not listed here is
defined as in revision 5, so rounds on the two revisions differ by this list only.

- **The input’s own frame is in its window** (`mb-s0e4`). Chrome can stamp the frame
  that draws an input a fraction of a millisecond before the input’s own `timeStamp`.
  Revision 5 placed frames in a window by their begin time alone, so it left that frame
  out: a valid transition read `framesToReady` 0 and could drop a blank frame from its
  counts. A frame is now in the window when its read came after the input reached the
  page, whatever its begin time, so a frame read before the input is out of it even when
  Chrome stamped it after the input, which revision 5 counted.
  `accountFrames` and `regionMovement` use the same rule, so a region’s box logged by
  the input’s own frame moves it, and one logged by a frame read before the input, which
  revision 5 counted from 1 ms before the input, is where the region stood.
- **The content search finds what is on screen, at a bounded cost** (`mb-86b9`, review
  C’s C1 on #373). Revision 5 rejected a subtree on its ancestor’s own box, so it missed
  text on screen under a box-less inline, a zero-height parent at the viewport’s top
  edge, a container of floats, a windowed list’s zero-height anchor, a parent whose
  content overflows into view, a fixed or a translated element under a scrolled-away
  parent: a windowed list scrolled after ready read blank frames with its rows on
  screen. It also measured every off-screen sibling without counting it, about 15 ms a
  call at the end of 10,000 lines.
  **How content is found** (above) is revision 6’s search.
  Media are now found by the walk and the hit test, not by a pass over the whole
  subtree, so an image after the walk’s bound is found only where a hit-test point lands
  on it. Review C found revision 5’s search agreeing with an uncapped reference on 52
  readings of the product’s file and commit views; revision 6’s has been checked on the
  synthetic pages only, since no series was run.
- **Hidden and parked retained surfaces read as hidden** (`mb-5xzz`, C2). Text under
  `visibility: hidden`, at zero opacity, or in a collapsed block no longer uses up the
  search’s 400 text nodes.
  A region is the first rendered match whose box is on screen, cut by every ancestor
  that clips it and the viewport; failing one, the first whose box a scroll could bring
  there: each scroll container takes the box when it lies within all it can scroll to
  and projects it onto its client box, before the ancestors outside it clip, so a tree
  row pushed below the fold of `#tree-content` inside the shell’s panes, which clip
  without scrolling, is still the row and still moves.
  On each axis where the box has extent its overlap must be positive, so a host that
  only touches an edge does not count.
  A retained page collapsed to height 0 with its overflow hidden, which revision 5 read
  as 0, 0, 0 for a 66 px move, one parked at `left: -10000px`, which it read as 10,000
  px, and one parked at `left: 100%`, translated off by `translateX(100%)`, or parked
  below inside the scrolling pane are now passed over like one hidden with
  `display: none`. Among the matches a scroll could bring on screen, the one that was
  the region in the previous read comes first while it still can, so a shown page
  scrolled out of its pane stays the region rather than a retained one parked below it
  in the pane; when the shown page is replaced, the first match in document order is
  taken. One clipped away by `clip-path` is still taken, as in revision 5.
- **The line-number gutter is not content.** A source view’s `.source-line-numbers` is
  passed over like a label, so a source view is useful only once its code is on screen,
  and the search measures the code’s first token rather than the gutter’s first 2,000
  characters. The product writes the gutter and the code in one `innerHTML`
  (`src/metabrowser/static/plugin-sdk-views.js`), so the two are painted in the same
  frame and the ready frame does not move.
- **Four reporting fixes** (`mb-5xzz`, C3). `compare` marks a settle time that either
  side reached after the other side’s shortest window closed (revision 5 marked only a
  control that settled after the candidate’s window); equal medians with as many pairs
  beyond the tolerance each way name the pairs of both ways (revision 5 printed one pair
  as “same beyond”); `blankFramesOriginPrompt` runs until the pane shows anything other
  than the prompt, by the `U` and `E` letters alone, so the pending modifier or a
  placeholder appearing beside the prompt no longer ends it; and a placeholder root
  reads `P` (above).
- **New readings.** The recorder’s own read cost per frame; retained memory at every
  journey’s end and, with `--memory-after`, after named transitions, shown and not
  judged (**How a round uses it**, below); a `sourceHighlighted` milestone on
  `files.cold.source_large` and `files.revisit.source_large`; and the `dwell` journey,
  last in the default order.
  The two source transitions’ predicate is evaluated in each of their frames until it
  holds, including the frames read after the window while it is awaited; those frames
  are read back after the wait, so each milestone records the reads up to it
  (`milestoneReads`), and the wait comes out of the 700 ms gap after them as every
  milestone’s does: when highlighting completes more than 700 ms after the window
  closes, the next Files transition starts later than in revision 5. The `dwell` journey
  also runs in the warm-up pass, as every journey does, so its four files are read by a
  warm server like every other subject; leaving it out would measure them server-cold.
  A hover-click row records its realized dwell, `hoverDwellMs`, from the pointer’s
  arrival over the target (its first `pointerover` inside the element the transition
  armed, so a boundary event elsewhere under a stationary pointer is not the arrival) to
  the press, shown as `hover_dwell_ms` and not judged: it runs some milliseconds past
  the requested `hoverMs` (23 ms for a 0 ms dwell on a loaded machine), and the
  product’s hover intent is 250 ms, so the 200 ms point can land on either side of it.
  The end-of-journey reading runs after a journey’s last transition and before its
  browser closes, so it changes nothing measured but adds a garbage collection and a few
  protocol calls between journeys.
  A worker’s session is forgotten when Chrome detaches it, so the reading does not ask
  an exited worker, and nothing Chrome sends on that session afterward is recorded.

**What each transition records.** The clock starts at the input event’s own `timeStamp`
(the first `pointerdown`, `keydown`, or `popstate`, which must be trusted; navigation
start for a landing).

- `readyMs`: the post-layout read of the first frame that showed the exact requested
  subject with useful content and no mounted placeholder.
  The ready predicate names the route, the active main tab, and a rendered surface, so a
  surface kept mounted but hidden cannot satisfy it, and a frame is a candidate only
  when the input reached the page before its read.
  A predicate that already holds when the transition is armed, or in a frame before the
  input, refuses the transition (`ready_before_input`).
- `paintedReadyMs`: when that frame reached the screen, on the frame clock: the first
  frame boundary after its main-thread rendering ended, which is its post-layout read or
  the end of a Long Animation Frame entry that covers the read, for a frame over 50 ms.
  A task that runs after the ready frame does not move it, however long.
  `nextFrameMs` is the begin time of the next frame, which revision 2 reported as
  painted ready.
- settle time, apart from readiness: `settledMs`, when the preview last changed in the
  window, and `navSettledMs`, when the navigation panels did.
- blank frames (the preview showed no useful content) and frames with a visible
  placeholder, in the preview and in the active navigation panel, counted over the whole
  window from the input to its end (the ready frame’s next frame plus the transition’s
  settle time), split before and after the ready frame, and in milliseconds; a frame
  that shows the destination’s own prompt, which a main tab with nothing selected lands
  on by design, is not blank where the journey declares it (`emptyState`). A frame that
  still shows the prompt that was on screen at the input is blank, unlike old content
  that lingers; those frames are also reported apart (`blankFramesOriginPrompt`), so a
  round that removes them can say what they showed;
- the movement of each named region (`REGIONS` in `transitions-recorder.mjs`) over the
  window, per tracked component of its post-layout box: the largest single step, the net
  displacement, and the path length (every step summed), for the page and for each group
  (`tree`, `palette`). A region is its selector’s first rendered match whose box is
  reachable (revision 6, above), not an element: one the product re-creates, or that is
  absent for some frames, is still the same region, a hidden surface kept mounted ahead
  of it is passed over, and its next box is measured from where it last was, so a pull
  request page replaced by one with a taller header moves the tab bar below it.
  A tree row is identified by its `data-path`, so a different row is a replacement, not
  a movement;
- Layout Instability entries with value, `hadRecentInput`, and their sources;
- requests by class (`data`, `plugin`, `static`, `kpress`, `background`, `stream`,
  `document`, `other`), from the page and its workers, and duplicate requests for the
  selected subject per route.
  A read of a pull request that follows the page’s own `pull-refresh` POST for that
  number in the same window is a settlement read, the page polling until a refresh it
  asked for settles, and is counted apart (`subjectSettlementReads`, shown but not
  judged), so a duplicate is a read that follows no refresh (`subjectReads`).
  `background` is the Pulls catalog work on its own timers: the core-preparation and
  catalog-refresh POSTs (the palette posts the same refresh, flagged background) and the
  warm walk over All, eight rows at a time (`pulls?state=all&limit=8`); the visible
  list’s own window reads are `data`. The rule is by URL shape (`requestClass`), so a
  change to the walk’s batch size moves it into `data`;
- cache disposition per request by route family (`static`, `plugin_static`,
  `kpress_static`, `data`, `document`): `revalidated` for a 304 on the wire, read from
  `Network.responseReceivedExtraInfo`, which is the only event that shows a 304 the
  browser answered to its own cache (`responseReceived` reports the cached 200). For a
  request a worker makes, Chrome sends that event on the page’s session, so it is
  matched to its request by ID across sessions; `cache` when the memory or disk cache
  answered with no exchange; `network` for any other response; and `pending` when no
  response event arrived;
- milestones, each timed like painted ready and waited for after the window closes, so
  no other field’s window moves: on a landing, `shellToolsReady` and `styledMarkdown`;
  on every pull request transition, `prHeader`, and on a Conversation,
  `prDescriptionShown` and `prDescriptionFinal`; and since revision 6, on the large
  source file’s cold visit and revisit, `sourceHighlighted` (H101), when its syntax
  highlighting is complete: the file is shown, every code block the shell highlights
  (`pre code` that is not `.no-highlight`) carries highlight.js’s `hljs` mark, which it
  sets as it writes the token markup, and the view holds a token span.
  A build that highlights another way must set the same mark, or the milestone never
  arrives. A milestone that never arrives is `null` and named in `milestonesMissing`;
- the recorder’s own read (revision 6), on the page clock, which resolves 0.1 ms there
  (the page is not cross-origin isolated), so each read is rounded to 0.1 ms:
  `readCostMaxMs`, the longest read of a frame in the window, `readCostToReadyMs`, the
  reads summed up to the ready frame, and for each milestone in `milestoneReads` the
  longest read, the reads summed, and the truncated searches up to it, the frames read
  while it was awaited after the window included.
  `searchTruncatedFrames` counts the window’s frames whose content search stopped at its
  hit-test bound, where on-screen content can have read as blank,
  `searchTruncatedToReady` the part of them up to the ready frame, and
  `searchTruncatedAfterWindow` those read while milestones were awaited.
  `searchTruncatedBeforeInput` is the same count for the arm check and the frames before
  the input, which the ready-before-input guard read: when it is not 0,
  `readyBeforeInputUncertain` is true, since a truncated search there can have hidden a
  subject shown before the input.
  `convergedUncertain` marks a converged check whose search was truncated, and its
  refusal says so. A read includes the frame’s state, its regions, and the ready and
  milestone predicates, so a condition whose page makes the search work harder shows it
  here. `compare` and `summarize` name every transition whose longest read, up to its
  ready frame or a milestone, passed `READ_COST_CEILING_MS` (4 ms, about a quarter of a
  60 Hz frame, in `transitions-stats.mjs`), as `INSTRUMENT COST`, since the recorder may
  have delayed that frame, and every transition with a truncated search, as
  `SEARCH TRUNCATED`. The ceiling’s basis is a search’s cost, and its comment says what
  it does not cover: a read runs one search per root it asks about, each with its own
  bounds; the rest of a read traverses the view unbounded; a text node costs up to 2,000
  characters; and a frame whose read hit-tests has its pre-paint run inside the read, so
  its `INSTRUMENT COST` is an upper bound on the instrument’s own cost.
  Where a search was truncated, on either side, `compare` leaves unjudged what it can
  have bent, each as a gap with the reason in its verdict: truncated before the input,
  every judged metric of the transition, since it should perhaps have been refused; up
  to the ready frame, every judged metric but its milestones, since readiness found late
  moves the end of the window that the settle times, the longest task, the placeholder
  counts, the movement, and the request, shift, and DOM node counts are measured over;
  after the ready frame, the blank counts (`blank_frames`, `blank_frames_after_ready`,
  `blank_ms`); and up to a milestone, that milestone;
- retained memory (revision 6), after a full garbage collection, at every journey’s end
  (`journey.memory`, compared as `<journey>.end`) and, with `--memory-after`, after
  named transitions (`memory`): the page’s main-thread V8 heap (`Runtime.getHeapUsage`,
  `jsHeapUsedKb`, and where Chrome reports it the embedder heap, Blink’s own objects
  with DOM nodes among them, `embedderHeapUsedKb`), the renderer’s live DOM nodes,
  documents, and event listeners (`Memory.getDOMCounters`, attached and detached nodes
  alike, so a surface kept off the document still counts), the elements attached to the
  document, and the summed V8 heaps of the page’s dedicated workers, each collected
  first. It does not count GPU memory, decoded images, compositor tiles, layout and style
  objects outside those heaps, the HTTP and memory caches, the browser process, or any
  other renderer. `performance.measureUserAgentSpecificMemory()` is not used: it needs a
  cross-origin isolated page, which the product is not.
  The collection is not something the page does on its own, so a reading between two
  transitions changes what the later one measures, which is why `--memory-after` is not
  the standard regime; the reading at a journey’s end follows its last transition.
  The reading first empties the recorder’s own logs (its frames, region boxes, DOM
  changes, entries, and inputs since the last arm, about 10 KB a second of logging on
  review B’s probe), which every caller has read by then, so they do not count.
  A name `--memory-after` gives that no transition of the run measured refuses the run
  (`memory_after`), so a misspelled one does not quietly read nothing;
- `inputSpanMs` and `readyAfterLastInputMs` for gestures of several events, a watched
  list’s row replacements (the palette’s results), request body bytes of every POST,
  top-level preview nodes replaced, Long Tasks, Event Timing (with Chrome’s own
  presentation time for the first `pointerdown`, `click`, and `keydown`), the
  application’s `…ToReady` spans, the DOM node count, the one-minute load average when
  the transition started, and on a switch to Commits the landing it saw (`landing`) and
  the one it was ready on (`landingAtReady`).

**Guards.** A run is written with `valid: false` and its refusals, and `summarize` and
`compare` leave it out, when any of these fails anywhere in its passes:

- `build_identity` and `build_changed`: the version line the server renders equals
  `metab --version` for the condition, the server serves the corpus on the port the run
  chose, a dirty build has a content identity, and the build did not change;
- `corpus_changed`: the corpus’s commit, cleanliness, trunk, and refs did not move;
- `warmup_…`: the warm-up pass passed every guard;
- `visibility`, `viewport`, `raf`, and `frame_clock`: `visibilityState` stayed
  `visible`, the viewport was at least 1440×900, at least two frames arrived after each
  input, and the median frame step stayed under 50 ms (a throttled page, not a slow
  one);
- `page_exceptions` and `rendered_errors`: no uncaught exception in the page or its
  workers, and no visible `role="alert"` or `.preview-error` in the preview or the
  active navigation panel;
- `ready_before_input` and `converged`: each transition’s predicate was false before its
  input, became true within its timeout, and after settling the route, selected row,
  rendered subject, active tab, and mounted owner all agree;
- `input_observed`, `hit_test`, `target_missing`, `subject_missing`, and `setup`: the
  trusted input reached the page, a press at the target’s center lands on it, and every
  subject and setup step was found;
- `memory_after`: every transition `--memory-after` names was measured.

**How a round uses it.** Run the control and the candidate in one series, at least six
runs each, then `compare`, naming the hypothesis’s metric with
`--expect TRANSITION:METRIC:lower` (or `higher`). `compare` refuses, and exits 2, when a
condition has fewer than three valid runs, a label is missing (only `--aa` names one), a
condition pools two builds or a dirty build has no content identity, the corpus commit,
cleanliness, trunk, refs, server git log head, or indexed file count differ, the
scenario revisions differ, the regime or the journeys requested differ, or the runs’
Commits landings differ (unless `--allow-mixed-landing`). It notes a mixed harness or
Chrome version, a non-standard regime, a dirty build with its content identity, the
catalog totals per condition, the Commits landing, runs without a back-to-back partner,
and an A/A comparison.

For each transition and metric it needs three values on both sides, and it lists every
gap: a transition measured on one side only, a metric with fewer values, and a value
missing in some runs, such as a milestone that never arrived, including one that no run
on either side reached.
Times and frame counts are judged on back-to-back pairs, as the runbook’s tolerance rule
says
([Comparing a candidate with the previous release](#comparing-a-candidate-with-the-previous-release)):
each candidate run divided by the control run of its pair, against `--tolerance` (1.3 by
default, the rough cut on this loaded machine; it must be below 2). Ranges apart with
two or more pairs beyond the tolerance is a result; one pair beyond under separated
ranges is a rerun of that pair; and ranges apart with every pair within is not a result.
Under overlapping ranges the pairs beyond the tolerance are counted in each direction,
whatever the medians do, and every verdict names them both ways: two or more beyond in
one direction must be explained, and are a wrong-way result when that is the metric’s
worse direction, however close the medians are and whatever the other direction holds.
With fewer than three back-to-back pairs, one pair beyond in the worse direction is a
gap, since the tolerance cannot be judged.
One pair beyond under overlapping ranges, with three or more pairs, is listed with the
pair to rerun but is not a wrong-way result: at three runs a side it is common under
load (88 of the 4,199 comparisons of the exp-058 A/A split), and the runbook’s rerun of
that pair is for a release.
A line’s `direction` is the medians’, which an expectation’s first clause reads.
A zero control median against a non-zero candidate with separated ranges is a result on
the ranges alone, so a transition that gains its first long task in every run is a
result; under overlapping ranges it goes through the pair rule, where a pair whose
control is 0 and whose candidate is not is beyond any tolerance.
A settle time one side reached after the other side’s shortest window closed (the window
ends a settle time after the ready frame, so a build that is ready sooner is watched for
less time) cannot be compared, since a lower candidate value may only be a shorter
window, and a higher one only a longer window: `settled_ms` is then a gap, so it is
neither a result nor a met expectation, and `nav_settled_ms`, shown but not judged, is
marked.
Counts (requests, replacements, movement, and shifts) are judged on their ranges.
Every line shows the pooled medians and ranges beside the pair ratios, and the report
ends with the chance that two identical builds separate on one comparison at the n in
hand, `2 / C(a + b, a)` (10% at three runs each, under 1% at five), and how many
comparisons that predicts.
It exits 0 when the comparison is complete with no wrong-way result, 1 on a wrong-way
result (a judged metric that got worse, or a rerun or an explanation owed in the wrong
direction), a gap, or an expectation not met, 2 when it refuses, and 3 when the tool
itself fails, with its stack.
A met expectation accounts for its own metric, so a round that predicts a cost in the
metric’s worse direction and sees it met exits 0, and its line is marked
`[WRONG WAY, EXPECTED]`. Figures it shows but does not judge are marked:
`requests_background`, `input_span_ms`, `next_frame_ms`, `window_ms`, `nav_settled_ms`,
`uncredited_frames`, `tree_rows_replaced`, `subject_settlement_reads`,
`blank_frames_origin_prompt`, `read_cost_max_ms`, `read_cost_to_ready_ms`,
`milestone_read_cost_max_ms`, the `search_truncated_…` counts, `hover_dwell_ms`, the
retained memory, and the `revalidated` counts.
The retained memory (`memory_js_heap_kb`, `memory_embedder_heap_kb`, `memory_dom_nodes`,
`memory_worker_heap_kb`, `memory_listeners`, `memory_documents`) is report-only: shown
at each `<journey>.end` and after any transition read with `--memory-after`, never
judged, and a reading that is missing is named in a note, not a gap, so it counts toward
no exit code. A heap varies from run to run, and a candidate can retain more by design
(H101 moves lexing into a worker, H112 keeps hosts), so whether two ranges separate says
nothing a round can act on.
Judging it needs a budget a round registers first, as H112 asks, which `mb-eu2t` tracks;
until then a round that guards memory reads the table and says what it shows.
Write the verdict with the accept rule below, and say what did not move.

`compare RUNS.jsonl --aa LABEL` splits one condition’s valid runs into odd and even
halves, paired in recorded order, an A/A check of the instrument’s resolution on that
build (it needs six runs); it exits 1 only on a gap.
`samples RUNS.jsonl --out FILE` keeps only the fields `summarize` and `compare` read,
with paths reduced to their last component in identities and in refusal details, so a
round can commit its samples beside its artifact and regenerate its tables from them.

**A judged series.** A confirmatory round runs one pair at a time under
[paced-series.sh](paced-series.sh), not one `run --runs 6`, so that load, power, and the
corpus are checked before every pair rather than once.
The driver reads a round’s values from a config file, kept in the round’s worktree as
gitignored `attic/expNNN/series.env`, because it holds local paths; start one from
[paced-series.example.env](paced-series.example.env).
Run `paced-series.sh --config FILE --check` first.
It takes no lock and times nothing, and reports each gate; `--self-test` shows on
scratch fixtures that `--check` leaves the lock and the round’s files alone.
Only the coordinator starts the series itself.
The driver drives `transitions.mjs` only and needs macOS (`pmset`, `caffeinate`). The
rules it enforces are the round’s registered ones:

- **The lock.** The series lock under the git common dir, so no two `paced-series.sh`
  series overlap on one machine.
  `run.py`, `startup_pairs.py`, `wkprobe`, and a hand-run `transitions.mjs` take no
  lock, and the driver waits only for a live `transitions.mjs` run, so start none of
  them while a series holds the lock.
- **Load.** The one-minute load stays under the registered bound for 60 s before each
  pair.
- **Power.** Low Power Mode and the power source are read before and after every pair,
  and sampled every 15 s. The judged mode is the one read before the first attempt.
  A pair measured in another mode, or with power unreadable, is excluded and not judged;
  unreadable power before the first attempt stops the series, since there is no judged
  mode.
- **The corpus.** Never fetch, pull, or check out inside the corpus checkout.
  The standing corpus v2 is `7a02fed4` checked out, trunk `083e78e4`, refs digest
  `387f68dc4e8eb8e0` (`provenance.mjs`’s `corpusProvenance`). The driver refuses to
  start a pair on any other digest.
  On 2026-11-14 an unidentified `git fetch --quiet origin` moved its `origin/main`
  during exp-086’s round (exp-079’s protocol records it); the trunk and the refs digest
  both showed it, and the driver checks both.
- **Order.** Which condition leads alternates by attempt.
- **Stops.** The series stops at its target of judged pairs, or with a nonzero exit at
  its cap on attempts, and an exit trap releases the lock.
  A driver killed by SIGKILL, a crash, or a restart skips the trap and leaves its lock,
  which `--check` reports as stale and nothing removes on its own.

**A closing round** measures final `main` against the campaign’s control and judges
every landed hypothesis on its own record’s criteria (exp-079). Final `main` is one
build, so its results belong to all of it.
One lane’s cost can leave another lane’s guard unresolved, as the pull request page’s
first-paint holds did for H86 (b). Its record carries a **Final Performance Update**, a
table with one row per hypothesis, since the schema holds one decision per record.

`tests/test_transitions_instrument.py` runs the instrument’s pure logic browserless and
its recorder in headless Chrome on synthetic pages built to fail each definition above.
Each of revision 6’s changes has a check that fails under revision 5’s logic: the
`search` group’s seven shapes, windowed lists, hidden text ahead, long document, content
past the walk’s bound, the hit test’s bound and rows, a text node of more runs than are
measured, the line-number gutter, hidden roots, placeholder root, collapsed and parked
retained pages, and the review’s tree page, the product’s clipping panes around
`#tree-content`, and region page, scrolled as well as at its top; the `window` group’s
page, which wraps `requestAnimationFrame` to stamp every frame 34 ms early, so the
frames drawn after a press begin, by their stamps, before it, as Chrome’s did once by
0.2 ms, or 34 ms late, so the frames read before it begin after it; the `readings`
group’s memory, time to highlighted, and dwell journey on a stand-in Files tab; and the
browserless checks of the frame window, missed frames, the region log, the origin’s
prompt, the reads up to a milestone, the realized dwell, and `compare`’s pair rule,
gates, marks, expectations, and exits.
A check that can be repeated, and that failed while the recorder refused one of its
measurements for its frame clock alone, is taken again, up to three attempts in all.
A pass that needed another attempt is reported as a pytest warning.
A runner too busy to draw at the display rate says nothing about those definitions.
The two network checks are not repeated: they count what the server answered across two
measurements, so a second attempt would find the browser cache and the server’s hit
counts already changed.
The `frame_clock` guard itself is unchanged, and a check that fails any other way fails
at once.

**Limits.** Headless Chrome only; the native app’s WebKit is not measured.
Painted ready is read from the main thread: raster and GPU time are not visible to the
page, so a frame whose raster is slow reaches the screen later than its estimate, and a
headless Chrome presents earlier than a display would.
Painted ready is at most a frame after Chrome presents the ready frame, and can be
before it by the compositor, raster, and GPU time after the main thread.
Event Timing’s presentation time for the click, which Chrome rounds to 8 ms, is the
ready frame’s presentation only when the click’s next paint already shows the ready
subject, as on the recorder’s synchronous test pages; a transition that becomes ready
later, on a response or a timer, is ready some frames after that paint.
On the synchronous long-frame page, Chrome presented 9 to 12 ms after painted ready in
five CI runs and 23 to 43 ms after it with the renderer’s CPU throttled fourfold.
Chrome can set a frame’s begin time (the rAF timestamp) before the input’s own
`timeStamp` for a frame it draws after the input: a probe page’s ready frame began 0.2
ms before the press and showed what the press’s handler did (`mb-s0e4`, 1 run in 8).
Revision 5 placed frames in a window by their begin time alone, so such a frame was
outside it: its transition read `framesToReady` 0 and left that frame out of the blank
and placeholder counts.
Since revision 6 a frame is in the window when its read came after the input, whatever
its begin time, so the edge no longer drops a frame, and a frame read before the input
that Chrome stamped after it no longer enters; the frame’s times are still its own, so
`paintedReadyMs` can be under a frame interval there.
A frame whose read never came is placed by what the next frame’s tick knew: before the
input when the input had still not reached the page, in the window when the read before
it saw the input, and otherwise, when the input arrived between the two, by its begin
time, which can still drop it at the edge.
exp-058’s 462 transitions have no `framesToReady` 0, and whether any revision 5 round
dropped a blank frame cannot be told from its samples.
The walk weighs nothing that covers the content it reaches, in either revision: text
under an opaque overlay still reads as content.
The hit test does, since a point whose topmost element is outside the root shows nothing
of it. Content smaller than the grid that escapes a pruned ancestor can fall between its
points, and an element clipped away by `clip-path` is not read as hidden.
Content positioned out of a block collapsed to height 0 with its overflow clipped (a
fixed or absolute box whose containing block is outside that block, which CSS does not
clip) is not found at any size: the walk passes over the collapsed block without sending
the search on to the hit test, and a box found by the hit test is cut by every clipping
ancestor, the collapsed one included.
The product’s views have no such shape.
The hit test’s bound is counted in work, so a busier machine tries the same points and
reaches the same answer; sparse content past the points the bound allows reads as blank,
and the frame says so (`searchTruncated`). On the synthetic pages every sparse case was
found at the first point, which always runs.
The work is a model of what Chrome’s hit test passes, the children and text of the
elements a point lands among, so a shape it undercounts costs more per point than its
charge says, which the frame’s read cost shows.
A text node is measured over at most 2,000 characters and 32 runs of non-blank lines,
from its start, or in the hit test from the line the caret lands on, so blank lines on
screen after text that is not do not read as content; on screen beyond those characters
or runs, a node’s text is found only through the hit test.
The search reads an off-screen element’s scroll size to see whether its overflow reaches
the viewport. On 200 `content-visibility: auto` chunks of 50 lines scrolled to the
middle, the chunking H99 (b) proposes, a call found the lines in 0.2 ms, but whether
that read lays out a chunk’s skipped content was not measured directly; that round
checks the recorder’s read cost on its own chunks first.
The memory reading is Chrome’s own accounting after a forced collection, so it is
comparable between builds in one series, not a size a reader’s machine would report.
A ResizeObserver round after the first (the product’s own observers of content deeper
than the document element) can change a frame after the recorder read it.
The Pulls catalog walk runs for about the first minute of every page load and overlaps
most journeys; its requests are counted as `background`, not as data.
The palette query’s pull request results come from the live catalog, so which rows
interleave can change as pull requests are opened; the files answer first either way.

### Start-Up Work, in Pairs

Every probe above starts once a tree is being served.
None sees what a build does before that: importing itself, which every mode pays,
`--version` included.
That cost is a few percent of a start, which wall time on a busy machine cannot resolve,
so `startup_pairs.py` counts instructions retired and records wall and CPU time beside
them for a quiet machine:

```shell
$UV explorations/performance-loop/startup_pairs.py run \
  --tree /path/to/folder --pairs 9 --out .bench/startup-pairs.jsonl \
  --control /envs/release/bin/metab \
  --candidate candidate=/envs/candidate/bin/metab \
  --compile-bytecode

$UV explorations/performance-loop/startup_pairs.py summarize .bench/startup-pairs.jsonl \
  --candidate candidate --suffix _instr --ratios
```

Each round runs the control and then one candidate, so every ratio is between
measurements taken next to each other.
A round covers `--show`, `--api`, `--version`, and `--doctor` as one-shot commands, a
server from spawn to its first `/api/routes` answer, and the shell fetched cold and
warm. `--suffix _ms` and `--suffix _cpu_ms` summarize the wall and CPU columns of the
same file. Instructions retired are read through macOS interfaces; elsewhere only the
time columns are recorded.

**Every build is measured in one bytecode state.** A start that finds no compiled
bytecode compiles each module it imports, and that is most of its work.
For one wheel in two environments, a server did 9,344M instructions from spawn to an
accepted connection without bytecode and 2,805M with it (2026-10-01, five rounds).
So a build with bytecode beside one without reads as a regression of that size, whatever
the builds are: a compiled v0.11.0 against an uncompiled candidate read 3.2x on `--show`
in 12 pairs of 12, where the two builds compiled alike differ by 1.03x.

An environment has no bytecode more easily than it seems:

- `uv pip install` compiles nothing unless it is given `--compile-bytecode`. A fresh
  install of the wheel and what it requires left 0 of 1,322 source files compiled, and
  1,322 with the flag.
- Python compiles a module on its first import and keeps the result, unless
  `PYTHONDONTWRITEBYTECODE` is set.
  Some agent shells set it, and an environment built and used under it never gains
  bytecode. exp-037 measured both of its builds that way.
- Reinstalling the package removes its bytecode and leaves its dependencies’.
  One `metab --version` afterwards compiled 63 of the package’s 156 files, the ones that
  mode imports, which is a third state and not a stable one.

`run` reads the state before the first round: every source file of the installed
`metabrowser` distribution and of each distribution it requires, and whether the
bytecode file beside it is one the interpreter loads without compiling.
That is a file whose header names this interpreter and the source’s modification time
and size, or, for a hash-based file, the source’s hash where the file asks for the
check. It measures when every build is `cached`, with all of them compiled, or every
build is `uncached`, with none.
Anything else it refuses, naming each build’s state and the `compileall` command that
compiles the ones that need it.
`--compile-bytecode` runs that command before the first round, which is what the recipe
above does. No process a run starts writes bytecode, so the state read is the state of
every round. Each record carries it as `bytecode`, `summarize` prints it in its first
line, and a file holding records from both states is refused.

`cached` is what an installation runs from its second start, and the state a claim about
a release is made in.
A round that reports these figures names the state as `method.bytecode` in its artifact,
and `report.md` marks the round’s row with it.
The standard library’s bytecode is not read.
Each record names the interpreter its build ran on, as `python` and `python_base`, and
builds whose interpreters report different versions are refused; both environments come
from one interpreter when `uv venv` creates them as the release recipe does.

A run writes a file of its own.
`run` refuses an `--out` that already holds records, because pair numbers start at zero
in every run, and `summarize` refuses a file with two records for one pair and build, or
with a build recorded under two versions: such a file is not one comparison, and a
summary of it once paired a second run’s control with the first run’s candidate.

When a start-up number moves, the cause is an import.
`python -X importtime` names it, and the fresh-interpreter `sys.modules` assertions in
`tests/test_plugin_public_api.py` are where a boundary that matters is pinned.

### Loading-Tier Probe

A loading tier is a claim about what an asset costs and when it is needed
([the browser shell](../../docs/project/architecture/arch-browser-shell.md)).
`tier-probe.mjs` measures the claim in stock Chrome with a throwaway profile, loading
one address on each build in turn, each load with an empty HTTP cache:

```shell
node explorations/performance-loop/tier-probe.mjs \
  --out .bench/tier-probe.jsonl --pairs 8 --path "/view/src/a.py#L40" \
  --module plugin-sdk-views.js \
  --build base=http://127.0.0.1:8771 --build candidate=http://127.0.0.1:8773
```

It reports the scripts requested before `DOMContentLoaded` with the bytes they
transferred, which is what the `startup_script_requests` and
`startup_script_transfer_kb` gates bound; where a module that left that set is fetched
instead; the named module’s compile and evaluate time; and, on a file address, whether
the Source view had its line gutter when it first appeared, with every layout shift and
the elements that moved.
Those answers do not depend on how busy the machine is.
Its paint timings do, and they come from a headless window, so they are pair ratios for
a quiet machine and never a substitute for the visible-Chrome captures `record` takes.

**What loopback is sent.** Only a server started as the macOS app starts it, with
`--exit-on-eof` on a loopback bind, its stdin held, and outside a remote session, sends
a loopback client its answers uncompressed (H115,
[Compression](../../docs/command-line.md#compression)). The harnesses that start a build
make one of the two starts:

- **Compressed, the remote path’s bytes:** `run.py serve`, `transitions.mjs`,
  `pr-page.mjs`, and `server-time.mjs` by default start a build `--no-open` alone, as
  `metab --remote` starts its far server, so their bytes are the remote path’s, under
  `--network` too.
- **Uncompressed, the app’s start:** `wkprobe.mjs` adds `--exit-on-eof` to every build
  whose help lists the flag, so that its server dies with the probe, and the WebKit gate
  (`apps/macos/webkit-gate/processes.mjs`) always does.
  Both bind the default `127.0.0.1`, and `wkprobe.mjs`’s pass-through proxy adds no
  forwarding header. `server-time.mjs -- --exit-on-eof` starts a build this way on
  purpose.

So a `wkprobe.mjs` pair of a control from before H115 and a candidate from after it
compares compressed delivery with uncompressed: the candidate’s per-family `bytes` grow,
startup JavaScript about 3.4 times (185,791 against 630,836 bytes in #455’s untimed
reading), which is the delivery and not a regression.
Read such a pair’s bytes by decoded size.
To measure the local path with a harness that starts `--no-open`, start the build as the
app does: `--exit-on-eof`, with the harness holding the server’s stdin open, since a
closed stdin stops it.
An emulated link (`--network`) does not change which: the emulation is in the browser,
and the server sees a loopback peer either way.
`run.py record` reads `startup_script_transfer_kb` as the remote path sends it whatever
the server sent the page; see the note beside it in `performance-budgets.toml`.

It also splits what the startup scripts cost, from the load’s trace: when their last
byte arrived, their parse on a worker while they streamed in, their compile and
evaluation on the main thread, and the main thread’s busy time to the first tree row.
`--network LATENCY:DOWN:UP` puts an emulated link under every load (milliseconds per
request, then kilobits per second each way), as `metab --remote` puts an SSH tunnel;
`--cpu RATE` slows the page; `--warm N` measures in a profile whose HTTP and code caches
N earlier loads filled, as a returning reader’s are.
Read those costs as paired differences in milliseconds.
The summary gives each one as the median paired difference against the first `--build`
with a seeded 95% bootstrap interval, and, when the two builds transfer different
startup bytes, per transferred KB. Each pair rotates the build order by one and each
record names its position, so use a `--pairs` that is a multiple of the number of
builds; the summary says whether every build took every position equally often.
`--summarize FILE` prints the summary again from records already written,
`--series NAME` reads one series of a file that keeps several, as the committed samples
of exp-084 do, and `--control NAME` compares them with another build, as a slope between
two candidates needs.
`--out` appends, and each record names its run, so a file can hold several runs; the
summary compares pairs within a run and pools runs taken under the same conditions.
It refuses a file whose runs differ in path, link, CPU, or warm-up, which `--run ID`
then reads one at a time, and a file of older records that repeats a pair.

`eager-comments.mjs` counts how much of the startup scripts is comments, and writes
variants of them with every comment removed or with more comment added, checking that
neither changes a token of code.
`--fraction` sets the added comment’s length as a share of the comment it follows; the
default, 1, doubles each one:

```shell
cat docs/*.md > .bench/prose.txt
node explorations/performance-loop/eager-comments.mjs --origin http://127.0.0.1:8771 \
  --strip .bench/eager/stripped --pad .bench/eager/padded --prose .bench/prose.txt
node explorations/performance-loop/eager-comments.mjs --origin http://127.0.0.1:8771 \
  --pad .bench/eager/220kb --prose .bench/prose.txt --fraction 0.54
```

Copy `src/metabrowser` beside the corpus, put a variant’s scripts in its `static/`, and
serve it with that copy first on `PYTHONPATH`; the startup-script check and the probe
then measure the variant as they measure the checkout.
Check each variant’s size with the startup-script check: other prose compresses
differently. [Exp-084](experiments/exp-084-eager-startup-script-cost.md) is the round
that set `startup_script_transfer_kb` this way, with its samples; at 27ea216c these
commands gave its 225,531-byte and 261,266-byte builds.
[The eager startup-script cost](../../docs/project/research/research-2026-11-12-eager-startup-script-cost.md)
is its write-up.

### Server Time over a Landing

`server-time.mjs` reports the server’s own time over one landing, by phase.
It starts the named build’s `metab` on a tree, `--no-open` with the verbose request log
on and any arguments after `--`, waits for the inventory, and loads one address in
headless Chrome through the transition harness’s launcher (`launchBrowser` in
`transitions-recorder.mjs`):

```shell
node explorations/performance-loop/server-time.mjs --metab "$CONTROL/.venv/bin/metab" \
  --tree "$CORPUS" --path /view/docs/design-system.md --out .bench/server-time/control.json
# The same build started as the macOS app starts it, for a client on this machine:
node explorations/performance-loop/server-time.mjs --metab "$CANDIDATE/.venv/bin/metab" \
  --tree "$CORPUS" --path /view/docs/design-system.md --out .bench/server-time/app.json \
  -- --exit-on-eof
node explorations/performance-loop/server-time.mjs --summarize .bench/server-time/control.json
```

A run loads the address once in a fresh profile on a fresh server, then reloads it, each
window ending when the load event has fired and the network has been quiet for 750 ms.
That first landing is a cold reading: the app runs one server per folder, and a browser
keeps every stamped asset, so each asset usually reaches a server once per process.
`--warmup N` loads the address N times first, unrecorded; the record and its table say
“warm server”, and a warm reading is never read as a cold one.

For every request the server answered in a window it reports, by route family, over the
landing’s assets (`/static`, `/plugin-static`, `/kpress-static`), and over the assets
requested before `DOMContentLoaded`, as the startup budgets’ probe selects them:

- **`busy`, the server’s wall-clock time**: the union of the requests’ spans, from
  arrival to the end of the body, which is the time at least one request was open.
  It says how long a landing kept the server answering.
  It is not CPU time, and not the time the event loop was held: a render in a worker
  thread counts in full while the loop is free for everything else.
- **Each phase’s total** of `metabrowser.server_timing` (`read`, `render`, `git`,
  `encode`, and any other a route names): the wall-clock time spent in it, taken on the
  request’s path around the work, so a phase around a thread includes the wait for a
  pool thread (the module’s docstring states the convention).
  It attributes the busy time.
  It is not CPU time either: a change that moves work between the event loop and a
  thread, as H115 (a) moves compression, changes what a phase’s span holds as well as
  how long it is.
- **`server CPU`**, on each window’s title line: the server process’s user and system
  CPU time over the window, from `/proc` on Linux and from `ps` elsewhere, to the
  hundredth of a second on macOS. It is the process’s own time, not its Git children’s.
  A change that moves work off the event loop is read here and in `busy` together.
- **`latency`, the summed latency**: every request’s time to its last byte, added up.
  Requests run side by side on one event loop, so each counts the others’ work again
  while it waits; it measures contention, and decides nothing on its own.
  `other` is the summed latency less the phases.

Each window reads the log from where the last read ended, whole lines only, so a line
being written is read whole by the next window.
A row that arrived before the window began is left out of it and counted on its title
line: a background request still open when the window began, or a straggler of the
window before, whose whole span would otherwise count here.
A warm-up’s rows are read and dropped before the measured landing, and each warm-up’s
settling is kept in the record; one that did not settle is said above the tables.

The end of a body comes from the request log’s `end_ms`, because `Server-Timing` is sent
before a body and holds only what was done by then; the headers the browser saw are
summed beside it as that start-of-response view, counting only the responses the server
sent in the window, since a cached answer keeps the header it was stored with.
`end_ms` is taken when the application returns, so it includes a route’s background
tasks and the wait for the client to drain the body.
On loopback the second grows with the bytes sent, which counts against an uncompressed
answer. The Pulls catalog’s timer-driven work is its own family, `background`, and
`foreground` is the total without it; a landing does not wait for it.
A build from before `end_ms` logs the end of a body only to the millisecond; the table
says how many rows that is.

Then, with the page closed, it fetches the landing’s assets again one at a time in the
order the browser asked for them, with Chrome’s `Accept-Encoding`, and reports their
busy time. That is a warm serial reading: the server has answered each asset once
already, so a build that holds assets in memory (H115) is measured holding them.

**Which delivery the start produced.** The record names what the start asked for and
what it got: the serial pass’s encodings, and the line a build that has one prints after
its address, `Compression: off for loopback clients of this machine`. A start given
`--exit-on-eof` whose serial answers were gzipped, as one is from an SSH session, a
Codespace, or a Dev Container, is labelled `NOT THE APP'S START` above the tables: it
measured the compressed path.
Each window also says how many bytes its assets crossed the wire as and decoded to.

**Isolating H115’s two halves.** The default start, `--no-open`, compresses for every
client, as `metab --remote`’s far server does.
So the encoded asset store, H115 (a), is read as the branch against the control, both
started that way; leaving loopback answers uncompressed, H115 (b), is read as the branch
started `-- --exit-on-eof` against the branch started as it is.
With `--exit-on-eof` the instrument holds the server’s stdin open for as long as it
runs, as the app does, since a closed stdin stops that server.
Which harness measures (a) cold or warm matters as much as the start:

- **Cold**, each asset read and compressed once by the landing that asked for it:
  `run.py serve`, which starts a fresh server on an unused port for each sample, and
  `server-time.mjs --warmup 0`, its default.
- **Warm**, the store holding every asset, which is the shared-server case the app
  rarely meets: `transitions.mjs`, whose measured pass follows an unrecorded one on the
  same server, `server-time.mjs --warmup 1` or more, and the serial pass.

exp-095 judges (a) on the cold regime and reports the warm one as the shared-server
case; its protocol is in the load-time plan,
[The exp-095 Protocol for H115](../../docs/project/specs/active/plan-2026-08-21-load-time-performance.md#the-exp-095-protocol-for-h115).
The record also keeps the build’s provenance, Chrome’s version, the load average before
and after, and the server’s resident memory once the inventory is complete and again at
the end, with the difference, which is what the landings left held.
This is revision 3 of the record (`server-time/3`); `--summarize` reads a revision 2
record as it was taken, without its CPU times, first memory reading, or rows left out.

It is untimed by design: one landing, no pairs, no comparison.
A round that judges a change runs it under its own protocol on both builds, back to
back. Its logic is tested browserless by `tests/test_server_time_instrument.py`, which
also parses the line the server writes.
The served tree should be one the GitHub plugin has no remote for, or the run reaches
GitHub with the user’s `gh`; put `tests/no-real-gh` first on `PATH` to be sure.

### WKWebView Probe

The native app renders in `WKWebView`, and WebKit caches, schedules, and throttles
differently from Chrome, so a claim about the app’s requests or readiness needs WebKit
evidence. `wkprobe.mjs` drives a real `WKWebView` on macOS against a fresh server from a
given `metab`:

```shell
node explorations/performance-loop/wkprobe.mjs run --corpus /path/to/standalone-clone \
  --runs 3 --name NAME \
  --condition control=/envs/control/.venv/bin/metab \
  --condition candidate=/envs/candidate/.venv/bin/metab
node explorations/performance-loop/wkprobe.mjs summarize .bench/wkprobe/NAME/runs.jsonl
node explorations/performance-loop/wkprobe.mjs compare .bench/wkprobe/NAME/runs.jsonl \
  --control control --candidate candidate --expect SCENARIO.METRIC:lower
```

It needs macOS 14 or later (website data stores by identifier), `swiftc` from the Xcode
Command Line Tools, and Node 20.11 or later, and adds no dependency.
The corpus must be a clean Git checkout with a `README.md` at its root, the probe’s
fixed subject, and `run` refuses one that is not; a standalone clone with its own refs
keeps it still, as for the transition scenario.
The server and the proxy take the first free ports in 8930–8939.

**Runs need an unlocked screen with the display awake.** A locked screen, a sleeping
display, or a session moved off the console hides every page, and a hidden page never
finishes its first view.
The probe shows a 160×100 window at 2% opacity in the screen’s bottom-left corner, above
other windows and click-through, holding a web view of the full 1440×900 viewport; the
page lays out at that viewport and only a corner is drawn.
`--wait-for-screen SECONDS` waits for an unlocked screen before the first run.
Each probe process holds an activity assertion that keeps the display awake and the
process out of App Nap, which would otherwise coalesce the timers that poll the page.
It also watches a stdin pipe from `wkprobe.mjs` and exits when that closes, so a probe
whose wrapper was killed does not run on against a store or hold the display awake.

**One probe series at a time.** `run` and `clean` remove the probe’s WebKit data, so
either could wipe a running series’ store between its first launch and its relaunch.
Both hold the probe lock for as long as they run, a directory made with one atomic
`mkdir` with an `owner` file inside, and refuse to start while another process holds it.
It keeps probe series and cleans apart and nothing else: the transition harness takes no
lock, so a probe series can still run beside a timed transition round, and a round keeps
the two apart itself.
The default is `~/Library/Caches/metabrowser-wkprobe.lock`, beside the data it protects
and keyed by the home directory as that data is; `--lock DIR` names another.
A lock whose owner is no longer running is reported as stale and left for a person to
remove. Each run also writes a sentinel under the probe’s `~/Library` name, which every
cleanup removes, checks it after every launch, and refuses itself (`store_wiped`) if it
is gone.

**How it is built.** `wkprobe.swift` is one Swift file, compiled by `swiftc` the first
time a source, Info.plist, flag, and compiler combination is seen, into
`.bench/wkprobe/bin/`, under a temporary name that is renamed when the compile finishes.
There is no Xcode project and no signing.
The wrapper embeds an Info.plist naming the bundle identifier
`org.metabrowser.perf.wkprobe` and disabling App Nap, so WebKit files everything under
that one name in `~/Library/WebKit`, `~/Library/Caches`, and `~/Library/HTTPStorages`. A
run whose probe reports another identifier is refused (`bundle_identity`), since its
data would be filed where cleanup does not look.
Each run removes its website data stores and then every `~/Library` entry with that
identifier, and `wkprobe.mjs clean` does the same by hand.

**Ground truth.** WebKit reports no subresource loads to the app, so a logging reverse
proxy in front of the server is the page’s origin and records every request that reached
the network: method, path, status, and conditional headers.
It forwards every header, `Host` included, so the server sees the page’s own origin.
A 304 is a revalidation, a status of 400 or more or no response an error, and any other
response a network fetch.
A resource the page’s Resource Timing lists with no matching proxy request in the same
step came from WebKit’s cache.
WebKit’s own sizes cannot say so, because a disk-cache hit after a relaunch can report a
non-zero `transferSize`. Counts are reported by family: `document`, `static`,
`plugin_static`, `kpress_static`, and `data`. Every step is bracketed by `/__mark`
requests to the proxy, which is how each request is attributed to its step.
Requests are classed by the transition recorder’s `requestClass`: the Pulls catalog’s
own timer work (`background`) and the event stream (`stream`) are counted apart and kept
out of the judged totals and families, because they run for as long as a step’s window
stays open. On a reload the outgoing page lives until the new document commits, so a
request logged before the step’s own document request is counted as `outgoing`. The
server’s pull request catalog still differs between conditions, since each keeps its own
state directory, and `compare` prints the catalog totals each condition saw.
The page stays on the proxy: a main-frame navigation to another origin is cancelled and
refuses the run (`navigation`), and a content rule list blocks every load that would
leave loopback, so a corpus with remote images adds no requests the proxy cannot see.

**Scenarios.** Each run starts the server with the condition’s state directory
(`.bench/wkprobe/NAME/state/LABEL/`, so GitHub data comes from cache), loads
`/view/README.md` once from a throwaway ephemeral store to warm the server, and then, on
one fixed proxy origin:

| Scenario | What it does |
| --- | --- |
| `cold` | The first load in a new persistent store |
| `reload` | `WKWebView.reload()` in the same process |
| `relaunch` | A new probe process on the same store and origin, as the app relaunches |
| `hidden-then-show` | A new process on a second new store loads into a window that has never been ordered in, waits up to 20 s for the first view to mount (the subject rendered and the shell tools ready), waits 5 s more to see whether it becomes ready while hidden, then shows the window and times the first painted frame with ready content |

`hidden-then-show` loads cold into a store of its own, so what it measures does not
depend on which other scenarios ran.

Ready is a subset of the transition scenario’s file-ready test with one of its
convergence checks: the route, the Files main tab, the exact subject rendered in a
laid-out active view with child content, and no placeholder laid out in the active view
(`fileReady` in `transitions-journeys.mjs`), and the pending modifier cleared
(`fileConverged`). It does not look for useful visible content.
In the visible scenarios, ready and mounted (`ready_ms`, `mounted_ms`) are DOM states
polled from the native side every 10 ms, so a page’s throttled timers cannot slow the
clock. Each poll forces a style and layout pass on the page’s main thread, the same in
every condition; while hidden, the poll does the same.
In `hidden-then-show`, an animation-frame chain started just before the show tests the
predicate at the start of each frame the page runs visible, and
`show_to_painted_ready_ms` is the start of the frame after the first one that began
ready: the double-animation-frame boundary of the transition scenarios, on the page’s
clock from the show.
A page that was ready while hidden is timed to its first painted frame, not to the first
poll. After the show the native side polls only two reads that force no layout, whether
the page is visible and whether the chain has stamped, so the only layout the probe adds
on that path is the predicate the chain tests once a frame.
`show_to_first_frame_ms` and `show_to_ready_frame_ms` (the start of the first frame that
began ready) are shown and not judged.
Not mounting, or not becoming ready, while hidden is an outcome (`mounted_while_hidden`,
`ready_while_hidden`), not a refusal; `hidden_mounted_ms` and `hidden_ready_ms` exist
only in the runs where it happened, and `compare` lists them apart when either side has
fewer than three.

**A relaunch depends on the install’s age.** An asset whose `Cache-Control` has no
freshness directive stays fresh for a tenth of the age its `Last-Modified` gave it when
it was last validated.
Whether a relaunch revalidates the stamped assets therefore depends on how long ago the
condition’s files were written, compared with the seconds between the launches.
For every asset the first launch stored that is judged by age, each row records its URL
and its lifetime minus the time from its last validation to the relaunch’s spawn and to
the end of the relaunch step, between which WebKit looked it up
(`relaunch_freshness.assets`), with counts of the assets whose headers decide.
`compare` classes each run as `fresh` when every asset judged by age was still fresh at
the step’s end, `stale` when every one was already stale at the spawn, each by more than
a 2 s guard for the 1 s resolution of `Last-Modified` and `Date`, `mixed` otherwise, and
`by-headers` when headers decide every asset.
It does not judge `relaunch`, and lists it as a gap, when a run is `mixed`, when one
condition’s runs differ, or when both conditions are judged by age and their regimes
differ. A condition whose headers decide is compared with either regime, because the
headers are then what differs.
Every `relaunch` verdict and `--expect` result names both sides’ regimes.

**What the stable regime can show.** Files written at least ten times the seconds from
the first launch’s last validation to the end of the relaunch step before the series
relaunch `fresh` throughout: that span is under a minute in the standard regime, so ten
minutes is enough, and about 16 minutes with `--exit-delay-ms` at its 60 s maximum.
A `stale` reading needs files younger than ten times that span, which a series outgrows
within a run or two, and `compare` then blocks the condition whose runs differ.
So over three or more runs a side, the only regime an age-judged control holds is
`fresh`, in which WebKit serves its stamped assets from cache with no request.
A header change such as H87’s immutable stamped assets can then show a relaunch saving
only on the families revalidated every time (`plugin_static` and `kpress_static`, served
`no-cache`); its `static_*` figures read 0 against 0 by construction, and the verdict
says so. `--stale-assets` holds the stamped share stale to measure it: the proxy gives
every asset response that no freshness directive covers `Cache-Control: no-cache`, so an
age-judged condition revalidates its stamped assets at every relaunch, as a stale
install does, and is classed `stale` throughout.
It is a diagnostic regime, recorded in `regime_flags`, and it can also add revalidations
inside a load where WebKit reuses an asset.

**Guards.** A run is written with `valid: false` and its refusals, and `summarize` and
`compare` leave it out, when:

- `screen`: the screen was locked, the display asleep, or the session off the console,
  before the run or before or after any step;
- `visibility`: a visible scenario saw `visibilityState` other than `visible`, or
  `hidden-then-show` was not hidden throughout its hidden phase and visible from the
  show to the end of the step;
- `build_identity` and `build_changed`: the version line the server or the page renders
  differs from `metab --version`, the server serves another tree or port, a dirty build
  has no content identity, or the build changed during the run;
- `corpus_changed`: the corpus’s commit, cleanliness, trunk, or refs moved;
- `converged`: a visible scenario never became ready, or `hidden-then-show` drew no
  painted frame with ready content after the show;
- `raf`: a scenario ran fewer than 30 animation frames per second at the end of its
  step, which for `hidden-then-show` is after the show;
- `store_wiped`, `bundle_identity`, and `offline_rules`: the probe’s data was removed
  during the run, the probe ran under another bundle identifier, or its content rule
  list did not compile;
- `viewport`, `page_exceptions`, `rendered_errors`, `webcontent_terminated`,
  `navigation`, `probe`, `marks`, and `run_error`: the page was not the requested size
  or its scenarios disagreed on the device pixel ratio, it threw, showed an alert, lost
  its web content process or a navigation, the probe wrote no result, the proxy did not
  log a step’s marks, or the run failed outright, as when a server does not start.

**Builds, corpora, and servers.** Builds and corpora are identified as the transition
scenario identifies them, by the same functions (`provenance.mjs`): a build by its
version line, commit, dirty state, and the content of a dirty tree or a wheel’s
`RECORD`, and a corpus by its commit, cleanliness, trunk, and refs, each read again when
the run ends. A server is started with `--exit-on-eof` when its `metab --help` lists it,
so it stops when the Node process that started it dies, however it dies; an older build
is stopped by its process group only.
A server that fails to start is stopped at once.

**How `compare` judges.** It applies [the accept rule](#the-accept-rule) with the
transition scenario’s arithmetic (`judge` and the pair ratios in
`transitions-stats.mjs`). For each scenario and metric it needs three values on both
sides, and it lists every gap: a scenario measured on one side only, a metric with fewer
values, and a value missing in some runs.
Times are judged on back-to-back pair ratios against `--tolerance` (1.3 by default; it
must be below 2), with the outcomes the transition `compare` gives (a result, a pair to
rerun, not a result, or a difference to explain), and counts on their ranges.
`--expect SCENARIO.METRIC:lower` (or `higher`) names the hypothesis’s metric.
It refuses, and exits 2, when a condition has fewer than three valid runs, a condition
pools two builds or a dirty build has no content identity, the corpus has no commit or
is not clean, the corpus commit, trunk, refs, server git log head, or indexed file count
differ, the scenarios requested, viewport, device pixel ratio, or regime flags differ,
or a row is of an older probe revision.
It notes mixed WebKit, macOS, or harness states, each condition’s catalog totals and
relaunch regimes, and runs without a back-to-back partner.
It exits 0 when the comparison is complete with no wrong-way result, and 1 on a
wrong-way result, a gap, or an expectation not met.
A figure every valid run of its scenario should have (`ready_ms`, `mounted_ms`, and
`commit_ms` in the visible scenarios; the show figures, `commit_ms`, and the two hidden
outcomes in `hidden-then-show`) is a gap even when no run on either side has it.
Figures it shows but does not judge are marked: `show_to_first_frame_ms`,
`show_to_ready_frame_ms`, `hidden_ready_ms`, `requests_background`, `requests_stream`,
`requests_outgoing`, and the `revalidated` counts.
An `--expect` may name one of them; its result is reported the same way.
`tests/test_wkprobe_compare.py` runs these decisions, and the run side’s step
attribution, scenario rows, and lock, on synthetic rows and probe output.

`--no-preflight` skips the screen check before each run, so the other guards can be
exercised while the screen is locked, when every scenario is refused by its own screen
guard; on an unlocked screen its runs are valid.
`--exit-delay-ms MS` keeps each probe process alive after it writes its result, to test
whether a relaunch depends on cache writes the first process had not yet flushed.
These, and `--stale-assets`, are recorded in `regime_flags`, and `compare` refuses to
mix them and notes any.

**Limits.** Only a 160×100 corner of the page is drawn, so raster and compositing cost
less than in the app’s full window.
Every request passes through a proxy the app does not have.
Outside `hidden-then-show`, ready is a DOM state read by a poll, not a painted frame,
and the painted frame that scenario reads is the page’s animation-frame clock, which
does not see raster or compositing.
The ready test is a subset of the transition scenario’s and does not look for useful
visible content. The probe is a bare executable, not the app: it has none of the app’s
sandbox, process settings, or delegates beyond navigation.

**Validated on an unlocked screen (2026-11-13).** On macOS with Low Power Mode on, at a
one-minute load of 14 to 28, against a frozen corpus, the control build at 09903292, and
the H87 candidate at 10d659ae, every check of the guards held:
- **Visibility and frames:** WebKit counts the 2% window as visible, and every run of a
  standard series was valid.
  In `hidden-then-show` the frame chain skipped the 2 frames run while hidden and
  counted 3 visible ones after the show, the first 24 to 54 ms after it.
- **Origin:** no navigation was refused, and the content rule list compiled.
- **Freshness:** a `fresh` control served its 41 stamped `/static/` assets from cache at
  the relaunch; under `--stale-assets` it revalidated all 41. The candidate’s
  `immutable` assets came from cache in both.
- **Cache writes:** relaunch counts were the same with `--exit-delay-ms 2000` as without
  it, so a relaunch does not depend on writes the first process had not flushed.
- **Lock and sentinel:** a second `run` and a `clean` refused while a series held the
  lock. A lock left by a killed run was reported with its dead owner and not removed.
  A `clean` under another lock during a run made that run `store_wiped` and refused.
- **Processes:** with a build that has `--exit-on-eof`, its server and the probe exited
  within 8 s of SIGKILL to node.
  On SIGINT, a control run stopped its server, its probe, and itself, released the lock,
  and left no probe data in `~/Library`. A build without the flag keeps its server after
  a SIGKILL to node; the probe reports which applies.
- **App Nap:** the probe held its “wkprobe measurement” assertion while it ran.

### Attributing Stateful-Navigation Delay

Use this sequence when an interaction feels late even though one measured application
phase looks fast:

1. Freeze the exact product build, corpus fingerprint, selected subjects, viewport, and
   foreground visibility.
   Resolve driver-owned scrolling and click coordinates before starting the transition
   clock or pending monitor; otherwise the harness can charge its own layout preparation
   to application response time.
   A single run can validate scenario wiring, but a performance conclusion needs at
   least three runs per condition.
   Interleave control and candidate runs when making a comparative claim.
2. Record three separate clocks: the small synchronous acknowledgement phase, the full
   selection-to-painted-ready handoff, and browser Event Timing.
   Pending-state mutation time proves that application state changed; it does not prove
   that the browser painted the change.
3. If acknowledgement is fast but Event Timing is slow, inspect the complete input task.
   Include capture and bubble listeners, synchronous focus handlers, browser default
   actions, route/history updates, mutation observers, and work scheduled before the
   next paint. Moving work immediately outside the named application span does not make
   the interaction faster.
4. Subdivide only the unexplained interval with finite, stable operation labels.
   Match their timestamps to Long Tasks and Long Animation Frames, and use
   forced-style/layout attribution to identify synchronous layout triggers.
   Remove diagnostic labels that do not separate competing explanations.
5. Exercise cold, prepared, rapid-replacement, and active-background-work paths.
   Require exact selection, route, rendered subject, mounted owner, pending-state
   clearance, continuous useful content, bounded request concurrency, and cancellation
   of obsolete work before accepting any timing.
6. Report the narrow result the evidence supports.
   A handler-level cost can be fixed while input-to-next-paint or cold data and render
   work remains slow; keep those residual costs visible as follow-up evidence rather
   than folding them into the local win.

The standard `git-revisions` scenario enforces the required phase labels, ordered
pending onset and clearance, blank-frame and convergence checks, mounted-owner count,
request bounds, and obsolete-work cancellation.
The `file-views` scenario enforces the same useful-readiness and convergence contract
for connected plugin renderers.
It deterministically traverses a cold source file, a cold JSON or YAML structured view,
a cold Markdown view, and a cached source revisit so an asynchronously ready renderer
cannot disappear behind otherwise synchronous cases.

### Reviewing Pull-Request and Git Navigation

Pull-request and Commits navigation is reviewed with this playbook, timed by the
sequence above, with the focused browserless sessions for deterministic behavior:

1. Freeze the build, public repository, PR numbers, full Git revisions, and viewport.
   Name the Git-object, detailed-record, browser HTTP, asset, and prepared-payload cache
   states separately, and use an isolated test cache for absent-record cases.
2. Open a first PR from the neutral prompt, then a different uncached PR from a fully
   rendered, settled cached PR; a neutral prompt is not prior useful content.
   The previous description and reading position survive until the correct new
   description or an actionable failure appears.
3. Measure description readiness separately from completed discussion, checks, and
   comparison. Exercise row selection, a cold direct link, retry after failure, rapid
   keyboard replacement, and cached reopening, on a managed repository and a checkout.
   A description preview never claims that unread sections or Git acquisition are
   complete. Hold the selected refresh after its description appears and finish it
   between polling ticks; the waiting cache read returns the correct full record, and a
   duplicate or canceled read does not change provider work.
4. For background description preparation, start in Files and open Pulls.
   Click once as soon as the row is visible, once while preparation runs, and once after
   it finishes, recording the batch state with each planned dwell.
   - With two tabs, a refused preparation leaves the first tab’s window available.
   - Let one owned batch settle without polling its result, then scroll to a cohort that
     answers cache-only `ready` or lease-held `partial`: the previous exact token is
     released before another cohort starts.
     Hide or dispose during that release, and the coverage-only token is never treated
     as the owner.
   - Hold a batch while scrolling to a second window: viewport demand covers every
     visible row, and the background cursor continues through the cached catalog beyond
     the first transport batch.
   - Keep the provider busy for over a minute: retry resumes without another scroll.
     Hide or disconnect the browser, and the unfinished cursor resumes.
   - Default Open rows warm before newer Closed rows, a known rate reset resumes the
     pass while Files stays selected, and repeated ready reads do not refetch unchanged
     rows.
   - Reopen an early prepared description after later batches, a minute, and a server
     restart: the durable lightweight record is served without a provider call.
     While a batch runs or after it is ready, change one admitted summary: an unchanged
     sibling stays readable.
   - Replace the repository or authenticated reader: old admission or cached metadata
     cannot cross that boundary.
5. In Commits, compare natural and prepared selection, re-enter the displayed row, and
   leave for a file while deferred requests are active.
   Check exact route and subject, cancellation, queued work, single active ownership,
   and final content.
6. Keep matching request counts and bytes beside painted readiness, Long Tasks, Event
   Timing, retained heap, and sampled backend RSS. Follow the loop’s repetition and
   [accept rule](#the-accept-rule), keep failures, and distinguish an isolated mechanism
   probe from a complete navigation result.

```shell
uv --config-file uv.toml run --frozen python explorations/performance-loop/run.py serve --files 100000 --provider python
```

That restarts the server on a port nothing has used this session and prints its URL. The
port is the cold-cache mechanism: a port is part of the origin, so a fresh one gives
every static asset an empty HTTP cache without touching cache headers, and a fresh
process gives a scan that is still running.
Both are what a reader opening a large tree actually meets.

**Give the browser a real viewport first.** The tree pages its rows against the height
of the nav scroller, and the sweep that warms folders reads the same box, so a pane that
never got a size measures every layout-dependent number against nothing — while still
producing timings that look entirely reasonable.
This was learned by taking six runs in a 0x0 pane and only noticing when a rect came
back 8 px tall. 1280x900 is the size these numbers were taken at; `record` refuses
anything under 900x600 rather than letting it into the ledger.

**Check `document.visibilityState` too.** A hidden pane does not run idle callbacks on
any schedule — measured here at over 30 seconds for a single
`requestIdleCallback(fn, { timeout: 2000 })`, which is to say never.
Anything the shell defers to idle is unmeasurable in that state, and two runs of the
same code will disagree depending on how long each waited.
Request counts and transferred bytes do not care; scheduling does.
Record which one a finding depends on.
The same holds when debugging: in an agent’s hidden browser pane,
`requestAnimationFrame` stalls and the viewport resizes, which looks like scroll and
paint bugs that are not there.
Reproduce a suspected one in headless Chrome before treating it as real.

The normal browser path starts a visible Chrome profile, evaluates [probe.js](probe.js),
and records the result:

```shell
uv --config-file uv.toml run --frozen python explorations/performance-loop/run.py capture --headed --output .bench/profile.json --record
uv --config-file uv.toml run --frozen python explorations/performance-loop/run.py compare before after --expect-build 'before=<control identity>' --expect-build 'after=<candidate identity>'
```

`compare` prints each metric’s median with its range beside it.

### Rendering Without Application Requests

The [diff layout](../diff-layout/README.md) and
[diff intraline](../diff-intraline/README.md) fixtures load inputs before starting their
clocks and call the production renderer or its refinement directly.
Run them without an application server by serving static files on loopback from the
repository root:

```shell
uv --config-file uv.toml run --frozen python -m http.server 8412 --bind 127.0.0.1
```

In a second terminal run the headless fixture reader.
It emits one JSON line per fixture and run, with a fresh Chrome profile and the
fixture’s own timing.

```shell
node explorations/performance-loop/render-fixtures.mjs --runs 3
```

Use `--origin` if the static server is on another loopback port.
Use `--fixture diff-layout` or `--fixture diff-intraline` to narrow the run.
The fixture clocks exclude transport and startup.
The headless HTTP cases cover server work and the full transition driver provides the
separate navigation and paint check.

### Measuring External Fetching

Use the transition rows to find the clicks whose destination arrives late, then look at
requests and the matching server log for those clicks.
A request’s elapsed time includes client waiting and transfer.
Its `Server-Timing` entries attribute instrumented work on the server.
See [Git Route Pairs](#git-route-pairs) for an equal-answer HTTP comparison with Git
process counts.

The product’s [event log](../../src/metabrowser/event_log.py) records subprocess spans
for `gh` and for Git commands.
First-visit runs record the directory in `server.event_log`. Use the span’s start or end
timestamp, duration, and parent to distinguish selected work from overlapping background
work. Long-lived Git history processes and open spans need separate accounting.
Use the PR probe’s subprocess shim only with its overhead called out.
Keep raw logs with machine-local output.

Run the bounded live GitHub probe with a working `gh` login:

```shell
node explorations/performance-loop/github-fetch-probe.mjs > github-fetch-probe.json
```

It measures a local `gh --version` invocation, identical REST reads in serial and at
concurrency two, conditional REST reads, and one minimal GraphQL batch per round.
The GraphQL results report query cost and price a small projection.
Compare only matched REST workloads when reading the concurrency result.
The probe stops on refusal or exhaustion signals and reports only allowlisted status,
rate headers, and byte counts.
Read the rate-limit resource and reset with each observation.
An account’s counters include other clients, so adjacent counter changes cannot always
be attributed to the probe.
Use deterministic responses to exercise retry and hold handling without exhausting a
live quota.

### How the browser half is driven

Time to first row is a browser fact.
`run.py capture --headed` owns the server, corpus, port, visible Chrome load, trusted
input, committed probe, and record without adding an automation package to the
dependency surface. That keeps the standard run repeatable under
[SUPPLY-CHAIN-SECURITY.md](../../SUPPLY-CHAIN-SECURITY.md).
Manual loading and probe pasting remain a diagnostic fallback for environments where the
headed driver cannot control Chrome; they are not the release-comparison workflow.

## Responsiveness, and the one precondition that invalidates it

**The principle.** The UI thread is never blocked by backend work.
Responsiveness is independent of server latency, of bandwidth, and of how much data the
tree holds. The dominant case is a local server answering in single-digit milliseconds,
and that is what to tune for — but the design must not *depend* on it, so that
`--remote` over an SSH tunnel degrades by showing content later rather than by freezing.

Network traffic cannot block a browser UI; the I/O is off-thread by construction.
What blocks it is our own synchronous handling of what arrived.
The invariant that follows is:

> Main-thread work per task is bounded by a constant, never by the size of the data.

The input is unbounded — a tree holds however many files it holds — so a design is
correct only if arbitrarily much arriving data still yields bounded synchronous slices.
Five mechanisms produce that, in the order they pay off here: preserve exact operations
across boundaries; coalesce events into one render of the latest state per frame;
deadline-slice any loop over inventory-sized data and yield; move aggregation into a
worker; and let speculative work yield to a real interaction rather than queue ahead of
it. The server learned this in exp-005 and exp-007, where a watching client stole CPU
from the walker. exp-012 found the client’s first violation: an exact file eviction had
crossed the wire as a possible subtree removal and scanned the complete catalog.

**The precondition, which is not optional.** Every responsiveness number must be
measured in a **visible, foregrounded** tab.
Chromium throttles hidden tabs — it clamps timers, suspends rendering, and batches
deferred work — so a background capture is not comparable to what a reader experiences.
The invalid capture that prompted this rule reported a 14.4-second block and 81.8%
blocked share while its instrumented spans accounted for only 137 ms.
That mismatch did not prove throttling was the whole signal: exp-012 later found a real
multi-second catalog scan in a visible tab.
So check `document.visibilityState === "visible"`, record it beside the numbers, and
discard any run that cannot say it stayed visible.
This is why the browser half runs in a visible headed window with trusted input rather
than through an automation surface that may not be showing the page.

**How to run it.** The recorder is part of the document and attaches before application
work, because the interesting part is the start:

```shell
UV="uv --config-file uv.toml run --frozen python"
$UV explorations/performance-loop/run.py serve --exp exp-0NN --label before --files 300000
$UV explorations/performance-loop/run.py capture --headed --output .bench/profile.json --record
```

The headed capture opens a fresh Chrome profile through the Chrome DevTools Protocol.
It foregrounds the browser on macOS and pulses a tiny inert paint target through
Chromium’s trusted input pipeline from first usable state until client quiescence.
The target changes no application state, while Event Timing observes input-to-next-paint
latency throughout the update stream.
The recorder requires at least five inputs spanning 80% of the measurement window.
One early click therefore cannot miss a later freeze and certify the run.
The driver also rejects input outside its controlled pulses, so a person clicking the
temporary benchmark window invalidates that capture instead of quietly changing it.
After the backend reports completion, the driver waits until application fetches are
idle and browser work remains stable across several polls; a fast backend response
cannot end the responsiveness window while the client is still consuming it.
It sends one final controlled input at that settle boundary and freezes the
responsiveness snapshot before the adapter’s buffered-observer wait and diagnostic route
requests. Fast loads therefore retain late-window interaction coverage without counting
the measurement itself as product work.
It then asks V8 to collect garbage and records the resulting retained heap separately
from both UI timing and the runtime-timed `performance.memory` sample.
The driver uses Node and browser APIs already present in the development environment; it
adds no automation package or product dependency.

For a manual diagnostic fallback, load the served URL in a visible browser window and
interact throughout the load while later inventory updates arrive.
Then evaluate the exact output of `run.py probe` once the tree settles and pass its JSON
to `run.py record`. `interaction_inputs` and `interaction_input_coverage_pct` prove that
trusted input spans the loading window, so `record` refuses an untouched page or one
early click. The probe reads exact whole-window aggregates from `metabrowser.perf`; if
that navigation-time source is absent, it labels its bounded responsiveness and visual
history `late-buffer`, and `record` refuses it rather than letting a floor read as a
total.

## What is measured

| Metric | What it is | Why |
| --- | --- | --- |
| `ttfb_ms`, `response_download_ms`, `dom_interactive_ms` | Navigation phases before the existing DCL/load markers | Separates server arrival, document transfer, and browser work |
| `first_row_ms` | Wall clock until tree rows exist in the DOM | The measure that matters. Read from the app’s own `renderTreeNodes:root` span |
| `load_tree_ms` | The root `/api/tree` fetch plus its render | The largest single component of the above |
| `dcl_ms`, `load_ms` | Navigation timing | `load` reports a shell that painted, not a tree a reader can use |
| `last_resource_ms` | End of the last request the page made | The tail. A page can look finished and still be requesting |
| `subtree_requests` | `/api/tree?path=…` count | The folder-warming sweep, which is invisible in a page that looks idle |
| `tree_items`, `lazy_stubs`, `dom_nodes` | Rendered size | What row windowing has to bound |
| `collapsed_diff_rows_materialized` | Unified or split rows mounted beneath a collapsed diff fold | Hard-gates visual folding as a real DOM bound; the value must be zero |
| `transferred_kb`, `vendor_first_start_ms` | Payload and when the prefetched tier starts | The asset tiers |
| `long_task_max_ms` | The longest single main-thread block | The one a reader feels. A total cannot tell sixty 100 ms hitches from one six-second freeze, and only one of those is a broken product |
| `long_task_max_ms_first_5s` | The same, restricted to the first five seconds | Event rate peaks right after load, so the naive design is worst exactly when the reader is deciding whether the app is alive |
| `long_tasks_over_200ms`, `total_blocking_time_ms` | Absolute-budget crossings and the standard sum of task time beyond each task’s first 50 ms | The first is the hard invariant; the second catches accumulated smaller stalls |
| `main_thread_blocked_pct` | Blocked time over its window | Always read with `long_task_window_ms`. The same work in half the time doubles the share while improving every absolute |
| `inventory_delivery_*` | Batch and work-item volume, worst callback, total time, and share of the measurement window for filesystem and catalog delivery | Directly guards the failure exp-012 found. A backend may produce any volume, but the browser must preserve exact operations, coalesce or slice them, and keep each synchronous delivery below 50 ms and their sustained share below 5% |
| `interaction_inputs`, `interaction_input_first_ms`, `interaction_input_last_ms`, `interaction_input_span_ms`, `interaction_input_coverage_pct`, `interactions`, `interaction_p50_ms`, `interaction_p95_ms`, `interaction_max_ms` | Trusted-input count and loading-window coverage, plus interaction-to-next-paint latency from Event Timing grouped by non-zero `interactionId` | Rejects untouched and single-early-click runs, separates fast inputs below Event Timing’s reporting threshold from missing input, and proves that responsiveness was sampled while later updates arrived. One click’s pointer and click events count once; the profiler retains the exact interaction maximum, while percentiles describe the explicitly reported bounded recent sample |
| `animation_frame_*`, `forced_style_layout_ms_max`, `worst_animation_frames` | Chromium Long Animation Frame duration, attributed blocking, and bounded script/resource detail | Names the callback and rendering cost behind a Long Task without making an optional signal look universal. Attributed blocking is gated; raw duration remains a target because Chromium can report a long initial navigation frame with zero blocking or work attribution |
| `label_totals` | Per-span count, total and max, never evicted | Attribution. `longtask` says the thread was blocked; this says by what |
| `gitRevision:selectionFeedback` | Synchronous pending-sheet, route, and selected-row work for one Git revision choice | Separates immediate main-thread acknowledgement from fetch/render time; the Git scenario requires this phase but leaves paint responsiveness to Event Timing |
| `gitRevision:selectToReady` | Complete Git selection-to-painted-ready handoff | Keeps data, decoding, mounting, and paint latency visible after synchronous acknowledgement |
| `gitRevision:rowAnchor` | Post-readiness update of the focused Git row’s one-row Tab anchor | Keeps focus-order cost visible without charging it to immediate selection feedback |
| `*_samples_seen`, `*_samples_retained`, `labels_overflowed`, `fetch_concurrency_keys_overflowed`, `resource_timing_buffer_full` | Retention provenance | Proves bounded detail did not silently become a whole-window claim and refuses incomplete attribution or network totals |
| `fetch_network_errors`, `fetch_aborts`, `fetch_http_4xx`, `fetch_http_5xx` | Exact whole-window fetch outcomes outside the detail ring | Keeps a failed click from looking like a merely slow one. Rejected non-abort requests and 5xx responses are hard gates; cancellation and expected-not-found semantics remain visible targets |
| `fetches_in_flight`, `fetches_in_flight_max`, `fetches_in_flight_max_by_key` | Application fetches unresolved at capture, the measurement-window maximum, and maxima grouped by request class | Prevents a faster server-completion marker from cutting the browser measurement off, and exposes request fanout even when every request eventually settles |
| `script_transfer_kb`, `style_transfer_kb`, `image_transfer_kb`, `api_transfer_kb`, `largest_resource_kb` | Transfer split by requested resource path; Resource Timing classifies preloaded JavaScript as a `link` initiator and its later script tag reuses that response | Makes an asset or API trade visible without omitting the preloaded shell or charging it to CSS |
| `startup_script_requests`, `startup_script_transfer_kb`, `startup_script_last_response_ms`, `startup_script_duration_max_ms`, `startup_scripts_slowest`, `startup_scripts_latest` | Count, transfer, tail, worst duration, and bounded path-only attribution for non-vendor scripts started before `DOMContentLoaded`; attributed rows split response wait, server work, and download time. The transfer is the scripts as the remote path sends them, gzipped, which `record` reads again from the server, because a local server sends a loopback browser its scripts uncompressed; the browser’s own figure is kept as `startup_script_loopback_transfer_kb` | Catches an eager plugin or feature tier added to every page even when noisy paint timings obscure the waterfall, and distinguishes handler work from queueing or transfer |
| `startup_style_server_ms_max`, `startup_style_wait_ms_max`, `startup_style_last_response_ms`, `startup_styles_slowest` | Worst server work, wait, response tail, and bounded path-only attribution for active stylesheet links requested before `DOMContentLoaded` | Hard-gates a cold server-side import on the render-blocking path and distinguishes it from request queueing or transfer |
| `shell_tools_missing`, `file_catalog_incomplete`, `plugin_view_containers`, `plugin_view_nonempty` | Application-adapter readiness, final data authority, and selected-view facts after settle | Prevents an asset-tier improvement from passing by silently losing deferred controls, stopping at a partial search catalog, or omitting the requested renderer |
| `js_heap_mb`, `js_heap_after_gc_mb` | Chromium’s optional natural used heap and the trusted driver’s controlled post-GC retained heap | The first is an in-session endurance signal; the second makes side-by-side retention comparisons robust to different GC timing |

`first_row_ms` is wall clock until a tree row exists.
Waiting for `load` reports a page that painted its shell, and waiting for network idle
reports a scan that finished; neither is when the reader can use the tree.

### What the reader sees, as opposed to when the data arrived

Every metric above answers the second and none of them answers the first, which is how
the loop spent nine rounds driving `first_row_ms` from 1,473 ms to 276 while the tree
region went from one paint per load to three.
Painting *something* early scores well on `first_row_ms` and is exactly the
placeholder-then-replace that a reader experiences as flicker.
The objective these decide is in
[the plan](../../docs/project/specs/active/plan-2026-08-21-load-time-performance.md#what-we-are-optimizing-for):
what the reader can see reaches its final state in a single paint, and nothing above it
moves afterwards.

| Metric | What it is | Why |
| --- | --- | --- |
| `reserved_region_shift_px` | Downward movement of the two regions that reserve a height, populated minus empty | The jump a reader gets. Two named regions, *not* the page — the name says so on purpose |
| `filter_bar_shift_px`, `summary_shift_px` | The two halves of it | They have different causes and different fixes |
| `tree_region_repaints` | `renderTreeNodes:root` spans per load — the label on the only span that replaces the panel wholesale | A region can hold perfectly still and still be assembled in front of the reader. Today’s proxy for H56’s `visual_states`. Counts one paint once: the fetched answer now reconciles through `reconcileTreeNodes:root`, while `:subtree*` patch a tree already standing |
| `lcp_ms`, `cls` | Navigation-time paint entries and CLS’s largest layout-shift session window | Valid only in a visible page. The record gate refuses hidden or late-observer runs that used to turn absence or a truncated buffer into misleading evidence |
| `page_visible`, `page_laid_out` | Whether the pane could answer visual questions | Provenance beside the visual metrics rather than an assumption made afterwards |
| `frame_missing_px` | Settled height minus shipped height, summed over the regions the shell places | H52: how much of the frame does not exist at first paint. 532 px today, all of it the files panel |
| `region_heights` | Settled and shipped height per region | Reads `frame_missing_px` back to the region that owns it. A region sized by its container rather than by its content reports settled and shipped alike, and contributes nothing — that is the right answer for `#preview-pane`, which fills its frame from first paint |

The shift figures are read by cloning a region stripped to the markup its pending render
emits, inserting it beside the real one, and subtracting.
“Beside” is beside the region as its container sees it: a region that is the only child
of an element that frames it, as `#preview-pane` is of `.preview-frame`, has its
stand-in placed beside that element, inside a copy of it.
Placed inside the frame it would share the frame’s space with the region, which read
half the pane as missing until harness version 23. They remain useful beside CLS because
they name which reserved region moved and can be reconstructed after settle; CLS is
page-wide and must observe the visible transition.
They are layout facts, so they have no run-to-run variance: three runs of exp-010 gave
identical values where `first_row_ms` swung 213–533 ms.

Dimensions added for the registered hypotheses, so each can be accepted or rejected by
this loop rather than argued:

| Metric | Hypotheses it decides | Notes |
| --- | --- | --- |
| `tree_reprobe_ms`, `tree_reprobe_srv_ms`, `index_status_at_probe` | H8 | The root tree route asked again at probe time, with the server’s own `Server-Timing` share and the scan state it was measured in. H8 is a claim about the scanning regime, so the regime is recorded with the number |
| `fcp_ms` | H10 | Null where the browser reports no paint entries — a pane created hidden never does — and never a fabricated 0 |
| `long_tasks`, `long_task_ms_total`, `long_task_max_ms` | H9, H11, H58 | Whole-window aggregates from the observer attached with the document, not the bounded late buffer |
| `render_spans`, `render_ms_total` | H7, H11 | Every `renderTreeNodes:*` span from non-evicting label totals: what patching-not-replacing and row windowing would move |
| `dom_nodes`, `tree_items`, `lazy_stubs` | H7 | Rendered size |
| `subtree_requests`, `last_resource_ms` | H2 | The warming sweep’s footprint |
| `load_ms`, `vendor_first_start_ms`, `transferred_kb` | H1, H9 | The asset tiers |

Not everything runs in the page.
H13/H18 (walker) read `inventory walker complete: elapsed=` from the server log `serve`
writes, recorded and compared as `walk_elapsed_ms`; H14/H17 (CLI and imports) use
`python -X importtime -c "import metabrowser.server"` and `devtools/bench_serving.py`’s
start-to-serving phase; H15 is a correctness claim.
Each hypothesis names its instrument in the plan table, and a hypothesis whose
instrument does not exist yet is marked blocked rather than measured badly.

For a provider-level comparison, use the serving benchmark directly:

```shell
$UV -m devtools.bench_serving --files 100000 --provider python \
  --label python-before --json .bench/inventory-provider-before.json
$UV -m devtools.bench_serving --files 100000 --provider python \
  --label python-after --baseline .bench/inventory-provider-before.json \
  --json .bench/inventory-provider-after.json
```

Run the two conditions on the same immutable corpus and interleave them when the
expected effect is below 2×. The benchmark records cold and reader-attached discovery,
first useful rows, scanning and settled rollups, retained bodies, validators, concurrent
clients, tree routes, navigation’s first and memoized paths, the catalog’s first body,
retained body, and `304` paths, process CPU and memory, provider work, and binding-copy
bytes. Navigation summaries must agree with the settled walker, and repeated catalog
bodies and validators must remain identical, so lower latency cannot hide a semantic
change. Fresh settled aggregation is accepted as a sample only after a visible marker
changes the inventory ETag; non-200 route responses invalidate the phase.

## Known gaps in this loop

Raised in review and tracked rather than fixed here, because each changes how every
later round is judged and deserves its own change:

- **The accept rule gets stricter as evidence accumulates** (`mb-wnrv`). The band is
  min–max, which widens monotonically with n, so collecting more data makes a real
  effect *harder* to confirm — exp-003 is the worked example, 342–413 at n=3 widening to
  342–561 at n=6 for the same effect.
  A fixed-percentile band or a rank test is stable in n.
- **The load-time probes have no measured noise floor** (`mb-ot8o`). An A/A control —
  the same build under two labels — would measure the harness’s own resolution, so “the
  ranges do not overlap” is judged against a known floor instead of an assumed one.
  The transition scenario has one: `compare --aa` splits one condition’s runs, and
  exp-058’s split is its reference.
  `run.py` has none.
- **A metric that cannot come out false is not a metric.** `skeleton_complete` asked
  whether each region was present, sized and non-empty *at probe time* — which is after
  settle — and returned true on all ten runs ever recorded, including every one carrying
  a 532 px hole where the files panel belongs.
  It was replaced by `frame_missing_px`, which is a distance rather than a predicate.
  Its first replacement, `regions_non_empty`, was retired the same day for the same
  reason: it read `textContent`, which counts screen-reader-only text, and the files
  panel ships exactly that — a spinner and an `.sr-only` label — so the hole passed the
  floor check written to catch it.
  Worth checking a new metric against its own recorded history before trusting it: one
  that never varies is either measuring nothing or measuring after the fact.
- **Nothing guards the wins** (`mb-c7ck`). Every number here was measured once.
  A small committed corpus and a deliberately generous CI threshold would catch an
  order-of-magnitude regression without making CI flaky.

## The accept rule

A candidate is accepted when all of these hold:

- the median of the metric the hypothesis named moved in the predicted direction,
- the two ranges do not overlap, at three or more runs per condition, and for a time or
  frame count, two or more back-to-back pairs are beyond the tolerance (ranges apart
  with every pair within the tolerance is not a result),
- nothing else in the table moved the wrong way without being accounted for, and
- the complexity is worth it.

The first three are arithmetic.
The fourth is a judgment and gets written as one.

**Which tool applies the pair rule.** Only `judge()` in `transitions-stats.mjs` applies
it, for the transition scenario’s `compare` and for `wkprobe-stats.mjs`: it computes
each pair’s ratio and judges at 1.3x unless the protocol registers another
`--tolerance`. `run.py compare` and `probe-server` compute no pair ratios, and
`startup_pairs.py summarize --ratios` prints them but judges nothing.
A round on those tools registers, in its protocol, the tolerance it judges at (careful
or rough cut, as
[Comparing a candidate with the previous release](#comparing-a-candidate-with-the-previous-release)
defines them) and the script that applies the rule.

**What the third clause sees, and what accounts for a result.** The table is the one the
hypothesis’s own record declared: its deciding metrics and guards on its transitions.
A wrong-way result there is accounted for in only two ways:

- by a rule that record declared before it measured, such as exp-085’s E1 to E3 or
  exp-087’s later-frame test;
- by that record’s own account of the same metric, on the same transition, moving the
  same way.

An account never carries to a transition its record saw unchanged.
Where a protocol can be read two ways, the reading that accounts for less governs.
exp-079’s Deviation section is the worked example.

**Who judges what.** The operator who runs a round computes clauses 1 to 3 with the
analysis the protocol registered, mechanically, and reports the facts clause 4 needs:
the diff size, the mechanism, and the failure modes from the record.
The coordinator, the agent or person who owns the campaign, writes clause 4, one
judgment per hypothesis, in the record.
A round with several hypotheses keeps one schema decision, so its body carries a
per-hypothesis verdict table.

**Size n to the effect you are hunting.** Three runs per condition resolves a 5x effect;
it does not resolve a 40% one — exp-003’s candidate band read as 342-413 at n=3 and
widened to 342-561 at n=6. For an expected effect under 2x, measure each condition from
its own clean, content-identified build, alternate them in back-to-back pairs, and take
at least five runs per side, or use `probe-server`, which gets a dozen samples per run
for free. A one-frame difference does not resolve at six pairs: frames are quantized, so
a view that lands one frame later in some runs needs exp-087’s later-frame test
([exp-087-analyze.mjs](experiments/exp-087-analyze.mjs)), a Fisher test on how often
each side lands later, declared before the round.

Two rules about honesty, both learned the expensive way:

**A median without its range is not a result.** These corpora are noisy — a cold run’s
`dcl_ms` has spanned 152 ms to 1,176 ms with nothing changed.
If the ranges overlap, the finding is “no detectable effect”, not “a small win”.

**The metric is named before the measurement.** Measuring on the metric a hypothesis
predicted, missing, and then finding another metric that passes is not an accept.
Say what moved and say the prediction failed.

## Measure a real tree, not only the synthetic one

```shell
$UV explorations/performance-loop/run.py count /path/to/tree          # files and dirs, the walker's rule
$UV explorations/performance-loop/run.py serve --tree /path/to/tree --files <count> --exp exp-00N --label before
```

A real tree is recorded by its basename plus a hash of its path, never by the path:
someone’s working directory is not a fact about Metabrowser and does not belong in a
committed ledger.

**Do this before trusting any synthetic result.** exp-005 is the cautionary tale:
`build_corpus` puts 309 files in every directory and a real working tree puts 2.4, a
128× difference in how often every per-directory cost is paid, and nothing measured
before that round could see it.
It overturned the plan’s ordering and showed exp-004’s headline result to be conditional
on state a first open does not have.

**A client perturbs the thing it measures.** On a real tree the walk takes 21 s
unattached and 258 s with one polling client.
So `probe-server` is measuring the route *and* changing the scan it measures.
When the walk’s own duration is the subject, time it with nothing attached; when the
route is the subject, `probe-server` is right and the walk figure it records should be
read as “under load.”

## Re-running an old round against today’s corpus

The corpus and the harness are versioned separately from the code they measure, so a
result can be reproduced, and so a change to the fixture cannot quietly invalidate the
ledger. Every run records `commit`, `corpus_shape`, and `harness_version`; two runs are
comparable when the last two match.

To re-measure an old commit on the current corpus — which is how you check whether a
past result still holds after the fixture changed:

```shell
git worktree add --detach /tmp/mb-at-<sha> <sha>   # the code as it was
(cd /tmp/mb-at-<sha> &&
  uv --config-file uv.toml sync --locked --all-extras --all-groups &&
  uv --config-file uv.toml build --clear --no-build-isolation --out-dir "$RESULTS/old")
OLD_WHEEL=$(ls "$RESULTS"/old/metabrowser-*.whl)
# Install it into the environment the other condition uses, then run today's harness:
use_wheel "$OLD_WHEEL"
$UV explorations/performance-loop/run.py serve \
  --metab "$ENVS/env/bin/metab" --artifact "$OLD_WHEEL" \
  --build-ref <full-sha> \
  --tree /path/to/corpus --files <count> --exp exp-0NN --label old
```

`RESULTS`, `ENVS` and its shared environment, and `use_wheel` are the ones set up in
[Comparing a candidate with the previous release](#comparing-a-candidate-with-the-previous-release),
including its warm-up cycle.
Every commit since the repository became a standalone package locks the `build`
dependency group that the isolation-free build installs.
Build the old commit as a wheel rather than syncing its checkout: an editable install is
refused, and a second environment would not share the other condition’s dependency
identity.

The harness lives in the repository it measures, so checking out an old commit reverts
the harness too.
Run the harness from the current worktree and point it at the old build;
never check out an old harness to compare against a new number.

**When the corpus shape changes, bump `shape` in the generator.**
`build_realistic_corpus` carries a `shape` version in its marker file, and a mismatch
rebuilds the tree rather than reusing a differently-shaped one.
exp-006 is why: its corpus was rebuilt mid-round with the same file count and a
different arrangement of ignored subtrees, and that flipped the verdict from a 42%
regression to a win.
Runs from before a shape bump are still in the ledger and are still true — of a
different tree.

## The corpus

Three generators live in `devtools/bench_serving.py`, and the difference between the
first two is the subject of
[exp-005](experiments/exp-005-a-real-tree-changes-the-priorities.md).
`bench_serving` is otherwise a different tool from this loop, but the corpus is shared:
these functions are what [Building the corpus](#building-the-corpus) calls.

`build_project_corpus` is **the one to use**, and it is what `project-10` means.
It does not approximate a real tree from summary statistics — it copies the actual
`node_modules` that `package-lock.json` produces and the actual `.venv` that `uv.lock`
produces, with the repository’s own `src`, `tests` and `docs` as the tracked half.
So the directory shapes, name lengths, nesting and file-size distribution are a real
dependency tree’s rather than a guess at one.
Copies use APFS clones, so ten projects cost about one dependency tree on disk.

**A comparison needs one tree, not a permanent one.** Build the corpus once, then run
both binaries against it — the old release and the candidate see the same bytes, which
is the whole requirement.
`compare_builds` fingerprints the tree before and after to prove it did not move under
the measurement.
Which commit the corpus was built from does not matter, as long as it is
one tree and the round records which.

So the determinism worth stating is narrow and sufficient: the inputs are two committed
lockfiles and a git checkout, with no network needed, so **one commit with one pair of
locks gives one tree**. Rebuilding at a later commit gives a different tree, because the
tracked half is the working tree’s own source — exp-020 measured 246,282 files in late
August and the same generator gives 248,872 today.
That is not a defect; it only means a round is comparable with another when their corpus
labels match, which the label now carries: it hashes the corpus marker alongside the
path, so a rebuild at the same path gets a new label rather than silently pooling with
the old round.

`build_realistic_corpus` approximates that shape from statistics instead: median two
files per directory, mean depth around nine, a nested `.gitignore` roughly every four
hundred directories, and most of the file count inside a few enormous ignored subtrees.
That last detail is not decoration — it decided the verdict in
[exp-006](experiments/exp-006-the-gitignore-prewalk-stops-traversing-what-it-cannot-use.md).
Use it when a round needs a size the project corpus cannot reach.

`build_corpus` is the original: 309 files per directory, shallow, and no `.gitignore` at
all. It is kept because exp-001 through exp-004 were measured on it and their numbers
mean nothing against a different tree.
Do not start a new round on it.

**Sanity-check on a real tree.** The reproducible corpus is what a result is recorded
against; a real working tree is what tells you the result is real.
exp-006 is the worked example — the corpus called the change a regression and two real
trees called it an 88% win, and the corpus was the one that was wrong.
Use `serve --tree` for those checks and record them as sanity checks rather than as a
baseline, because a working directory changes under you and nothing later can be diffed
against it.

Absolute numbers move with hardware and page cache and do not carry between machines.
The relation is what carries, so every experiment records its own before alongside its
after rather than comparing against a number from another day.

**`/` is a 307 to `/view/`.** Curl the shell at `/view/`; a `curl` of `/` returns an
empty body and reads as a broken server.

**A fresh server is not a cold scan.** `serve` restarts the process, so the index starts
empty, but the operating system’s metadata cache does not.
After the corpus has been served a few times the walk finishes in well under a second,
and a page loaded then meets a settled index rather than a running one — which is a
different regime, and the difference is large: the folder-warming sweep took 32 requests
and stopped at 2.2 s against a settled index, and trickled one request per ~800 ms past
28 s against a running one.
Dropping the page cache on macOS needs root, so a run that did not do it says so rather
than implying a cold disk.
Record which regime a run met.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
