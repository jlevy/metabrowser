---
title: Deferring unused Git imports and view-phase browser code brings v0.12 start-up within 1.05x of v0.11.0 and back under its startup-script gate, except --doctor
softschema:
  contract: metabrowser.loadtime:Experiment/v1
  schema: experiment.schema.yaml
  envelope: experiment
  status: enforced
experiment:
  id: exp-037
  title: Deferring unused Git imports and view-phase browser code brings v0.12 start-up within 1.05x of v0.11.0 and back under its startup-script gate, except --doctor
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
    runs_per_condition: 12
    interleaved: true
    control: the v0.11.0 wheel, built from 6c278f3f
    candidate: >-
      the 9a56f513 wheel, the head after review; f9d88f50, the commit this change was
      first cut from, is the second condition. The series was first recorded at 2421889b
      and its ratios agree with these to within 0.002
    record: >-
      startup_pairs.py over installed console scripts from three environments created
      outside every work tree, 12 back-to-back pairs per candidate, control then
      candidate; tier-probe.mjs for the browser half, and run.py serve and capture, the
      gate's own harness, for the startup-script metric. Output stayed under .bench/ and
      is summarized here
  results:
    - metric: cli_show_instr_millions
      control_median: 7400.8
      candidate_median: 7689.4
      control_range: [7366.4, 7433.6]
      candidate_range: [7609.1, 7700.7]
      change_pct: 3.9
      overlapping: false
    - metric: cli_api_tree_instr_millions
      control_median: 7441.5
      candidate_median: 7693.5
      control_range: [7407.1, 7460.4]
      candidate_range: [7660.0, 7748.1]
      change_pct: 3.4
      overlapping: false
    - metric: cli_version_instr_millions
      control_median: 5465.4
      candidate_median: 5441.2
      control_range: [5445.3, 5474.8]
      candidate_range: [5430.4, 5455.1]
      change_pct: -0.4
      overlapping: true
    - metric: serve_first_api_instr_millions
      control_median: 9069.6
      candidate_median: 9310.8
      control_range: [9046.5, 9093.2]
      candidate_range: [9294.0, 9338.2]
      change_pct: 2.7
      overlapping: false
    - metric: cli_doctor_instr_millions
      control_median: 5721.0
      candidate_median: 8811.2
      control_range: [5711.7, 5742.2]
      candidate_range: [8797.5, 8824.8]
      change_pct: 54.0
      overlapping: false
    - metric: shell_instr_millions
      control_median: 105.5
      candidate_median: 106.4
      control_range: [105.0, 106.3]
      candidate_range: [104.3, 107.0]
      change_pct: 0.9
      overlapping: true
    - metric: startup_script_transfer_bytes
      control_median: 175352
      candidate_median: 177539
      control_range: [175352, 175352]
      candidate_range: [177539, 177539]
      change_pct: 1.2
      overlapping: false
    - metric: startup_script_requests
      control_median: 20
      candidate_median: 20
      control_range: [20, 20]
      candidate_range: [20, 20]
      change_pct: 0.0
      overlapping: true
  complexity:
    lines_changed: 6487
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
        The SDK's view helpers, the syntax service and the line gutter are not on
        `window.metabrowser` until something needs them. The shell fetches them beside
        the view compositor and the plugin loader has them in place before any plugin's
        code runs; shell code that runs before either, and is no plugin, would find
        them missing. As two bundles they were a defect: the loader waited for one, and
        a plugin loaded without the compositor threw in `renderSourceView`. They are one
        file now.
      - >-
        `ensureKindAssets` can reject. It never did; it does when the view helpers
        cannot be fetched, and every caller has to say so. The pull-request page and
        the Git panel do, and a caller added later that swallows it would show a page
        with nothing in it.
      - >-
        A page that loads at a pull-request address needs `pull-route.js` in its shell,
        and a pin's needs `git-path.js`. Each is a script tag the server writes for that
        shell. A pin's page that finds the codec missing stops and says so.
      - >-
        The syntax service used to learn that the optional assets had settled from an
        event it could now load after. The prefetch chain leaves a flag behind the
        event; a second late listener would need to read it too.
      - >-
        A startup script that outgrows the budget now fails `make lint-check`. That is
        the point, and it means a change to app.js can fail for its size alone. So does
        a script that asks for another one before DOMContentLoaded has been handled,
        and the check runs the shell's scripts in a document double to see it: startup
        code that calls something the double lacks fails the check until the double has
        it.
    notes: >-
      About a third of the changed lines are code moved between files, not written; the
      line gutter's 707 lines count twice. Two instruments are new and committed,
      startup_pairs.py and tier-probe.mjs, because the loop had neither a start-up
      measurement nor a tier one; one check, devtools/check_startup_scripts.py; and
      three browserless sessions that run what the tests used to read as text.
  verdict:
    decision: accepted
    primary_metric: cli_show_instr_millions
    reason: >-
      Judged on instructions retired, because the machine never became quiet. Against
      v0.11.0 the branch point did 1.068x the work for --show, 1.063x for --api, 1.049x
      for --version and 1.053x from server spawn to the first /api answer, above 1.05x
      in every one of 12 adjacent pairs for the first two. The candidate does 1.038x,
      1.034x, 0.996x and 1.026x, and no pair of any of the four exceeded 1.05x. Startup
      JavaScript went from 187 KB, over the 175 KB gate, to 173 KB, 1.012x the release's
      transferred bytes, and a check now holds it there. A Source view still appeared
      with its gutter in every load, a served mirror's and a served pull request's
      pages read the same before and after, and a third-party plugin's calls to the
      SDK work where they worked at the branch point. Accepted as a change. It is not a
      release clearance: wall time was not resolved, --doctor does 1.54x the work by
      design, and no visible-Chrome capture was taken.
    commit: 9a56f513
---
# exp-037: deferring unused Git imports and view-phase browser code brings v0.12 start-up within 1.05x of v0.11.0 and back under its startup-script gate

## The question

A regression check of the v0.12 stack against v0.11.0 found routes and memory unchanged
and start-up 5–7% heavier in every mode, `--version` included.
All of it was import cost, and it was paid by a plain folder that never opens a
repository. The same check found startup JavaScript 9% larger, with one new module,
`source-line-anchors.js`, on the eager path with no recorded measurement for its tier,
and two Markdown modules loaded on trusted folders that may not use them.

Four questions, then.
Is the start-up cost still there at the head of the stack?
Can the imports a folder does not use be deferred without changing behavior?
Which tier do the three browser modules belong in, by measurement?
And, once the measurement found the stack over the repository’s own startup-script gate:
what in the startup scripts does a folder’s first tree not need?

## What was run

Three wheels, built the way `make build` builds a release and installed into three
environments outside every work tree: v0.11.0 from `6c278f3f`; the branch point
`f9d88f50`, which is the head of the v0.12 stack this change was first cut from; and the
candidate.
Each `metab --version` was asserted against its own wheel before a measurement
was taken.

The candidate was `2421889b` when this round was first recorded.
An independent review then found one defect and several gaps, described under
[What review found](#what-review-found), and the candidate measured here is the head
after those fixes, `9a56f513`, installed with the same dependency versions as the other
two. Where a table or a figure below was taken at `2421889b` and not again, it says so.

`startup_pairs.py` ran 12 rounds per candidate.
A round is the control and then one candidate, back to back, so each ratio is between
two measurements taken next to each other.
Per build a round runs `--show README.md`, `--api /api/tree`, `--version` and `--doctor`
as one-shot commands, spawns a server and times it to its first `/api/routes` answer,
then fetches the shell once cold and nine times warm.

Start-up work is reported in instructions retired.
The machine was carrying other work throughout: across the series the load average on
its ten cores ran from 11 to 193, and it was 48–109 during the one tabulated below.
Instructions retired count what the process did; in a 20-pair series the control’s own
count for `--show` spread by 1.2% across its 40 runs, while its wall time for the same
command ran from 1.3 to 6.1 seconds.

`tier-probe.mjs` drove stock headless Chrome 152 with a throwaway profile, every load in
a browser context of its own so the HTTP cache started empty.
It was read for what does not depend on load: which scripts were requested before
`DOMContentLoaded` and how many bytes they transferred, whether a Source view had its
gutter when it first appeared, and which elements each layout shift moved.

The startup-script metric was also taken with the gate’s own harness, `run.py serve` and
`run.py capture`, which run the committed `probe.js` in Chrome.
Two things differ from a release capture, and neither changes this metric.
The capture was headless, because a visible window is required only for the
responsiveness gates and for `--record`; and the tree was `project-1`, one copy of the
tree `project-10` holds ten of, because the disk had 19 GB free and `project-10` writes
five. The metric is the sum of the shell’s own script responses, which the tree does not
enter.

## Start-up work

Instructions retired, in millions, as the median of 12 rounds.
The ratio is the median of the 12 pair ratios, with the smallest and largest pair, and
the count of pairs above 1.05x.

| Metric | v0.11.0 | Branch point | Ratio | Above 1.05x | Candidate | Ratio | Above 1.05x |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `--show README.md` | 7,410 | 7,904 | 1.066 (1.061–1.071) | 12/12 | 7,689 | 1.038 (1.024–1.044) | 0/12 |
| `--api /api/tree` | 7,445 | 7,922 | 1.064 (1.061–1.066) | 12/12 | 7,694 | 1.034 (1.030–1.040) | 0/12 |
| `--version` | 5,465 | 5,731 | 1.048 (1.044–1.050) | 0/12 | 5,441 | 0.996 (0.992–1.000) | 0/12 |
| Server spawn to first `/api` | 9,070 | 9,530 | 1.051 (1.048–1.054) | 9/12 | 9,311 | 1.026 (1.023–1.031) | 0/12 |
| `--doctor` | 5,725 | 8,951 | 1.562 (1.558–1.569) | 12/12 | 8,811 | 1.540 (1.536–1.543) | 12/12 |
| Shell `/`, first request | 120.5 | 121.9 | 1.007 (0.980–1.076) | 1/12 | 122.1 | 1.026 (0.963–1.062) | 2/12 |
| Shell `/`, warm | 105.4 | 106.9 | 1.016 (1.004–1.024) | 0/12 | 106.4 | 1.005 (0.984–1.017) | 0/12 |

Peak memory footprint of the one-shot commands moved the same way: `--show` 1.033x to
1.023x, `--api` 1.037x to 1.018x, `--version` 1.025x to 0.998x, and `--doctor` 1.165x to
1.147x.

No pair of the candidate exceeds 1.1x on any metric but `--doctor`. On the four start-up
metrics no pair of 48 exceeds 1.05x. The first shell request is 120M instructions that
swing by a twentieth from run to run in every build; two of its pairs are above 1.05x
for the candidate and one for the branch point, and its median says nothing either way.

The series was taken seven times before this one as the change grew, three with 9 pairs,
three with 20 and one with 12, under load averages from 11 to 193. The candidate’s
medians stayed within 0.005 of these each time: `--show` at 1.035–1.039x, `--api` at
1.030–1.036x, `--version` at 0.994–0.998x, and the server at 1.025–1.029x. In one
20-pair series a single `--show` pair reached 1.051x, beside two at 1.0495x and
seventeen between 1.031x and 1.043x.

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
`isinstance(subject, GitRevisionSubject)` now asks `source.as_git_revision_subject`,
which compares the subject’s kind before importing the class.
A pin’s own code path has imported the tree source by the time a pin exists, so the
answer is unchanged and that import costs a pin nothing.

The routes are another matter, and the first record of this round was wrong to say a pin
pays nothing more.
With `git.content_routes` imported where a pin is served, a served pin
imported it inside its first request, on the event loop, while that request and every
other waited: the cost had moved from the pin’s start to its first reader.
A served pin now imports the module as the pin is handed to the server, before the
server starts (`cli/git_pin_cli.py`), and a test serves a pin with nothing requested and
finds the module loaded.
A one-shot command on a pin still imports it with its one request, which is the whole of
that command.

`tests/test_plugin_public_api.py` pins the boundary the way it already pinned the schema
libraries: a fresh interpreter runs `metab`, and the test asserts on `sys.modules`. It
covers `--version`, and on a folder `--show`, `--walk`, and `--api` for each route a
folder’s page asks for.
`--api` reaches only `/api/` routes, so the page routes go through the same in-process
client in the same kind of interpreter: `/`, `/view/`, a file’s and a folder’s page,
`/raw/`, and a commit and a pull-request address.
The shell’s handler branches on the subject before it renders, which makes it the
easiest place to hoist a pin’s import, and review showed that a `git.tree_source` import
hoisted there passed the test as it stood.
With the page routes in it, that import fails five cases.

### The routes, and the import a deferral exposed

A deferred import is paid by whoever imports the module first, so the routes were
measured again, at `20d7d54b`, on a 20,000-file tree and a tree of large documents, four
pairs per candidate, 28 metrics: first and warm requests for the tree, rollup, catalog,
file, raw, KPress render and view page, the scan to settled, and the settled footprint.

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
The quietest series was 20 pairs taken at `c5b807cb`, under a load average of 12–21.
What the candidate adds to that commit is one request handler and code moved between
browser scripts, which no start-up metric runs.
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
on ten cores. A later series, under a load of 25–90, spread wider still, from 0.23 to
2.93 on `--show`.

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
| With this move alone | 20 | 184,320 | 620,918 |

The module was 7,992 of the transferred bytes and 25,515 of the decoded ones.
Its compile and evaluate together took a median 0.09 ms across loads, because V8
compiles a function when it is first called and nothing calls these on a folder page.
So the module costs nothing to run and something to fetch, and transfer before
`DOMContentLoaded` is exactly what `startup_script_transfer_kb` bounds.

The candidate fetches it on demand, beside the view compositor, and waits for it.
At `2421889b` it was a bundle of its own.
That was a defect, found in review and described under
[What review found](#what-review-found): the plugin loader waited for the SDK’s view
helpers and not for the gutter they draw.
It is now part of `plugin-sdk-views.js`, the one file that holds what a view’s renderer
calls, and one bundle.
It is not a second script in a bundle, because the asset loader fetches a bundle’s
scripts one after another.

Whether a Source view could now paint without its gutter was measured on a cold deep
link to a 27 KB Python file with a line anchor, and on the same file without one, ten
loads each per build:

| Build | Gutter present when the view first appeared | Gutter width | Code left edge | Layout shift sources |
| --- | --- | --- | --- | --- |
| Branch point, eager | 10/10 and 10/10 | 32.98 px | 356.98 px | tree rows and their sizes only |
| `2421889b`, on demand | 10/10 and 10/10 | 32.98 px | 356.98 px | tree rows and their sizes only |

No layout shift in either build had a node of the preview pane as a source.
At `9a56f513` the probe ran again on an anchored link to a smaller file, six cold loads
per build: the Source view appeared with its gutter in 6/6 at the branch point and in
the candidate, the gutter 26.39 px wide in both, and every layout shift moved tree rows
and their sizes only.
The gutter and the code are one synchronous insertion, so this is the result the design
predicts; the measurement is what says the design holds.

Navigation is the other consumer: it reads an address’s anchor to decide whether a file
opens in its Source view.
Only an address with a fragment or a query can ask for one, so that is the only open
that now waits for the module, and its load starts before the tree row is revealed and
overlaps it. A plain file open is unchanged.
The preview-pane session runs this with the production asset loader fetching the
production file: a cold `/view/a.py#L10` opens the Source view, the fetch is under way
while the row is revealed, and a plain address asks for nothing first.
With the wait removed from `addressedView`, the same step opens the default view.

Time to the Source view was recorded and is not a result.
From `DOMContentLoaded` to the painted view the medians were 254 ms at the branch point
and 249 ms in the candidate on the anchored link, and 161 ms and 169 ms on the plain
one, with pair ratios from 0.38 to 1.71 under a load average of 60–71. The two disagree
in direction, which is what noise looks like.
A file view fetches the same code in either tier, 330,607 bytes of script at the branch
point and 331,102 in the candidate: the modules moved, they were not removed.

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
| `2421889b` | 17 | 62,955 | 207,001 |

This table and the untrusted check below were taken at `2421889b`. Nothing after it
touches the Markdown plugin.

Under `--untrusted` the candidate fetched both modules through the dynamic import, built
the inert article, drew its table of contents with ten entries, and marked the entry at
the reading line. The page logged no exception and no policy violation, which matters
because that profile’s Content-Security-Policy admits scripts only from the server’s own
paths.

### The SDK’s view helpers and the syntax service

With the gutter moved, startup JavaScript was still 180 KB against the gate’s 175, and
none of what was left was a module the shell could do without.
What was left was code inside the modules it could not.

`plugin-sdk.js` is a startup script: the shell needs the plugin host and the registry
before it can start.
It also held the helpers a renderer builds a view’s markup with, `renderSourceView`,
`wrapWithCopy`, `partialNoticeHtml`, the two truncation notices, `langForPath` and
`langForExtension`, and the syntax service, `highlightSyntax` and `isLargeTextPreview`.
Nothing runs any of them until a view renders.
They were 5,632 of the script’s 22,308 compressed bytes.

They are now in `plugin-sdk-views.js`, the `sdk-views` on-demand bundle, with the line
gutter.
`loadViewComposition` fetches it beside the compositor, the two requests starting
within 0.2 ms of one another, and `loadPluginsForKind` has it in place before any
plugin’s code runs. The second is the one that matters for a page that mounts a plugin
without the compositor, as the commit page and the pull-request page do: Chrome shows
those pages fetching the helpers on that path.
So every helper is on `window.metabrowser` wherever a plugin’s code can run, and a
plugin sees the SDK it always did.

The syntax service needed one change to move.
It waits for a grammar until the optional assets have settled, and it learned that they
had from an event. Loaded with the first view, it can arrive after the event, and would
then wait forever for a grammar that was never coming.
The prefetch chain now sets `METABROWSER_OPTIONAL_ASSETS_SETTLED` before it dispatches
the event, and the service reads it when it loads.
The syntax session checks a service loaded after settlement, and fails with the flag
unread.
A 27 KB Python file highlighted the same 888 tokens in Chrome at the branch point
and at `2421889b`.

### The pull-request routes

`pullHref`, `parsePull`, `pullHistoryAction` and `createPullPageHost` were part of
`navigation.js`, and the shell created the page’s host as it loaded: 1,818 of that
script’s 13,265 compressed bytes, for an address space only a served pull request has.

They are now `pull-route.js`, and the host is created when an address under `/pull/` is
opened. The server knows the address when it renders the shell, so it writes the script
into the shell of a pull-request address, as it writes `git-path.js` into a pin’s: the
request starts with the rest of the shell’s. At `2421889b` the script was requested by
`app.js` as it ran, which put it one round trip behind the shell and made it a startup
request no script tag showed; see [What review found](#what-review-found).
A history landing on a page’s address with no host yet takes the `pull-route` on-demand
bundle and then applies the landing, unless history has moved on.
Any other address never asks for the module.

A served pull request’s page was driven in Chrome on the branch point and on the
candidate, `9a56f513`, through seven steps: the landing, a click on Files changed, back,
forward, a load at `/pull/7/files`, a file opened from the tree, and back to the page.
The address, the active tab, the page’s text and the count of changed files were the
same at every step, with no page error.
On the candidate the request for `pull-route.js` started 24 ms into the load, with the
shell’s other scripts, 128 ms before `DOMContentLoaded`. A folder at `/pull/7` shows
what it showed, the GitHub plugin’s “This server serves no pull request”, and `/pull/x`
is still the server’s 400.

### The GitPath codec

`gitPathWire` and the decoder behind `displayPath` spell a pinned revision’s paths as
`/view/` addresses them.
Only a pin’s page reads or writes that spelling: 885 compressed bytes of `navigation.js`
on every folder’s page.

A pin needs them before its first paint, because `displayPath` is synchronous, so this
is not an on-demand bundle.
It is `git-path.js`, which the server writes into a pin’s shell ahead of `navigation.js`
and leaves out of a folder’s, the way it already writes the pin guard.
The tier is eager; the shell it is eager on is the one that uses it.

### A served mirror’s page, before and after

The freshness row and the ref selector were not moved.
They were already fetched on demand after the first tree request, and a pin’s page was
measured to see that nothing moved under them.
Six cold loads per build of a served `file://` mirror, at `9a56f513`:

|  | Branch point | Candidate |
| --- | --- | --- |
| Freshness row | “Fetched just now”, 6/6 | “Fetched just now”, 6/6 |
| Ref selector | “Branch: topic”, 6/6 | “Branch: topic”, 6/6 |
| Row and selector after the first tree row | 17–110 ms | 27–101 ms |
| Layout shifts | one of 0.0057 in 6/6, as they arrive | one of 0.0057 in 6/6, as they arrive |
| File header on a file’s address | the decoded name | the decoded name |
| Page errors | none | none |
| Startup scripts on the pin’s shell | 21, 191,862 bytes | 21, 179,425 bytes |

The row and the selector do arrive after the first rows, and push the tree down by a row
when they do. That shift is in the branch point in every load.
It is the stack’s own tier decision for those two, not this change’s, and it is the one
thing here a reader of a pin’s page sees arrive.
The delay ranges overlap and were taken under a load average of 70–75, so they say
nothing about which build is quicker.

## The startup-script gate

`performance-budgets.toml` gates `startup_script_requests` at 25 and
`startup_script_transfer_kb` at 175: the non-vendor scripts a folder’s shell requests
before `DOMContentLoaded`, by `transferSize`, in KiB.

| Build | Requests | Transferred | Decoded | Gate metric | `run.py capture` on project-1 | `check_startup_scripts` |
| --- | --- | --- | --- | --- | --- | --- |
| v0.11.0 | 20 | 175,352 | 591,090 | 171 KB | 20, 171 KB | 20, 171 KB, 175,352 |
| Branch point | 21 | 191,862 | 644,947 | **187 KB** | 21, 187 KB | fails: 21, 187 KB, 191,862 |
| After the gutter move | 20 | 184,320 | 620,918 | **180 KB** | 20, 180 KB | fails: 20, 180 KB, 184,320 |
| `2421889b` | 20 | 176,984 | 595,187 | 173 KB | 20, 173 KB | 20, 173 KB, 176,984 |
| Candidate, `9a56f513` | 20 | 177,539 | 597,270 | 173 KB | 20, 173 KB | 20, 173 KB, 177,539 |

The stack had crossed the gate by 12 KB. The candidate is 2 KB under it and 1.012x the
release’s transferred bytes; the margin to the point where the metric rounds to 176 is
2,172 bytes.
The 555 bytes the review’s fixes added are 368 in `app.js`, for the states a
page shows when on-demand code does not arrive and the check that a pin’s page has its
codec, 160 in `plugin-sdk.js`, for the loader that starts a plugin’s assets beside the
helpers, and 27 in `navigation.js`.

Each move’s share, as the shell’s transferred bytes after it:

| Move | Startup bytes after |
| --- | --- |
| Line gutter, with the view compositor | 184,320 |
| SDK view helpers, with the view compositor | 181,124 |
| Pull-request routes, on demand | 179,909 |
| Syntax service, with the view helpers | 177,832 |
| GitPath codec, on a pin’s shell only | 176,984 |
| The review’s fixes | 177,539 |

What the candidate still carries over the release is 2,187 bytes: `app.js` is 4,603
larger, `navigation.js` 613 larger, and `plugin-sdk.js` 3,029 smaller.
Some of the `app.js` growth is this change’s own: the code that creates the page host on
demand, waits for the gutter module, and says what did not load.

### Why nobody saw it, and the check

The gate is applied by `run.py compare` to browser captures, which no ordinary change
takes, and `make verify` did not know about it.

`devtools/check_startup_scripts.py` now applies both ceilings on every
`make lint-check`. It renders a folder’s shell through the application, counts every
`<script src>` in it, compresses each file as the application’s gzip middleware does,
and adds 300 bytes. That is the browser’s number and not an estimate of it: Chrome
reports `transferSize` as the encoded body plus a fixed 300 bytes, whatever the headers’
real length, and the application’s compressed body is what a one-shot gzip at the
middleware’s level produces.
The last column above is the check run against each build, the first four with the check
as it was first written and the last with the check as it stands, and it matches the
browser’s count to the byte on all five.
Its limits are read from the budget file, and its tests hold the script list, the
equality with the body the running application sends, and the probe’s own selection and
rounding, run as code on the entries the check models.

As first written the check failed open, which review showed with a deferred script and
an inline `ensureAsset(...)`: the check said 176,984 bytes and Chrome 204,301. It left
out `async`, `defer` and module scripts, and it could not see a script that another
script requests, which the gate counts all the same when the request starts before
`DOMContentLoaded` ends.
It now counts a script tag whatever its attributes and refuses a module script, whose
imports no reading of the HTML shows.
For the rest it runs the shell: `tests/dom/shell-startup-requests.js` evaluates the
shell’s own scripts and inline blocks in a document double, dispatches
`DOMContentLoaded`, lets every promise chain that needs no response run, and reports
each script asked for through the asset loader, an appended element, a preload or
`import()`. The whole of `app.js` starts in that double and asks for the tree, as it
does in Chrome. Any script it reports fails the check by name.
It is not added to the total, because the session delivers no response and so cannot see
what a requested script goes on to request.

That rule is why the two shells that need a script more carry it as a tag.
The check reports both beside the budget and gates neither, since the budget is
calibrated on a folder’s page:

| Shell | Requests | Transferred | Against the 175 KB ceiling | In Chrome |
| --- | --- | --- | --- | --- |
| A folder’s page | 20 | 177,539 | 2,172 under | 20, 177,539 |
| A pull-request address, `pull-route.js` | 21 | 180,517 | 806 over | 21, 180,517 |
| A pinned revision, `git-path.js` | 21 | 179,425 | 286 under | 21, 179,425 |
| A pinned revision’s pull-request page, both | 22 | 182,403 | 2,692 over | 22, 182,403 |

A folder’s server answers a pull-request address with the page that says it serves no
pull request, which the GitHub plugin renders through the same host, so that page has
its routes too; the check renders it from the same folder server.
A pin’s shell cannot be rendered on every lint, because a pin has to be acquired, so the
check adds `server.PIN_STARTUP_SCRIPTS` to the folder’s scripts and
`tests/test_serve_pin.py` holds a real pin’s shell to that list.

What would bring the pull-request shell back under the ceiling is recorded in
[Asset Loading Tiers](../../../docs/development.md#justifying-a-tier): the rest of the
SDK’s view-phase surface is 5,957 compressed bytes of `plugin-sdk.js` that only a view’s
renderer calls.

Raising the ceiling was the other way to pass, and would have needed what the budget
file asks of any ceiling, a measurement showing the headroom is still real.
None of the growth was something the first tree needs, so none of it argued for more
headroom.

## What review found

An independent review of `2421889b` found one defect and a set of gaps.
Each is fixed in the candidate measured above, and each is recorded here with what was
run to show it.

### A plugin outside the compositor lost a documented function

The SDK’s view helpers and the line gutter had left the startup scripts as two bundles.
`loadViewComposition` fetched both.
The plugin loader, which a page without a compositor relies on, fetched only the
helpers, and `renderSourceView` reads the gutter’s module without checking for it.

A scratch third-party plugin, installed with `--plugins-dir`, calls `renderSourceView`
while its module evaluates, from its view’s `render`, and from a click handler, and
registers its view on `text`, `diff` and `pull-request`. Each page was loaded cold in
Chrome 152 on the three builds:

| Page | Branch point | `2421889b` | Candidate |
| --- | --- | --- | --- |
| `/view/<file>.py`, with and without `#L10` | all three calls draw a gutter | all three | all three |
| `/commit/<sha>` | all three | throws at module evaluation: `reading 'gutterHtml'`; the plugin does not load | all three |
| `/pull/7` | all three | throws at module evaluation; the plugin does not load | all three |
| `/pull/7/files` | all three | throws at module evaluation; the plugin does not load | all three |

The pull-request and commit pages were served from a pin, which forces the untrusted
profile, so the candidate’s result holds under that profile’s Content-Security-Policy.

The fix is one file.
Nothing uses the helpers without the gutter or the gutter without the helpers, a loader
cannot wait for half of one file, and the bundle now names the global it must leave, so
a file that arrives without defining the gutter is a failed load.
Keeping two bundles and waiting for both would also have fixed it.
A cold `/view/<file>.py#L10`, six loads per build under a load average of 60–64:

| Build | View-phase scripts requested with the first file | Transferred |
| --- | --- | --- |
| `2421889b` | 3: compositor, gutter, helpers | 17,466 |
| Candidate | 2: compositor, and gutter with helpers | 16,871 |

One request fewer on a pool of six connections that the tree and the prefetched syntax
library also use, and 595 bytes fewer.
The longest any request after the shell waited for a connection was a median 23 ms at
`2421889b` and 12 ms in the candidate; under that load the ranges overlap, and that
figure is not a result.
The commit and pull-request pages now fetch the gutter’s 7.7 KB with the helpers though
a diff draws no gutter, which is the price of the guarantee and is paid once per page.

`types.d.ts` now declares the gutter’s global optional, so a strict module that reads it
unchecked fails the type check.

### The wait cost a round trip, and a second one on a pull-request page

The loader awaited the helpers before it started any of a plugin’s assets, and `app.js`
asked for `pull-route.js` as it ran, after the shell’s scripts had arrived.
On a served pull request’s page, one cold load of three per build, as start–end in
milliseconds from navigation, under a load average of 76–84:

| Request | Branch point | `2421889b` | Candidate |
| --- | --- | --- | --- |
| `pull-route.js` | in `navigation.js` | 158–166, after the shell | 26–80, with the shell |
| `plugin-sdk-views.js` | in `plugin-sdk.js` | 175–188 | 152–178 |
| the plugin’s `styles.css` | 199–208 | 195–198 | 151–157 |
| the plugin’s `index.js` | 209–212 | 199–211 | 151–158, preloaded |
| `pull-page.js`, which it imports | 213–219 | 219–223 | 182–187 |
| `/api/plugin/github/pull` | 222–240 | 232–242 | 189–197 |
| the body’s Markdown | 246–255 | 246–250 | 201–214 |
| Sequential steps after the shell | 5 | 7 | 4 |

The same on a commit’s page, where the comparison request runs beside all of it and
decides when the diff appears:

| Request | Branch point | `2421889b` | Candidate |
| --- | --- | --- | --- |
| `plugin-sdk-views.js` | in `plugin-sdk.js` | 276–341 | 352–429 |
| the diff plugin’s `styles.css` | 364–374 | 342–361 | 351–358 |
| the diff plugin’s `index.js` | 374–394 | 362–364 | 352–360, preloaded |
| the modules it imports | from 395 | from 364 | from 430 |
| `/api/plugin/diff/comparison` | 365–552 | 276–485 | 352–586 |
| Sequential steps after the Git panel | 3 | 4 | 2 |

The order is the result: it is the same in all three loads of each build.
The times are not. They were taken under load, the three builds’ times to the page’s
content overlap on both pages, and nothing here says which build is quicker.

The loader now starts a plugin’s stylesheets and preloads its module beside the helpers,
and waits for the helpers only before it evaluates the plugin’s code.
Chrome fetches a preloaded module and not what it imports, so a plugin’s own imports
still start once its module is evaluated, as they did.
The server writes `pull-route.js` into the shell of a pull-request address.

### On-demand code that does not arrive

Each bundle can fail to load, and two of the states that followed were wrong: a
pull-request page whose routes failed showed “Select a file to preview.”, and one whose
helpers failed showed “No plugin renders pull-request pages here.”
With the request blocked in Chrome, the candidate shows:

| Blocked | Page | The pane says |
| --- | --- | --- |
| `plugin-sdk-views.js` | `/pull/7` | Could not load the pull-request page. Refresh the page to try again. |
| `pull-route.js` | `/pull/7` | Could not load the pull-request page. Refresh the page to try again. |
| `plugin-sdk-views.js` | `/commit/<sha>` | the commit, and “Could not load this commit’s diff.” |
| `plugin-sdk-views.js` | `/view/<file>.py` | Could not open this file. Failed to load asset: … |

The plugin loader rejects when the helpers cannot be fetched, with no plugin code run
and nothing remembered, so the next call tries again.
`ensureKindAssets` never rejected before; the commit page’s load of the diff plugin left
that rejection unhandled until it took it.
A pin’s page whose GitPath codec did not arrive stops and says the page did not load.
The alternative was a tree of wires for names.

### Tests that read the source

Several tests held this change’s wiring by asserting on the text of `app.js`,
`plugin-sdk.js`, `probe.js` and the Makefile.
They now run it. `tests/dom/plugin-view-helpers-session.js` loads a third-party plugin
through the production asset loader and SDK with no compositor.
`tests/dom/preview-pane-state-session.js` runs the production loader, SDK and
`loadViewComposition` against the production files, with a step for the cold anchored
address and one for each refused bundle.
`tests/dom/shell-startup-requests.js` starts the whole shell.
Each was run against the change it exists to catch, and failed: the wait removed, the
handler removed, the flag set after the event, the import hoisted.

## What this does not say

It does not say v0.12 starts as fast as v0.11.0. It does 3% more work to start, and the
wall-clock pairs that would say what a reader notices have not been taken.

It does not clear the release.
The release comparison is the visible-Chrome captures and the pair comparison on
project-10, and this round took neither.
The startup-script metric is the one release gate it did establish, and it took that
headless on a smaller tree, for the reasons given above.

It does not say a pin’s first paint is settled.
The freshness row and the selector arrive after the tree and shift it, before and after.

One thing the probe saw that is not this change’s: a Markdown view shifts its layout by
0.037 in about one load in twenty-four on a quiet machine, in v0.11.0, the branch point
and the candidate alike, and more often under load.
Code blocks and the paragraphs after them move.
It is recorded here so that the next reader of a layout-shift number does not attribute
it to whatever changed last.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
