# Browsing Files

`metab ROOT` serves a folder and opens it in your browser; `metab FILE` serves the
file’s folder with that file selected.
The page has three main tabs: **Files**, **Pulls** for a GitHub repository, and
**Commits** for a Git repository.
This guide covers Files.
[Browsing history](browsing-history.md) covers Commits,
[reviewing pull requests](reviewing-pull-requests.md) covers Pulls, and
[the command-line guide](command-line.md) has every option.

## The Files Tab

The Files tab is a tree of the served folder beside the selected file or folder.

The selected file or folder has a header above its views: a quiet line with the Up
button and the folders that hold it, then its icon and its name, then its size and age,
and a folder’s file count, “4.7 MB · 138 files · 8m ago”.
In a narrow pane a long name is cut short, with the whole name in its tooltip, and the
values that do not fit leave the line from its end, each whole.
When the folder is a checkout of a repository on github.com, or a mirror of one, the
header’s upper right holds two marks: Metabrowser’s, the view you are in, and GitHub’s,
which opens the same file or folder on github.com.
A browser opens it in a new tab, since github.com cannot be shown inside the page, and
the macOS app opens it in your default browser.
In a narrow pane only the GitHub mark is shown.
It opens the page at the branch you are on when your last fetch saw that branch on
`origin`; otherwise it opens your commit, and its tooltip says that origin had no such
branch at your last fetch, so that commit may not be on github.com either.
It opens a page whether or not github.com has one: a file Git ignores or has not been
told about, or a file inside an archive, opens a missing page there.
The link is set when the page loads, so after switching branches, reload the page.

- **Rows:** a file row shows its size and age; a folder row shows its file count, total
  size, and newest change, for everything beneath it.
  Age is drawn in a color that runs from the freshest files to the oldest.
- **Opening:** click a row, or move with the arrow keys or `J` and `K`. Enter or Space
  opens or closes a folder; Left and Right collapse and expand.
  A folder with many children shows them a page at a time.
- **Addresses:** each file and folder has its own `/view/<path>` address, so the
  browser’s Back, Forward, new tab, and copied links work as they do anywhere.
  A fragment selects a place in a document, such as a heading.
- **Up:** `U`, or the header’s Up button, opens the folder that holds the file or
  folder.
- **Home:** the folder’s name at the top of the navigation pane, or `0`, shows the
  folder as a fresh load shows it: Files in front, every filter and Group by at its
  default, and every tab back at its first view.

Large trees are indexed in the background: the first view does not wait for the whole
walk, and counts fill in as it goes.
The index stops at 500,000 files; past it, the tree and Quick Search say that the index
is incomplete. [Keyboard shortcuts](keyboard-shortcuts.md) lists every key.

### Folders: Overview and Treemap

Selecting a folder shows two views, **Overview** (`O`) and **Treemap** (`M`).

**Overview** has a **File Overview** section and, when the folder has one, its
**README** rendered as a document, with the table of contents it has opened as a file;
an entry scrolls the Overview to its heading.
File Overview counts what the folder holds:

- **Files, Ignored, and Total:** the folder’s files, the files Git ignores, and both
  together, each drawn as a bar split by file-type family.
- **The type summary:** a legend of the largest file-type families, such as Python,
  Markdown, and JSON, up to nine, each at least 1% of what is shown, then **Other** for
  the rest; **Details** opens the full table, where each family lists its extensions.
- **Files or Bytes** switches every figure between counts and sizes, and **Show
  ignored** adds the ignored files to the type summary.

**Treemap** draws the same folder as nested rectangles sized by bytes or file count,
colored by the same families.
Click a folder’s rectangle to go into it and a file’s to open it.
The Files or Bytes choice and Show ignored apply to Treemap too.

The Details table lists each family’s extensions; the
[File Rollup Format](project/architecture/file-rollup-format/file-rollup-format.md)
defines the families.

### Filters and the Recent View

The bar above the tree groups and narrows it:

- **Group by** splits the tree into headed sections, one full tree per group under the
  active filters: **By age**, in bands of how recently a file changed, or **By file
  type**, with Documentation first.
  **No grouping** is the default.
  While its menu is open, `N`, `A`, and `T` choose No grouping, By age, and By file
  type.
- The chevron opens the filters, and Clear beside it shows while any is set:
  - **Modified within** keeps files changed within a window, from Live to the past
    month. Live means changed in the last 90 seconds.
  - **File type** keeps the categories, families, or exact extensions you choose.
  - **Minimum file size** keeps files at least that large.
  - **Show ignored** is on by default and shows gitignored files dimmed; turn it off to
    hide them.
- **Clear** removes every filter and turns Show ignored back on; it keeps the grouping.

A type or size filter keeps the tree’s shape, shows only matching files and the folders
that hold them, and says how many files match.
Filtering runs over the whole index, not only the folders you have expanded.

Setting **Modified within** turns the tree into the **Recent** view: only the matching
files, grouped by folder and sorted newest first.
A chain of folders that each hold one folder shows as one row, and a folder whose files
were all written at about the same time starts collapsed.
The view holds at most 5,000 files; when more match, it leaves out gitignored files
first and says how many matched.
A Git revision has no modification times, so a file’s age is the time of the last commit
that changed it, as a hosting site’s file list shows, and a folder’s the newest of its
files’. They come from `git last-modified`, which needs Git 2.53 or newer, and are read
in the background after the page opens, so a file shows its age a moment after it shows
its name; with an older Git a revision shows no ages, and `metab --doctor` says what to
upgrade. With file ages, Modified within and By age work on a revision as on a folder: a
file is in a window or a band by its last commit, and a file whose last commit is not
known (a shallow clone, or a read that has not finished) is in a last group, Undated,
which says what it is older than when that is known; the page draws again when the ages
arrive, the open file’s age included.
Until then the Modified within counts read “…”, and the Undated group is named for it.
The line that counts the files a filter keeps says that the ages are being read, why
they could not be read when a read failed, and how many files could not be dated when
some could not, and the Undated group says so too.
A folder in a group or a window is dated by the newest of the files that put it there,
and a submodule has no age, so it is in no group.

The same filters are available from the command line:
`metab ROOT --walk --type .md --age 7d`.

## Reading Files

Each file opens in the view its kind declares; a kind with several views shows them as
tabs, each with a key.
`V` and `S` are the rendered view and the source on most kinds; an agent log gives its
Session, Log, Charts, and Raw JSON views keys of their own.
`metab ROOT --show PATH` prints the kind and views a file gets.

| File | Views |
| --- | --- |
| Markdown (`.md`) | Document, rendered by KPress, and Source |
| Mermaid diagrams (`.mmd`, `.mermaid`) | Diagram and Source |
| JSON and YAML | Tree, a collapsible view of the parsed structure; Table, a list of records as a table; and Source |
| JSONL logs | Log, a timeline of events, and Raw JSON; a coding agent’s session log opens on Session and adds Charts, and Codex’s compressed rollouts (`rollout-*.jsonl.zst`) open as Session and Log |
| Event logs (`events-*.jsonl`) | Timeline, Latency, By kind, Errors, and Raw JSON: Metabrowser’s own log of what it served and how long each took |
| CSV and TSV | Table and Source |
| Code and text | Source, with syntax highlighting where a grammar exists |
| Images | Image |
| PDF | PDF |
| HTML | Preview, in a sandboxed frame, and Source |
| Patches (`.patch`, `.diff`) | Diff, the same view commits and pull requests use |
| SQLite databases, whatever their name | Table lists tables and views and opens their rows. Schema shows definitions and relationships. Info shows the access mode, database details, and SQLite version. |
| An fsqlite store’s `fsqlite.json` | Table, Schema, and Info, for the store’s database |
| Other binary files | Bytes, a view of the file’s bytes |

A patch file also expands in the tree like a folder, with one row per changed file.
A compressed copy of a supported file, whose name ends in `.gz` or `.zlib`, opens as the
file it holds. A large source file opens with its beginning and a **Load more** button.
Plugins add views for other formats ([plugin authoring](plugins.md)).

### SQLite

Metabrowser opens SQLite databases read-only in a separate process.
When committed write-ahead log (WAL) frames cannot be read, Table and Schema refuse the
incomplete read. Info shows the access state and reason.

SQLite can create a new log or index file if a live owner closes between the final check
and the reader opening its connection.
Info reports the race when detected.
A read in progress when the owner closes can also leave the existing log and index files
in place.
[SQLite guest-read measurements](../explorations/sqlite-guest-reads/README.md#process)

### Markdown

The Document view renders Markdown with KPress: headings with a table of contents,
tables, footnotes, highlighted code, math, images, and YAML frontmatter, which shows as
a closed **Frontmatter** disclosure.
Open **Frontmatter** or choose **Explore YAML** or **Explore JSON** above an eligible
code fence to inspect it in Table, Tree, or Source.
Source highlights YAML and JSON with the same colors as diffs and keeps the Markdown
file’s line numbers.
Hover over a table row or focus it with the keyboard to reveal its copy button.
When the window is wide enough to show the document as a card, a print button at the
card’s top right prints the document without the rest of the page, and the README on a
folder’s Overview has the same button.
Command-P, or Control-P outside macOS, prints whichever view is shown, at any width.

A fenced `mermaid` code block is drawn as a diagram, as GitHub draws it, in the page’s
light or dark theme.
Hovering a diagram shows buttons to copy its source, show the source in its place, and
open it in a dialog where the buttons, the arrow keys, `+`, `-`, `0`, the scroll wheel,
a pinch, and dragging zoom and pan it.
A diagram Mermaid cannot parse shows Mermaid’s message above its source.
Mermaid loads only for a document that has a diagram.
With active content off, each diagram is drawn as a picture, so its text cannot be
selected, and Mermaid’s `click` links and scripts never run in either mode.
A `.mmd` or `.mermaid` file opens as one diagram, drawn the same way, with its source a
tab away.

Links resolve the way GitHub resolves them:

- **Relative and root-relative links** open the file they name from the document’s own
  folder or from the served root, including headings, images, spaces, and Unicode.
  A link to a missing file opens a not-found page; nothing guesses a target by its name.
- **GitHub links to this repository** open their page in Metabrowser when it shows the
  same thing: a file or folder on the branch or commit being browsed, the repository’s
  root, a pull request and its Changes and Checks, a commit, and the list of pull
  requests. A link to another branch, a tag, an issue, or a comparison stays a web link,
  since there it would show the branch being browsed instead; so does every other link
  to the web.
- **Published sites:** when an MkDocs, Docusaurus, or Jekyll configuration sits at the
  served root, a link to a published page such as `/guide/` opens the source file behind
  it, if no file has that exact path.
- **PDFs:** a link to a `.pdf` opens the PDF’s own page in Metabrowser.
  An embedded one, such as `![](report.pdf)`, `<img src="report.pdf">`, or
  `![[report.pdf]]`, is a card with the PDF’s first page, its name, and its page count,
  or why there is no image, and a View link to that page; a document never opens the
  PDF’s viewer itself.
  A PDF named without `.pdf` embeds as any other file does.

Obsidian wiki links work too:

- `[[note]]`, `[[note#heading]]`, `[[note#^block]]`, and `[[note|label]]` open a note,
  heading, or named block.
  A name resolves to an exact path, then to a note in the document’s folder, then to the
  only note in the tree with that name.
  A name that matches several notes or none says so, with the candidates, instead of
  picking one.
- `![[note]]`, `![[note#heading]]`, and `![[note#^block]]` embed that note, heading, or
  block in the document.
  Embeds nest, within limits on depth, count, size, and time; past them, or in a cycle,
  the embed says why it stopped.
- `![[image.png]]` and other media embed the file, and `![[report.pdf]]` shows a PDF’s
  first page, as an embedded PDF does above.

HTML a README writes for its layout on GitHub lays it out here as github.com does:
`align` on a paragraph, `div`, heading, image, or table cell or row, and `width` and
`height` on an image or a table cell, such as a logo in `<p align="center">` drawn at
`width="192"`, an image floated by `align="right"`, or a badge sized by its `height`.
This holds with active content off too.
An `<img>` given both a `width` and a `height` draws at that size, as on github.com,
while a wiki embed sized as `![[image.png|640x480]]` keeps the image’s proportions.

With active content off (`--untrusted` or `--no-active-content`, and always for a
repository URL), a document renders without its styles and scripts, and with a time
limit: a document that takes longer than a few seconds to render shows its source
instead, under one line saying so.
Reloading it shows the source again at once for a while, since the server remembers it.
The same line says when the renderer is busy with other documents or could not start;
reloading the page then tries again.

With active content off, a document shows its images from the web over `https`, as on
github.com, such as a README’s badges, and the browser fetches them with no referrer
sent. A badge that links somewhere keeps its link.
An image the page does not load, one over `http`, is its alt text in a small chip with
an image mark, in the link it was in or in a link to the image, and hovering the chip
shows the address. Those requests tell the image’s host that you opened the page, so the
Metabrowser menu has **Block remote images**, off unless you tick it: every such image
is then its chip, and the page’s policy refuses an image from another site, so the
browser sends no request for one.
It applies to what is untrusted, a repository opened from its URL, a pull request’s
text, a commit’s, a Markdown diff, and a folder served with `--untrusted`; your own
folder’s Markdown is not changed.

### Data, Logs, and Code

- **CSV and TSV:** Table shows the file as a table: press a column’s header to sort it
  either way, open its menu to filter or hide it, search the text, and press a row, or
  Enter on it, to see every value of that row.
  `null`, an empty value, and a missing one look different, and a value too long for its
  column shows whole in its tooltip.
  The table’s sort, filters, search, and columns are in the page’s address, so a link or
  Back returns to them.
  **Source** shows the file’s text.
- **JSON and YAML:** Tree shows the parsed document with collapsible levels and draws
  only the rows in view.
  **Table** (`A`) shows a file whose top level is a list of mappings as a table, one row
  a mapping and one column a key, with the CSV table’s sort, filters, search, and
  records; a nested value is its JSON in the table and a collapsible tree in the record.
  A YAML file of several documents that are mappings is a table of them, one row each.
  Only such a file has the tab: Metabrowser decides from the file’s start, so a list
  that begins with a mapping but holds something else further on has the tab, which then
  says why it shows no table.
- **JSONL:** Log lists one row per event, with filter chips by kind of event, such as
  text, tool calls, and tool results, and each row expands to its raw JSON. For the
  session logs of Claude Code, Codex, Gemini CLI, and Pi, Metabrowser shows the agent in
  the header, opens on **Session**, and adds **Charts**.
  [Working with agents](working-with-agents.md#reading-agent-logs) has more.
- **Event logs:** a file named `events-*.jsonl`, which a served `metab` writes about
  itself, opens as spans nested under what started them, the slowest spans, each kind’s
  timings, and failures by cause.
  [Browsing the log](realtime-debugging.md#browsing-the-log) has more.
- **Code and text:** Source highlights common programming, markup, and configuration
  languages, and Lean, by file extension, and names such as `Makefile` by file name; it
  shows plain text for the rest, `.log` files among them.
  A diff of such a file is highlighted the same way.

### HTML

Preview shows the page in a sandboxed frame that cannot reach Metabrowser’s own page.
**Open as full page** opens the same document as its own browser tab, under the same
sandbox. With active content off (`--untrusted` or `--no-active-content`), HTML files
show Source only; [the command-line guide](command-line.md#serving) explains those
settings.

## Live Updates

The server watches the served folder and streams changes to the page.

- **The tree, counts, and Recent** update as files are created, changed, and removed; a
  newly arrived row is highlighted briefly.
- **Overview and Treemap** recount when the folder’s contents change.
- **An open table** (a CSV or TSV file, and any other table) refreshes when its file
  changes, whether or not the file is ignored or deep in the folder: changed rows flash
  once, new rows above where you are reading are offered rather than pushed in, and your
  scroll position, focused row, open menus, and unsent filter text stay.
  The **Live** button above the table pauses it, and counts the changes it holds back.
- **A container’s entries**, such as a patch file’s changed paths, are read again when
  the file changes.
- **Any other open file** shows its new content the next time you open it, or when you
  press **Refresh**.

**Refresh**, the circular arrow at the top of the navigation pane, is there on every
tab. It reads the tree and the open file or folder again, and everything else the page
holds, starting with what is on screen.
Where the foot of the navigation pane says when the origin or the mirror was last
fetched, it fetches from the origin first.
Its key is `1`.

Files that a running process writes get more.
Metabrowser watches the files in a folder named `.logs` or `.state` whose names end in
`.csv`, `.json`, `.jsonl`, `.md`, `.pid`, `.yaml`, or `.yml`. One that is being written
shows an activity dot in the tree, and when it stops, an open view of it reloads.

### Tailing a JSONL Log

A JSONL log under `.logs` or `.state` that is being written tails itself: new events
append to its Log view as the process writes them, without a reload.
The header shows the run’s state: **Live** while the log is being written, **Running**
while it has not recorded its end, **Done** or **Failed** for the end the log records,
and **Run ended** when the tail closes because the file was removed or replaced.

- A `.pid` file beside the log names its writer; when that process has exited, the log
  is not tailed.
- Compressed logs, and very large ones, open but are not tailed.
- Charts count the events there were when they loaded; they do not grow with the tail.

### When a Live Update Is Missing

1. Check that the file is inside the served folder and that no filter hides it,
   including Show ignored turned off for a gitignored file.
2. Check whether the file is under a tool directory the file watcher skips, such as
   `node_modules`, `.venv`, or `__pycache__`. The tree can list those files, but a
   change to one does not update the page live.
3. Press **Refresh**, or reload the page.
4. If the server log says it is refreshing slow browser connections after a queue
   overflow, a burst of changes outran the page, which then reconnects and catches up
   from a fresh snapshot.
   If that repeats, report it with the size of the tree and its filesystem.

[Real-time debugging](realtime-debugging.md) has the diagnostics for a deeper look.

## Quick Search

Press `T` or `/` to find a file by name or path.
Matching is fuzzy, so the letters you type need only appear in order, and matches in the
file name rank above matches elsewhere in the path.
Up and Down move through the results, Enter opens one, and Escape closes the search.

Quick Search searches the files indexed so far, so in a large tree it grows as indexing
proceeds and says when the index is incomplete.
It leaves out gitignored files.
In a GitHub repository it also finds pull requests: type `#` for recent ones, then a
number or words from the title
([reviewing pull requests](reviewing-pull-requests.md#find-a-pull-request-with-quick-search)).

## Browsing a Remote Host

To browse a folder on another machine, run `metab` there and view it here:

```shell
metab --remote example-host --path /srv/shared-files
```

`metab` connects with SSH, starts `metab` on the host bound to the host’s loopback
address, so other machines cannot reach it, and tunnels that port to `localhost`, where
the page opens in your local browser.
Ctrl-C closes the tunnel and stops the remote server, and so does losing the connection.

- **On the host:** install the same Metabrowser version, so `metab` is on the SSH
  session’s `PATH` or in `~/.local/bin`. If it is missing, the command says so.
- **Several sessions** coexist: each takes the next free port on both machines.
- **SSH settings** come from your SSH configuration; `--ssh-options` adds flags, and
  `--gcp` connects with `gcloud compute ssh`.

[Remote directories](command-line.md#remote-directories) in the command-line guide has
every option.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
