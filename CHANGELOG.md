# Changelog

All notable changes to Metabrowser are documented here.

## Unreleased

Features:

- Git history pages now come from a bounded server session that advances one ordered Git
  walk on demand and replays visited pages by indexed seek.
  Opaque page cursors replace progressively expensive skip offsets; ref movement,
  expiry, eviction, and storage exhaustion remain explicit recovery states rather than
  appearing as the end of history.

- The Git panel now stores decoded history pages in a bounded LRU and mounts only a
  fixed-height row window with measured overscan.
  Versioned server checkpoints make evicted pages independently replayable without
  retaining expanded rows or a complete ordinal map.
  Continuous paging reaches Git’s real end instead of stopping after 500 commits;
  spacers preserve logical scroll geometry, and long histories rebase before the browser
  height clamp while keeping selection and logical focus independent of row mounting.

- The Git tab opens with a header tally — the total commits in the panel’s scope and the
  age of the repository’s first commit, e.g. `142 commits (first 1mo ago)` — styled like
  the file tree’s summary row and loaded the same way: off the render path, after the
  first page of history paints.

Fixes:

- A history row can no longer render with an invisible commit message.
  The subject used to absorb all of a row’s flex shrinkage and could collapse to zero
  width — most often on merge rows, whose converging lanes widen the graph gutter —
  reading as a commit with no message.
  The subject now keeps a readable floor and ref chips clip beyond it.

- The commit page’s abbreviated revision no longer reads larger than the author, age,
  and stat text beside it: monospace at body size renders optically larger than the sans
  text, so the hash now sits one step down the size ramp.

- A Git history page at the route’s maximum `limit` no longer fails with HTTP 500. The
  measured parser budget now scales with the requested page size instead of holding
  every page to the default page’s fixed budget.

- Keeping a repository’s history open in three or more tabs no longer makes the tabs
  evict each other’s live Git walks and thrash through expired-session recovery.
  The concurrent-walk bound now matches the eight-session registry bound.

- Recovering an idle-expired history session replays a bounded prefix — at most the
  page-cache depth — instead of one request per 250 rows back to the prior position, and
  a recovery interrupted by further ref movement no longer recurses without a depth
  bound.

- Scrolling back to a distant, previously visited part of a long history now replays
  each needed page in one request.
  The panel retains every visited page’s replay cursor, so reaching page 2,000 no longer
  steps through 2,000 intermediate requests whose results were evicted unseen.

- Leaving the Git panel restores the shared tree scroller’s focusability instead of
  leaving a stray `tabindex` on a node other panels keep using.

- Ctrl-C stops the server on the first press and reports exit 130 whatever the timing of
  any that follow. A repeat interrupt arriving while the process exited used to land on
  Python’s default handler and print an `Exception ignored on threading shutdown`
  traceback, or kill the process outright for exit `-2`. The first interrupt now prints
  `Stopping Metabrowser.` so the press is visibly registered rather than reading as a
  hang.

- Serving a directory that is not a Git repository no longer repeats
  `git rev-parse --show-toplevel exited 128` every few seconds, and opening the Git tab
  no longer logs one line per history ref that does not resolve.
  These are questions the browser asks git by exit code, so they are DEBUG detail; git
  failures that are failures still log at WARNING, now including git’s own message.

- The inventory boot walk reports its summary only when the result is worth reading — a
  truncated index, or a walk slow enough to have been noticed.
  `--log-level debug` still shows every completion.

## 0.8.0

Features:

- Diff views now open in Split by default, retain a remembered Unified choice, and apply
  the same bounded syntax highlighting as ordinary Source views.
  Similar replacements emphasize changed words or characters; neighboring wholly changed
  lines join the refined hierarchy only when their contiguous run contains a meaningful
  partial replacement.
  Independent additions, deletions, paragraphs, and files retain the ordinary whole-line
  treatment.

- Large diffs keep collapsed content out of the DOM and materialize expanded rows in
  cancellable batches.
  The browser performance gate rejects hidden rows mounted beneath collapsed folds and
  attributes decode, model, projection, and attachment work separately.

- File and Git navigation retain the prior useful preview at full opacity until the
  selected renderer reaches painted readiness, then install the replacement atomically.
  File navigation joins or cancels matching row-intent prefetches.
  Git navigation keeps at most one pointer-intent comparison, cancels obsolete work,
  hydrates deferred file sections with bounded concurrency, and preserves exact row,
  route, and rendered-view convergence.

- Git history uses the file tree’s one-Tab-stop Arrow-key navigation contract.
  Commit details and pointer tooltips share subject, author, revision, refs, age, exact
  modified/added/deleted file totals, and line totals.
  Details preserve multiline commit descriptions as standard-size sans-serif prose,
  while pointer tooltips remain compact and pointer-only.

- Raw Source tabs highlight every extension backed by the shipped Highlight.js registry.
  Large syntax-known files retain highlighting for the measured prefix and fall back
  uniformly when the loaded content crosses the configured bound.

Fixes:

- File Overview no longer shows a passive “Show ignored” instruction when the selected
  scope contains only ignored files.
  The existing checkbox remains the action.

- Folders discovered while the Files panel is inactive retain their disclosure state
  when the reader returns from a Git comparison during an active inventory scan.

- Commit summaries keep the revision at the standard interface size and place file and
  line totals on dedicated rows with explicit units.

- Full navigation-tally passes yield often enough on slower hosts to preserve the
  deterministic 50 ms event-loop heartbeat guard.

Plugin API:

- A view handle may expose an optional `ready: Promise<void>` for its initial useful
  connected render. The shell waits for it before the atomic retained-navigation handoff;
  existing handles without `ready` retain their behavior.

- `metabrowser.highlightSyntax`, `metabrowser.renderSourceView`,
  `metabrowser.langForExtension`, and `metabrowser.langForPath` expose the shell’s
  bounded syntax and Source rendering contracts to plugins.
  `PLUGIN_SDK_VERSION` remains `0.5`.

Development:

- The performance loop now gates stateful navigation from trusted input through painted
  readiness, audits forced layout, checks blank-frame continuity and exact convergence,
  and fails on deferred-diff request fanout, obsolete successful requests, or multiple
  mounted comparisons.

Validation:

- Five interleaved backend pairs against v0.7.1 return identical ordered rows and
  tallies on an unchanged 148,581-file corpus; first-row, index-completion, and peak-RSS
  ranges overlap.

- All three visible-browser candidate profiles pass every hard correctness and
  responsiveness gate with no Long Task, blocking time, failed fetch, rendered error,
  page exception, or collapsed row mounted beneath a closed fold.
  One LCP tail remains in the record but does not separate the candidate interval from
  v0.7.1 or cross a hard release gate.

## 0.7.1

Fixes:

- Opening the first Git commit in a fresh browser session loads the diff plugin on
  demand before mounting the commit view, while a completed stale request cannot replace
  a newer selection.

- The gear trigger no longer shows a redundant native tooltip over the open menu, and
  the menu reports the exact running build from `metab --version`.

## 0.7.0

Performance and scale:

- Large-directory startup moved built-in plugin assets, search, keyboard Help, and Git
  controls off the eager path.
  Server-carried first rows paint before unrelated assets, while inventory and tally
  work yield in bounded groups.

- The browser performance loop gained reproducible installed-build selection, headed
  Chrome capture, and hard responsiveness, readiness, network, error, and exception
  gates.

Plugin API:

- `PLUGIN_SDK_VERSION` became `0.5` for selected-kind asset loading.
  Browser-console tools moved under `window.metabrowser`, and `/api/tree` separated row
  delivery from tally computation.

## 0.6.0

File-type colors:

- Every file-type family now has its own color, taken from GitHub where GitHub names
  one. There were twelve colors for fifty-six families, handed out by hashing a family
  name to a starting slot and probing forward for a free one, per folder — so CSS and
  Markdown came out nearly the same color, a family’s color depended on which other
  families happened to be visible beside it, and the same language could be two colors
  in two folders.

- The type registry declares a `hue` per family, with the `linguist` language and its
  upstream color recorded beside it.
  Thirty-five families carry GitHub’s hue exactly, including where two of GitHub’s own
  colors are close together; the twenty-one GitHub names no color for take a hue whose
  painted color clears every other family by a perceptual distance, in both themes.
  `devtools/check_file_type_colors.py` holds both rules and runs in `make lint`, and
  reports the collisions it keeps because they are GitHub’s own.

- Lightness and chroma are the theme’s, stated as a narrow band rather than as one pair,
  and a family’s place inside it is its rank among the upstream colors GitHub gave the
  other families. Hue alone could not carry fifty-six families: they average 6.4 degrees
  of spacing, at or under what the eye resolves at a fixed tone, and GitHub’s own colors
  are separated mostly by the two dimensions a fixed tone throws away.
  Html and svelte came out `#dd5230` against `#dd5232`, and ruby and yaml one step apart
  in blue. Taking all three attributes moves the closest pair in the palette from an
  Oklab delta-E of 0.0020 to 0.0156, and pairs too close to tell apart from 41 to 9. The
  band is +-0.06 of lightness, which is the cost side of the trade: a stacked-bar
  segment can now read slightly heavier than a same-size neighbour, where one flat tone
  guaranteed it could not.
  Widening it buys almost nothing, so it stays narrow.
  The server ships finished colors for both themes rather than hues composed in CSS,
  because a browser handed an out-of-gamut `oklch()` clips it — moving hue by as much as
  nine degrees, more than the separation the palette is built on, and because a family’s
  rank is only knowable where the whole registry is in hand.

- Markdown does not take GitHub’s placement.
  GitHub puts it at hue 261.42, inside a run of seven families between Python’s 246.50
  and PHP’s 272.03, where it read as Python’s blue — and Markdown is the family this app
  shows most. It moves to 276.0 and below the lightness band, painting `#4c50ca` against
  Python’s `#0385d6` rather than `#3370e3`. That takes the pair from an Oklab delta-E of
  0.0606 to 0.1348, and Markdown’s distance to its nearest neighbour of any kind from
  0.0149 to 0.0725.

- A family may now declare a deviation: prose recording why it does not paint where its
  upstream colour puts it, and optionally a `lightness_rank` of its own that may sit
  outside the band. `linguist` and `linguist_color` stay, so provenance survives, and a
  deviating family is held to the same perceptual floor a colour chosen from a free gap
  is. A `lightness_rank` without a `deviation` is refused — leaving the band is the one
  change that must never read as a typo.
  `devtools/check_file_type_colors.py` lists the deviations in its report.

- The registry schema version is now `3` and its projection is `file-type-registry-v3`,
  carrying `hue`, `linguist`, and `linguist_color` on each family.
  `linguist_color` is in the projection because it is no longer provenance alone: it is
  what a consumer reads a family’s tone rank off, so a consumer that only had `hue`
  could not reproduce the palette.
  `--mb-distribution-category-1` through `-12`, the `.mb-distribution-slot-*` classes,
  and `DISTRIBUTION_PALETTE_SLOTS` are gone; `.mb-distribution-mark` and
  `METABROWSER_SETTINGS.DISTRIBUTION_COLORS` replace them.
  The File Rollup Format rollup and conformance schemas no longer pin the registry
  schema version, which the format has always said versions independently.

Folder Overview:

- A README reads at the same measure in Overview as it does opened on its own, at every
  breakpoint. Three things were out of step, each enough on its own: Overview’s
  breakpoints were measured against its own host rather than the container KPress names,
  so the two crossed 75rem about 25px apart and the text jumped in between; the wide
  column was the reading measure rather than KPress’s content track, so the prose kept
  insets sized for a track it was no longer in and read at 43rem against 48rem; and the
  narrow inset did not match the article padding it replaced.

- The breakdown’s icon is on the **family** now, one per family and in that family’s
  colour, with its extensions listed bare beneath it.
  It used to be the other way round — an icon on every extension and none on the family
  — and those icons disagreed with each other, because they resolved through a separate
  extension table that knows nothing about families: `.js` matched an entry and `.mjs`,
  `.cjs` and `.jsx` did not.

- Segments of a tally bar are separated by a hairline of the page ground, so two
  families of similar hue read as two rather than as one wide band.
  It is drawn inside the segment rather than as a gap, because the widths are
  percentages that sum to 100 and anything occupying layout would push the last segment
  past the end of the track.

- **`PLUGIN_SDK_VERSION` is `0.4`.** An external plugin must set `sdk_version = "0.4"`
  and update its tooltip call sites: `mb.tooltip.show` takes the anchor element rather
  than a `MouseEvent`, and `mb.tooltip.move` is gone.
  `mb.fileTypes.schemaVersion` and `registryIdentity.schemaVersion` are `3`, and a
  plugin comparing a rollup’s registry identity against them needs no other change.

- Tooltips are placed relative to the element they annotate and hold still once shown.
  They used to follow the pointer, which jitters while you are trying to read one and —
  worse, in a stacked bar or a treemap where the annotated things are adjacent and small
  — says nothing about which one the tooltip is about.
  Moving onto a different element dismisses the old tooltip and opens a new one; moving
  within one changes nothing.
  `mb.tooltip.show` now takes the anchor element and `mb.tooltip.move` is gone.

- Hovering a segment of a tally bar now recedes the rest of the track, so the segment
  the tooltip describes is findable.
  The shared brightness filter was doing the whole job on a track eight pixels tall,
  where it read as nothing happening.

- Treemap puts Files/Bytes and Show ignored in one row above the bars, the way Overview
  does. They used to sit apart — the measure above the tally bars, the gitignore switch
  below them — so two choices about the same numbers were in two places.

- Files and File Breakdown are one **File Overview** section.
  They answer the same question at two resolutions, and splitting them meant collapsing
  or scrolling past the first to reach the second — and, worse, splitting one set of
  controls: the Files/Bytes measure sat in one section and Show ignored in the other, so
  each silently moved the other’s numbers.
  Both now sit together in one control row above both bodies.

- A **Total** row joins Files and Ignored.
  The type distribution counts against the whole directory whenever Show ignored is on,
  so without a Total track none of its percentages corresponded to any bar on screen.
  Now one of the three always does: Total while Show ignored is on, Files while it is
  off.

- Show ignored no longer reorders the tally tracks.
  It used to decide their shared segment order, so toggling it silently rearranged every
  track — including Ignored, whose contents the checkbox has nothing to do with.
  The order now comes from the combined population, and `buildFolderTotalsComposition`
  no longer accepts the flag at all, so the tally rows cannot respond to it.

Navigation and the file header:

- The Metabrowser wordmark moved out of the navigation column and became the title of
  the gear menu, so the gear reads as the product’s menu and the column’s scarcest
  resource — width — goes to the path instead of to a line that never changes.

- The navigation heading shows the folder’s **name**; the main view shows the whole
  address, as one control per component.
  Every segment navigates, including the last: on a file it re-opens what is already
  open, so a run of links has no dead segment in the middle of it.

- A served root under your home directory renders as `~/wrk/project` rather than
  spelling the home directory out in full on every page.
  Display only — the API still reports the absolute root — and it falls through to the
  absolute path where the substitution would be a guess rather than a fact.

- The dimmed root prefix truncates from the **start**, so `…/wrk/github/project` keeps
  the part nearest what you are looking at rather than the part that is identical on
  every page. It reads at the same weight as the rest of the address; grey already says
  “this is context”.

- The two headers either side of the divider are one structure: path row, hairline, tabs
  row, hairline, each row the same height as its opposite number.
  The navigation header had no bottom rule at all, and the rows differed by half a
  pixel, so the line stopped at the divider and picked up again on the other side.

Navigation filters:

- A filtered navigation tree now shows only folders that contain a match, and each
  folder’s count, size, and age are rolled up from the matches inside it.
  Filtering had been a pass over the rows the browser happened to have mounted, so every
  folder whose children had not loaded was kept — and then disappeared the moment
  expanding it proved there was nothing inside.
  `/api/tree` resolves the filter itself (`types`, `recency`, `min_size`,
  `include_ignored`) over the whole index and returns the pruned tree with filtered
  aggregates, plus a `filtered` envelope block carrying the true match count.
  The “N collapsed folders may contain additional matches” note is gone with the problem
  it described.

- Filtering is answerable from a terminal: `metab ROOT --walk --type .md`, `--age`,
  `--min-size`, and `--no-ignored` print which folders survive and what each one rolls
  up to, in every walk output format.
  `metab ROOT --check-api` gained a filtered step.

- A filter can exclude the folder you are standing in — reached from a breadcrumb, a
  link, or a pasted URL — and the tree then has no row to select.
  The panel names it (“docs/project is outside this filter.”) instead of going silently
  unselected. Deliberately a line rather than a pinned row: keeping the selection in a
  filtered tree means refetching as you navigate, and a refetch repaints the panel and
  collapses every folder you had open.

- Navigation rows span the full width of the panel at every depth.
  Indentation moved into the row’s own left padding, so the hover background, the
  selection background, and the accent bar are one constant shape instead of a box that
  narrowed and shifted right with each level of nesting.

Routing:

- Commits are addressable: selecting one in the Git panel puts it at `/commit/<rev>`,
  and opening that URL restores the panel and the commit.
  The browser URL grammar now states the whole rule — one route per address space, with
  a uniform `<container address>/<inner path>` shape after it — so a patch file
  (`/view/changes.patch/src/app.py`) and a commit (`/commit/abc123/src/app.py`) read
  identically. `/compare/<base>..<head>` is specified and not yet built.

Design system:

- Progress is a box, never prose: a diff whose file has not been fetched shows the
  standard delayed spinner and loads itself, instead of stating that it has not loaded.
  Loads that fail — or that overrun their expected time — always reach the console with
  full detail (what was requested, which hook, elapsed milliseconds, the error).

- **One tooltip, and it is Metabrowser’s own.** The navigation heading used to show two
  at once — the app’s, anchored and styled, and the browser’s, from a `title` attribute.
  Every tooltip the app owns now goes through its own pointer-hover controller; keyboard
  focus uses the control’s accessible name and dismisses tooltip presentation.
  `devtools/check_tooltips.py` fails the build on a `title` attribute anywhere the app
  owns the markup, because a rule with no check is how this one was lost.
  `aria-label` is untouched: it is the accessible name, not a tooltip.

- **A hover is drawn on the thing under the pointer, and on nothing else.** Hovering one
  segment of a bar used to dim every other segment, which picks one thing out by
  restyling fifty — and a dimmed neighbour reads as excluded, which a hover is not
  saying. The hovered segment now grows and lifts its own colour, and its neighbours do
  not change. It grows on the axis that carries no data: on a horizontal bar the width is
  the value, so the segment thickens instead, centred on the bar, on a curve that
  overshoots and settles.

- Every expand/collapse now travels with one standard, short motion: bodies animate
  height on the same 150ms the chevrons rotate with — tree folders, patch containers,
  diff file sections, fold expanders, and folder Overview panels alike — and collapsed
  content leaves the tab order.
  Reduced-motion keeps the state change and drops the travel.

- The green/red `+N −N` change stats are always bold, in the diff view and the commit
  view alike.

- Branch and tag chips are their own vocabulary: bold at their small size, square-ish
  corners so a ref never reads as a filter chip; the `HEAD` chip keeps a hairline ring.

- The commit graph is denser: lanes at a 9px pitch with smaller dots, so multi-branch
  history spends its width on subjects, not spacing.

Git history:

- **Metabrowser browses Git history.** Serving a repository root adds a Git panel beside
  the file tree: the commit graph with one lane per line of development, subjects,
  authors, ages, and branch and tag chips on the commits they point at.
  Selecting a commit opens it, and history pages as you reach the end of the loaded
  rows.

- A read-only Git API backs it — `/api/git/repo`, `/api/git/refs`, `/api/git/log`, and
  `/api/git/commit/<revision>`. Nothing in it writes, and every cost is bounded: each
  `git` subprocess has a timeout and an output cap (`GIT_SUBPROCESS_TIMEOUT_S`,
  `GIT_SUBPROCESS_MAX_BYTES`), history is cursor-paged with a bound on how far back a
  cursor may seek (`GIT_LOG_MAX_SKIP`), the panel retains a bounded number of rows
  (`GIT_HISTORY_MAX_ROWS`), and a commit touching more than `GIT_COMMIT_MAX_FILES` files
  reports itself truncated rather than being silently shortened.

- The panel appears only when the served folder is itself a repository root, and every
  other case is a stated answer rather than a broken tab: `git` missing from `PATH`, a
  folder that is not a repository, a repository Git refuses to read, and a discovery
  call that times out are distinct, and an unborn or detached `HEAD` is carried as its
  own state rather than as an error.

Diff rendering:

- Diffs use the same syntax foregrounds and Highlight.js grammars as regular source
  views while their context, addition, and deletion rows keep their own backgrounds.
  Old and new hunk streams are highlighted independently, so deleted text cannot alter
  the lexical state of added text; plain text remains the bounded fallback.
- An always-visible Unified/Split control reprojects the loaded comparison immediately
  and remembers the choice without fetching or highlighting again.
  Split view aligns changed runs by position, preserves side-specific line numbers and
  token state, keeps full-width hunk and fold controls, and scrolls horizontally when
  both practical code-column minimums do not fit.
- Plugin render contexts gain a `revision` field: a surface may ask a registered view
  for a Git comparison rather than a file, which is how the history view mounts the diff
  view. Plugin-visible via the SDK’s `MetabrowserRenderContext` type.
- **Long runs of changed lines fold behind an expander**, so one large rewrite cannot
  bury the changes around it.
  A contiguous run longer than 40 lines shows its first 20 and offers the rest behind a
  control stating exactly how many it holds; folding is per run, not per file, so
  ordinary edits beside a rewrite stay visible.
  Measured on this project’s own 65-file pull request: 42 runs fold and 83% of the
  changed lines start hidden, while most real changes are untouched.
  `DIFF_FOLD_THRESHOLD` sets the bound; 0 disables folding.
- **The Git history view shows real diffs.** Selecting a commit renders its first-parent
  comparison through the diff view — the same renderer, model, and validation a patch
  file uses — instead of a file list alone.
  The commit header keeps only what that view cannot show: files outside the served
  folder, and a statement when a very large commit’s diff is bounded.
- **Patch and diff files expand in the navigation tree.** A `.patch` or `.diff` file
  keeps its own row and views and gains a chevron: expanding lists the files it changes,
  each with its change indicator, and selecting one opens just that file’s diff at its
  own URL (`/view/changes.patch/src/app.py`). Keyboard navigation, filtering, and
  selection work exactly as they do for folders, because disclosure is now a capability
  any row can declare rather than something only directories have.
  Plugins declare it in one manifest line, so archives and pull-request mirrors get the
  same affordance without new tree machinery.
- `.patch` and `.diff` files now open as rendered diffs: a change summary, per-file
  sections with GitHub-style indicators (renames with the old path, mode changes, type
  changes such as file to symlink, binary), and numbered unified hunks.
  Each file sits under a sticky bar: the nav tree’s own chevron, the filename with its
  green/red `+N −N` stat pair right beside it, change notes, and the standard copy-path
  control revealed on hover.
  The bar is a row in the design-system sense — tree-row height, the shared hover color,
  one activation surface (clicking anywhere toggles), a single border when collapsed —
  and these agreements are now test-enforced.
  Sections start expanded, and collapsing keeps the rows mounted.
  Line totals stay exact when a change set contains binaries: binary changes contribute
  no lines (git’s own semantics), so a patch with images no longer shows
  `+? −? (estimated)`, and the change-set summary reads at regular UI size instead of
  small print. Every unavailable state is a labeled explanation rather than an empty box,
  and input that is not a diff says so instead of claiming no changes.
- New `metab --diff SPEC` mode: `BASE..TARGET`, a single revision (compared against its
  first parent), or a `.patch`/`.diff` file.
  `--format json` emits the full change-set document, `--diff-patch PATH` prints one
  file’s hunks, and `--diff-check` applies the change set to the base tree and verifies
  it reproduces the target tree exactly.
- Both are built on File Diff Format v1, a documented change-set model with a JSON
  Schema, a conformance corpus run by the Python and browser implementations alike, and
  an apply oracle that proves a produced document captures everything — verified
  byte-for-byte against git’s own trees, including renames, chmods, symlink type
  changes, binaries, and missing trailing newlines.

Large directories:

- Opening a large folder is now fast regardless of how large it is, and its detail fills
  in while the crawl runs instead of after it.
  Previously a folder Overview showed a loading box for the whole scan — about fifteen
  seconds on a 100,000-file tree — and then filled in at once.
  The counts were already available throughout; the browser discarded them until the
  index reported itself complete.
  A folder now shows what has been counted so far, labeled as still scanning, and
  refines as the crawl proceeds.

- Folder rollups no longer re-read the whole index on every request.
  Per-directory subtree aggregates and the parent/child index are kept up to date as
  entries arrive, so a rollup costs what changed rather than what is stored.
  On a 100,000-file tree with the Overview open, the median rollup fell from 610 ms to
  83 ms and the full scan from 52 s to 16.5 s. Past roughly a quarter-million files the
  old cost exceeded the browser’s own refresh interval, so each response arrived already
  stale and the view could stop converging.

- Expanding a folder in the navigation tree no longer scans the whole index first.
  Expansion now costs what the response contains instead of what the tree holds: on a
  100,000-file tree, expanding a small folder fell from 63 ms to 7 ms, and no longer
  depends on whether a scan is running.

- Several browser tabs open on the same folder no longer each pay for the same answer.
  A folder summary is now revalidated against the index revision, so a tab that already
  holds the current one is told so instead of being sent it again, and tabs that ask at
  the same moment share a single computation.
  On a settled 100,000-file tree, eight tabs cost what one used to.

- The crawl now visits directories in strict level order, so the layers the navigation
  tree shows are complete early.
  On a 100,000-file tree the first two levels are discovered 2 ms and 21 ms into a
  6.4-second walk. The scan previously followed one top-level directory to the bottom
  before looking at its siblings.

- Loading the navigation tree no longer re-counts the whole index every time.
  The counts behind the type and age filters cover every file, so they were rebuilt on
  each request for the root of the tree — 516 ms on a 100,000-file tree, for a 4 KB
  response, paid again by every browser tab.
  They are now computed once per change and reused, which brings that request to 4 ms
  and lets tabs opening together share one count.
  Expanding a folder was already unaffected; this was the request the page makes first.

- The type and age filter counts in the navigation sidebar no longer freeze partway
  through a scan. On a large tree the first page paint can land before the index can
  answer, which rendered a fallback summary row — and the refresh that would replace
  that row was gated on the row it installs, so it never ran again.
  The counts beside it kept updating, which made the stale ones easy to trust: on a
  400,000-file tree the menu offered “past day 198,998” for a tree the server already
  reported as 400,002. Reloading fixed it; nothing else did.

- A folder’s file count can no longer settle on a number that is too high and stay
  there. A folder reads its totals from two places, and while a scan is running both are
  partial, so the one reporting more files is the one further along.
  Once the scan finishes that reasoning stops holding: each source keeps its last
  reading, so if one stopped updating — a delta lost during heavy churn, say — its
  larger stale number won every comparison after that and nothing could displace it.
  Observed on a tree of 400,000 files, where a folder showed 400,019 and kept showing it
  across a reload. A finished count now comes from the server’s own answer rather than
  from whichever number is larger.

Page load:

- Chart.js no longer loads on every document.
  It and its two plugins are 297,531 bytes read by one view — the agent-log charts — and
  parse and evaluate were paid on every page whether or not that view was ever opened.
  They now load the first time a chart is asked for.
  Measured on this repository in Chromium 141, median of five cold loads of
  `/view/README.md`, the load event fell from 853 ms to 411 ms and transferred bytes
  from 823,391 to 732,836. First contentful paint did not move, at 76 ms either way: the
  chain never blocked paint, it competed with the tree render behind it.

- highlight.js, its TOML grammar, and Mustache now load on the first idle callback
  rather than the moment the document parses.
  They were fetched and evaluated in the same window as the first tree fetch, and the
  `load` event stayed open until the whole chain finished.
  Measured on a 100,000-file tree, median of three cold loads: `load` fell from 3,883 ms
  to 750 ms. Time to first tree row did not measurably change.
  A source view still highlights: the libraries arrive during idle and re-enhance what
  is already on screen, so nothing waits for them.

- **Opening a large folder is far faster to become usable.** On a 241,000-file working
  tree, the wait before any row could appear was about twenty seconds and the full scan
  took over four minutes with a browser watching; those are now about two seconds and
  fifty seconds. Three changes compound to get there.

- Loading the ignore rules walked the whole tree a second time before the real scan
  started, descending into vendored, built, and hidden directories to look for
  `.gitignore` files that cannot change any answer.
  It now skips those, and does not rebuild its pattern set on every file it finds.
  On that tree: 21.4 s to 2.2 s, with no change to which files count as ignored —
  checked against the old behavior for all 341,872 visible paths.

- The navigation counts no longer travel in the same response as the folder rows.
  They cost a pass over every file in the index and the rows do not, so a reader was
  waiting for the expensive half to see the cheap one: asking for rows during a scan
  cost about three quarters of a second, now six milliseconds.
  Those requests had also been taking processor time from the scan itself, so the scan
  finishes sooner as well.
  The counts now arrive a moment after the rows rather than holding them up, and while a
  scan runs they may lag it by one pass — the same beat the progress row already tells
  you they are provisional for.

- The file tree appears as soon as the page does, instead of after a round trip.
  The server already knows the top level when it renders the page, so it sends those
  rows with the page. Measured on a 300,000-file synthetic tree, median of three cold
  loads: the first row went from 1,604 ms to 242 ms, the same moment the rest of the
  page appears. The full tree still arrives a moment later and replaces what was shown;
  the difference is that there is something to look at in the meantime.

- Opening a large folder no longer downloads a megabyte of folders you cannot see.
  The browser warms collapsed folders in the background so expanding one is instant, but
  it was picking them in document order rather than by what is on screen — and on a
  large tree every folder it picked was inside a collapsed branch, at least two clicks
  away. Measured on a 300,000-file tree: 32 background requests and 1,566 KB on every
  cold load, now 0 and 517 KB. Expanding a folder still warms exactly the children it
  reveals, so the next click is still instant — measured at no request and 75 ms — and
  scrolling now warms what scrolls into view.

- Warming a folder you just opened no longer waits for the browser to declare itself
  idle. A browser may defer that indefinitely, and when it does, the folder you just
  opened is exactly the one that stays slow.
  Speculative warming — on first load, and while scrolling — still waits for idle, which
  is what idle is for.

- The page shifts much less under you while it loads.
  Two parts of the navigation pane were drawn before they had anything in them and grew
  once they did: the filter row, which the server sends empty for the browser to fill,
  and the counts row above the tree, which appears with the files and gets its numbers a
  moment later. Between them the whole tree slid down 67 pixels on every load and every
  reload; now it slides 23. Both rows hold a line of space from the start, so the filter
  chips appear in place.
  The counts row can still grow once, when its numbers are long enough to wrap onto a
  second line in a narrow pane.

Plugin SDK:

- `metabrowser.ensureAsset(name)` loads a vendored library that the shell keeps off the
  every-page path, and resolves once its globals are present.
  A loaded bundle resolves immediately and simultaneous callers share one load.

- A plugin announces a short hint with `data-tip-text="…"` on any element, which the
  host turns into its own tooltip, and rich content through `mb.tooltip.show` as before.
  A `title` attribute in plugin markup still works — the browser draws it — but it will
  be a second tooltip beside the host’s, which is what the rule above exists to prevent.

- `metabrowser.chart()` now requires the chart bundle:
  `await metabrowser.ensureAsset("chart")` before the first call, or it throws saying
  so. A plugin that renders charts adds that one await; nothing else in the SDK changed.

## 0.5.1

Folder views:

- The README embedded in a folder’s Overview is now main content: its card fills the
  same column as every other panel, with the same left and right edges.
  Three things had pushed it off that column — the panel body was the one body no width
  rule sized, KPress’s article frame reserved space per side for a table-of-contents
  control the Overview turns off, and the wide column was built as the text measure plus
  a gutter per side, so the card floated inside a column the other panels filled.
  The padding between the card’s border and its text is unchanged, and still varies with
  width exactly as it does when the same README is opened as a file.

## 0.5.0

Document navigation and URL scheme:

- Every selected file and folder now has a canonical, reloadable `/view/<path>` URL. A
  URL fragment identifies a location inside the selected document and never the file
  itself, so headings, browser history, new tabs, and copy-link all work from a real
  `href`. The previous `/#<file-path>` hash route is gone; it is not read, rewritten, or
  redirected.

- The bare origin `/` now redirects to `/view/`, and both the CLI startup banner and the
  header **Jump to root** link emit that canonical route.
  Previously the origin was a second spelling of the served root that rendered an empty
  preview pane.

- Standard Markdown links resolve exactly as they do on GitHub, from any nesting depth:
  relative, `./`, `../`, and leading-slash targets, reference-style links, sanitized raw
  HTML anchors, folders, queries, fragments, spaces, Unicode, and literal percent signs.
  Embedded images, audio, and video route through the bounded `/raw` endpoint.
  Missing targets keep an exact URL and fall through to the ordinary not-found state
  rather than being guessed at by basename.

- Obsidian wiki links work without configuration: `[[Note]]`, `[[Folder/Note]]`,
  `[[Note|Label]]`, heading and `#^block` targets, attachments, and media embeds, plus
  bounded whole-note, heading, and block transclusion.
  Ambiguous and missing notes stay visible and keyboard reachable instead of resolving
  by catalog order.

- A link written as an absolute GitHub URL now opens locally when repository identity
  proves it names the working tree currently being served: the origin remote, the
  checked out branch or the exact revision, and the served subdirectory must all match.
  Anything else — another repository, another branch, a stale revision, a
  non-`blob`/`tree` URL — stays an ordinary outbound link.

- In a repository that carries an MkDocs, Docusaurus, or Jekyll config at its root, a
  root-relative link written as a published-site route — `/guide/`, `/docs/setup` — now
  falls back to the source document behind it once exact lookup fails.
  A route that resolves exactly, or a repository with no such config, keeps ordinary
  Markdown behavior.

- Plugins gain `window.metabrowser.fileCatalog` (`snapshot`, `subscribe`),
  `window.metabrowser.repository` (verified GitHub identity for the served tree, or
  `null`), and the bounded source readers `fetchText` and `fetchCompleteText`.
  `mb.builtins.markdown.analyzeGraph()` returns a bounded immutable snapshot of Markdown
  nodes, resolved edges, unresolved destinations, backlinks, and diagnostics.

- Query strings on `/view/` URLs are carried verbatim and never interpreted, so a query
  an author wrote survives resolution unchanged.
  Metabrowser now reserves query keys beginning with `_mb_` for future presentation
  parameters such as a pinned view or line range; every other key belongs to the
  document. Plugin authors should not introduce `_mb_` keys of their own.
  See the browser URL grammar in `docs/architecture.md`.

Keyboard discovery and navigation:

- Press `?` or use the visible Help control to open a concise product description, the
  project link, and the complete shortcut list, all generated from the same binding
  registry that dispatches commands.
- The navigation footer keeps Help and Quick File hints visible above indexing progress.
  The strip names one preferred key per command and stops there — `? Help` and
  `T Quick File`. Tree arrows are the first thing anyone tries unprompted, so they stay
  in Help rather than spending a permanent line; `/` still opens Quick File and is still
  documented there.
- Jump-to-edge in the tree is now `Shift`+`↑` and `Shift`+`↓` as well as Home and End,
  which a Mac laptop keyboard does not have.
- The GitHub link in Help uses the accent color every other link uses, instead of the
  browser’s default blue.
- Every file-tree row is now reachable and operable from the keyboard.
  The tree carries the conventional ARIA roving-focus model — one tab stop,
  `aria-level`, `aria-posinset`, `aria-setsize`, and disclosure state — and focus
  survives filtering, live updates, lazy subtree loads, and pagination.
  The preview pane keeps native browser scrolling, so arrow, Page Up, Page Down, Home,
  End, and Space still scroll there.
- An expanded folder no longer flickers shut when navigation reaches something inside
  it. Revealing a path treated a folder as unloaded whenever any descendant still carried
  a lazy stub, so it refetched a folder whose rows were already on screen and swapped
  them for a loading placeholder before restoring them.
  The check now looks only at the folder’s own direct children.
- Selection follows focus in the tree: arrows, `Shift`+arrows, Home, and End open the
  row they land on, so skimming costs one keypress per row rather than two.
  Enter and Space are action keys rather than view keys — they expand or collapse a
  folder, or mount a deferred page, and no longer open a file.
  Skimming replaces the route instead of pushing it, so Back returns to wherever the
  reader entered the tree rather than replaying every row they passed.
  Clicking is unchanged: a pointer gets one gesture per row, so a click still opens and
  toggles together.
- Live inventory events now refresh deferred tree pages without mounting their rows
  early, so activating a pagination row cannot duplicate files and removals cannot
  resurrect a stale deferred entry.
  Type replacement also discards deferred pages owned by the removed subtree.
- Recursive folder expansion and collapse each batch tree synchronization once after the
  full operation instead of re-walking the visible tree for every descendant, and live
  inventory bursts coalesce into one pass instead of one per event.
- Help and Quick File now share the same modal, key-presentation, focus-restoration, and
  dismissal primitives for consistent pointer and keyboard behavior.
- Quick File result movement now wraps at both ends, and Home and End keep their normal
  meaning in the query box.

Plugin SDK:

- **Breaking:** `PLUGIN_SDK_VERSION` is now `0.2`. Plugins navigate through the
  documented `window.metabrowser.navigation` namespace (`href`, `open`, `current`),
  which replaces `metabrowser.openPath` and the `metabrowser:open-path` event; both are
  removed with no shim.
  An external plugin must update its call sites and set `sdk_version = "0.2"`. A
  manifest left at `0.1` — or one that omits `sdk_version`, which resolves to `0.1` — is
  now refused at load time with a message naming the required version, and
  `metab --doctor` reports it before it reaches a user.

- `fetchPluginData` accepts `options.signal` and rejects a non-ok response with an
  `Error` carrying `status` and the parsed `payload`, matching `fetchKpressRender`. A
  data hook can now explain a refusal in its body and have the caller read it.

Speed and loading states:

- Expandable folders are prefetched while the browser is idle, so opening one in the
  navigation tree renders instantly instead of fetching its contents on the click.
  An expansion that lands on a prefetch already in flight joins it rather than issuing a
  second request.
- Nothing announces loading inside the quiet period before a placeholder appears, at
  every grain rather than only for view- and panel-level placeholders.
  Lazy subtree placeholders no longer flash a spinner on expansions that resolve in a
  few milliseconds, and the window widens from 30ms to 50ms.
- Spinners no longer carry a redundant visible label such as **Loading folder…**; the
  label is now screen-reader-only.
  States a spinner cannot express on its own, such as a scan still running, keep their
  visible copy.

Documents:

- The README embedded in a folder’s Overview no longer renders its own table of
  contents. The panel stack around it is already the reader’s way through the folder, so
  a second navigation inside the embed competed with it.
  Opening the same README as a file is unchanged.
- Markdown documents need to be both sectioned and long before they get a table of
  contents, rather than sectioned alone, so a short note with a few headings no longer
  gets a sidebar listing sections already on screen (KPress 0.3.3).

Folder views:

- Treemap’s file tally is segmented by file type with the same structure, colors, and
  tooltips as the identical tally on Overview, instead of one flat neutral bar.
- Overview opens File Breakdown by default, alongside Files.
- A collapsed Overview section drops its rule and most of its trailing space, so a
  closed section no longer reads as an empty one.
  Expanded sections are unchanged.
- Hovering a distribution bar segment now visibly shifts the segment.
  The shared data-mark hover moves in the direction that gains contrast in each theme
  rather than brightening in both, which on the light palette was as likely to lose
  contrast as gain it.

Binary and source previews:

- Files classified `binary` now open in a new built-in **Bytes** view instead of showing
  “No preview is available”.
  Each byte renders as exactly one display unit: printable ASCII as itself, and every
  other byte as uppercase hex in guillemets such as `‹00›` or `‹FF›`. Nothing is
  decoded, so the bytes on screen are the bytes on disk.
  Literal text takes the full-strength text color and byte codes recede to the muted
  one; on content where the two alternate too often to mark apart, the view drops the
  distinction for the whole file and says so.
- Large previews load in far fewer steps.
  The source view opens at 2 MiB and doubles per click to 8 MiB, so a 4 MiB file opens
  in one click rather than 31 and a 16 MiB file in three rather than 127. Both views
  append each chunk instead of rebuilding the pane, so a click costs what it loaded
  rather than the running total.
- Loaded bytes stay real text in the DOM, so browser find-in-page, select-all, and print
  continue to cover everything loaded.
- Partially-loaded content now offers **Load more at both ends**, above and below what
  has loaded, and the notice carries the button itself rather than naming a control
  elsewhere. Reaching the end of a chunk no longer means scrolling back to the top to
  continue. Both appear and retire together.
- Binary files larger than the preview ceiling now open and load up to it, instead of
  refusing with “Preview unavailable”.
  The ceiling caps how much may be loaded, not which files may be opened; at the cap the
  notice says the limit was reached rather than silently looking like a finished file.
- Progress is stated once.
  Both views carried a second readout in their pane chrome saying the same thing as the
  notice directly below it.
- Message boxes are now one primitive.
  A **notice** — anything the app says about the content it is showing — always uses the
  ordinary surface as its fill, and carries its severity on the border alone.
  The KPress render error previously wore an informational blue fill under a warning
  border, so an error announced itself in the color of an aside beneath a border naming
  the wrong severity; it is now a plain surface with an error border.
- Every partial-content notice is now one style, in the source view and the Bytes view
  alike: the ordinary surface fill with a warning border, rather than an informational
  blue that meant something else elsewhere.
  The rule is documented in the design system and enforced by a test.

File typing:

- Files with no known text extension are classified by **looking at their content**
  rather than guessing from size.
  A small binary previously fell under a 512 KiB rule that read it as text with
  `errors="replace"`, so it rendered as a field of `�` and could never reach the Bytes
  view; a large extensionless text file was refused for the opposite reason.
  Both now resolve correctly, and a compressed artifact is judged by its decompressed
  content. The check is a single bounded read that runs only when the extension does not
  settle the question, so it stays off the path for almost every file.

## 0.4.2

Release automation:

- Post-publication smoke retries now refresh the package index on every attempt, so an
  initial negative lookup cannot remain cached while a new PyPI release propagates.

## 0.4.1

Folder views and navigation:

- Folder Overview now paints separate nonignored Files and Ignored totals immediately,
  with full-width composition bars segmented by semantic file family.
  The bars reuse the File Breakdown palette and navigation tooltip, including exact file
  and byte values, without another crawl or rollup request.
- Files, File Breakdown, and Treemap share one Files or Bytes choice.
  File Breakdown and Treemap also share the labelled Show ignored control.
  Detailed views wait for a complete rollup instead of briefly rendering partial or
  zero-valued data.
- File Breakdown sorts each section by the selected metric and bounds repeated rows to
  ten plus an exact, expandable **N more** row.
  Files opens by default; the complete breakdown starts collapsed.
- Treemap adds parent-folder navigation, full-cell pointer targets, consistent semantic
  colors and hover feedback, and removes redundant headings and footer status text.
- Overview sections align with the visible README card, including the responsive narrow
  layout. Recommended File-Type Registry revision 2 moves Log files under Other while
  retaining `.log`, `.jsonl`, and `.ndjson` membership and removes the misleading broad
  Other filter preset.
- File ages use centralized light and dark OKLCH tokens.
  Live and under-one-minute entries share one bold orange treatment, newer files remain
  vivid yellow, and age is conveyed by the text itself rather than an adjacent dot.

Plugin compatibility and maintenance:

- Plugin SDK versions are enforced at discovery and by `metab --doctor`, so a manifest
  targeting a different SDK fails with an actionable message instead of breaking inside
  a renderer. Existing Metabrowser 0.4.0 manifests that omit `sdk_version` remain
  compatible by targeting the original SDK `0.1`; omission does not follow future host
  versions.
- Removed unused file-rollup compatibility fields and aliases.
  Consume `file_type_breakdown`, `remaining_top`, `mb.fileTypes.groups`, and
  `groupForFile`. The old `type_tallies`, `type_top`, duplicate limit settings, taxonomy
  projection, `categories`, and `categoryForFile` surfaces had no known consumer.
- Removed unreleased treemap-preference migration code, an unreachable theme
  localStorage fallback, and an unused legacy treemap state sanitizer.
- Development guidance now requires a named consumer before adding an alias, fallback,
  shim, deprecation window, or duplicate transitional field.
  Repository-specific rules link to the shared compatibility guidance and replace
  drifting prose baselines with their real checks and tracked work.

## 0.4.0

Folder Overview and Treemap:

- Every directory now opens with an extensible Overview whose always-present Files
  summary appears above a rendered README when the folder contains one.
  Files and README share responsive alignment and independently collapsible section
  headings, while the README retains the ordinary Markdown document surface.
- The Files summary compares exact file counts and byte totals with percentages and
  independently normalized bars.
  A leading Total row and conditional Ignored row make the selected population explicit,
  including deliberate empty, pending, partial, incompatible, and unavailable states.
- Treemap is now a peer folder view with Bytes and Files sizing, a Show ignored
  checkbox, adaptive labels, and hierarchy-preserving hover.
  File icons and colors match Overview and navigation, folder labels end in `/`, and
  folder navigation keeps the Treemap active.

File types and folder summaries:

- One versioned File-Type Registry now drives folder Overview, navigation filters,
  Treemap colors, and the public browser SDK. Common extensions roll up into readable
  semantic families under Code, Documentation, Data, Logs, Archives, Media, and Other;
  singleton families remain expandable to their exact extension.
- The Files summary now explains extensionless and unknown populations.
  No extension expands to exact basenames and Other types expands to raw logical
  extensions; each list is capped at 20 and conserves omitted files and bytes in an
  exact Others row.
- Logical extensions are ASCII-case-insensitive, treat bare dotfiles as extensionless,
  and retain at most two trailing components.
  This keeps `.js.map` and `.tar.gz` useful without fragmenting reports into names such
  as `.umd.min.js.map`. This intentionally merges uppercase suffixes into their
  lowercase identities: `README.MD` joins `.md`, `photo.PNG` joins `.png`, and `.C`
  joins `.c` rather than retaining a case-distinct language bucket.
- Log files include `.log`, `.jsonl`, and `.ndjson`; archives and common image, video,
  audio, and font formats gain explicit families.
  JSON Lines retains its data-analysis identity and SVG retains its markup identity
  while using those display families.
- Registry, Breakdown v1, JSON Schemas, conformance cases, and a checked export tool now
  form a self-contained compatibility packet that `fdu` can adopt without a sibling
  checkout or network access.
  Packet export prunes stale destination content, verifies exact manifest membership and
  hashes before returning, and supports an independent `--verify` mode.

Navigation, plugins, and reliability:

- The file-type chooser uses the same registry-backed hierarchy as Overview: broad
  groups, semantic families, and exact canonical or raw extensions can be selected
  independently, with parent choices selecting their children.
- The public browser SDK adds immutable file-type definitions, bounded folder-rollup
  helpers, folder context, view-aware navigation, shared formatters and file identity,
  active-view state, and an extensible folder-panel registry.
- Folder rollups run off the event loop and reuse the inventory snapshot instead of
  crawling the filesystem again.
  Rapidly rebuilt directories are reconciled against the current filesystem so stale
  watcher deletes cannot leave an Overview blank, and brief local navigation no longer
  flashes loading chrome.

## 0.3.0

Filtering and file navigation:

- The Files pane gains one always-available filter bar for age, type, minimum size, and
  gitignored visibility, with Docs, Code, and Data presets and a one-click Clear action.
  The separate Recent tab is folded into this pane so every dimension composes in one
  place.
- Age filters query the complete inventory rather than only expanded folders.
  Each age row shows its cumulative index-wide file count, refreshed when the menu
  opens. Capped results prioritize tracked files over ignored dependency churn, report
  the shortfall, and continue to incorporate filesystem changes while the view is open.
- **Live** now has one general definition: every file modified in the past 90 seconds.
  The server owns that cutoff, and expired rows disappear even when no later filesystem
  event arrives. Agent-log activity remains a separate capability that supplies active
  badges and live tailing for supported logs.
- Filter controls are keyboard navigable, expose their state through ARIA, keep the
  active value visible when the drawer is closed, and share the documented design-system
  primitives with plugin views.
- Agent-log event-type filters use the same additive chips, including counts and a
  visible selected state for dynamically discovered record types.
- Filter selections are transient view state and reset on every page load instead of
  leaking through a host-wide browser preference.
  Durable appearance choices such as theme and typography remain shared across
  Metabrowser instances.
- Recency overlays no longer grow after returning to the full tree, compound extensions
  match consistently on streamed rows, and filtered tallies update under every
  dimension.

Quick File navigation:

- A new Quick File palette opens with `/` or `T` and jumps to any file by name or path
  fragment, the way go-to-file works on GitHub.
  Matching is fuzzy and deterministic, ranking whole-word, path-boundary, and camel-case
  hits above scattered letters, and the ranking contract is pinned by a fixture set.
- The palette searches every non-gitignored file under the root, not just the subtree
  the browser happens to have expanded.
  A one-shot `GET /api/catalog` endpoint serves a minimal gzipped payload with ETag
  revalidation, and `catalog.change` events on the existing stream keep it live.
- An open search converges as coverage grows: files that arrive after the query was
  typed join the visible results instead of waiting for another keystroke.
  The status line distinguishes complete coverage from a walk still in progress or
  stopped at the file cap.
- Results hold their previous contents until real ones replace them, so the list no
  longer flickers empty on each keystroke, and a row stays inert until the results it
  describes are the ones on screen.
  A result reads as one line of navigation: the filename at full contrast, the parent
  path beside it muted.
- Catalog upkeep costs the same whether the palette is open or closed, and a batched
  directory removal now costs an entry’s depth rather than the size of the removal
  batch. Removing 2,000 directories from a 100,000-entry catalog went from 1441ms to
  52ms, and stays flat as the batch grows.
- Quick File catalog recovery now closes the last reconnect gap: if a restarted server
  is still scanning, its terminal state triggers one authoritative membership fetch
  before stale paths can survive.
  This also repairs capped inventories while keeping their root coverage labeled
  incomplete.

Document rendering:

- KPress is upgraded through `0.3.2`. Version 0.3.1 adds the `toc_rail` option this
  repository’s host CSS had been standing in for.
  The host reimplementation is deleted, so the reading column holds one position whether
  or not a document earns a table of contents.
- Version 0.3.2 fixes the content-card breakpoint for a narrow preview pane inside a
  wider browser window and restores the intended lighter code size inside wide tables.
- KPress now owns the whole document size ramp.
  The host had collapsed graded size families onto single values, which rendered inline
  code inside a table larger than the cell around it; prose code is now 12.3px, table
  cells 14.25px, and code in a table cell 12.3px.
- Unscoped `.md-body` chrome rules no longer reach inside embedded documents.
  Twenty-six of them had been capping the reading column at 50em, overriding KPress’s
  list rhythm, and constraining blockquotes.
  `.md-body` remains the documented convention for plugins that render their own
  Markdown.
- Embedded documents are square.
  KPress’s own box radii are bridged to `--radius-document`, so code blocks, tables, and
  callouts no longer sit rounded inside square panes; pills and circles keep their
  shape.

Design system:

- Chrome icons draw at one `--icon-glyph` size inside a 16px alignment box, and
  icon-only controls collapse into a single `.icon-btn` primitive that raises a surface
  and hairline border only while hovered, focused, or holding a menu open.
- Keyboard keys get one `.kbd` component, and a chrome typography rule puts navigation
  text — file paths, parent paths, ancestor segments, and shortcut hints — in the same
  sans face as the rows they point at, leaving mono for the user’s own content.
  A contract test enforces the three named exceptions.

Reliability:

- Symbolic links now appear as explicit, non-expanded leaves with the standard link
  icon. They never contribute file counts or type tallies, never graft a target directory
  into the served tree, and report whether an unavailable target is missing, outside the
  served root, or otherwise unreadable.
- Live filesystem updates now replace an existing row when its path changes between a
  file, directory, and symbolic link, including removing a former directory’s rendered
  descendants before mounting the replacement.
- Ctrl-C during command startup or an in-progress filesystem scan now exits quietly with
  status 130 instead of printing a traceback or waiting on a background thread.
  A second Ctrl-C remains an immediate forced exit if another operation cannot finish
  cooperatively.
- Live updates remain correct when a large filesystem burst fills a bounded event queue.
  The server replaces the incomplete backlog with a resynchronization marker, and each
  affected browser reconnects with bounded exponential backoff for a fresh inventory
  snapshot instead of remaining open with stale state or reconnecting in a tight loop.
- Folder totals that remain pending now produce a bounded client/server diagnostic and
  recover through a fresh root tally.
  The tracked/ignored split stays pending until its inventory snapshot is complete,
  tally values and scan status stay aligned, and a filter change during recovery cannot
  restore a stale view.
- `metab ROOT --check-api` runs the application in-process and validates the initial,
  filtered, cleared, and completed navigation responses without opening a browser.
- Default server output no longer reports routine lifecycle events, expected concurrent
  inventory conflicts, protected directories, or sub-threshold helper timings.
  Slow requests, long inventory scans, plugin problems, and operational failures remain
  visible, while `--log-level debug` retains the detailed trace when needed.

Security documentation:

- SECURITY.md now states the content trust model: application surfaces (the shell,
  static assets, `/api`, and plugin assets) are first-party code, browsed content is
  not, and browsed content never executes inside the application page.
- Two boundaries are documented as **not yet enforced**, so the trusted-local guidance
  stays operative until they are: `/raw` serves in-root files on the application origin
  with no sandboxing, and `/api` routes take no proof that a request came from the
  application’s own pages.
  A tracked plan closes both with an opaque content origin, same-origin proof on `/api`,
  and an `--untrusted` profile.

Agent Skill:

- The skill now prefers a locally installed `metab` and falls back to
  `uvx metabrowser@latest`, instead of reaching for the runner first.
  The zero-install guarantee is unchanged; an agent that already has Metabrowser no
  longer pays a `uvx` resolve.
- The skill no longer carries a version pin, so an installed copy does not go stale
  between releases. Release cool-off is enforced by uv configuration instead
  (`exclude-newer`, or `UV_EXCLUDE_NEWER`), which is read from the environment the agent
  runs in rather than from this repository.
- The skill declares its `compatibility` requirement (a local `metab`, or uv with
  network access on first use).
- The skill states that serving blocks until the server is stopped, so an agent
  backgrounds it and reports the printed URL instead of hanging on the most common
  operation, and that passing a file selects it inside its parent directory.
- The release workflow no longer requires the skill to name the release version, and
  still keeps the worked pin examples in the README and installation guide current.
- The README leads with the skill: its install command now sits directly under the
  introduction instead of below the plugin documentation.

Contributor workflow:

- Repository-wide checks ask git for the file set instead of walking the filesystem and
  naming skipped trees by hand, so a newly ignored tree is excluded in one place.
  Read-only third-party checkouts under `attic/` and agent worktrees checked out inside
  the repository are excluded from doc lint, codespell, Biome, and the sdist.

## 0.2.0

Flat single-command CLI:

- Serving is now the default operation: `metab .` serves the current directory the way
  `open .` opens a folder on macOS. The `serve`, `walk`, `plugins`, and `remote`
  subcommands are removed and replaced by mode flags on one command: `--walk`,
  `--remote HOST`, `--plugins`, `--plugin NAME`, and `--doctor`.
- Exactly one mode applies per invocation.
  Options explicitly passed outside their mode are rejected as usage errors, and
  `--help` groups options by mode.
- This is a breaking change with no compatibility aliases: scripts that invoked a
  subcommand spelling must drop `serve` or switch to the matching mode flag.
  `metab --remote` starts the remote side with the flat syntax, so both hosts need
  Metabrowser 0.2.0 or newer.
- The Agent Skill, README, and installation guide pin `uvx metabrowser@0.2.0`, the first
  release with the flat CLI.

KPress embedding and visual consistency:

- KPress is upgraded to `0.3.0` and its declarative fragment architecture.
  Metabrowser owns one root theme attribute and one root type-size hook, fragments are
  theme-agnostic, the KPress asset manifest is authoritative, and host-side heading,
  bullet, theme-restamping, resolver-filtering, and numeric-table workarounds are
  removed.
- Embedded document prose is now 15px, down from 17px and one step above the 14px app
  body. KPress derives headings from that base, while proportional host tokens keep code
  and secondary text tied to it, so the document hierarchy stays stable when the browser
  root size changes.
- Embedded document navigation now matches KPress’s polished static-site treatment:
  compact hierarchy and active states in the narrow drawer, plus a borderless docked
  rail at the wide document breakpoint.
- Theme changes now keep embedded KPress content, full-file syntax highlighting, and
  plugin charts aligned with the Metabrowser chrome.
  The host owns the complete Highlight.js palette with WCAG AA contrast checks in both
  themes. Token-colored SDK and built-in canvas charts repaint when the resolved palette
  changes and release their theme subscriptions through the existing chart `destroy()`
  lifecycle.

Reliability and distribution:

- Pressing Ctrl-C twice now forces an immediate server exit without non-actionable
  Uvicorn cancellation tracebacks.
  Graceful shutdown keeps normal error reporting, and every exit path restores the
  process-global logger state for later in-process runs.
- Repository and package metadata now state AGPL-3.0-or-later explicitly, matching the
  license obligation that has always applied through the required KPress runtime.
  Vendored browser components remain under their own licenses in `NOTICE.md`, and built
  distributions verify the license expression and include both license files.
- The publish workflow refuses a release whose tag does not match the Agent Skill,
  README, and installation-guide version pins.
  After publishing, it smoke-tests the pinned Skill invocation with `--help` and
  `--doctor` directly from PyPI.

Contributor workflow:

- Golden console-output tests now pin the CLI surface (help, every mode, and the
  usage-error matrix) under `tests/golden/`, run with tryscript
  (github.com/jlevy/tryscript) via `make test` and regenerated with
  `make golden-update`.
- Repository automation is updated to tbd 0.4.2. Its exact fallback stays usable under
  the dependency cool-off policy, and release documentation incorporates the verified
  GitHub CLI workflow for proxied agent sessions.

## 0.1.1

Hardening, offline support, and UI refinement:

- Offline-first assets: every third-party browser library is vendored into the wheel
  from lockfile-verified npm packages with a hash manifest, license texts, and size
  caps. The served page references no external origins, so Metabrowser works without
  network access; unused elkjs was dropped.
- Host-header validation defends against DNS rebinding.
  Loopback names and a concrete `--host` value are permitted automatically; wildcard
  binds keep validation and use loopback for the printed URL and auto-open, and
  `METABROWSER_ALLOWED_HOSTS` extends the allowlist (see SECURITY.md).
- First-paint navigation expands folders within a visible-row budget instead of
  expanding every top-level folder; document and tab spacing tightened, prose sized
  relative to navigation, compact TOC rows, and Markdown tables right-align signed
  percentages and localized number formats.
- Server responsiveness: live-tail polling, watcher classification, active-file sweeps,
  and synchronous plugin data hooks no longer block the event loop, and the mtime cache
  no longer serializes reads behind slow filesystem stats.
- Browser resilience: superseded file loads abort, client caches are bounded, the
  inventory event stream reconnects with backoff after repeated failures, live tree
  updates handle filenames containing backslashes and quotes, and the SDK owns
  copy-button behavior end to end.
- Documentation: project design records reorganized under a dedicated records tree with
  maintained architecture documents and dated plans, plus a research brief on the
  planned diff viewer architecture.
- Licensing: Metabrowser is licensed under AGPL-3.0-or-later, aligned with its required
  KPress runtime. Vendored browser components remain under their own licenses listed in
  `NOTICE.md`.

## 0.1.0

Initial standalone release:

- Local file, log, Markdown, structured-data, image, and binary browsing.
- Primary `metab` command with a `metabrowser` compatibility alias.
- Concise zero-install and global-tool onboarding, plus a portable Agent Skill that
  delegates to the pinned `uvx metabrowser@0.1.0` runner.
- Trusted manifest-driven plugins with JavaScript views and Python data hooks.
- KPress-backed Markdown rendering through `kpress==0.2.2`.
- Gzip- and zlib-transparent previews, frontmatter classification, Markdown rendering,
  and KPress export with bounded input, output, and text windows.
- Background inventory indexing, live filesystem updates, and recent-file navigation.
- SSH and optional GCP remote tunnels.
- AGPL-3.0-or-later licensing, PyPI packaging, locked uv environments, and isolated
  wheel checks.
- Review hardening for bounded compressed reads, safe rendered labels, byte-accurate
  event streaming, renderer disposal, explicitly repository-configured development
  commands, and release builds without mutable dependency caches.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
