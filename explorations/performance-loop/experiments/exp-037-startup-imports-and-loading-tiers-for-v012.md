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
    candidate: the 2421889b wheel; f9d88f50, the commit it was branched from, is the second condition
    record: >-
      startup_pairs.py over installed console scripts from three environments created
      outside every work tree, 12 back-to-back pairs per candidate, control then
      candidate; tier-probe.mjs for the browser half, and run.py serve and capture, the
      gate's own harness, for the startup-script metric. Output stayed under .bench/ and
      is summarized here
  results:
    - metric: cli_show_instr_millions
      control_median: 7467.7
      candidate_median: 7733.6
      control_range: [7387.3, 7546.4]
      candidate_range: [7697.3, 7783.9]
      change_pct: 3.6
      overlapping: false
    - metric: cli_api_tree_instr_millions
      control_median: 7503.0
      candidate_median: 7746.7
      control_range: [7450.4, 7596.5]
      candidate_range: [7690.6, 7821.4]
      change_pct: 3.2
      overlapping: false
    - metric: cli_version_instr_millions
      control_median: 5511.4
      candidate_median: 5484.1
      control_range: [5428.2, 5592.5]
      candidate_range: [5436.1, 5572.1]
      change_pct: -0.5
      overlapping: true
    - metric: serve_first_api_instr_millions
      control_median: 9131.5
      candidate_median: 9380.3
      control_range: [9090.5, 9248.0]
      candidate_range: [9303.9, 9518.0]
      change_pct: 2.7
      overlapping: false
    - metric: cli_doctor_instr_millions
      control_median: 5759.8
      candidate_median: 8879.3
      control_range: [5706.4, 5850.3]
      candidate_range: [8828.8, 8980.3]
      change_pct: 54.2
      overlapping: false
    - metric: shell_instr_millions
      control_median: 106.9
      candidate_median: 107.0
      control_range: [104.6, 108.9]
      candidate_range: [106.0, 110.7]
      change_pct: 0.0
      overlapping: true
    - metric: startup_script_transfer_bytes
      control_median: 175352
      candidate_median: 176984
      control_range: [175352, 175352]
      candidate_range: [176984, 176984]
      change_pct: 0.9
      overlapping: false
    - metric: startup_script_requests
      control_median: 20
      candidate_median: 20
      control_range: [20, 20]
      candidate_range: [20, 20]
      change_pct: 0.0
      overlapping: true
  complexity:
    lines_changed: 2411
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
        `window.metabrowser` until the first view. The shell waits for them with the
        view compositor and the plugin loader waits for them before it loads a plugin;
        code that runs before either, and is no plugin, would find them missing.
      - >-
        The syntax service used to learn that the optional assets had settled from an
        event it could now load after. The prefetch chain leaves a flag behind the
        event; a second late listener would need to read it too.
      - >-
        A startup script that outgrows the budget now fails `make lint-check`. That is
        the point, and it means a change to app.js can fail for its size alone.
    notes: >-
      Most of the changed lines are code moved between files, not written. Two
      instruments are new and committed, startup_pairs.py and tier-probe.mjs, because
      the loop had neither a start-up measurement nor a tier one, and one check,
      devtools/check_startup_scripts.py.
  verdict:
    decision: accepted
    primary_metric: cli_show_instr_millions
    reason: >-
      Judged on instructions retired, because the machine never became quiet. Against
      v0.11.0 the branch point did 1.068x the work for --show, 1.063x for --api, 1.049x
      for --version and 1.053x from server spawn to the first /api answer, above 1.05x
      in every one of 12 adjacent pairs for the first two. The candidate does 1.038x,
      1.034x, 0.998x and 1.025x, and no pair of any of the four exceeded 1.05x. Startup
      JavaScript went from 187 KB, over the 175 KB gate, to 173 KB, 1.009x the release's
      transferred bytes, and a check now holds it there. A Source view still appeared
      with its gutter in every load, and a served mirror's and a served pull request's
      pages read the same before and after. Accepted as a change. It is not a release
      clearance: wall time was not resolved, --doctor does 1.54x the work by design, and
      no visible-Chrome capture was taken.
    commit: 2421889b
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
`f9d88f50`, which is the head of the v0.12 stack this change was cut from; and the
candidate `2421889b`. Each `metab --version` was asserted against its own wheel before a
measurement was taken.

`startup_pairs.py` ran 12 rounds per candidate.
A round is the control and then one candidate, back to back, so each ratio is between
two measurements taken next to each other.
Per build a round runs `--show README.md`, `--api /api/tree`, `--version` and `--doctor`
as one-shot commands, spawns a server and times it to its first `/api/routes` answer,
then fetches the shell once cold and nine times warm.

Start-up work is reported in instructions retired.
The machine was carrying other work throughout: across the series the load average on
its ten cores ran from 11 to 193, and it was 52–108 during the one tabulated below.
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
| `--show README.md` | 7,463 | 7,941 | 1.068 (1.058–1.076) | 12/12 | 7,734 | 1.038 (1.026–1.047) | 0/12 |
| `--api /api/tree` | 7,497 | 7,975 | 1.063 (1.053–1.082) | 12/12 | 7,747 | 1.034 (1.012–1.040) | 0/12 |
| `--version` | 5,492 | 5,761 | 1.049 (1.045–1.064) | 5/12 | 5,484 | 0.998 (0.973–1.008) | 0/12 |
| Server spawn to first `/api` | 9,126 | 9,615 | 1.053 (1.042–1.072) | 8/12 | 9,380 | 1.025 (1.013–1.038) | 0/12 |
| `--doctor` | 5,752 | 8,999 | 1.568 (1.554–1.578) | 12/12 | 8,879 | 1.542 (1.511–1.558) | 12/12 |
| Shell `/`, first request | 123.5 | 123.6 | 0.976 (0.793–1.074) | 1/12 | 124.0 | 1.007 (0.917–1.147) | 4/12 |
| Shell `/`, warm | 106.0 | 107.2 | 1.015 (0.991–1.049) | 0/12 | 107.0 | 1.006 (0.986–1.026) | 0/12 |

Peak memory footprint of the one-shot commands moved the same way: `--show` 1.037x to
1.012x, `--api` 1.035x to 1.012x, `--version` 1.023x to 0.993x, and `--doctor` 1.174x to
1.143x.

No pair of the candidate exceeds 1.1x on any metric but `--doctor` and the first shell
request, whose 100M instructions swing by a tenth from run to run in every build.
On the four start-up metrics no pair of 48 exceeds 1.05x.

The series was taken six more times as the change grew, three with 9 pairs and three
with 20, under load averages from 11 to 193. The candidate’s medians stayed within 0.005
of these each time: `--show` at 1.035–1.039x, `--api` at 1.030–1.036x, `--version` at
0.994–0.997x, and the server at 1.026–1.029x. In one 20-pair series a single `--show`
pair reached 1.051x, beside two at 1.0495x and seventeen between 1.031x and 1.043x.

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
From `DOMContentLoaded` to the painted view the medians were 254 ms at the branch point
and 249 ms in the candidate on the anchored link, and 161 ms and 169 ms on the plain
one, with pair ratios from 0.38 to 1.71 under a load average of 60–71. The two disagree
in direction, which is what noise looks like.
A file view fetches the same code in either tier, 330,607 bytes of script at the branch
point and 331,085 in the candidate: the modules moved, they were not removed.

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

They are now `plugin-sdk-views.js`, the `sdk-views` on-demand bundle.
`loadViewComposition` fetches it beside the compositor and the gutter, the three
requests starting within 0.2 ms of one another, and `loadPluginsForKind` waits for it
before it loads a plugin.
The second wait is the one that matters for a page that mounts a plugin without the
compositor, as the pull-request page does: Chrome shows that page fetching the helpers
on that path. So every helper is on `window.metabrowser` before any plugin module
evaluates, and a plugin sees the SDK it always did.

The syntax service needed one change to move.
It waits for a grammar until the optional assets have settled, and it learned that they
had from an event. Loaded with the first view, it can arrive after the event, and would
then wait forever for a grammar that was never coming.
The prefetch chain now sets `METABROWSER_OPTIONAL_ASSETS_SETTLED` before it dispatches
the event, and the service reads it when it loads.
The syntax session checks a service loaded after settlement, and fails with the flag
unread. A 27 KB Python file highlights the same 888 tokens in Chrome before and after.

### The pull-request routes

`pullHref`, `parsePull`, `pullHistoryAction` and `createPullPageHost` were part of
`navigation.js`, and the shell created the page’s host as it loaded: 1,818 of that
script’s 13,265 compressed bytes, for an address space only a served pull request has.

They are now `pull-route.js`, the `pull-route` on-demand bundle, and the host is created
when an address under `/pull/` is opened.
A page that loads at such an address starts the fetch as `app.js` runs, beside the rest
of the shell, so the address is not applied behind a request that began late: in Chrome
the request starts 7 ms before `DOMContentLoaded` on a served pull request’s page.
A history landing on a page’s address with no host yet loads it and then applies the
landing, unless history has moved on.
Any other address never asks for the module.

A served pull request’s page was driven in Chrome on both builds through seven steps:
the landing, a click on Files changed, back, forward, a load at `/pull/7/files`, a file
opened from the tree, and back to the page.
The address, the active tab, the page’s text and the count of changed files were the
same at every step, with no page error.
A folder at `/pull/7` shows what it showed, the GitHub plugin’s “This server serves no
pull request”, and `/pull/x` is still the server’s 400.

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
Six cold loads per build of a served `file://` mirror:

|  | Branch point | Candidate |
| --- | --- | --- |
| Freshness row | “Fetched just now”, 6/6 | “Fetched just now”, 6/6 |
| Ref selector | “Branch: topic”, 6/6 | “Branch: topic”, 6/6 |
| Row and selector after the first tree row | 35–221 ms | 36–328 ms |
| Layout shifts | one of 0.0057 in 6/6, as they arrive | one of 0.0055–0.0057 in 6/6, as they arrive |
| File header on a file’s address | the decoded name | the decoded name |
| Page errors | none | none |
| Startup scripts on the pin’s shell | 21, 191,862 bytes | 21, 178,870 bytes |

The row and the selector do arrive after the first rows, and push the tree down by a row
when they do. That shift is in the branch point in every load.
It is the stack’s own tier decision for those two, not this change’s, and it is the one
thing here a reader of a pin’s page sees arrive.
The delay ranges overlap and were taken under a load average of 63–65, so they say
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
| Candidate | 20 | 176,984 | 595,187 | 173 KB | 20, 173 KB | 20, 173 KB, 176,984 |

The stack had crossed the gate by 12 KB. The candidate is 2 KB under it and 1.009x the
release’s transferred bytes; the margin to the point where the metric rounds to 176 is
2,727 bytes.

Each move’s share, as the shell’s transferred bytes after it:

| Move | Startup bytes after |
| --- | --- |
| Line gutter, with the view compositor | 184,320 |
| SDK view helpers, with the view compositor | 181,124 |
| Pull-request routes, on demand | 179,909 |
| Syntax service, with the view helpers | 177,832 |
| GitPath codec, on a pin’s shell only | 176,984 |

What the candidate still carries over the release is 1,632 bytes: `app.js` is 4,235
larger, `navigation.js` 586 larger, and `plugin-sdk.js` 3,189 smaller.
Some of the `app.js` growth is this change’s own, the code that creates the page host on
demand and waits for the gutter module.

### Why nobody saw it, and the check

The gate is applied by `run.py compare` to browser captures, which no ordinary change
takes, and `make verify` did not know about it.

`devtools/check_startup_scripts.py` now applies both ceilings on every
`make lint-check`. It reads the blocking script tags from the shell `server.index`
renders, compresses each file as the application’s gzip middleware does, and adds 300
bytes. That is the browser’s number and not an estimate of it: Chrome reports
`transferSize` as the encoded body plus a fixed 300 bytes, whatever the headers’ real
length, and the application’s compressed body is what a one-shot gzip at the
middleware’s level produces.
The last column above is the check run against each of the four wheels, and it matches
the browser’s count to the byte on all four.
Its limits are read from the budget file, and its tests hold the script list, the
equality with the body the running application sends, and the probe’s rounding.

What the check cannot see is a script another script requests before `DOMContentLoaded`.
A folder’s shell has none.
A page that loads at a pull-request address starts `pull-route.js` on purpose, and a
pin’s shell carries `git-path.js`; those shells are 181,848 and 178,870 bytes, and
neither is the directory shell the budget is calibrated on.

Raising the ceiling was the other way to pass, and would have needed what the budget
file asks of any ceiling, a measurement showing the headroom is still real.
None of the growth was something the first tree needs, so none of it argued for more
headroom.

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
