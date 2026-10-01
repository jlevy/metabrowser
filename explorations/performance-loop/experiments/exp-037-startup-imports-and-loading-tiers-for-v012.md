---
title: Deferring unused Git imports and two browser modules brings v0.12 start-up work within 1.05x of v0.11.0, except --doctor and the startup-script gate
softschema:
  contract: metabrowser.loadtime:Experiment/v1
  schema: experiment.schema.yaml
  envelope: experiment
  status: enforced
experiment:
  id: exp-037
  title: Deferring unused Git imports and two browser modules brings v0.12 start-up work within 1.05x of v0.11.0, except --doctor and the startup-script gate
  date: "2026-09-30"
  hypotheses: []
  subject:
    corpus: >-
      a folder holding this repository's docs/, src/ and README.md as of v0.11.0, with
      no Git directory, served as a plain trusted folder. The measured quantities are
      start-up work and what a page requests, neither of which scales with the tree, so
      this round does not use project-10 and nothing here compares with a round that
      does
    corpus_files: 315
    corpus_dirs: 39
    host_cpu: Apple M1 Pro, 10 cores
    host_system: Darwin 25.5.0, CPython 3.14.7
    browser: >-
      headless Chrome 152 driven through the DevTools Protocol, read for requests, bytes
      and DOM facts only; no visible-window capture was taken
    viewport: "1280x900"
    cold: true
  method:
    runs_per_condition: 20
    interleaved: true
    control: the v0.11.0 wheel, built from 6c278f3f
    candidate: the 20d7d54b wheel; f9d88f50, the commit it was branched from, is the second condition
    record: >-
      startup_pairs.py over installed console scripts from three environments created
      outside every work tree, 20 back-to-back pairs per candidate, control then
      candidate; tier-probe.mjs for the browser half. Output stayed under .bench/ and is
      summarized here
  results:
    - metric: cli_show_instr_millions
      control_median: 7461.6
      candidate_median: 7741.3
      control_range: [7420.2, 7486.0]
      candidate_range: [7700.4, 7816.8]
      change_pct: 3.7
      overlapping: false
    - metric: cli_api_tree_instr_millions
      control_median: 7495.9
      candidate_median: 7744.5
      control_range: [7426.9, 7543.6]
      candidate_range: [7686.5, 7775.2]
      change_pct: 3.3
      overlapping: false
    - metric: cli_version_instr_millions
      control_median: 5510.7
      candidate_median: 5480.2
      control_range: [5453.0, 5538.2]
      candidate_range: [5443.7, 5512.8]
      change_pct: -0.6
      overlapping: true
    - metric: serve_first_api_instr_millions
      control_median: 9121.0
      candidate_median: 9381.5
      control_range: [9051.9, 9209.0]
      candidate_range: [9281.7, 9422.9]
      change_pct: 2.9
      overlapping: false
    - metric: cli_doctor_instr_millions
      control_median: 5770.6
      candidate_median: 8873.4
      control_range: [5701.3, 5802.7]
      candidate_range: [8784.8, 8914.7]
      change_pct: 53.8
      overlapping: false
    - metric: shell_instr_millions
      control_median: 105.5
      candidate_median: 106.3
      control_range: [103.5, 106.5]
      candidate_range: [104.2, 107.3]
      change_pct: 0.7
      overlapping: true
    - metric: startup_script_transfer_bytes
      control_median: 175352
      candidate_median: 184320
      control_range: [175352, 175352]
      candidate_range: [184320, 184320]
      change_pct: 5.1
      overlapping: false
    - metric: startup_script_requests
      control_median: 20
      candidate_median: 20
      control_range: [20, 20]
      candidate_range: [20, 20]
      change_pct: 0.0
      overlapping: true
  complexity:
    lines_changed: 389
    new_dependencies: []
    new_failure_modes:
      - >-
        `metab` modes that serve a folder no longer import the revision tree source, so
        code that needs a name from it on a folder's path must import it where it is
        used. A top-level import added later brings the cost back silently;
        tests/test_plugin_public_api.py fails when one does.
      - >-
        A handler that imports a pin's module before it checks the subject no longer
        gets that import for free. `api_catalog` did, and the deferral turned it into
        the first catalog request's cost on a folder until the route series caught it;
        the boundary test now runs the routes a folder's page asks for.
      - >-
        `renderSourceView` relies on the line-anchor module having arrived with the view
        compositor. A caller outside a view's render, before any view has mounted, would
        find it missing. No built-in caller is, and the changelog says so for plugins.
    notes: >-
      Two instruments are new and committed, startup_pairs.py and tier-probe.mjs,
      because the loop had neither a start-up measurement nor a tier one.
  verdict:
    decision: accepted
    primary_metric: cli_show_instr_millions
    reason: >-
      Judged on instructions retired, because the machine never became quiet. Against
      v0.11.0 the branch point did 1.066x the work for --show, 1.063x for --api, 1.046x
      for --version and 1.049x from server spawn to the first /api answer, above 1.05x
      in every one of 20 adjacent pairs for the first two. The candidate does 1.039x,
      1.032x, 0.995x and 1.027x; one --show pair of 20 reached 1.051x and no other pair
      of any of the four exceeded 1.05x. Startup JavaScript went from 1.094x the
      release's transferred bytes to 1.051x, and a Source view still appeared with its
      gutter in every load. Accepted as a change. It is not a release clearance: wall
      time was not resolved, --doctor does 1.54x the work by design, startup JavaScript
      is still 180 KB against a 175 KB gate, and no visible-Chrome capture was taken.
    commit: 20d7d54b
---
# exp-037: deferring unused Git imports and two browser modules brings v0.12 start-up work within 1.05x of v0.11.0

## The question

A regression check of the v0.12 stack against v0.11.0 found routes and memory unchanged
and start-up 5–7% heavier in every mode, `--version` included.
All of it was import cost, and it was paid by a plain folder that never opens a
repository. The same check found startup JavaScript 9% larger, with one new module,
`source-line-anchors.js`, on the eager path with no recorded measurement for its tier,
and two Markdown modules loaded on trusted folders that may not use them.

Three questions, then.
Is the start-up cost still there at the head of the stack?
Can the imports a folder does not use be deferred without changing behavior?
And which tier do the three browser modules belong in, by measurement?

## What was run

Three wheels, built the way `make build` builds a release and installed into three
environments outside every work tree: v0.11.0 from `6c278f3f`; the branch point
`f9d88f50`, which is the head of the v0.12 stack this change was cut from; and the
candidate `20d7d54b`. Each `metab --version` was asserted against its own wheel before a
measurement was taken.

`startup_pairs.py` ran 20 rounds per candidate.
A round is the control and then one candidate, back to back, so each ratio is between
two measurements taken next to each other.
Per build a round runs `--show README.md`, `--api /api/tree`, `--version` and `--doctor`
as one-shot commands, spawns a server and times it to its first `/api/routes` answer,
then fetches the shell once cold and nine times warm.

Start-up work is reported in instructions retired.
The machine was carrying other work throughout: across the series the load average on
its ten cores ran from 11 to 193, and it was 25–90 during the one tabulated below.
Instructions retired count what the process did, and the control’s own count for
`--show` spread by 1.2% across its 40 runs in that series.
Its wall time for the same command ran from 1.3 to 6.1 seconds.

`tier-probe.mjs` drove stock headless Chrome 152 with a throwaway profile, every load in
a browser context of its own so the HTTP cache started empty.
It was read for what does not depend on load: which scripts were requested before
`DOMContentLoaded` and how many bytes they transferred, whether a Source view had its
gutter when it first appeared, and which elements each layout shift moved.
The browser half was taken at `c5b807cb`, one commit before the candidate, whose static
files the candidate ships unchanged.

## Start-up work

Instructions retired, in millions, as the median of 20 rounds.
The ratio is the median of the 20 pair ratios, with the smallest and largest pair, and
the count of pairs above 1.05x.

| Metric | v0.11.0 | Branch point | Ratio | Above 1.05x | Candidate | Ratio | Above 1.05x |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `--show README.md` | 7,465 | 7,952 | 1.066 (1.058–1.070) | 20/20 | 7,741 | 1.039 (1.031–1.051) | 1/20 |
| `--api /api/tree` | 7,497 | 7,969 | 1.063 (1.052–1.080) | 20/20 | 7,745 | 1.032 (1.024–1.041) | 0/20 |
| `--version` | 5,511 | 5,768 | 1.046 (1.034–1.060) | 1/20 | 5,480 | 0.995 (0.985–1.002) | 0/20 |
| Server spawn to first `/api` | 9,143 | 9,597 | 1.049 (1.045–1.058) | 8/20 | 9,382 | 1.027 (1.018–1.035) | 0/20 |
| `--doctor` | 5,772 | 9,008 | 1.560 (1.547–1.569) | 20/20 | 8,873 | 1.537 (1.527–1.555) | 20/20 |
| Shell `/`, first request | 119.9 | 122.2 | 1.026 (0.943–1.125) | 5/20 | 121.8 | 1.012 (0.955–1.090) | 4/20 |
| Shell `/`, warm | 105.6 | 107.1 | 1.014 (0.992–1.030) | 0/20 | 106.3 | 1.009 (0.984–1.025) | 0/20 |

Peak memory footprint of the one-shot commands moved the same way: `--show` 1.029x to
1.019x, `--api` 1.039x to 1.024x, `--version` 1.032x to 0.998x, and `--doctor` 1.170x to
1.153x.

No pair of the candidate exceeds 1.1x on any metric but `--doctor`. On the four start-up
metrics one pair of 80 exceeds 1.05x: a `--show` pair at 1.051x, beside two at 1.0495x
and seventeen between 1.031x and 1.043x.

The series was taken five more times as the change grew, three with 9 pairs and two with
20, under load averages from 11 to 193. The candidate’s medians stayed within 0.005 of
these each time: `--show` at 1.035–1.039x, `--api` at 1.030–1.036x, `--version` at
0.994–0.997x, and the server at 1.026–1.029x.

### Where the work was

`python -X importtime` names the modules, and a tracer that reads instructions retired
around each import puts a cost on them.
The tracer’s own wrapper inflates every figure, so these rank the modules and do not sum
to the table above.

On a folder, the branch point imported `git.tree_source` (102M), `git.content_routes`
(89M), `mirror_refresh` (56M), `source` (52M) and `source_routes` (26M), none of which
v0.11.0 has, and `git.process` had grown by 38M. `--version` imported `git.tree_source`
through `cli.main`’s top-level import of the `--diff` CLI.

The candidate imports `git.tree_source` and `git.content_routes` only where a pinned
revision is served or a store blob is read, and the `--diff` CLI only in the `--diff`
branch. Every caller that asked “is this subject a pinned revision” with
`isinstance(subject, GitRevisionSubject)` now asks `source.git_revision_subject`, which
compares the subject’s kind before importing the class.
A pin’s own code path has imported the module by the time a pin exists, so the answer is
unchanged and a pin pays nothing more.

`tests/test_plugin_public_api.py` pins the boundary the way it already pinned the schema
libraries: a fresh interpreter runs `metab`, and the test asserts on `sys.modules`. It
covers `--version`, and on a folder `--show`, `--walk`, and `--api` for each route a
folder’s page asks for.

### The routes, and the import a deferral exposed

A deferred import is paid by whoever imports the module first, so the routes were
measured again on a 20,000-file tree and a tree of large documents, four pairs per
candidate, 28 metrics: first and warm requests for the tree, rollup, catalog, file, raw,
KPress render and view page, the scan to settled, and the settled footprint.

At the branch point every median ratio was between 0.96 and 1.01, start-up apart.
The first candidate wheel matched it on the rest and did 1.33x the work on the first
`/api/catalog` request, in four pairs of four: 798M instructions against 600M.
`api_catalog` imported `git.content_routes` ahead of its subject check, alone among the
event-route handlers, and while the server imported that module at start the line was
free.
Moved into the pin branch, the first catalog request costs about 600M in three runs
of four for the candidate and for the branch point, as it does for the release.
The fourth run costs about 730M in the candidate and in the branch point both, and the
release has one at 521M: that variation was there before and is not this change’s.

That is the reason the boundary test runs routes and not only modes.
A module absent at start says nothing about the first request that asks for it.

The settled footprint of the server on the 20,000-file tree is 1.03x the release’s at
the branch point and in the candidate.

### What remains, and why

`mirror_refresh` and `source_routes` still load with every server, about 1.1% of a
`--show` between them.
Each owns state or routes a folder’s server has too: the lifespan creates a refresh
coordinator for every subject, `/api/source/status` answers for a folder, and the pin
guard is in every middleware stack.
Leaving them out for a folder would change what the application holds, not when a module
loads, so it is not a deferral and was not done.

`source` is the subject abstraction every request reads, and `git.process` serves
gitignore rules and history for a folder inside a work tree.
Both are used.

The rest of the 3% is the server itself: `server.py` and the modules it always loaded
are larger than they were.

`--doctor` does 1.54x the work, and that is a feature: since `567d6b19` it validates the
packaged cache record contracts, which imports the schema libraries and regenerates each
schema to compare it.
With that one check replaced by a no-op, `--doctor` measured 6,160M at the branch point
and 6,030M in the candidate against the release’s 5,700M, or 1.08x and 1.06x. What is
left of that is the sidekicks `--doctor` imports to prove they resolve, which have grown
with the plugins.
The check is a diagnostic’s whole purpose, and removing it to recover a
ratio would be the wrong trade.
It is recorded here because it exceeds the rough-cut tolerance in every pair, and a
later reader should find the reason beside the number.

## Wall time, which this round does not resolve

Every round also recorded wall and CPU time.
The quietest series was the 20 pairs taken one commit earlier, at `c5b807cb`, under a
load average of 12–21. That commit differs from the candidate in one request handler,
which no start-up metric runs.
Median pair ratio against v0.11.0, with the smallest and largest pair:

| Metric | Branch point, wall | Candidate, wall | Branch point, CPU | Candidate, CPU |
| --- | --- | --- | --- | --- |
| `--show README.md` | 1.128 (0.77–1.86) | 1.074 (0.77–1.61) | 1.114 (0.99–1.22) | 1.050 (0.93–1.14) |
| `--api /api/tree` | 1.072 (0.77–1.66) | 1.086 (0.71–1.65) | 1.060 (0.96–1.19) | 1.023 (0.94–1.11) |
| `--version` | 1.002 (0.66–2.05) | 0.982 (0.60–1.19) | 1.045 (0.91–1.21) | 0.988 (0.84–1.04) |
| Server spawn to first `/api` | 1.113 (0.57–2.19) | 1.007 (0.66–1.87) | not recorded | not recorded |
| `--doctor` | 1.463 (0.77–3.20) | 1.373 (0.79–2.18) | 1.529 (1.32–1.73) | 1.460 (1.15–1.63) |

These are not results.
A metric whose instruction ratio spans 0.98–1.00 has a wall ratio spanning 0.60–1.19, so
the spread of a pair is ten times the effect being looked for.
The careful tolerance asks for a quiet machine, and the load average never fell below 11
on ten cores. The series at the candidate itself, under a load of 25–90, spread wider
still, from 0.23 to 2.93 on `--show`.

What the columns do show is direction.
CPU time, which is less exposed to the scheduler than wall time, moves the way the
instruction counts do on every command.
That is consistent with the instruction result and adds nothing to it.

The wall-clock comparison is still owed.
On a quiet machine:

```shell
UV="uv --config-file uv.toml run --frozen python"
$UV explorations/performance-loop/startup_pairs.py run \
  --tree /path/to/folder --pairs 9 --out .bench/startup-pairs.jsonl \
  --control /envs/v0.11.0/bin/metab --candidate tip=/envs/tip/bin/metab
$UV explorations/performance-loop/startup_pairs.py summarize .bench/startup-pairs.jsonl \
  --candidate tip --suffix _ms --ratios
```

## Loading tiers

### The line gutter

`source-line-anchors.js` was a blocking script in the shell.
The comment beside its consumer said the gutter is part of the first paint.
Measured on the folder shell, which draws no gutter:

| Startup scripts, before `DOMContentLoaded` | Requests | Transferred | Decoded |
| --- | --- | --- | --- |
| v0.11.0 | 20 | 175,352 | 591,090 |
| Branch point | 21 | 191,862 | 644,947 |
| Candidate | 20 | 184,320 | 620,918 |

The module was 7,992 of the transferred bytes and 25,515 of the decoded ones.
Its compile and evaluate together took a median 0.09 ms across loads, because V8
compiles a function when it is first called and nothing calls these on a folder page.
So the module costs nothing to run and something to fetch, and transfer before
`DOMContentLoaded` is exactly what `startup_script_transfer_kb` bounds.

The candidate makes it an on-demand bundle that `loadViewComposition` fetches beside the
view compositor and waits for.
Every Source view is mounted by the compositor, so the module is present before any
renderer asks for a gutter.
It is a bundle of its own, not a second script in the compositor’s, because the asset
loader fetches a bundle’s scripts one after another: as a second entry it started when
the first had finished, and as its own bundle the two start within 0.1 ms of each other.

Whether a Source view could now paint without its gutter was measured on a cold deep
link to a 27 KB Python file with a line anchor, and on the same file without one, ten
loads each per build:

| Build | Gutter present when the view first appeared | Gutter width | Code left edge | Layout shift sources |
| --- | --- | --- | --- | --- |
| Branch point, eager | 10/10 and 10/10 | 32.98 px | 356.98 px | tree rows and their sizes only |
| Candidate, on demand | 10/10 and 10/10 | 32.98 px | 356.98 px | tree rows and their sizes only |

No layout shift in either build had a node of the preview pane as a source.
The gutter and the code are one synchronous insertion, so this is the result the design
predicts; the measurement is what says the design holds.

Navigation is the other consumer: it reads an address’s anchor to decide whether a file
opens in its Source view.
Only an address with a fragment or a query can ask for one, so that is the only open
that now waits for the module, and its load starts before the tree row is revealed and
overlaps it. A plain file open is unchanged.

Time to the Source view was recorded and is not a result.
From `DOMContentLoaded` to the painted view the medians were 104 ms at the branch point
and 116 ms in the candidate on the anchored link, and 125 ms and 104 ms on the plain
one, with pair ratios from 0.37 to 3.87 under a load average of 19–21. The two disagree
in direction, which is what noise looks like.
The total a file view fetches is the same in both tiers, 38 scripts and 330,607 against
331,057 bytes: the module moved, it was not removed.

### The inert Markdown render

`inert-render.js` and `inert-toc.js` place an untrusted document’s render and draw its
table of contents.
The server marks a render inert only when active content is off, which
is a property of the server, not the document, so a trusted folder never receives one.
The views imported both statically anyway.

The candidate places a render through `place-rendered.js`, which imports the inert path
on the first inert render.

| Trusted folder, first Markdown view | Modules | Transferred | Decoded |
| --- | --- | --- | --- |
| Branch point | 18 | 66,982 | 217,471 |
| Candidate | 17 | 62,955 | 207,001 |

Under `--untrusted` the candidate fetched both modules through the dynamic import, built
the inert article, drew its table of contents with ten entries, and marked the entry at
the reading line. The page logged no exception and no policy violation, which matters
because that profile’s Content-Security-Policy admits scripts only from the server’s own
paths.

## The startup-script gate is not met

`performance-budgets.toml` gates `startup_script_transfer_kb` at 175, measured as this
round measured it: transferred bytes of non-vendor scripts requested before
`DOMContentLoaded`, in KiB.

| Build | Requests, gate 25 | Transfer, gate 175 KB |
| --- | --- | --- |
| v0.11.0 | 20 | 171 KB |
| Branch point | 21 | 187 KB |
| Candidate | 20 | 180 KB |

The candidate recovers 7.4 KB of the 16.1 KB the stack added and is still 5 KB over.
What remains is growth in three modules every page needs: `app.js` by 3,578 transferred
bytes, `navigation.js` by 3,281, and `plugin-sdk.js` by 2,109. None of that is a tier
decision. Either code moves out of those modules to behind the first usable tree, or the
ceiling is raised with a measurement that shows the headroom is still real.
This round does neither and says so, because the gate is checked by `run.py compare`,
which is not part of `make verify`, and a release could cross it unnoticed.

The number comes from headless Chrome on a small folder.
The gate was calibrated on project-10 in a visible window, but the quantity is the sum
of the shell’s own script responses, which the tree does not change.

## What this does not say

It does not say v0.12 starts as fast as v0.11.0. It does 3% more work to start, and the
wall-clock pairs that would say what a reader notices have not been taken.

It does not clear the release.
The release comparison is the visible-Chrome captures and the pair comparison on
project-10, and this round took neither.

One thing the probe saw that is not this change’s: a Markdown view shifts its layout by
0.037 in about one load in twenty-four, in v0.11.0, the branch point and the candidate
alike. Code blocks and the paragraphs after them move.
It is recorded here so that the next reader of a layout-shift number does not attribute
it to whatever changed last.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
