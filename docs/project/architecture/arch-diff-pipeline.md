# Diff Pipeline

**Status:** Implemented: the patch-file and Git revision sources, the apply oracle,
manifest-first hydration on the server and in the page, the comparison caches, the
rendered projections of Markdown, YAML, and JSON on a pull request’s Changes, and the
unchanged lines between a comparison’s hunks, read on demand
([Context Between Hunks](#context-between-hunks)). Planned: working-tree and index
sources, in the
[Git status plan](../specs/active/plan-2026-08-26-git-status-and-working-tree-diffs.md);
and anchoring a patch file to a repository, in the
[general diff rendering plan](../specs/active/plan-2026-08-17-general-diff-rendering.md).

[File Diff Format v1](file-diff-format/file-diff-format.md) defines what a comparison
document is. This document covers where documents come from, how much of one is sent and
drawn at a time, what is kept, and the rendered view of a Markdown, YAML, or JSON
change.

## Three Stages

Viewing a diff is three separable stages:

1. **Acquisition** obtains the raw material: a `.patch` file, two Git revisions, or a
   pull request’s commits in a repository store.
2. **Modeling** converts it to a `ChangeSetDocument` and validates it.
3. **Rendering** projects the document.
   The renderer never learns which source produced it.

The stages compose because everything converges on the format, and because unified patch
text is itself a convergence point: Git emits it for any pair of trees, GitHub serves it
for any pull request, and both parse through `parse_unified_patch`. The format has no
Git vocabulary, and Git is one source of it, not a substrate.
The GitHub plugin’s records refer to Git object IDs and add nothing to the format.

## The Source Port

`DiffSource` in `diff/adapters/base.py` has no source-specific vocabulary: `resolve` an
intent to a `ResolvedComparison`, list its `manifest`, give one `file_patch`, and stream
one side’s `content`. An intent is adapter-specific plain data; everything a source
returns is File Diff Format.
There is no source registry: callers construct the source they need, so the port, not a
table, is the contract.

Two sources exist:

- **`diff/adapters/patch_file.py`** parses a `.patch` or `.diff` with no repository,
  subprocess, or network.
  Malformed input is a value: a section it cannot model is left out and named, and a
  document it cannot model at all degrades to an empty one that says why.
- **`diff/adapters/git.py`** (`GitDiffSource`) compares revisions at a `GitLocation`.
  One revision compares against its first parent, and two endpoints compare directly or
  from their merge base.
  It lists changes with one `git diff --raw --numstat -z`, and its patches come from a
  path-limited `git diff` fed through the patch-file parser, so Git’s own output must
  round-trip through the neutral model.
  A comparison the diff plugin’s route asks for lists its files and prints its patch in
  one run, within `MAX_LISTED_PATCH_BYTES`, and Git stops once the patch passes that
  size. That run passes `--no-textconv`; where the configuration names a textconv driver,
  the page’s files are diffed in a run of their own, with their drivers
  (`diff/adapters/textconv.py` keeps that answer per configuration).
  On a store it reads blobs through the shared batch readers.

## Where Documents Come From

| Path | Pipeline | Status |
| --- | --- | --- |
| A patch file | `.patch` or `.diff` → patch source → render | Implemented: a folder-like entry in the tree, and `metab --diff FILE` |
| Git revisions | Revision or pair → Git source → render | Implemented: the Commits tab, and `metab --diff A..B`, a single revision, and `--diff-check` |
| A pull request’s patch | GitHub’s `.diff` download → a patch file | Implemented, as a patch file |
| A pull request over Git | Its head fetched into the store → merge base → Git source | Implemented: the pull-request page’s Changes |
| Uncommitted states | Working tree or index against `HEAD` → Git source | Planned |
| A patch anchored to a repository | A patch file plus a claimed base revision → validate → enrich | Planned; the oracle it needs is implemented |
| Document edit history | Editor sessions → a future source | No source; the format has room for one |

A pull request’s `.diff` and a merge-base comparison of the same commits describe the
same changes but are not the same document.
The patch source emits `patch` snapshots and `empty` content references, and shows a
type change as a deletion and an addition, because that is what patch text holds.
The Git source emits commit IDs and `git_object` content references and folds the pair
into one `type_changed` entry.

## Adding a Source

A new source answers four questions before it is written, because each is expensive to
retrofit:

1. **What is its identity?** Use content-addressed IDs where the source has them.
   Where it does not, as for a working tree or an index, manufacture one and say what it
   covers. The format reserves `generation` on `SnapshotRef` and `ContentRef` for such an
   identity, and no source sets it yet.
   A manufactured identity is never an immutable cache key.
2. **When does that identity go stale, and how is it detected?** A source over mutable
   state samples its identities before and after reading, and answers the `stale`
   availability rather than a document that mixes two states.
3. **What are its snapshot kinds?** `SnapshotKind` already has kinds for an index and a
   working tree; a new kind is a format change.
4. **What does it answer when it cannot produce?** `Availability` is the whole set of
   honest answers. Silently substituting an inferior rendering is not one.

What binds all four: no source-specific field enters File Diff Format.
Something the format has no room for belongs in the source’s own response beside the
document.

## Anchored and Unanchored Comparisons

A bare patch is self-contained but context-blind: it carries hunk-neighborhood context,
paths, and sometimes abbreviated blob IDs.
The patch source records this as an **unanchored** comparison.
An **anchored** comparison names real trees, as the Git source’s does.
A repository context gives a comparison whole files for Before and After, exact totals
and rename scores, folded type changes, and a computed merge base instead of a trusted
one.

**The apply oracle** decides whether a document matches its trees.
`apply_change_set` in `diff/apply.py` replays a hydrated document against a base tree
and either reproduces the target tree byte for byte, modes and entry types included, or
refuses with the first mismatch.
`metab --diff A..B --diff-check` runs it and reports the tree hashes it compared.

Anchoring a foreign patch is planned on that oracle, in two levels by cost: compare the
object IDs the patch claims against the repository first, then replay it in full, and
upgrade a clean result to an anchored document.

## Hydration

A comparison is sent manifest first and patches later, and every file states its
availability, so an absent patch is never an empty one.

**On the server**, the comparison route of the diff plugin
(`GET /api/plugin/diff/comparison`, in `builtin_plugins/diff/sidekick.py`) lists the
manifest, up to `MAX_MANIFEST_FILES` in `diff/adapters/git.py`, and hydrates the first
`MAX_HYDRATED_FILES` ready files from one diff run and one parse.
The rest are `deferred` and load alone when the reader reaches them.
A pull request’s first answer hydrates fewer, `INITIAL_PULL_FILES` in
`builtin_plugins/github/sidekick.py`. `MAX_FILE_PATCH_BYTES` bounds one file’s patch and
what one run hydrates: one file past it is `too_large`, and a file that would take a run
past it is `deferred`. Each constant’s comment records the measurement that set it.

**Narrowing** keeps part of the listed manifest, before the hydration bound applies.
`&file=` keeps one path, for a deferred file’s own request.
`&types=` keeps the changed files of some file types, in the Files tab’s File type
vocabulary (`tree_filter.parse_types`), matched by `file_type_match.py`, the rule the
Files tree on a revision uses.
A change matches when either of its sides does, so a rename from `.txt` to `.md` is of
both. The bound then counts kept files, the totals are the kept files’, and `truncated`
still says the listing stopped at its own bound.
A narrowed answer is cached apart from the whole one, whose key and tag are unchanged.
`&view=types` answers the comparison’s File type counts instead of a document, for the
diff view’s File type menu: the rows the Files tab’s menu reads, over every listed
change whatever `types` and `file` say, counted by `file_type_match.type_tally`, which
the Files tree on a revision counts with too.
`cli-api-diff-type-filter.tryscript.md` pins the answers.
In the browser, `builtin_plugins/diff/diff-type-filter.js` keeps the whole comparison
and mounts each choice’s `types=` answer in its place, so going back to every type, or a
jump to a file the choice hides, asks for nothing; a served folder’s comparison is not
cached, so there each choice reruns the listing (bead mb-no6c records the cost).

**In the page**, `builtin_plugins/diff/diff-view.js` keeps every file’s bar in the page
and draws rows only near the viewport:

- **The mount** draws rows for the ready files within the pane and one screen more
  (`firstScreenBudget`). Later ready files are bars that reserve their height from
  `patchRows` until they are drawn.
  A file with a rendered view is held wherever it is, and its Source rows are drawn only
  while its rendered view shows Source and once the file is reached (`bodyWanted`), so a
  long document behind its rendered view costs nothing to load.
- **`createHydrationScheduler`** asks for one deferred file at a time, from the top of
  the viewport through `HYDRATION_AHEAD_PX` below it, and draws at most one file per
  frame. A file jump goes first and cancels other requests, and a burst of jumps waits
  `JUMP_QUIET_MS` and asks for the file it rests on.
- **A collapsed run** mounts only its visible prefix; expanding it adds
  `FOLD_MATERIALIZATION_BATCH_ROWS` rows per task, and collapse, reprojection,
  replacement, and disposal cancel pending batches.
  The performance loop’s browser profile gates `collapsed_diff_rows_materialized` at
  zero.
- **A layout switch** reprojects `LAYOUT_PROJECTION_BATCH_FILES` files per task and
  drops stale batches when a newer selection arrives.
  [The layout benchmark](../../../explorations/diff-layout/README.md) holds the fixture.
- **Intraline refinement** counts its edit-distance work and falls back to positional
  rows past `INTRALINE_WORK_BUDGET`, which bounds the pathological cost without a second
  file-size limit.
  [The intraline benchmark](../../../explorations/diff-intraline/README.md) holds the
  evidence.

Find in page finds what is drawn and every file’s path, since every bar is in the page.
A list of the comparison’s files reaches one through the view’s handle:
`scrollToFile(path)` puts the file at the top of the pane, expanded, and holds it there
as files above fill in, until the reader scrolls; `fileForPath`, `currentFile`, and
`onCurrentFile` answer which file a path names and which is on screen.
Each answer is typed, because a list from GitHub and a comparison computed here can
differ. `tests/dom/diff-file-jump-session.js` pins the contract, and
[exp-040](../../../explorations/performance-loop/experiments/exp-040-files-changed-recomputes-the-whole-patch-per-request.md)
holds its budgets.

Syntax tokens, intraline ranges, and split-row pairings are browser enrichments derived
from the line records (`diff-syntax.js`, `diff-intraline.js`, `diff-render-model.js`),
not format fields, so a palette, algorithm, or layout change cannot invalidate a
comparison.

### Context Between Hunks

A hunk carries the context lines Git writes around its change, so the unchanged lines
between hunks, above the first, and below the last are not in the document.
The patch run passes `CONTEXT_LINES` (`diff/adapters/git.py`) as `--unified`, and the
comparison says it as `options.context`, so a reader’s `diff.context` cannot move where
the page expects a last hunk’s trailing context to end.
The comparison route reads the lines on demand: `&view=lines&file=PATH&start=N&count=M`
answers up to `DIFF_GAP_LINES` (`settings.py`) lines of that change’s new side from its
snapshot, and `&end=N` in place of `start` the lines before line N, with the side’s
`line_count` and `ends_with_newline`, so the page learns where the file ends below its
last hunk.
`diff/side_lines.py` cuts the run as Git numbers the side’s lines, finding its
start by counting newlines rather than splitting the side; the route reads the side
within `MAX_LINES_SIDE_BYTES` (`builtin_plugins/diff/sidekick.py`), through the store’s
shared readers or a folder’s `cat-file`, and an answer carries at most
`MAX_LINES_ANSWER_BYTES` of line text, keeping the lines nearest the line it was asked
from, and one longer line whole.
A side the hunks do not number as its bytes, or cannot be read, is refused with 409 and
a `code`: a deleted file’s, which has no new side (`no_side`), not a file’s text
(`not_text`), past the bound (`blob_too_large`), or converted by a textconv driver in a
folder (`textconv`), whose hunks number the conversion’s lines.
`view=lines&whole=1` reads from the first line for Full source, using the single
answer’s line and byte bounds.
The client compares the returned line count with the file’s total before it draws the
result as Full. It keeps the excerpt if the file exceeds either bound.
`cli-api-diff-lines.tryscript.md` pins both reads.

Every comparison has this view, whatever its source: a commit’s, a branch comparison’s,
a pull request’s through its own route (`comparison_at` serves both), and a checkout’s,
all of which compare commits.
A patch file names no snapshot and has none, and a working-tree or index source, once
one exists, answers `no_content` until it can read its side, so its separators stay
plain.

In the page, `hunkGaps` in `diff-view.js` places each gap from the hunks’ ranges, and
`renderGapFold` draws it as the diff’s fold bar (`foldExpander`), opening in one ask up
to `DIFF_GAP_LINES` at a time nearest its hunk, or what one answer holds of long lines,
up to a hunk by `end` and down from one by `start`, in batches of
`FOLD_MATERIALIZATION_BATCH_ROWS`, with the reader’s place held (`GapSource.keep`) and
the lines highlighted within the file’s `SYNTAX_HIGHLIGHT_MAX_BYTES`, counted with the
hunks’ bytes. A file keeps what it read while the diff is mounted.
An answer must name the comparison the diff drew; one for another, as a ref that moved
since gives, is declined as a refused file is.
A code file’s hunks in a guided review step (`mountFilePatch`) and a patch file draw
plain separators. `cli-ui-diff-hunk-gap.tryscript.md` pins the states, and
`tests/test_diff_hunk_gap_chrome.py` the bar and the place in Chrome.

## Caches

A local repository, a mirror, and a pull request all reduce to object IDs that the same
Git source compares.
Only the repository store must be kept; every comparison kept beside it, on disk or in
memory, can be computed again:

- **The repository store** holds Git objects across sessions; see the
  [repository cache](arch-repository-cache.md).
- **The pull request’s manifest bank** (`builtin_plugins/github/pull_manifest.py`) keeps
  a prepared manifest beside the store after each fetch, one for each pull request, so a
  fresh server skips the costly listing.
  A missing, stale, or corrupt manifest is recomputed.
- **The server’s comparison cache** (`builtin_plugins/diff/comparison_cache.py`) keeps a
  store comparison’s resolution and manifest, and each encoded answer, in memory, keyed
  by the commit IDs and every request input the answer reads.
  Its entity tags are scoped to the build and the store, so a browser’s HTTP cache keeps
  them too. It keeps nothing for a served folder, whose answer can change with its
  working tree’s `.gitattributes`, `.git/config`, the reader’s Git configuration, or a
  replace ref; the module docstring lists what a store’s answer depends on and why each
  is covered.
- **The Commits panel’s cache** (`static/git-panel.js`) keeps each answered comparison
  whose revision is a full commit ID, so a revisited commit’s diff mounts with no
  request. It is bounded by `GIT_COMPARISON_CACHE_BYTES` of JSON, with a quarter for one
  answer, least recently used first, and is sized in a task after the one that hands the
  answer to the diff. Refresh, the panel’s teardown, and a history walk found stale clear
  it, and an answer requested before a clear is not kept.
  A folder’s answer kept here can outlive a change to its Git configuration until one of
  those clears.
- **A pull request page’s keep** (`createComparisonKeep` in
  `builtin_plugins/github/comparison-prefetch.js`) keeps each comparison a pull
  request’s page reads for the document rather than for one page, keyed by the
  comparison’s route and bounded by `KEPT_COMPARISON_CHARS`, so a revisit draws its Diff
  summary and mounts Changes with no request; see
  [The Comparison Keep](arch-github-pull-requests.md#the-comparison-keep).

A refusal is never kept, since a fetch can answer it.

## Rendered Projections

A pull request’s Changes defaults to **Rendered** for Markdown, YAML, and JSON.
**Source** shows the same presentation as lines of the file.
The rendered view marks changes in one gutter beside Markdown blocks or the YAML and
JSON tree. Markdown front matter uses the Document view’s Frontmatter disclosure
([Markdown Views](#markdown-views)). `GET /api/plugin/github/pull-rendered-diff` answers
one file’s projection, by the format of its extension, and
`builtin_plugins/diff/diff-markdown.js` mounts it.
Both projections run in one long-lived child process
(`diff/markdown_projection_worker.py`), so a projection never holds the server’s GIL;
the module records the measurement.
Until the child is ready, projections run in a thread.

### Markdown

`diff/markdown_projection.py` parses each side once with KPress’s own MarkdownIt core,
so a block’s source range is the map of the token that renders it, and renders every
top-level block from its own tokens through KPress’s sanitizer and the inert-HTML
hardening. `tests/test_markdown_diff_projection.py` checks the joined blocks against
KPress’s own render.
Changed words are marked by a bounded word diff.

- **Fallback:** a side nested past what MarkdownIt keeps is refused with that `reason`,
  and the file shows Source with its rendered chips unavailable and saying why.
  The budgets beside `MARKDOWN_DIFF_MAX_BYTES`, each with its measurement, bound a
  projection in a thread, which nothing can stop, only for Markdown without raw HTML. No
  count over the input bounds what the sanitizer makes of raw HTML, which rebuilds each
  formatting element left open at every later block (`_Limits`), so a thread refuses a
  side that holds any, a comment the sanitizer ends early included (`_COMMENT`). Past a
  budget, or with raw HTML, the pair goes to the Markdown child, whose deadline bounds
  its time (`markdown_projection_worker.py`), and the pull request route reads a pair up
  to `_MARKDOWN_PAIR_MAX_BYTES` in `builtin_plugins/github/pull_rendered_diff.py`
  (mb-rm40). The projection renders with math and diagrams off and without code
  highlighting. The rest of its refusals guard what it checks rather than what a file
  holds: a patch that does not match the two sides’ bytes or cover their differences,
  and a hardened render it cannot read back as one tree.
- **Source text:** each side reads as the Document view reads it.
  A byte that is not UTF-8 is U+FFFD, and a patch line that is not carries its exact
  bytes, which the projection checks; MarkdownIt makes a NUL U+FFFD. MarkdownIt also
  ends a line at a carriage return no line feed follows, which Git does not, so a Git
  line holding one is that many lines, changed or unchanged as Git says the whole line
  is (`_markdown_lines`).
- **Raw HTML:** renders as the Document view renders it, through the same sanitizer and
  allowlist. The blocks are rendered together with a numbered marker at each boundary,
  written with a private-use character the render does not hold (`_separator`), and a
  boundary whose marker the render does not carry at its top level, inside a `<div>` or
  a `<details>` that raw HTML opened in one block and closed in a later one, parts
  nothing, so those blocks are one block of all their lines (`_units`). Raw HTML the
  render drops whole, such as a script, has no block, as a comment has none.
  A comment that the sanitizer’s HTML5 parser ends before MarkdownIt’s token does, at
  `--!>` or at an opening `<!-->`, is raw HTML that renders the rest, as the Document
  view renders it (`_COMMENT`). `_trusted` says when a top-level boundary can still be
  misplaced, and how the projection then finds it.
- **Task lists:** KPress draws each box from a token of its own (`_TASK_BOX`), with the
  box’s state in the token’s `meta["checked"]`, and the allowlist keeps the `input` it
  renders as a disabled checkbox, ticked as the token is (`CHECKBOX_ATTRIBUTES` in
  `inert_html.py`). So a tick is a change in what the block renders, the box is one
  element of the tally that bounds the render tree, and its attributes are no part of
  the hidden signature.
  Each side draws its own box, so a tick beside a word edit in the same item still marks
  the words (`_inline_change`). A checkbox the document writes in raw HTML, as a README
  writes one in a table cell, is kept in the same shape, so the raw-HTML reader
  (`_RawMarkup`) counts as hidden its other attributes and any value of `checked` or
  `disabled` but the two HTML defines, empty or the attribute’s own name
  (`_shows_value`). It reads an input as a box where KPress’s sanitizer keeps one, when
  its `type` is `checkbox` in ASCII letters of any case, with or without ASCII
  whitespace around it (`_kpress_keeps_box`); any other `input` it reads as an element
  the render drops, with every attribute hidden.
  KPress writes the item’s and the list’s classes as token attributes, where attribute
  syntax writes its own, and the allowlist drops both, so a task list a change adds, or
  an item that gains its box, is `source_only`. KPress now lists the classes it writes
  in `meta["kpress_classes"]`, and reading them so those changes render is mb-y5uc.
- **Footnotes:** a reference renders in place, numbered as the Document view numbers it,
  and each note is a block of its definition’s lines, a list of its own that starts at
  its number: `_footnotes_in_place` takes the place of KPress’s `footnote_tail`, which
  moves every note to one list at the end, in the projection’s parser.
  An inline note follows the top-level block that holds it, as part of that block.
  A definition that renders nothing, one no reference names or one a later definition of
  its label replaces, has no block.
  When notes follow no source line, as a definition written inside another’s does, the
  side is one block of KPress’s own render.
- **Hidden signature:** whatever a block’s source says that its render does not show,
  such as a link destination, a title, alt text, a fence’s info string, or raw HTML the
  allowlist drops (an attribute, a copy of one after its first, a value it does not
  read, such as a link’s `target`, an element with its content, a comment).
  A changed block whose hidden signature differs is flagged `source_only`, as is a file
  whose source changes include one with no visible counterpart.
  A flagged block never folds, and the page draws no note for it: Source is how a reader
  reaches such a change.
- **Front matter:** each side’s front matter is read as the Document view reads it, and
  its keys are listed as KPress’s Frontmatter disclosure lists them, sorted, each value
  in the disclosure’s own words.
  A key whose value changed is removed and added; values are compared with each type
  kept, so one whose type changed and whose text did not is drawn unchanged and makes
  the file `source_only`. Front matter that does not load, or that composes to more
  nodes than `_FRONTMATTER_MAX_NODES`, shows no disclosure and leaves its lines
  unmapped, so the body still renders and the file is `source_only` when those lines
  changed. Changed front matter lines count as shown when any key changed, since the
  disclosure cannot say which line a key came from, but only for a side the disclosure
  lists: a side whose front matter is not a non-empty mapping keeps its lines unmapped.
- **Off the server’s interpreter:** projections run in one long-lived child process
  (`diff/markdown_projection_worker.py`), started on the second projection or on a
  page’s prefetch, so a projection never holds the server’s GIL; the module records the
  measurement. A prefetch waits for the child to start; until it is ready, a reader’s own
  projections run in a thread.
  The same child renders every untrusted Markdown document, under a deadline
  ([What a Pin Serves](arch-source-sessions-and-pins.md#what-a-pin-serves)); a
  projection that finds such a render holding the child runs in a thread instead, and
  one waiting for the child goes before every waiting render.
- **Paint:** a file near the first screen waits for its projection with Source hidden,
  so its rendered view is the first thing its body shows, and nothing after it in the
  diff shows meanwhile (`WAITING_CLASS` in `diff/diff-markdown.js`): its body takes a
  height only its answer knows, so whatever followed it would move when the answer came.
  A page that keeps the diff out of sight for its first screen shows it at a bound
  (`holdMs`), with any file still waiting drawn so.
  The wait ends at a ceiling from mount, `RENDERED_WAIT_MS`, or the host’s hold for a
  file drawn alone (`waitMs`): a file still waiting shows Source and keeps it, its
  request goes on and its answer is kept for the reader’s choice of Rendered, and it is
  asked for no more by itself, which bounds a busy server’s retries.
  Conversation prefetches the projections of the first screen’s files.
  The diff draws a file’s Source rows only while they show (`onSource`), so Source
  hidden behind the rendered view is never drawn.

### Markdown Views

A Markdown projection has two coverage levels.
The route’s `full` answer carries every block.
Its `concise` answer keeps `CONTEXT_BLOCKS` unchanged blocks on either side of each
change and folds the runs between.
The browser draws both sides in Diff and the new side in Excerpt and Full.
A file’s Rendered or Source choice is independent of coverage.
`diff/markdown_views.py` is the one place that says which runs fold (`fold_runs`), and
the route answers either view from the projection it keeps
(`builtin_plugins/github/pull_rendered_diff.py`, `view=full|concise|prefer-full`).
Changes asks for `concise` and Docs for `prefer-full`, which the route answers in `full`
within `FULL_MAX_BLOCKS` and `FULL_MAX_BYTES` (`prefers_full`) and in `concise` past
either, saying which in the answer’s `view`.

- **Folds:** a `concise` answer lists its folds, each with where it starts, its blocks,
  its source lines, and the anchors of the headings it holds.
  A fold that spans `INLINE_FOLD_MAX_LINES` source lines or more is withheld: its blocks
  are left out, and the page asks for them with `blocks=I-J` when the reader opens it or
  follows a link to one of its headings, so a long document with a few edits answers in
  the size of its edits.
  The file’s progress mark shows while they are asked for, and a fold whose blocks do
  not load closes again with its bar saying so; a press asks again.
  A shorter fold comes with the answer and opens at once.
  The route assembles every answer, a range included, from the encoded blocks it keeps,
  so a fetched block is the bytes the projection made and passes the same sanitizer and
  hardening on the page as the rest.
- **One fold bar:** the page draws each fold with `foldExpander`
  (`builtin_plugins/diff/diff-fold.js`), the bar a code file’s long changed run folds
  behind, so both open and close alike
  ([Fold Expanders](../../design-system.md#fold-expanders)).
- **Windowing:** `diff-markdown.js` draws a file whole within `WHOLE_UNITS` and
  `WHOLE_BYTES`, the Full bounds, and past either a chunk at a time (`CHUNK_UNITS`,
  `CHUNK_BYTES`): the first chunk with its answer, and each later one, kept until then
  as a spacer of estimated height (`BLOCK_PX`, `BYTE_PX`, `FOLD_PX`), when the reader
  comes within `LOOKAHEAD` of it.
  A link to a heading draws every chunk through the one that holds it before it scrolls,
  so the rows above the target stand at their own heights; `beforeprint` draws the rest.
  Find in page and Select All reach only the chunks drawn, as the
  [large-content rules](../../large-content-rendering.md) record.
- **The reader’s place:** a Markdown file’s rows, to the diff’s place-keeping
  (`drawnRows` in `diff-view.js`), are its blocks in the page’s order, those inside an
  open fold among them, so the block at the pane’s top is the place wherever it is.
  Changing presentation draws the chunk that holds that block first (`drawBlock`), so
  the block keeps its place rather than its chunk’s first block;
  `tests/dom/diff-current-chrome.mjs` reads it in Chrome deep in a long document and
  inside a long open fold.

### YAML and JSON

`diff/structured_projection.py` parses both sides as the structured plugin’s tree view
parses them, YAML through the bounded loader (`frontmatter_yaml.py`), and merges them
into one tree (`structured-diff-v1`): each entry unchanged, `added`, `removed`, or
`modified`, a mapping or list whose entries differ.
A changed scalar is its old entry removed and its new one added.
Mappings align by key, a removed key drawn after the key it followed.
Lists align by value: Myers’ shortest edit script over each item’s identity, within a
work budget; past it a list’s middle is one replaced run.
In a replaced run, removed and added mappings and lists that share the most entries are
paired first, within their own budget, and the items between paired ones in order.
`builtin_plugins/diff/diff-structured.js` draws the tree with the structured plugin’s
own rows (`materializeRows` and `renderRowHtml` in `static/structured-tree.js`), opening
modified containers and whole added or removed values within a first-draw budget
(`ROW_BUDGET`), drawing each open container’s children a page at a time (`PAGE`) behind
a “more” row, and leaving unchanged ones closed with the tree view’s preview.
Rows are keyed by position, not key text, and a click redraws only the rows under the
row it changes.

- **Fallback:** a side that does not parse, YAML with a key twice in one mapping, or a
  pair past the byte, node, nesting, and entry budgets beside each constant is refused,
  and the file shows Source; a refusal of the route itself answers in the same format.
  The tree view refuses both of the first two as well, and shows its parse error.
  The YAML loader also refuses two keys one text spells, such as `1` and `"1"`, which
  the tree view reads as two keys and draws as the last.
  JSON with a key twice in one object reads as the tree view reads it, the last value at
  the key’s first place.
  Each value it hides is kept with the path of the object that hid it, and a change to
  one, or the same value hidden in another object, is `source_only`, as is an added or
  deleted file that hides any.
  Aliases and merge keys load within the loader’s budget on the value written out.
  [The structured diff measurement](../../../explorations/structured-diff/README.md)
  records the budgets over this repository’s history and the worst shapes.
- **Source only:** the projection reads no patch.
  Values are compared before they are made JSON-safe, with each type kept.
  A pair whose bytes differ and whose trees do not, as for a comment, quoting, or key
  order, is `source_only`, and so is one where two values differ only in what the tree
  does not draw, such as a date and the string that spells it, which are drawn
  unchanged. The page says either in one line above the tree.

A further format can supply an equivalent bounded, inert projection once its renderer
can map changes to what it draws.

## References

- [File Diff Format v1](file-diff-format/file-diff-format.md)
- [Git Reading and History](arch-git.md)
- [Source Sessions and Pins](arch-source-sessions-and-pins.md)
- [General diff rendering plan](../specs/active/plan-2026-08-17-general-diff-rendering.md),
  the design history of this pipeline
- [File patch formats](../research/archive/research-2026-08-19-file-patch-formats.md)
- [Rendering large content](../../large-content-rendering.md)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
