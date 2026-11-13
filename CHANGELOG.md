# Changelog

All notable changes to Metabrowser are documented here.

## Unreleased

- Switching to the Commits tab selects the newest commit and shows its detail, every
  time, by a click, its shortcut, or Back onto the tab, even after you read an older
  commit there. It used to show “Select a commit to preview” on the first visit and
  return to the last commit you read after that.
  A link or address that names a commit still opens that commit.
  The page you were reading stays on screen until the commit is ready, and a repository
  with no commits says “No commits yet.”

- The folder’s name at the top of the navigation goes home from any tab: clicking it, or
  pressing Enter on it, shows the Files tab at the served root, with the tree scrolled
  to the top. It no longer reloads the page, which from the Commits tab with no commit
  selected came back to Commits.
  Back returns to where you were, and a Command-click or middle click still opens the
  root in a new tab. Screen readers announce that it goes home, and so does its tooltip.

- A pull request’s **Conversation** shows its description, and the comments and reviews
  on its first screen, as Markdown from the first paint: the page waits up to 200 ms for
  them, out of sight, keeping the page it replaces on screen meanwhile, and shows plain
  text only past that wait.
  The first screen is the new page’s own top, wherever the page it replaces was
  scrolled. A page shown first as a description preview waits for its description alone.
  A cold link or reload keeps its loading heading, and its loading blocks if they have
  appeared, where they are until the pull request’s header and conversation show
  together, so nothing moves and the body is never empty in between.
  A rendered text is kept for the rest of the session, so a revisit, Back, Forward, or a
  refresh that leaves a text unchanged shows it at once without asking again.
  When the full record replaces a description preview, the description stays where it is
  and only the sections below it change; ages in kept cards and commit rows still read
  as of each paint. Commits that arrive after the conversation has painted are added
  after everything shown, so nothing you are reading moves; a conversation painted with
  its commits already known, as when you return to it from another tab, places them
  among the comments and reviews in GitHub’s order.
  The state badge shows the fresher of the cached record and the repository’s list of
  pull requests, so a stale record of a merged pull request no longer shows Open first.

- A pull request’s **Changes** with rendered Markdown appears once the first screen’s
  Markdown files are drawn, waiting up to 200 ms, so the files below them no longer
  shift as rendered diffs arrive.

- In the Pulls tab, a pull request’s changed files open in one step at their full height
  when Metabrowser holds the list.
  A list GitHub takes a while to return is offered on the tree’s line as **Show N
  files** instead of being drawn by itself, and so are its later pages (**Show N more
  files**) and a refresh that changes a list already shown, which floats over the tree’s
  top: the rows below never move while you are not interacting with the list.
  A refresh that leaves the same files is drawn at once, since it moves nothing, and the
  tree’s notices and **Retry** stay while something is offered.

- For plugin authors: the diff view’s render context accepts `markdownHoldMs`, how long
  the first screen’s Markdown files wait for **Rendered**, and the mounted diff’s handle
  adds `firstScreen()`, a promise that settles once none of those files is still
  waiting. A page can keep the comparison out of sight until then.
  Each hold of the pull request page records a span with how long it held and why it
  ended (`githubPull:firstPaintHold`, `githubPull:changesHold`,
  `githubPulls:openingHold`, and `githubPulls:lateRowsHold`).

- A pull request’s Changes no longer says “Rendered diff unavailable.
  Showing source.” above a Markdown file it cannot render, or “Could not render Markdown.
  Select Rendered to retry.”
  when rendering one fails.
  Such a file shows Source and says nothing: one that can only show Source has no
  **Rendered** | **Source** chooser, as before, and one whose rendering failed keeps the
  chooser, so choosing **Rendered** tries again.
  A failed rendering is logged to the browser console.

- Clicking a toggle no longer selects text, even on a double or triple click.
  A folder in the Files tree, a rendered Markdown diff’s “5 unchanged blocks”, a
  section’s chevron, a diff file’s bar, a log event, and every other control that shows
  or hides content leave their own label and the text beside them unselected, in Chrome
  and in the macOS app, and what they reveal stays selectable.
  In the macOS app, a diff’s or a Source view’s line numbers, tabs, chips, and tree rows
  are now kept out of a selection too, as they were in Chrome: WebKit had ignored every
  rule that did so. A plugin marks such a control with the host’s `disclosure-toggle`
  class; see
  [Disclosure Toggles Never Select Text](docs/design-system.md#disclosure-toggles-never-select-text).

- A merge between two branches reads source → target, left to right, everywhere it
  appears. The Pulls list shows `claude/x → main` instead of `main ← claude/x`, and a
  pull request’s header reads “octo wants to merge 1 commit: wip → topic” instead of
  “wants to merge 1 commit into topic from wip”.
  The arrow is named “merges into” for screen readers, stays left to right in a
  right-to-left page, and stays whole in a narrow Pulls row, down to the narrowest
  navigation pane: the row’s author and branch names now shorten with an ellipsis, and
  where even that is too wide the branches move to a line of their own, so nothing is
  clipped; the arrow used to disappear from a row too narrow for its line.
  Plugins draw the same notation with the new SDK helper
  `mergeRefs(source, target, options)`; see
  [Merge Direction](docs/design-system.md#merge-direction).

- Branch chips are blue.
  A pull request’s base and head, the branches in the Pulls list, a mirror’s branches,
  and the branch selector no longer share the purple of a merged pull request.
  A checkout’s own local branches, in its history, are a blue-green instead of blue, and
  the history line of the branch you are on stays blue.

- The word in a badge is centered in its box instead of sitting about a pixel high: a
  pull request’s Draft, Open, Merged, or Closed, its review and check states, and a file
  header’s badges such as Gzip.
  The badges keep their size.

- A source file’s **Load more** is faster in Safari and other WebKit browsers.
  The text it loads goes into the page in pieces of at most 64 KiB, the size WebKit’s
  own HTML parser makes, and on a 16 MiB file each click takes WebKit a quarter to two
  fifths of the time it did.
  In those browsers the line numbers after **Load more** are also right again: numbers
  left over from the opening window no longer repeat after the new ones, and a line
  anchor’s highlight stays on its line.

- `metab ROOT --exit-on-eof` stops serving when its stdin closes, so a program that
  starts the server and holds its stdin, such as the macOS app, leaves no server running
  when it exits, even by crashing.
  The watch begins before startup reads the disk or acquires a Git source, so a server
  still starting stops too.
  See
  [Stopping When the Parent Exits](docs/command-line.md#stopping-when-the-parent-exits).

- Stopping a server, by Ctrl-C, a hangup, or `--exit-on-eof`, no longer waits on a
  stderr that is full because nothing reads it: the stop notice is dropped and the
  process stops.

- Stopping a server by Ctrl-C, a hangup, or `--exit-on-eof` now also kills a fetch’s or
  clone’s Git, or a `gh`, whose start was under way at that moment, which used to keep
  running and could keep holding the store’s fetch lock; no new one starts once the stop
  has begun. The stop finds them from the system’s list of the server’s children, so it
  ends promptly even when the server’s event loop is stuck.

- The Pulls tab no longer stays stuck on “The metadata catalog could not be written”
  after a different Metabrowser build used the same cache.
  A list of pull requests this build cannot use, because it is damaged or from another
  schema, is rebuilt at the next refresh, and the server log says why.
  A list a newer Metabrowser wrote is left as it is for that build, and the refresh ends
  with the new outcome `newer_cache`, without asking GitHub for anything, and says to
  upgrade. A list whose versions cannot be read, such as a write-ahead-log database, is
  left as it is too, and the refresh ends with the new outcome `unknown_cache`. A cache
  that refuses a write still ends `cache_unwritable`, but the message of the list, a
  pull request’s record, its changed files, the previews, and stack metadata now says
  why and names the repository and the command that clears its GitHub cache.
  That command is the new `POST /api/plugin/github/cache-clear`:
  `echo '{}' | metab https://github.com/owner/repo --api /api/plugin/github/cache-clear --data -`,
  or `metab .` in a checkout.
  `--data -` reads a request body from standard input, and `--data` reads at most the
  largest body a route accepts, 96 MiB and 64 KiB by default, refusing a longer one.
  An unexpected error in a refresh of the list is reported as one, which the server log
  names, instead of as `cache_unwritable`.

- A folder’s File Overview is shorter.
  Under the Files, Ignored, and Total bars it shows a legend of the five largest file
  types, each a dot in its color with its name and share, plus **Other** for the rest,
  as GitHub’s Languages box does.
  The full table of groups, types, and **N more** rows is behind **Details**, which
  starts closed and stays as left while the folder is open.
  The “Share of Total” line is no longer shown; screen readers still hear it as the name
  of the legend and the table.
  `GET /api/rollup` adds `file_type_legend`, which names the legend’s families for each
  measure and population, so `metab --api` shows the same choice the page makes.

- `L` switches a diff between Split and Unified, in a diff file, a commit, and a pull
  request’s Changes, exactly as its layout control does: where Split does not fit, `L`
  chooses it with its sideways scroll, and the choice is remembered.
  While Shift is held, the key shows on the layout it would choose.
  Help lists it under Controls.

- A pull request’s page answers to `C` for Conversation, `G` for Changes, and `H` for
  Checks, and shows those keys on its tabs while Shift is held.
  A key moves the address as a click on the tab does, so Back returns to the tab before.

- Plugin SDK: `metabrowser.shortcuts.attach(element, spec)` gives a control of a plugin
  view a letter key, listed in Help and badged while Shift is held, and returns a handle
  with `retarget()` and `detach()`; an `AbortSignal` in the spec detaches it too.
  A view may attach before the shell’s keyboard support loads.
  Malformed input throws an error starting with `shortcuts.attach:`; an attachment made
  before the keyboard support loads is checked when it loads, and a malformed one is
  logged to the console with that prefix instead.
  A letter the shell reserves, `T`, `J`, `K`, `U`, `W`, `X`, `Y`, `A`, `N`, or `P`, is
  refused with one console warning, and a shell key or an earlier plugin’s key wins a
  letter two shown controls hold.
  `METABROWSER_SETTINGS` serves the reserved keys as `RESERVED_SHELL_KEYS`.
  `PLUGIN_SDK_VERSION` remains `0.7`.

- Hold Shift outside a text field to see the keys: a keycap appears on each control a
  key reaches now, and the shortcut strip lists the common keys that are live.
  Releasing Shift, a click, or a scroll hides them, and `?`, capitals, Shift+click, and
  Shift+wheel never show them.
  A file’s view tabs answer to their letters, such as `D` and `S` for a Markdown file’s
  Document and Source, `O` and `M` for a folder’s Overview and Treemap; `U` opens the
  parent folder; `Y` copies the file’s path, or a commit’s revision; `X` opens the file
  type filter and `A` the modified-within filter; and `W` opens a pin’s branch and tag
  switcher. A key does nothing while its control is not on screen.
  `1`, `2`, and `3` now also move focus to the panel’s rows.
  Help lists the new keys under View tabs, Controls, and Filters, and ends with a note
  about Shift. The main pane’s view tabs are a tablist to assistive technology.

- The keys Shift reveals are drawn in the yellow that marks a newly arrived row.
  Each keycap sits over the end of its own tab, button, icon, or breadcrumb, never over
  the file name, note, or path after it, and is translucent, so the label under its edge
  still reads; a copy button that otherwise shows only on hover shows while Shift is
  held. The shortcut strip turns the same yellow and grows upward over the bottom of the
  navigation pane, so the tree does not move.
  Text on the yellow keeps at least 4.5:1 contrast in both themes.
  The keycaps fade in briefly, appear at once under reduced motion, and never print.

- Every keyboard shortcut is a single key, and Shift no longer changes what any of them
  does. `⌘1`, `⌘2`, and `⌘3` no longer open Files, Commits, and Pulls; `1`, `2`, and `3`
  still do, and the browser keeps Command and Ctrl with a digit for its own tabs.
  A pull request’s stack moves from `⇧J` and `⇧K` to `N`, toward the stack’s top, and
  `P`, toward its base, so `J` and `K` on a focused Pulls row always move the row.
  In the file tree, `⇧↑` and `⇧↓` move one row, as `↑` and `↓` do, and Home and End
  still jump to the first and last row.
  Shift with `T`, `J`, `K`, an arrow, or a digit now acts as the key alone, even where
  Shift+`1` types `!`, and `/` opens Quick Search on layouts that type it with Shift.
  In a text field, Shift with an arrow still selects text.
  The removed keys shipped in 0.12.0 and have no aliases.

- A plugin manifest’s `[[view]]` may declare a one-letter `key` for its tab, and every
  view of a built-in kind with more than one view declares one: Markdown’s Document `D`
  and Source `S`, structured data’s Tree `R` and Source `S`, HTML’s Preview `P` and
  Source `S`, an agent log’s Log `L`, Charts `C`, and Raw JSON `R`, other JSONL’s Log
  `L` and Raw JSON `R`, and a folder’s Overview `O` and Treemap `M`. `/api/file` serves
  it, lowercase, as `views[].key`, and `metab --show` and `metab --plugin NAME` print
  it. The manifest loader refuses a key that is not one letter or that the shell reserves
  everywhere: `T`, `J`, `K`, `U`, `W`, `X`, `Y`, and `A`. When two views of one kind
  share a key, the first keeps it; the later view, like a `pull-request` view that takes
  the stack keys `N` or `P`, is served without a key, and `metab --doctor` reports it,
  naming the plugin that holds a shared key.
  A view left alone, as HTML’s Source is without active content, has no tab and is
  served without its key.
  `PLUGIN_SDK_VERSION` remains `0.7`.

- A pull request that is already shown no longer shows a spinner while it refreshes.
  Its page, the changed files under its row, and the Pulls list keep what they show and
  refresh in the background; the line that says when it was fetched, the folder and file
  names, and the list’s “Updated” line breathe gently until the refresh lands, and stop
  under reduced motion.
  A description preview shows gray blocks for the comments and checks still to come.
  Nothing says “may be out of date” any more: stale data is being refreshed, and a page
  left open refreshes again each time it goes stale.
  A view names a problem only when it cannot refresh: offline, GitHub’s rate limit with
  the time of the next check, or the last failure with **Refresh** or **Retry**.

- A cached pull request is checked against the repository’s list of pull requests, which
  says what changed on GitHub since: one that has not changed is current however long
  ago it was read, and one that has, or whose head moved, is refreshed at once.
  An open pull request’s checks, statuses, and mergeability, which that list does not
  track, are read again on their own once a minute while its page is shown.
  A pull request’s list of changed files stays current across comments and reviews and
  is read again when its head or base moves.
  `GET /api/plugin/github/pull` adds `verified_at`, `verified_by`, `head_moved`, and
  `checks_pending`; each row of `GET /api/plugin/github/pulls` adds `head_oid`; and
  `GET /api/plugin/github/pull-files` sets `head` for GitHub’s list and adds `base_ref`.
  A pull request’s page says `Checked just now · fetched 3 h ago` when the list vouched
  for a record read earlier, keeps that list scanned while it is shown, and says
  `New commits were pushed; updating.` over the diff it keeps when the head moved.
  `GET /api/plugin/github/pull` answers a poll with `304` across a scan, and carries the
  check in `x-metabrowser-verified` instead.

- The Pulls tab asks Metabrowser to prefetch the pull requests a reader is likely to
  open next, the rows around the one opened and the top of the list, and their changed
  files, through the new `/api/plugin/github/pulls-prefetch`. It runs behind everything
  the reader asks for, within hourly caps, and stops while less than a quarter of the
  account’s GitHub rate limit remains.

- A pull request’s header leaves out an updated age that reads the same as its opened,
  merged, or closed age, and keeps the exact updated time in that age’s tooltip.
  Conversation commit hashes match the surrounding metadata size.
  A check on **Checks** shows its name, then a link that says where its details open:
  **View action on GitHub**, **View on GitHub**, or **View details** on the check’s own
  site. The pull request’s **View on GitHub**, a check’s link to GitHub, and a
  conversation commit hash are muted, with a leading GitHub mark.
  A pull request’s title is bold in normal text ink in the Pulls list and the stack
  menu, as it is in its page’s heading, whatever the row’s state.

- Opening a pull request’s **Changes** tab fetches a missing comparison automatically.
  A served checkout reuses a healthy cached store or borrows Git objects without
  changing the checkout.
  If preparation fails, the tab reports the reason and offers a retry.

- Once a served checkout has a comparison store, its **Conversation** prepares a fresh
  pull request’s comparison in the background, fetching only that pull request’s head
  and base, and gives way to anything the reader asks for.
  Reading **Conversation** never creates a store or runs Git: only **Changes** does.

- A cold open of a repository another Metabrowser process is acquiring says that it is
  waiting, and then uses that process’s store.

- In a pull request’s **Changes**, **View file** and **View at base** open the file at
  that exact commit on its own page, and no longer switch the commit the server serves.
  A link stays valid after the pull request moves on, for the last 16 comparisons.
  A file at the commit a mirror’s page shows still opens in the app’s viewer.
  A Markdown file whose rendering would cost more than a few hundred milliseconds, such
  as a long task list or thousands of very short lines, opens as Source.
  Its code blocks show as plain text, as on any inert page, whatever language they name.

- A pull request’s **Changes** shows Markdown files **Rendered** by default: changed
  blocks are shown as removed and added, with changed words marked, and a changed list
  item or quoted paragraph is shown on its own.
  **Source** remains one click away, and is used for files with raw HTML, task lists,
  footnotes, or more than 48 KiB of Markdown.
  A file that can only be shown as Source has no **Rendered** | **Source** chooser.
  When the source changed in a way the rendered view cannot show, such as a link
  destination or an HTML comment, the file and the block say so.
  The first screen is rendered in the background while you read **Conversation**.

- Each browser tab is titled by what it serves, so windows can be told apart: the
  folder’s name, or a cached mirror’s repository name (`tbd #123` on a pull request’s
  head), then `• Metabrowser`. `GET /api/identity` reports that title with a short name,
  a full name (the folder’s path with `~`, or the mirror’s origin and ref, such as
  `github.com/jlevy/tbd@main`), and whether it is a local folder or a cached mirror.

## 0.12.0

- Configuration and repository-cache contract names use `metabrowser.config` and
  `metabrowser.cache`, independent of their hosting location.
  An unreadable config names its location and explains how to recreate it without
  discarding cached repositories.

- Plugin template rendering waits for its shared library before plugin code runs, so a
  directly opened custom view works before idle asset prefetch finishes.

- Treemap explains when a hidden folder or a path through a symbolic link is outside the
  file index, using the same message as File Overview without requesting totals.

- Cache validators accept Unicode paths and arbitrary content identities, including
  progress responses, while retaining build and source isolation and conditional reads.

- Expanded folders that failed to load while the server was unavailable retry when an
  authoritative inventory snapshot arrives after reconnection.

- **Breaking:** Cache and configuration now use separate XDG locations on macOS and
  Linux: `~/.cache/metabrowser` and `~/.config/metabrowser/config.yml`. Use
  `--cache-dir` / `METABROWSER_CACHE_DIR` and `--config-dir` / `METABROWSER_CONFIG_DIR`
  for exact overrides.
  `METABROWSER_HOME` and the old home layout are no longer read; existing files are left
  untouched. Cache initialization preserves configuration.

PR and Git navigation:

- Document and Source use the same outer gutter.
  Markdown card borders align with display tabs while retaining KPress’s normal padding
  inside the card.
- Files, Commits, and Pulls appear in that order and open with `⌘1`, `⌘2`, and `⌘3`.
  Help lists plain digits for browsers that reserve the Command chords.
- Pulls resumes incremental GitHub updates after reconnect and shows one connection
  status with a **Reload** action.
- Pulls loads older rows automatically as you approach the end of the list.
- Space on a focused pull request expands or collapses its changed files in place.
- Comparisons load nearby patches ahead of scrolling and show a notice for a failed
  patch or truncated result.
- Pull request check runs and status contexts have their own **Checks** tab with a
  direct link.
- **Quick Search** finds files and cached GitHub pull requests.
  Type `#` for recent PRs, then add digits or title words to narrow the PR completions.
- A visible direct PR link fetches and caches its record on the first visit.
- The PR page shows when GitHub CLI fetched the description or complete record.
- Treemap and its file totals load for folders in Git-backed repositories.
- Conversation interleaves clickable commit summaries with comments and reviews in
  GitHub’s order. Cached timelines are available offline.
- The PR diff tab is called **Changes**. A PR that already shows content uses the shared
  gray spinner for active refreshes and pending sections.
- Files, Commits, and Pulls each restore their own selection when switching tabs.
  The Open, Closed, and All filters show their exact totals from the Pulls catalog.
- The Pulls tab names the repository once in bold and uses a single spinner line for
  loading and refresh.
- Pull request metadata warms after idle startup in both checkouts and managed
  repositories. Visible rows take priority as the reader scrolls, and background
  preparation continues through the cached catalog.
  Lightweight descriptions persist locally across batches and server restarts.
  Selection takes priority; discussion, checks, and Git objects load when needed.
- PR stacks open from a compact position menu with titles, ordinals, and PR numbers.
  Use ⇧J toward the stack base and ⇧K toward its top.
- Usernames and repository names use bold normal text ink, with names inheriting their
  context’s font size.
  Branches share colored, copyable ref chips across navigation and page headers.
- PR author, action, and age share one metadata size and baseline.
  Commit descriptions share PR cards’ neutral surface and sans prose typography.
- A selected PR can show its verified header and description before discussion, checks
  and comparison preparation finish.
  Pending sections stay explicit, cached full records take precedence, and a superseded
  page stops its work while retaining inert content until the next page is ready.
- Git diffs mount in a connected hidden stage, so initial rendering can use the pane’s
  viewport. Hovering the currently displayed revision reuses its detail without fetching
  its comparison again.
- Once a selected PR shows its description, a waiting cache read can show the full
  Conversation as soon as the refresh settles, without waiting for the next poll.
- The pull envelope gains nullable `core_preview`; an explicit missing-record refresh
  may set `wait_core: true` to await that stage for up to two seconds.

Page lifecycle:

- A folder page kept for Back releases its inventory and live-log event streams,
  preventing repeated page loads from exhausting the browser’s connection limit.
  Restoring it reopens those streams once, preserves filter controls and their focus,
  and reconciles changed content without inserting unfiltered folder rows.
- Unchanged reconnect snapshots avoid parsing and repainting the tree, and catalog
  reconnects use explicit ETag validation.
  A live log deleted or truncated while the page was away stops showing as live on
  return.
- `GET /api/stream` asked to resume past the end of the file now ends the stream: it
  sends `event: closed` with `data: {"reason": "rotated"}` and stops.
  0.11.0 clamped the cursor to the file’s size and kept streaming, so a client saw
  `: heartbeat` and resumed at the wrong offset, although a cursor past the end means
  the file was rotated or truncated under the reader.
  This is the route’s side of the live-log entry above, which a plugin or script reading
  `/api/stream` directly sees.

Plugin SDK:

- **Breaking:** `PLUGIN_SDK_VERSION` is now `0.7`. The shared copy and Load more
  listeners act only on a control carrying the page’s owner mark, so a plugin that wrote
  the documented `data-mb-copy`, `data-mb-copy-text`, and `data-mb-copy-label` markup by
  hand now gets a button that silently does nothing (see Content trust below for why).
  A Load more button fails the same silent way in two cases: one a plugin wrote by hand
  as `button.metabrowser-load-more`, which carries no mark, and one whose
  `partialNoticeHtml` `action` string names the plugin’s own function.
  That string no longer becomes an inline handler, and the listener runs only an action
  the shell registered by name, which is its own text loader.
  Nothing is logged in any of these cases.
  To migrate, set `sdk_version = "0.7"` and stamp each copy control the plugin builds
  itself: `mb.ownDelegate(element)` on an element, or `mb.delegateOwnerAttribute()`
  spliced into markup.
  For a Load more that continues the plugin’s own content, pass `action: null` to
  `partialNoticeHtml` and wire the plugin’s own listener to its button.
  Controls from `wrapWithCopy` and `partialNoticeHtml` are stamped already and need no
  change. A manifest left at `0.6` is refused when it loads.

- `renderSourceView` renders a line-number gutter beside the code and wires line
  anchors, so every view that uses it gets both.
  The code is still the `<code>` inside `pre.code-block`, now beside a
  `span.source-line-numbers`; the copy button still copies only the code.
  The markup it writes has LF where the source has CRLF or a lone CR, so that the gutter
  counts the lines the browser shows.
  The text in the page and the text the copy button copies are what they were: the
  browser’s HTML parser already read both as LF when 0.11.0 assigned the markup.

- `ensureKindAssets(kind)` rejects when the SDK’s own view helpers cannot be fetched.
  Those helpers, `renderSourceView` among them, are no longer part of the shell’s
  startup scripts; the SDK has them in place before any plugin’s code runs, so a plugin
  calls them exactly as before.
  When they cannot be fetched no plugin code has run, and the next call tries again.
  While it waits for them it starts each plugin’s stylesheets and appends one
  `<link rel="modulepreload">` per plugin module to the document head, so the module is
  fetched early. Each module is still evaluated once, by the import that follows.

- `window.metabrowser.sourceKind()` reports whether the served tree is a filesystem root
  or a `git_revision` pin.
  Markdown link and wiki resolution use that kind instead of inferring GitPath encoding
  from `g1-` filenames, so a tracked file literally named `g1-notes.md` is a name rather
  than an identity to decode.
  Built-in views read the kind through this accessor rather than a page global.
  `sourceKind()` is an addition, and a plugin that never asks sees the filesystem answer
  it saw before.

- `mb.sizeHtml(undefined)` now renders nothing instead of a pending skeleton.
  `null` still means “this aggregate is still being computed” and keeps its skeleton
  cell; `undefined` means the subject has no such number at all, which is what a Git pin
  reports for a tree with no blob size, and a permanent skeleton would have read as a
  tally that never arrives.

- `metabrowser.plugin_api` exports the content-source boundary a hook needs to work on
  more than a served folder: `source_capabilities`, `require_source_capability`,
  `SourceCapabilities`, `UnsupportedSourceCapabilityError`, and `open_content`.
  `resolve_path`, `served_root`, and `open_content` are now explicitly filesystem-only
  and raise `UnsupportedSourceCapabilityError` on a Git pin, so a hook that assumed a
  host path fails where it is wrong rather than resolving against the wrong tree.

- A hook that only needs bytes reads them on either source kind through
  `resolve_content`, `resolve_content_container`, `stat_content`, and
  `read_content_window`, over an opaque `ContentRef` that carries the identity to echo
  back, the logical extension to dispatch on, a fingerprint that changes when the bytes
  do, and `stored_size`, the size the source stores: a file’s size on disk, which for a
  compressed artifact is its compressed size, and a blob’s length.
  Every read takes a required `max_bytes` and reports whether content continues past the
  window; there is no unbounded variant, and the bound is on bytes rather than on a
  decoded string. Failures are one catchable `ContentReadError` family carrying a stable
  `code` and the `http_status` Metabrowser’s own routes answer with, so a hook writes
  one error path for a missing object, an oversized blob, an unreadable compressed
  stream, and a timeout alike.
  The four built-in data hooks — binary bytes, structured parse, agent-log charts, and
  diff documents — now read this way and no longer branch on the source kind.
  These are additions to the Python helper surface; no manifest, kind, or
  `window.metabrowser` call changes.
  `content_source()`, added earlier in this unreleased series and never part of a
  release, is gone: it handed a hook the raw active source, which is what the content
  reader replaces.

Reviewing beside a checkout:

- A folder served from a GitHub checkout can show a pull request’s Files changed.
  Its explicit **Fetch changes** attaches a cached store, borrowing the checkout’s
  objects when one is needed.
  The folder and its Commits tab stay on the checkout; Git and writes run only in the
  managed store. Reading a cached comparison starts no network work.
  `POST /api/plugin/github/pull-refresh` accepts
  `{"number": n, "retry": true, "comparison": true}` for the same action, and the pull
  envelope names the comparison route to read after the job finishes.

- Files changed offers **Refresh** even for a current record.
  An explicit refresh can recover objects observed missing from the displayed
  comparison, then reload that same comparison and restore the reading position.
  A newer PR head remains an offer; a failed repair preserves the cached record and
  selection. Corrupt objects are refused, and the checkout is never modified to repair
  them.

- `--checkout <path>` serves a repository or pull-request URL by borrowing objects from
  a checkout you already have instead of cloning it: a 1.2 GB repository that took 185 s
  and 1.2 GB as a full mirror took 5 s and about 1 MB.

  The store is the same store, read and served the same way, and it is remembered from
  then on. Nothing is written to the checkout, and no Git runs in it.
  See [Beside a checkout](docs/command-line.md#beside-a-checkout).

- Only a checkout you name lends.
  `metab <url>` inside a checkout clones as before, and prints the `--checkout` command
  once.

- `/api/source/status` gains `borrows` and `shallow`, and `/api/cache/stores` and
  `/api/cache/source/<slug>` gain `mode` and `lender`, on every store.
  `store.yml` gains an optional `lender`, which a full store does not write.

- On a shallow store, a merge base is used only when it is provably right.
  Otherwise the record’s `unavailable.comparison` is the new `base_uncertain`, Files
  changed shows no diff, and the pull request’s refresh deepens the store from the
  origin. A comparison asked for with `base_policy=merge_base` on such a store is refused
  the same way.

- A checkout that moved is a typed refusal, `lender_missing`, with the recorded path and
  the command that repairs it; a store whose alternates file disagrees with its record
  is refused as `damaged`. The same refusal, with its own reason, answers a checkout
  that can no longer lend: one that has grown an `objects/info/alternates` of its own,
  whose objects can no longer be read, or whose directory holds another repository now.
  The checks that admitted a checkout run again on every open that uses it and before
  every fetch, so a mirror never follows a chain of alternates nothing recorded.
  A repair that stopped before its record was written is finished by the same
  `--checkout` command, and a repair takes the store’s fetch lock, so it never changes
  what a fetch in flight reads.
  A repair the disk refuses is an `Error:` line naming the reason, never a traceback,
  and the same command finishes it once the cache can be written.

- A refresh of a mirror that borrows offers the mirror’s own refs to the origin as well
  as the checkout’s, so it fetches only what the mirror lacks: on a replica, a branch of
  24 commits the checkout never fetched, moved by one commit, cost that one commit’s
  three objects per refresh rather than the branch’s 75 again each time.

- A mirror whose checkout cannot be read does not sweep its refs: a present but
  unreadable checkout answers `lender_missing` and the refs stay.
  A ref is swept only when the checkout shows its commit gone, so one loose object or
  one pack it cannot read now, or a checkout whose refs no file holds, as reftable keeps
  them, leaves every ref in place rather than deleting a live `refs/pull/<n>/head` or
  the default branch. A served `refs/pull/<n>/head` the sweep removed, because the
  checkout collected its commits, is unobserved in `/api/source/status`
  (`ref_on_origin: null`) rather than reported as removed by the origin, which keeps
  every pull-request head.
  A boundary the mirror owns is dropped once the checkout has no shallow file, so
  `shallow` turns `false` when the checkout is deepened or unshallowed.

- A comparison that needs a commit the mirror cannot read is `commits_unavailable` in
  the record’s `unavailable.comparison`, and `no_merge_base` is only Git’s own answer
  that the two commits share no history.

- A checkout whose remote is spelled as a path, as `git clone /x/origin.git` records it,
  is a checkout of the `file://` source of that path, so the documented commands work
  against a local origin; a `--checkout` refusal lists the checkout’s remotes with any
  credentials left out, whatever the URL’s scheme, the scp form included.

- Every read of a repository’s `.git` metadata, a folder’s included, now refuses
  anything but a regular file, so a FIFO planted in a `.git` directory cannot block it.

GitHub URLs and HTTPS:

- A GitHub URL copied from the browser opens the repository it names:
  `metab https://github.com/owner/repo` clones it into the cache and serves it, pinned
  and untrusted like any acquired source; `--no-serve` only clones it, and `--show` and
  `--api` inspect it in-process.
  Serving a `/blob/` or `/tree/` URL opens the browser at that file or folder, with the
  `#L10-L20` anchor kept in the address and those lines highlighted, and the banner
  names the ref, the selection, and a pull request’s number; `/api/source/status`
  reports that number as `pull_request`. `/tree/…`, `/blob/…` (with `#L10`, `#L10-L20`,
  or `#L10C5-L20C8` and `?plain=1`), `/commit/<id>`, `/pull/<n>/commits/<id>`, and
  `raw.githubusercontent.com` file URLs pin the commit they point at; the mirror decides
  where a branch name containing `/` ends, preferring a branch, then a tag, then a full
  or abbreviated commit ID. `--no-serve` prints the selection after the identity lines,
  and `--show` and `--api` print it on stderr.
  A `/pull/<n>` URL pins the pull request’s head; see below.
  Ref names match exactly, including letter case, and `HEAD` names the default branch;
  on a case-insensitive filesystem, a repository whose branch or tag names differ only
  in case is refused as `ref_case_collision` rather than risk pinning the wrong commit.
  Every spelling of a repository — one trailing `.git`, a trailing slash, `www.`, letter
  case, and `git@github.com:owner/repo.git` — is one source,
  `https://github.com/owner/repo`. Other github.com pages, `http://`, and GitHub’s own
  top-level pages are refused with a typed reason and a message that offers the
  repository URL; tracking parameters are dropped and never echoed.
  A URL pasted as an address bar shows it, with a raw space or a character outside ASCII
  such as `docs/雪.md` or `space name.md`, opens what its percent-encoded spelling opens:
  as a browser does, the space and the character are sent percent-encoded as UTF-8. A
  character a reader cannot see or tell from a space is refused with its code point and
  the encoded spelling to use: whitespace other than a space, format characters such as
  a right-to-left override, Unicode’s default-ignorable characters such as the Hangul
  filler U+3164, the blank braille pattern U+2800, and unassigned and private-use code
  points. A variation selector is default-ignorable too, but one attached to a visible
  base is part of an emoji or ideographic name, so `docs/❤️.md` (U+2764 U+FE0F) opens
  pasted raw; one with no base, such as `README<U+FE0F>.md` or a selector that begins a
  name, is refused. So are a trailing space, which a browser strips, control characters,
  named by code point, and a `%` that starts no percent escape, with the hint to write a
  literal `%` as `%25`. A C1 control character in a path, such as `%C2%9B`, is shown as
  U+FFFD like C0, so an error message cannot send a terminal an escape sequence, and so
  is a format character such as a right-to-left override (`%E2%80%AE`) or a zero-width
  space, and a character drawn as nothing or as a space, such as the Hangul filler
  U+3164 (`%E3%85%A4`), a variation selector with no base, the blank braille pattern
  U+2800, or a space other than the ASCII one, such as a no-break space (`%C2%A0`) or a
  hair space (`%E2%80%8A`), on the `path:` line, in errors, and in a pinned tree’s file
  names, so a name cannot pass for another.
  The line and paragraph separators U+2028 (`%E2%80%A8`) and U+2029 are shown as U+FFFD
  too, so a message stays on one line.
  Unassigned and private-use code points, which are refused raw in a URL, are displayed
  as they are: a font draws them as a glyph or a missing-glyph mark, and which code
  points are unassigned depends on the Python that is running.
  A ref, commit, or path the mirror does not have is reported by `--no-serve`, `--show`,
  and `--api` as `ref_not_found`, `commit_not_found`, or `path_not_found`; those modes
  read the mirror as it is and do not fetch.
  A server instead serves the default branch, fetches once in the background, and
  switches to the selection if the fetch brings it, like any pin switch; a page opened
  meanwhile then goes to the selection’s address, line anchor included, which status
  reports as `selection_href`. Until then the page’s freshness row says the address is
  still being fetched, is not on the origin, or could not be fetched, with a Retry.
  `/api/source/status` reports `selection_state` as `pending`, then `found` or
  `not_found`; `fetch_failed` when the fetch could not run, in which case the next
  refresh tries again; and `superseded` once a pin switch serves something else, which a
  waiting selection then never undoes.
  A mirror cloned by the same command has just been fetched, so there a missing
  selection is not found at once.
  One-shot `--api /api/source/refresh --data …` also waits for the refresh it asks for
  and reports the selection after it.
  In a server, `POST /api/source/pin` for a branch, tag, or commit the mirror lacks
  likewise answers `202` with `selection_pending` and fetches once; asked again after
  that fetch it switches, answers `404`, or answers `502` `selection_fetch_failed` when
  the fetch could not run.
  The pin route resolves as URL opening does: `HEAD` is the default branch, and a name
  that is not a commit, such as a tag of a tree, answers `409` `not_a_commit` at once
  rather than fetching.
  A commit ID in a URL or a pin request has 7 to 64 hexadecimal digits, and a trailing
  newline is not one. github.com links inside a rendered README of a served GitHub mirror
  open inside the pin, as they already did for a served checkout of the repository.

- A served page opened at `/commit/<id>` for a commit the mirror does not have now says
  what is known instead of “Could not load this commit.”
  When the mirror is older than the freshness window the page fetches in the background
  and shows “Fetching this commit…”, then opens the commit when the fetch brings it,
  says “Commit not found” when the fetch ran and the origin’s branches and tags do not
  reach it, or says “Commit not fetched” with the reason when the fetch could not run.
  On a mirror fetched inside the window the page fetches nothing by itself, because a
  link in a served page can lead to any commit’s address, and says the commit is not in
  the mirror as fetched; **Retry**, offered in each of these states, always fetches.
  The page claims a fetch of branches and tags only when one ran: a refresh of a served
  pull request’s record alone is waited for and not called one.
  `/api/git/commit/<id>` names the miss as `commit_not_found`, still with HTTP 404, and
  never fetches; in a served folder, which has no mirror to fetch into, the page says
  the commit is not in the repository.
  A request that fails for another reason, including one that fails when the commit is
  asked for again after the fetch, still reads “Could not load this commit.”
  `POST /api/source/refresh` takes `{"for": "commit"}` for that fetch: it fetches the
  mirror only outside the freshness window, joins a fetch that is running, and otherwise
  answers `fresh`; `"retry": true` always fetches, and any other key is refused as
  `invalid_request`.

- `https://` sources are acquired, anonymously for a public repository.
  When `gh` is installed it is Git’s credential helper for `https://github.com` only,
  after every configured helper is cleared, so `gh auth login` opens a private
  repository and no other host is offered a GitHub token.
  A failed https acquisition names its cause: `not_found_or_private`,
  `network_unreachable`, `connection_interrupted`, `tls_failed`, `timed_out`,
  `server_error`, `rate_limited`, `proxy_auth_required`, or `too_large`, the last when
  `gh` reports a repository over the first-clone size limit, which the refusal states
  along with how to go past it: `METABROWSER_MAX_FIRST_CLONE_KB`, for a network fast
  enough to finish within the acquisition deadline.
  A `not_found_or_private` message says the repository was not found, or is private and
  could not be read, and claims nothing about credentials: GitHub answers the same way
  for a repository that does not exist, one read anonymously, and one the account `gh`
  answered with cannot see.
  The size check asks github.com only, whatever host `GH_HOST` names.
  Git runs with `HOME=/dev/null` while it acquires, so curl reads no `~/.netrc`; `gh`
  alone is given the real home, without `GH_DEBUG`, `GH_HOST`, `GH_REPO`,
  `CLICOLOR_FORCE`, or `GH_FORCE_TTY`. A transfer slower than 1000 bytes per second for
  30 seconds is treated as stalled, and an origin that does not answer the first request
  within 30 seconds times out rather than waiting for curl’s five-minute connect
  timeout. A served mirror refreshes from the same URL with the same arguments, including
  the prune and single retry after a ref that cannot be locked, and a refresh’s outcome,
  in the status and in the store’s `state.yml`, carries the same names, plus
  `ref_case_collision` where a case-insensitive filesystem cannot hold two refs apart.
  Git does not always refuse that fetch: given `SAME` beside an unchanged `same`, it
  writes `SAME` into `same`’s file and succeeds, repointing `same`. A refresh on such a
  filesystem checks the store holds every ref the fetch wrote under its exact name, and
  otherwise puts every ref back and reports `ref_case_collision`, so no pin resolves to
  the twin’s commit.

- A first clone says where it goes and shows that it is running, in every mode that
  clones. A clone of a 740 MB repository used to print two lines and then nothing for 100
  seconds, and nothing at all when stderr was not a terminal, so it looked hung.
  Now stderr names the cache directory once (`cloning <url> into ~/.cache/metabrowser`),
  then reports Git’s own progress with the elapsed time
  (`receiving objects: 45%, 334.0 MiB at 9.5 MiB/s (40 s)`), and ends with
  `cloned <url> in 104 s (742.0 MiB)`, to which serve mode adds that the server starts
  next. On a terminal the progress is one status line redrawn in place, with the time
  counting through a stall; elsewhere it is a whole line at most every ten seconds, so a
  quick clone adds two lines to a log.
  The progress is read from `git fetch --progress` as numbers and printed in
  Metabrowser’s words: Git’s and the origin’s own text still never reaches the terminal,
  whatever control characters it carries.
  `--log-level debug` is how to read that text when a clone fails, and a log line that
  quotes it, here and in a server’s log, now writes every character that is not
  printable as its escape (`\x1b`, `\r`), so an origin’s escape sequence is read and not
  obeyed. Before, it was written to the terminal as it came.
  A source that is already cloned says so in one line in serve mode and `--no-serve`
  (`using the clone of <url> cached in ~/.cache/metabrowser, fetched 3 hours ago`), so a
  second run reads differently from a first; `--show`, `--api`, and `--check-api` stay
  silent on a cache hit.
  stdout is unchanged.

- A page served from a mirror is headed by the repository’s name, and says where the
  mirror is kept. Opening `https://github.com/jlevy/squares` used to head the main view
  with the full commit ID (`fe6399451f1c… / README.md`), and nothing on the page said
  the files came out of `~/.cache/metabrowser`. Now the navigation heading reads
  `squares main fe6399451f1c` and the main heading `squares / README.md`: the name a
  checkout of the repository would have, by one rule for every `https://` and `file://`
  origin and for a pull request, with the ref and the short commit beside it.
  A control after the short commit copies the full one.
  The main heading ends with `mirror in ~/.cache/metabrowser/repository-stores/…` when
  the pane has room for it, and the tooltip on the name, on that note, and on the
  navigation heading says what the directory is:
  `Mirror of <origin> at <commit>, stored in <location>: a bare Git repository, with no checked-out files.`
  Nothing is checked out, so the location is never shown as the start of a file’s
  address. The directory named is the store’s bare repository, where
  `git -C <location> log --all` works.
  `/api/source/status` reports the same as `name`, `origin`, and `location`, and `--api`
  prints them as answered.
  The location, and a `file://` origin, have your home directory as `~` when they are
  under it, so nothing spells the home directory out when it can be abbreviated.
  On a GitHub mirror the name is lowercase, as the mirror’s canonical address is.
  This is the one place a route’s answer names a path in the cache: file content,
  listings, errors, and every other envelope still name none, and repository content
  still cannot read it, since a mirror’s Markdown renders inert and `/raw` is a sandbox
  with no access to `/api`. A folder’s page is as it was.
  One thing a folder’s server answers differs: `/api/source/status` carries the three
  new fields, each `null`.

- The pull-request page and its routes are a new built-in plugin, `github`, and a
  built-in plugin loads whatever is served.
  So it is listed for a plain folder too: `metab --plugins` has a `github` row, the
  `Plugins:` line a server prints when it starts names it, and `metab --doctor` counts
  one plugin more than 0.11.0 did.
  On a folder it serves nothing: `/api/plugin/github/pull?number=<n>` answers
  `state: "absent"` with `reason: "not_github"`,
  `/api/plugin/github/pull-markdown?number=<n>&part=body` answers 409 `not_github`, and
  `--show /pull/<n>` reports that state.
  Without a valid `number` or `part`, each answers 400 on any source.

- Pull-request data:
  `metab https://github.com/owner/repo/pull/<n> --api '/api/plugin/github/pull?number=<n>'`
  reads the pull request with `gh api` (its description, labels, state, merge status,
  commit count, who merged it, conversation, reviews, review comments, check runs, and
  statuses), fetches its commits through GitHub’s `refs/pull/<n>/head`, a fork’s
  included, pins the head commit, and prints the record.
  The record is cached as one JSON file per pull request, so later `--show` and `--api`
  answer from the cache without running `gh` or reaching the network; `--no-serve`
  refreshes it, with conditional requests that GitHub does not count against the rate
  limit when nothing changed.
  The record names Files changed as two pinned commits, the merge base and the head, as
  GitHub computes it, and `/api/plugin/diff/comparison` now honors
  `base_policy=merge_base` for such a comparison.
  The route also validates the parameter, which 0.11.0 ignored: a value other than
  `direct` or `merge_base`, or one given with `revision`, answers 400 `diff_comparison`.
  Two commits that share no history have no merge base, and the route answers 404
  `diff_comparison` with a message that says so.
  Reading pull requests needs `gh` 2.81.0 or newer signed in to github.com, because
  `gh api` refuses unauthenticated requests.
  A pull request that cannot be read does not stop the command: with a cached record,
  the pin stays at its head and the report adds why the refresh failed; without one, a
  `/pull/<n>` URL pins the default branch and a `/pull/<n>/commits/<id>` URL the commit,
  as before pull-request data existed, and the `pull_request` line says why.
  Serving a pull-request URL serves its head and keeps the record fresh beside the
  mirror, in the same refresh jobs: a stale record makes the source `stale`, so it is
  refreshed when serving starts and when a stale page becomes visible, and
  `POST /api/plugin/github/pull-refresh` with `{"number": n}` starts or joins its
  refresh and returns at once.
  `/api/plugin/github/pull` adds `refreshing` and `last_refresh`, and answers `pending`
  while the first record is being read.
  Any server of a GitHub repository answers for any number, not only one its URL named.
  The pull and Markdown routes and the refresh body require an explicit pull-request
  number. Only `"retry": true`, a reader’s own action, can add a pull request to the
  cache: without it a number with no record answers `not_cached`, a record inside the
  window or before a rate limit lifts answers `not_due`, and neither starts anything.
  Past eight pull requests queued or running, a request is refused 429 `too_many`. The
  mirror’s fetch and the pull request whose head is served go ahead of that queue, and a
  list’s refresh does not wait for it.
  The served one may run one over the bound; past that, `/api/source/refresh` answers
  429 `too_many` too when that pull request is all it would refresh.
  A newer head is offered as the source’s `latest`, and `/api/source/pin` accepts
  `refs/pull/<n>/head` to take it.
  Only the stale one of the mirror and the record is refreshed, a pin the mirror lacks
  never runs `gh`, and how the last refresh ended is kept beside the record, so a later
  command reports it and does not ask `gh` again within the minute.
  A one-shot `--api /api/plugin/github/pull-refresh` waits for the refresh, prints the
  record after it, and exits 1 when it failed.
  A `/pull/<n>/commits/<id>` URL naming a commit newer than the cached record refreshes
  the pull request to reach it.
  Each cause is named: `gh_missing`, `gh_too_old`, `not_logged_in`, `rate_limited` with
  the reset time when GitHub gives one, `not_found_or_private`, `network_error`,
  `account_changed`, `head_mismatch`, `gh_failed` for an answer that cannot be read,
  `fetch_failed` and `git_failed` for Git, `record_too_large`, `cache_unwritable`, and
  `not_github`. Check runs or statuses GitHub refuses, and a comparison whose base
  cannot be fetched, leave the rest of the record standing and are listed in its
  `unavailable`; an item that cannot be read or is too large for one page is left out,
  an `http://` link is left empty, and the list is marked incomplete.
  Lists and text are bounded per pull request, and a cut is reported, never silent.
  A repository’s pull-request catalog fills incrementally in the background using
  lightweight GraphQL metadata pages, with exact counts and resumable backfill.
  `POST /api/plugin/github/pulls-refresh` starts or joins that work and accepts a
  display `target`; `/api/plugin/github/pulls` answers filtered windows from the cache
  alone, including offline.
  Descriptions, conversations, reviews, checks, and Git comparisons remain separate from
  catalog loading. A pull request’s changed files are new too:
  `POST /api/plugin/github/pull-files-refresh` with `{"number": n}` lists them from the
  mirror’s own comparison when the store holds both commits, with no network, and
  otherwise from GitHub’s list with `gh` and no Git, checking the active account before
  each progressive publication and before the complete list; an observed account change
  stops publication and marks previously checked prefixes stale;
  `/api/plugin/github/pull-files?number=<n>` answers what is held, offline too, while it
  fills, and says when GitHub stopped at 3,000 files.

- Pull-request refreshes distinguish changed-file replacements and edited Markdown even
  when their timestamps match.
  File-list generations preserve progressive appends; Markdown content revisions reject
  superseded replies and stylesheet completions while keeping unchanged text on a
  freshness-only refresh.
  A changed-file refresh that cannot admit its application cache reports its error and
  backs off automatic retries in bounded server memory, without contacting GitHub or
  writing the refused home.
  The newest refresh outcome remains visible while active provider deadlines still
  prevent premature network retries.

- Pulls tab: a GitHub repository opened from its URL has a **Pulls** tab beside Files
  and Commits, listing every pull request newest first, with GitHub’s icon for open,
  draft, merged, and closed, Open, Closed, and All filters (defaulting to Open), and
  what to do when `gh` cannot read them.
  It is in front whenever a pull request’s page is, and at the list’s own address,
  `/pulls`. Selecting a row reads the pull request in the same page, fetching it if it
  has no record; holding K, J, or an arrow walks the rows and opens the one it stops on,
  and one Back leaves the rows however many were passed.
  The status shows a bold numeric total and repository name.
  Initially up to 500 matching PRs are displayed; **Fetch more** expands that window
  while catalog metadata continues filling independently.
  Rows expand into a windowed changed-files tree with folder navigation and inline
  change counts. Selecting a file opens `/pull/<n>/files/<path>` and shows Changes in
  place; keyboard walks keep focus in the tree and replace one history entry when they
  stop. The selected file follows a reader’s diff scroll.
  Opening a GitHub repository now runs `gh` for its list of pull requests once the first
  file tree has painted, at most once a minute, whether or not the tab is opened; the
  request names the repository and carries `gh`’s own sign-in.

- The Conversation and Changes tabs align with the PR reading column on narrow and wide
  screens; the diff itself retains the full pane width.

- GitHub CLI setup messages provide installation and sign-in steps, with official
  download links when `gh` is missing or needs updating.
  The [installation guide](docs/installation.md#git-and-github-setup) explains which
  features need Git or `gh`; local files and cached PR metadata remain readable without
  `gh`.

- Pull-request profiles include JSON decoding, rendering, and DOM-readiness stages
  through the existing performance recorder.
  Catalog jobs check the account once and validate the viewer returned with every page,
  avoiding repeated account-status requests during backfill.

- When the optional `gh stack` extension is installed, pull-request rows show their
  stack position. PR pages offer a matching position menu with the stack number and
  ordered member links.
  Stack metadata refreshes separately from PR content; unavailable tooling leaves the
  normal PR views usable.

- Moving between pull requests clears the previous file tree’s current-file highlight
  while retaining its expansion and keyboard position.
  Repeated route notifications preserve the active diff’s file selection.

- An uncached pull-request page shows pulsing gray loading blocks in the reading column.
  Cached content stays visible while it refreshes.
  PR numbers use dark text, usernames use bold normal text ink, and branch names use a
  smaller consistent treatment across the list and PR pages.

- External GitHub links show a shared destination icon in rendered text and application
  controls. Issue and PR links use neutral entity icons when state is unknown; matching
  PR metadata supplies the state icon.
  Localized file links remain internal, and decoration makes no additional API requests.
  Branch-copy controls also restore visible row focus before dragging a pane splitter.

- File change letters share muted semantic colors across Git, diffs and PR file trees:
  additions green, deletions red, modifications ochre and renames blue.
  Branch names share ref chips with hover/focus copy controls.
  GitHub authors have small lazy circular avatars.
  Full metadata uses relative ages such as “2h ago”, “just now”, or “in 2h”; compact
  navigation retains short labels.
  Split and unified diffs use the shared monospace block size and matching reserved row
  heights, fixing a root-font fallback that made code larger than other code views.

- Pull-request page: serving a pull-request URL now opens its page at `/pull/<n>`, the
  way github.com shows it: title, state (open, draft, merged, or closed), github.com’s
  header line (“author wants to merge 2 commits into base from head”, and once merged
  “merger merged 2 commits into base from head”, or “merged 2 commits into …” when the
  record names no merger; when the head is in a fork both sides carry their owner, as in
  “into cli:trunk from 00200200:fix/…”), times, labels, merge status (unknown until
  GitHub has computed it), the description, a conversation of comments and reviews in
  time order with review states, review comments with their file, line, and diff hunk,
  checks and statuses with links to their details, and notes for anything the record cut
  or could not read. The Checks summary counts each check run and commit status under one
  of: success; failure (a run that failed, timed out, needs action, or failed to start,
  and a status of failure or error); cancelled; skipped; stale; neutral; pending (a run
  not yet completed, whatever its status, and a pending status); and unknown (a
  completed run with no conclusion, or a conclusion or state GitHub does not document).
  `/pull/<n>/files` is its Files changed, the diff view over the record’s merge-base
  comparison, and a `…/pull/<n>/files` URL copied from GitHub opens there, with
  `tab: files` among the lines that report what the URL selected.
  The page reads only the cached record, so it opens instantly and offline; it says how
  old the record is and who read it, offers a refresh when it is stale, shows a quiet
  loading state while the first record is fetched, and updates the conversation and
  checks in place when a refresh brings a new record, while the diff stays on what it
  showed and offers a newer head.
  When the served code is not the head the record names, as when the pull request could
  not be opened at startup and serving fell back to the default branch, the page offers
  to switch to the head (`refs/pull/<n>/head`) and reloads on it.
  Descriptions and comments render as Markdown through KPress’s sanitized mode, one text
  at a time a screen before it scrolls into view, so a fast scroll does not show raw
  Markdown, never from GitHub’s own HTML, and are then reduced to an allowlist of plain
  markup, on the server and again in the page: paragraphs, headings, emphasis, code,
  quotes, lists, tables, and details, with no class, `id`, `data-*`, style, or event
  attribute. SVG, MathML, media, frames, forms, stylesheets, and scripts are removed with
  their content, and no KPress script or stylesheet is loaded for a comment, so a
  comment cannot load anything, restyle or cover the page, reach the application’s own
  handlers, or clobber a global.
  An image is a link to it rather than loaded, links open on GitHub in a new tab, only
  `http` and `https` ones kept, with the scheme in lower case in the Markdown route’s
  answer too, and code blocks show as plain text without highlighting.
  A text’s paragraphs, headings, lists, quotes, code, tables, and details have their own
  spacing and list indent inside the card, with none above the first block or below the
  last; a table wider than its text scrolls there, and a long word or URL breaks to fit.
  A review comment’s file opens at the served head, at its line, and it shows the end of
  its diff hunk, where it anchors: the last eight lines, back to the start of a
  multi-line comment’s range for up to 100 lines, with the earlier lines behind a
  disclosure and added and deleted lines tinted as in the diff.
  The freshness row links to the page, and back, forward, and reload keep its tab.
  They also return a reader to their place in either tab, by the comment or file they
  were in rather than by pixels, because what has rendered above it differs when the
  page loads again; a new entry starts at the top, and a fragment in the address or a
  reader who has started scrolling with a wheel, a finger, the scrollbar, or a key is
  never overridden. `/pull/<n>` opens any number on a server of its repository: with no
  record it offers **Fetch**, and an address alone fetches nothing.
  **Browse code** moves the pin to the pull request’s head first when something else is
  served, and View file serves a commit under the head of any pull request it is the tip
  of. `metab <url> --show /pull/<n>[/files]` reports the page’s kind and a summary of its
  record, and `/api/plugin/github/pull-markdown?number=<n>&part=…` answers the
  allowlisted HTML of the description (`body`) or one comment, review, or review
  comment, and nothing else of KPress’s render.
  `/api/plugin/github/pull` answers with an entity tag and a `304` when nothing changed.
  The description and every comment and review read in the interface sans at a Markdown
  file’s size and “Max text width”, whichever reading font is chosen, because serif is
  kept for committed documents.

- A terminal hangup or `SIGTERM` now cancels an acquisition the way Ctrl-C does: Git and
  every helper it started are stopped, staging is removed, and `metab` exits with status
  129 or 143. A hangup that was already ignored, as under `nohup`, stays ignored.
  A cancellation that arrives while Git is still starting also stops the helpers it
  already forked, rather than only `git` itself.
  While a Git source is served, a hangup stops the server as Ctrl-C does, killing a
  running refresh’s Git first, and exits 129.

Source views:

- A text or source file’s Source view shows line numbers, and a `/view/` address ending
  in `#L10`, `#L10-L20`, or `#L10C5-L20C8` highlights those lines and scrolls the first
  one into view, when the file opens and whenever the fragment changes; columns are kept
  but highlight whole lines.
  Clicking a line number anchors that line and shift-clicking extends the anchor to a
  range, replacing the address rather than adding a history entry, so a copied address
  keeps the anchor. This works the same in a served folder and on a pin.
  A large file’s anchor past the part loaded so far says so and names Load more; once
  Load more reaches the line, it is highlighted and scrolled to.
  An anchor past the end of the file says how many lines the file has.
- An address with a line anchor, or with GitHub’s `?plain=1`, opens the file in its
  Source view, and adding a line anchor to the address of the file already shown selects
  its Source tab; Load more keeps the tab it was used in.
  A GitHub `blob` URL for a Markdown file with `#L10` or `?plain=1` shows its source
  with those lines highlighted; a served `blob` URL keeps `?plain=1` in the address.
  The Markdown Source tab has line numbers and anchors, with front matter highlighted as
  YAML and the body as Markdown beside one column of numbers.
- The line numbers are reachable from the keyboard: Tab focuses them, the arrow keys,
  Page Up, Page Down, Home, and End move the anchor, and Shift extends it to a range.
  A screen reader announces the highlighted lines as the anchor moves and when an
  address sets it.
- Opening a Source tab for the first time scrolls to the address’s line anchor, as
  opening the file does.

Repository cache:

- `metab --doctor` also checks the packaged cache record schemas, so an installation
  whose schemas are missing or no longer match their models is reported there instead of
  at the first acquisition.
  A healthy result reads as before.
  The check costs time: `--doctor` takes about 250 ms longer than in 0.11.0, 385 ms to
  629 ms of wall time and 350 ms to 560 ms of CPU time on an Apple M1 Pro, and does
  1.78x the work in instructions retired.
  That is the median of 15 back-to-back pairs of installed wheels with compiled
  bytecode, taken on 2026-10-01 under a load average of 12 to 16.

- The cache validates the records it writes with SoftSchema, so `softschema==0.8.1` is a
  new runtime dependency and the minimum `frontmatter-format` rises from 0.3.0 to 0.4.0,
  which SoftSchema requires.

- Acquiring or refreshing a Git source requires Git 2.43.7 or, on a later release track,
  the patched release that carries the same security fixes, up to 2.50.1;
  `ACQUISITION_PATCHED_TRACKS` in `src/metabrowser/git/process.py` lists them.
  An older Git is refused with a message that names the version found and the version
  required, and a refused acquisition does not create the application home.
  With no `git` on `PATH`, the same refusal says that git was not found and which
  release to install. Reusing a store already in the cache and serving a folder on disk
  do not check the floor.

- New read-only routes `/api/cache/layout`, `/api/cache/sources`,
  `/api/cache/source/<slug>`, and `/api/cache/stores` report the cache’s layout and
  config formats, abandoned staging entries the next sweep removes, sources with their
  alias generation and publication state, and stores with the aliases that name them.
  Reach them with `metab <root> --api /api/cache/layout` like any other route.
  They resolve `METABROWSER_CACHE_DIR`, or `~/.cache/metabrowser`, on each request and
  change nothing: a missing home reports `absent` rather than being created, an entry
  other users can reach is reported as `not_private` rather than tightened, and a home
  other users can access, or one a newer release wrote, is refused with a typed error
  that names the fixed cache directory to fix and no path of yours.
  Sources and stores are paged with `limit` and `after`, 25 rows by default and 100 at
  most; no response reports a cache path, pack file, or Git internal.

- The CLI classifies `ROOT` as a string before any path is constructed.
  A bare local path is still served; `ssh` clone URLs stay closed.
  `file://` is the only way to ask for a local origin to be acquired — a bare
  `/path/to/repo` is never rewritten into one — and `ext::` remote-helper syntax is
  rejected. `metab file://… --no-serve` fetches into the cache and prints slug, store
  identity, and revision without starting a server.
  The application home and `CACHEDIR.TAG` are created by the first acquisition, of a
  `file://` or an `https://` source alike.
  A Git timeout, oversized output, missing executable, or failed command during that
  acquire is reported as its own error message without a traceback or a local path.
  `metab file://… --api /api/cache/…` acquires as a side effect, then inspects cache
  state against an empty throwaway root so cache inspection cannot expose origin objects
  through `/api/tree`. `metab file://… --show PATH` and non-cache `--api` acquire or
  reuse the store, pin the default revision, and inspect that `GitRevisionSubject`
  in-process, and `--check-api` runs its navigation scenario on that pin, where the live
  filter’s `unsupported_for_subject` answer is the pass.
  `--walk` refuses a Git source: the walker reads a filesystem, and a pin’s complete
  listing is `/api/tree`. None of these binds a port.
  ssh stays closed. Those pin modes report acquisition failures with the same messages as
  `--no-serve`, and a Git failure while opening the pin is also path-free.
  A pin’s `/api/tree` lists directories before files, as a folder listing does.
  A pinned blob larger than the 16 MiB whole-read limit is classified from a bounded
  window and paged in the text and byte views like a large file on disk, instead of
  answering 413; a text window starting past that budget answers 416. `/raw` still
  refuses such a blob.
  A pinned symlink resolves one path component at a time, as a checkout does.
  No store read fetches from the origin.
  A pin always runs under the untrusted profile: `METAB_ACTIVE_CONTENT=1` and
  `METAB_ALLOW_EDITS=1` do not lift it, and `--allow-edits` on a pin is an error.

- `--diff` does not open a URL or `file://` source.
  `metab file:///path/to/repo --diff A..B` is refused with a message that says so and
  names the modes that do open one.
  It compares revisions of a repository served as a folder, as before.

- Opening a URL or `file://` source needs a POSIX system.
  The clone is kept under the application home, which is verified as private to the
  current user with ownership and no-follow checks.
  Where a platform lacks them, as Windows does, such a source is refused: “The
  Metabrowser application home cannot be verified as private to the current user”, and
  nothing is stored. Serving a folder does not use the home and is unaffected, which is
  what the package’s `OS Independent` classifier still describes.

- An argument that names an existing path is that path, whatever it resembles.
  A folder called `file:notes`, `a::b`, `me@host:dir`, `https:x`, or `-dash` (after
  `--`) is served, a file is opened, and a symbolic link is followed, as in 0.11. Only
  an argument that names nothing on disk is read as an scp-like address or refused as a
  malformed URL or remote-helper syntax.
  The one exception is an argument that starts with `scheme://`, which is always a
  source: no path needs that spelling, so a pasted URL opens the same thing in every
  working directory and a local folder cannot stand in for the repository it names.
  `metab https://host/x` therefore no longer serves a folder at `https:/host/x`; write
  that path with one slash, or as `./https://host/x`. An scp-like address has no such
  exemption: `git@github.com:o/r` names a local folder of that name when the working
  directory has one, as in 0.11, and the GitHub repository only when it does not;
  `https://github.com/o/r` always opens the repository.
  A path that exists but that the process may not read is a usage error, as in 0.11
  (`Path 'x' is not readable.`, exit status 2), not a tree that walks or serves as
  empty. An empty argument, `metab ""`, is refused as `invalid ROOT (empty)`, where 0.11
  read it as the current directory.

- `metab file://…` serves the acquired source in the browser, pinned to the commit its
  default branch named at the store’s last fetch, until Ctrl-C. Every page reads from
  the store; only the background refresh below reaches the origin.
  The banner names the source and prints a `Revision:` line with the full commit and
  branch. `--path` deep-links a path within the pin, spelled as `--show` accepts it, and
  prints a directory’s address with a trailing slash.
  The branch name on the `Revision:` line is the origin’s, so it is shown as a path is:
  a control character in it, such as the one-character CSI U+009B, or an invisible
  character, is U+FFFD, there as on a GitHub URL’s `pin:` line.
  If the pin cannot be opened again when the server starts, the command prints the same
  path-free error as `--show` and exits 1 rather than a traceback.
  The tree, file views, Markdown and its images, JSON, images, history, commit detail,
  and diffs all read from the store.
  The navigation heading shows the branch and short commit; its tooltip and the file
  header show the full commit.
  A served pin always runs under the untrusted profile, exactly as `--show` and `--api`
  do, and HTML offers only its source.
  Its `/api/cache/…` routes answer `unsupported_for_subject`, so nothing about other
  cached sources is served beside acquired content.
  The `/raw/<path>` form answers the same way, because its only consumer is the HTML
  preview a pin never offers; Markdown images resolve within the pin through
  `/raw?path=`. A served `file://` pin has no `repository_context`.

- `metab ROOT` exits non-zero when the server’s startup fails, instead of reporting
  success for a server that never listened.

- New `GET /api/source/status` reports what the server serves: the subject kind, the
  session generation, and on a Git pin its full commit (`pin`), the store ref it was
  resolved from (`ref`), and that ref’s branch or tag name (`ref_name`). Reach it with
  `metab <root> --api /api/source/status`. On a served mirror it also reports freshness:
  the commit the pinned ref names in the mirror now (`latest`), `last_fetch_at`, the
  last operation and its typed outcome (`last_outcome`), `refreshing`, `stale`, and
  whether the origin still had the pinned ref at the last fetch (`ref_on_origin`), all
  from server memory so polling runs no Git.
  The outcome is recorded in the store by name, so a restarted server reports it too.
  It sends an ETag and answers an unchanged `If-None-Match` with 304.

- A served `file://` mirror refreshes in the background and never makes a page wait.
  `metab file://…` starts one refresh when the mirror’s last fetch is older than a
  minute. New `POST /api/source/refresh` starts a refresh, or joins the one running, and
  answers 202 at once.
  A refresh is one `git fetch --prune --atomic` of every branch and tag: every ref moves
  together or none does, a branch or tag deleted upstream leaves the mirror, and no
  object is removed, so a commit that was pinned stays readable after a force-push or a
  deleted branch. A branch replaced by a directory of branches (`side` then `side/x`), or
  renamed only in case on a case-insensitive file system, no longer wedges every later
  refresh: the stale ref is pruned on its own and the fetch runs again.
  A refresh another process is running is reported as `refreshing_elsewhere` instead of
  waited on, and a served page follows it until it ends.
  A fetch’s Git holds the store’s fetch lock for as long as it runs, so a server killed
  mid-fetch leaves no second writer in the store, and Ctrl-C stops the fetch before the
  server exits. Files a killed fetch left behind are removed before the next one, and a
  missing origin, a failed fetch, or a detached origin HEAD is a typed outcome in the
  status while the pinned revision keeps serving.
  Reach it with `metab file://… --api /api/source/refresh --data <file with {}>`; that
  one command waits up to one Git deadline for the refresh it asked for, prints the
  status after it, and exits 1 unless the fetch ran or another process’s refresh is
  running. No other one-shot command fetches.

- New `POST /api/source/pin` switches what a server serves to another branch, tag, or
  commit of the same mirror: `{"ref": "feature"}`, `{"ref": "v1"}`, or
  `{"oid": "<full or at least 7-digit commit ID>"}`. A name is tried as a branch, then a
  tag, then a commit ID, and is looked up in the mirror alone; revision syntax such as
  `:/text`, `@{…}`, and `^{/…}` is refused rather than evaluated.
  The old revision’s readers are released, the new one is served under a new session
  generation, and the answer carries the new status.
  Both new routes are POST routes with a JSON body behind the existing same-origin
  guard, so content in a served page cannot reach them with a link, an image, or a form;
  on a folder they answer `unsupported_for_subject`.

- A page on a served mirror shows when the mirror was last fetched at the foot of the
  navigation pane, polls quietly while it is visible, and asks for one refresh when it
  opens or becomes visible on a stale mirror.
  When a refresh moves the pinned branch it offers the commit the branch now names,
  usually a newer one, and accepting switches the pin and reloads the view.
  When another tab switched the pin, or the server restarted onto another commit, even
  before the page’s first poll, it offers a reload.
  The page’s data requests name the commit it shows and are refused with `pin_changed`
  rather than answered from another commit.
  Images and raw documents the page loads directly are not checked, so a stale page can
  still show one of those from the new pin until it reloads.
  A failed refresh reads as a warning there, not as an error in the page.
  The row repaints only when what it says changes, and announces its state and offer to
  a screen reader, not its age.

- A page on a served mirror has a branch and tag selector: a compact button under the
  navigation header names the served ref, and opening it lists the mirror’s branches,
  the default first, or its tags, newest first, with a filter box.
  Choosing one serves it and reloads the view on the same file or folder when the new
  revision has it, or at the root otherwise.
  The list comes from the new `GET /api/source/refs?kind=branch|tag&q=&limit=`, which
  reads the mirror alone, never the network: `q` is a case-insensitive name fragment,
  `limit` is clamped to 1–1000 (default 100), and `total` and `truncated` say how many
  matched. A tag is listed when it names a commit, directly or as an annotated tag of
  one; a tag of a tree, a blob, or another tag is not, on any Git version, and still
  pins by name. `POST /api/source/pin` also takes the page’s address as `"view"` and
  answers `view_href`, where that page goes on the new revision.
  The address is checked before the switch: one that is not percent-encoded ASCII is
  refused with nothing changed, and a query or fragment is dropped.

- On a served mirror, each file bar of a diff offers the changed file at either side of
  the change, as GitHub’s View file does, for a commit’s diff and for a pull request’s
  Files changed. **View file** opens the new side; **View at parent** (a commit’s diff)
  or **View at base** (Files changed, where the base is the merge base) opens the old
  side. A deleted file has only its old side, an added file only its new side, and a
  renamed file opens its old path at the old side.
  Only a regular file’s side is offered: a submodule has no file to show, and a symbolic
  link would open its target rather than the link text the diff shows.
  A side at the commit the page shows is a link to the file’s `/view/` address, so a new
  tab, a copied link, and back and forward work as for any link.
  A side at another commit is a button that switches the served pin to that commit with
  `POST /api/source/pin` and opens the file there; its tooltip names the commit, and a
  switch the server does not make, such as a commit the mirror lacks, is said under the
  file bar while the page stays as it was.
  There is no address for a file at a commit the server does not serve, so such a side
  has no link to copy or open in a new tab.
  A name that is not UTF-8 is addressed by its bytes.
  A diff in a served folder, and a patch file’s diff, have no such control: a folder has
  no file at a commit to open, only its working tree’s. The first diff on a pinned page
  requests `/plugin-static/diff/diff-view-file.js`, which decides the View file
  controls; a folder’s diff does not.

- `POST /api/source/pin` with `{"oid": …}` keeps the ref when the commit is its tip.
  A commit pinned by ID had no ref.
  It is now served under the ref the server last served, or the served pull request’s
  `refs/pull/<n>/head`, when it is that ref’s tip in the mirror, so going to another
  commit and back by ID, as View file does, ends on the branch or the pull request
  again: the selector names it and freshness follows it.
  A commit ID that is the tip of the ref already served answers `changed: false`. Any
  other commit pinned by ID still has no ref.

- Back and forward onto a page whose commit the server no longer serves now land on the
  commit it does serve.
  A browser brings a page back from its back/forward cache or its HTTP cache without
  asking the server, so after a pin switch (the selector’s, the freshness row’s, View
  file’s) Back showed a page naming the commit served before, with “Could not load
  files” and every data request refused as `pin_changed` until a reload.
  On such a landing the page now asks `/api/source/status` once and reloads itself, at
  most once, when another commit is served.
  A landing with nothing switched is untouched: it stays in the back/forward cache and
  keeps its scroll position.
  A page that stayed open while another tab switched still gets the reload offer rather
  than a reload.

- The Git panel no longer rebuilds a different history under the rows on screen when the
  refs its walk was fingerprinted by moved, as a refresh, a pin switched in another tab,
  or a commit in a served checkout does.
  It keeps the rows, stops paging, and says “History changed since this list loaded”
  with a Reload history action.
  An expired history session still rebuilds silently, because nothing changed.

- A timed-out or cancelled acquisition kills Git’s whole process group, including the
  helpers it forks, rather than only the `git` process.
  Git built by a distribution that backports the security fixes without raising the
  upstream version is still refused below the acquisition floor.

- A classified `file://` source can be fetched into an isolated worktree-free staging
  store using Git’s pack transport (`git fetch`, not `clone --local` hardlinks).
  The fetch is a full clone, every object reachable from the origin’s branches and tags,
  so a published store never needs its origin again.
  An origin that is itself a partial clone missing objects is refused with a message
  that says so. A later acquire of the same `file://` source publishes that staging entry
  into `repository-stores` and a source alias as the visibility commit, or reuses a
  store already published for that identity.
  The default branch is read only from the origin’s own `HEAD`, and an acquire whose
  fetched default branch does not resolve to the observed `HEAD` commit is refused
  before publication. Acquisition runs Git without any inherited `GIT_*` variable, so an
  ambient `GIT_ALLOW_PROTOCOL` or `GIT_DEFAULT_REF_FORMAT` cannot widen the protocol
  policy or change the published store’s ref format.
  It also stops repository discovery at its own staging directory, so a repository that
  encloses the application home, such as a dotfiles checkout, does not lend its
  `url.*.insteadOf` or other local configuration.
  A staging entry whose liveness lock is free is swept on the next cache open.
  Nothing deletes a published store: one that an interrupted acquisition left without
  its alias is reused by the next acquisition of that source.
  Read routes do not sweep.
  A cache that an earlier v0.12 development build wrote is not migrated: every `file://`
  mode refuses it with one message, without a traceback or a path, saying to move the
  cache directory aside or set `METABROWSER_CACHE_DIR` to a different directory.
  A `file://` acquire that the Git version floor refuses does not create the application
  home, including when that path already exists as an empty directory; a cache hit still
  reuses a published store without fetching, including against an application home the
  process cannot write.
  That hit does not open the cache or require the Git floor.
  A miss against that home fails instead of fetching.
  A future layout is still refused before any write.
  A successful acquire or cache hit may record `last_opened_at` on the source; a
  read-only home, full disk, or contended lock drops that write and still returns the
  published alias.

Content trust:

- Markdown from an untrusted source renders inert.
  With active content off — every served mirror, where a fork’s author controls the
  head’s Markdown, and a folder served with `--untrusted` — a document’s KPress render
  reaches the page only as an allowlist of plain markup, on the server and again in the
  page: paragraphs, headings, emphasis, code, quotes, lists, tables, details, links, and
  images inside the served tree, with no class, `name`, `data-*`, style, or event
  attribute, no `id` the document wrote, and no SVG, MathML, media, stylesheet, frame,
  form, or script. KPress kept such markup in its sanitized mode, so a README could load
  a stylesheet or images from anywhere, make the page load KPress’s video script and a
  YouTube frame, cover the page with the application’s own dialog styling, reach its
  document-wide handlers, or clobber a global.
  Repository images and relative links keep working inside the pin; an outside image
  becomes a link; code blocks show without highlighting; and no KPress script loads.
  Headings get the anchors github.com gives them, `user-content-` and the GitHub slug of
  the heading’s text, numbered on repeats, made by the allowlist and never taken from
  the document; a `#name` link becomes `#user-content-name`, and a GitHub address’s
  `#name` scrolls to that heading.
  The page draws the table of contents from KPress’s entries and runs it itself.
  `GET /api/kpress/render` answers such a render marked `inert`, with only stylesheets
  in its assets, KPress’s table of contents taken out of the HTML, `toc` saying whether
  KPress drew one, and `model.headings` pointing at the anchors.
  Trusted folders render as before.
  The pull-request page uses the same allowlist, now in core
  (`src/metabrowser/inert_html.py`, `static/inert-html.js`). The Markdown plugin has
  three more files for it, which `metab --plugin markdown` lists among its assets:
  `inert-render.js`, `inert-toc.js`, and `place-rendered.js`, which places a render and
  imports the other two on the first inert one.

- One more module is requested on every Markdown view, with nothing visible changing on
  a folder: `/plugin-static/markdown/place-rendered.js`, for the reason above.

- The comparison adapter resolves a revision with
  `git rev-parse --verify --end-of-options <rev>^{commit}`, so a revision that begins
  with `-` is an argument and not an option.
  A revision that names a commit resolves as before.

- With active content off the application page carries a Content-Security-Policy:
  scripts run only from the application’s `/static/` and `/plugin-static/` paths and the
  shell’s inline scripts by a per-response nonce, never from the browsed tree’s `/raw`
  files; stylesheets, fonts, images, requests, and the Markdown worker load from this
  server alone; the page frames nothing and nothing may frame it
  (`X-Frame-Options: DENY`); and no plugins, `<base>`, or form submission.
  `/raw` refuses a browsed file requested as a script, stylesheet, worker, or worklet,
  and sends JavaScript and CSS as `text/plain`. See SECURITY.md.
  The help for `--untrusted` and `--no-active-content` now says that they render
  Markdown inert and apply this policy, not only that `/raw` loses `allow-scripts`.

- **Changed for a folder on disk:** `--untrusted` and `--no-active-content`, and their
  `METAB_UNTRUSTED=1` and `METAB_ACTIVE_CONTENT=0` forms, now apply both entries above
  to a served folder, not only to an acquired source.
  In 0.11 they dropped `allow-scripts` from the `/raw` sandbox and omitted the HTML
  Preview tab, and Markdown rendered as it does in a trusted folder.
  Such a folder’s Markdown now renders inert, so code blocks lose their highlighting, an
  outside image becomes a link, and Obsidian wiki links and embeds show as plain text;
  and its page carries the Content-Security-Policy.
  It keeps KPress’s card and the reader’s measure, on the one inert path a mirrored
  file’s Markdown and a pull request’s text also take.
  A folder served with neither flag renders as before.

- In an inert render, a query alone and root-relative `/api`, `/_debug`, and `/raw`
  references lose their address, as does any link or image past the link enhancer’s
  limit; images resolve before the page loads them; and Obsidian wiki links and embeds
  show as plain text.

- The application writes no inline event handlers: the file header’s print button, the
  structured view’s copy button, an agent log’s event toggle, and the partial-content
  notice’s Load more use delegated listeners.
  A partial-content notice’s Load more runs only an action registered by name, only from
  the button the notice built: the shell’s text loader by default.
  `partialNoticeHtml`’s `action` string no longer becomes an inline handler; a view that
  continues its own content passes `action: null` and wires its own listener.

- The application’s document-wide handlers act only on controls the page created.
  A trusted folder’s Markdown keeps class, `id`, and `data-*`, so a document could write
  `data-mb-copy="text"` with its own `data-mb-copy-text` and replace the clipboard on a
  click, or spell an address crumb (`data-nav-dir`, `data-nav-file`), the print button,
  or a Load more button.
  The copy, Load more, crumb, parent-folder, and print handlers now require
  `data-mb-owner` with a value drawn when the page loads, which a document written
  earlier cannot carry, and the tooltip ignores a rendered document’s `data-tip-text`.
  The header’s print button no longer has an `id` (`print-view-btn`), so a label naming
  it could not click it with its mark; SECURITY.md lists what the mark does not cover.

- The warning that a `.env` or `.env.local` file’s names were ignored shows those names
  and the file’s path as visible escapes on one line.
  A browsed repository could otherwise colour or erase that line, or add a line of its
  own, with a name holding escape sequences or a line break.

Content source:

- The server now has one active repository subject per process.
  An attached local folder is `AttachedFilesystemSubject`. File, raw, tree, container,
  and event routes read through its `ContentSource`, and inventory open goes through
  `InventoryCoordinator.open_subject`. A Git pin is accepted there without opening a
  filesystem walker; Git routes own the complete-at-once index.
  `resolve_path` and `served_root` stay filesystem-only; a non-filesystem subject raises
  `UnsupportedSourceCapabilityError`. Recency, ignore, watcher, activity, and mutation
  each have a typed capability gate.
  Filesystem browsing is unchanged.
  A `GitRevisionSubject` can pin a full-OID tree over a worktree-free store: `GitPath`
  is a lossless byte-segment identity, `GitTreeSource` lists NUL-framed trees and reads
  size-gated blobs through exclusive `cat-file --batch-command` actors, and missing or
  oversized objects fail before an unbounded body read.
  `open_revision` pins a commit in a published store without a lock or a ref of its own:
  nothing runs `gc`, `prune`, or `repack` on a store, so a commit in it stays readable.
  Two processes can read different OIDs in one store, and a pin opens from a home the
  process cannot write.
  Batch `cat-file` actors are pooled per store, at most four in one process.
  `/api/git/repo`, refs, summary, log, and commit detail honor a `GitRevisionSubject`
  through `GitLocation` (a worktree path or a `RepositoryStoreTarget` plus pinned OID).
  Discovery reports a detached HEAD at that OID and never a cache path; the default
  history walk is the pin, not the store’s ambient HEAD. `/api/tree`, `/api/file`, and
  `/raw` honor `GitPath` wire identities on that subject: tree listings carry mode,
  kind, oid, symlink, gitlink, and `cat-file` blob sizes (trees and gitlinks stay
  unsized; no mtime or ignore); recency returns `unsupported_for_subject`; `min_size`
  filters blobs that have a size; blob reads are size-gated through the shared cat-file
  pool. `/api/plugin/diff/comparison` honors that pin through `GitLocation`: `HEAD` is
  the pinned object id, not the store’s ambient HEAD, and the document names Git object
  facts rather than a cache path.
  `GitDiffSource.content` on that pin reads the blob through the shared cat-file pool
  and the same size gate.
  `/api/kpress/render` reads the blob by `GitPath` and uses the object id as the render
  cache key instead of a filesystem mtime.
  A patch-file container inner is a `GitPath` `g1-` prefix plus a host inner path;
  `/api/file` returns that envelope, and the diff plugin’s document and children hooks
  read the patch blob through the shared cat-file pool.
  `/api/plugin/binary/chunk` reads a bounded window of one Git blob by `GitPath` and
  uses the object id as the cache key instead of a filesystem mtime.
  Git blobs classify by extension, basename, sniffed adapter, and bounded JSON, YAML,
  and Markdown-frontmatter mappings parsed from blob bytes (`classify_identity`).
  `path_glob` stays filesystem-only.
  `/api/plugin/structured/parsed` reads the blob by `GitPath` and uses the object id as
  the cache key instead of a filesystem mtime.
  Its `size` on a pin is the blob’s length; on a folder it is the file’s size on disk,
  as in 0.11.0. Neither is capped at the parse limit.
  `/api/file` for a Git `.jsonl` blob is a parsed JSONL envelope; adapter sniffing
  claims `agent-log` when the bytes match Claude, Gemini, or Pi.
  `/api/plugin/agent-log/charts` reads that blob by `GitPath`. `/api/rollup` on a pin
  answers from recursive blob names and sizes, omits mtime, and treats ignore as absent
  so unignored equals total.
  A missing blob size is `object_unavailable` rather than a partial sum.
  `/api/catalog` on a pin lists those blob names as Quick File rows (`p` GitPath wire,
  `e` display suffix, `n` display basename) and is complete at once; a truncated tree is
  an empty truncated snapshot rather than a partial list.
  `/api/index/progress`, `/api/index/meta`, and `/api/capabilities` report that same
  complete-at-once index without a watcher or invented mtime; events stay off.
  `/api/tree` carries whole-tree `extensions`, `canonical_extensions`, `type_families`,
  and `type_presets` rows (`[key, tracked, 0]`), `tally_cache_status`, and a `summary`
  (`files`, `size`, ignored 0/0) from that index so the type filter, truncation banner,
  and nav header counts do not wait on a filesystem walker.
  Incomplete blob sizes omit `summary` rather than inventing 0. `types` and `min_size`
  keep ancestor trees of matching blobs and emit subtree `filtered` totals; empty filter
  dirs are omitted. Git listings, catalog rows, and type filters use the same bounded
  compound-tail logical extension as filesystem inventory (`bundle.min.js` is
  `.min.js`), so a basename that merely ends in `md` is not a `.md` match.
  `include_ignored=0` on a pin is a no-op, because ignore is absent and unignored equals
  total; the SPA hides Show ignored.
  `/api/tree` `depth` nests SPA children the way filesystem listings do (default 2) and
  emits a lazy sentinel past the cap; `depth=0` returns chrome without a listing.
  The SPA hides Modified within: recency still has no honest mtime and remains
  `unsupported_for_subject`. Git SPA file nodes emit `ext` as that compound-tail
  extension; `logical_ext` is only the inner extension of a compressed name
  (`events.jsonl.gz` is `ext=.jsonl.gz` and `logical_ext=.jsonl`). Git `/api/file` blob
  envelopes include that same `ext` so plugin-sdk `langForPath` and `ctx.ext` do not
  fall back to a GitPath wire; they omit compressed identity because blobs are stored
  bytes with no gzip smudge.
  Git `/api/file` markdown envelopes include parsed YAML `frontmatter` and
  `frontmatter_error` the way filesystem envelopes do; KPress on a pin uses that parse
  rather than an empty mapping.
  Git text envelopes use the same first-window and highlight bound as filesystem
  listings (`bytes_read`, `content_preview_limit`, `content_max_preview_limit`,
  `highlight_disabled`) so Load more and `fetchText` can continue a truncated pin.
  `/api/file`, `/raw`, KPress, and plugin sidekicks follow in-tree relative symlink
  blobs to the target object; the requested GitPath stays the route identity.
  Kind checks (JSONL, structured, patch) use the leaf path.
  Listings still show the symlink.
  A Git image blob is SPA `image` chrome (`ext` from the compound tail, preview view, no
  inline content); `/raw` serves the stored bytes and the image plugin uses the display
  name as `alt`. Newline and invalid-UTF-8 GitPath names stay lossless on the wire;
  display chrome replaces C0 and undecodable bytes with U+FFFD. Absolute, dangling, and
  cyclic targets 404. `/api/stream` still returns `unsupported_for_subject` rather than
  the lifespan filesystem inventory.
  A Git LFS pointer blob is the stored pointer bytes, with no smudge filter.
  A blob the tree names but the store lacks is `object_unavailable` and does not contact
  the remote. `/view/` on a Git pin accepts a `GitPath` wire, optionally plus a
  patch-file container inner, and refuses a filesystem spelling; missing Git objects
  remain valid shell destinations.
  `/api/tree` on that pin keeps Git-native `entries` and also projects a SPA `tree`
  array (`dir` / `file` / `symlink`, `GitPath` wires, depth-bounded nested `children`
  with a lazy sentinel past the cap) with `cat-file` blob sizes on files and symlinks
  and recursive blob `total_files` / `total_size` on directories, without mtime or
  ignore facts. Gitlinks project as files, not directories.
  A Git tree `/api/file` envelope is SPA `folder` chrome (`git_kind` stays `tree`) with
  recursive blob `total_files` / `total_size` and no mtime or ignore.
  Markdown and wiki links on that pin encode authored segments as `GitPath` wires; the
  known-file catalog uses the tree node’s display `name` as the basename, and KPress
  `source_path` is the wire rather than a display path.
  A Git tree folder with a complete blob-size tally mounts Overview and treemap.
  A direct-child README blob sets `readme_path` to its GitPath wire.
  File Overview mounts when `dir` carries `total_size`. SPA path chrome and copy-path
  decode GitPath wires to display names; navigation identities stay wires.
  Omitted Git mtime still leaves age chrome empty rather than pulsing as a
  still-finalizing inventory walk.
  Blob listings carry `cat-file` info sizes so `min_size` can filter; trees and gitlinks
  stay unsized. Recursive `ls-tree -r` tallies fill directory `total_files` /
  `total_size` and the Git `/api/rollup` tree.
  Inventory open and archive containers are not switched yet.

- The content-trust profile applies to a Git pin.
  A pin runs under the untrusted profile on `--show` and `--api` as it does when it is
  served, and `GET /api/capabilities` on a pin carries the resolved block,
  `active_content: false` and `mutations: false`, so Preview is withdrawn there too.
  `--untrusted` and `--no-active-content` are accepted on a pin and change nothing;
  `--allow-edits` is refused.

- `/api/tree` on a Git pin nests at most 20,000 nodes below the listed directory.
  Direct children are always listed; a directory whose children no longer fit is the
  same lazy sentinel the depth cap emits.
  Whole-tree tallies, filter totals, index status, rollup, and the catalog are derived
  once per pin instead of on every request.

- Git failures on a pinned tree answer with a typed JSON envelope instead of a bare 500:
  `git_timeout` is 504, a tree the store lacks is `object_unavailable` 404 naming the
  missing object, and any other Git failure is `git_failed` 500. No envelope carries Git
  output, so none carries a local path.

- Every request-path read of a published store (tree listing, history, commit detail,
  diff) runs under one store-read policy: isolated configuration, no lazy fetch, and the
  15-second request deadline instead of the 15-minute acquisition deadline.
  A store target read without a named policy gets the same policy, and whole-tree blob
  sizes are read in chunks that each get the batch deadline.

Large pull requests:

- PR refresh prepares and retains the immutable comparison manifest, so opening Files
  changed on a fresh server can reuse it.
  The GitHub comparison route remains scoped to the PR’s published store, and missing or
  invalid cache entries heal on demand.

- `diff/comparison` no longer recomputes a comparison on every request.
  The patch is limited to the files being hydrated, and the manifest is computed once,
  in one Git run. On a store, a request naming two commit IDs keeps its manifest and
  answer in memory, sends an `ETag` naming the build and the store, and answers
  `If-None-Match` with 304; with `&build=` naming this build and `&store=` naming this
  store, which the page gets as `METABROWSER_SETTINGS.STORE_TAG`, it is also
  `immutable`, so a browser’s Back makes no request, and one store’s kept answer never
  stands for another’s or for a folder’s on the same origin.
  Its documents are unchanged, and a folder’s comparison keeps nothing and sends neither
  header. A store’s reads see none of the reader’s attributes files (`HOME`,
  `XDG_CONFIG_HOME` and the system file), so every reader gets the same answer, and no
  commit’s `.gitattributes`: Git 2.43 reads a bare repository’s from its default branch,
  so on that Git a store’s comparison of two fixed commits changed with a fetch that
  moved `HEAD`, and 2.50 reads none; a store read now names the store’s empty tree as
  its attributes source, and the same two commits answer the same bytes on every Git
  Metabrowser admits. A store’s own `info/attributes` is the one attributes input a store
  read honors; it is in the store’s token and in the key an answer is kept under, so an
  edit to it moves every address and is answered afresh by a running server.
  A folder’s comparison keeps honoring its working tree’s `.gitattributes`, its
  `.git/info/attributes`, and the reader’s own attributes files and configuration, as
  `git diff` in that folder does.

- A pull request’s Conversation prepares the initial Changes comparison when the browser
  is idle. Opening Changes reuses that payload when ready; nearby deferred patches still
  load as needed. A pull request’s page no longer fetches the repository’s file catalog
  until its search palette opens or the reader leaves for a file.

- A comparison’s 8 MiB bound applies per file, and only to the files a request asked
  for. One file past it says it is too large to show, a file that would take a request
  past it loads when the reader reaches it, and neither costs the rest of the
  comparison. A file past 8 MiB of the whole patch could not be loaded at all before.

- Deferred diff files use the shared delayed spinner while loading.
  Failed loads and truncated results have notices, in pull-request and commit
  comparisons alike.

- A pull request’s record refreshes with its five parts in flight together instead of
  one after another, and serving one with no record says “reading pull request N” after
  half a second, on the cadence of a clone’s progress, instead of saying nothing.

- A deferred file reserves an estimate of its height.
  The diff asks for one file at a time, prioritizing an explicit jump before visible and
  nearby files, and renders at most one per frame.
  What is at the top of the pane stays there as files fill in.
  This holds in a commit’s diff in a served folder as well.

Fixes:

- A commit at a shallow repository’s boundary is no longer shown as if it were a root
  commit. Git grafts such a commit into a root, so its diff was taken against the empty
  tree and every file read as added, with no warning, in the commit view, `--diff`, and
  `/api/plugin/diff/comparison?revision=`, on a served shallow checkout and on a mirror
  borrowing from one alike.
  The comparison now answers a typed refusal, `parent_unavailable`, that says the parent
  is beyond the history here, and `/api/git/commit/<id>` reports that commit’s `stats`
  as `null` counts with no files, which the panel shows as `?`. A real root commit is
  unchanged. `/api/git/log` still lists the commit with no parents, as Git’s own log does
  on a shallow clone; the status route says the history is shallow.

- A pull request or a `.patch` file that deletes an empty file now shows its changes.
  Git writes no hunks for that, nor for a deleted binary file, and the parser could not
  model the section, emptied the whole document, and left the comparison route answering
  `404 "file 'f1' not found in the produced diff"`, so such a pull request had no Files
  changed. A section that still cannot be modeled now keeps its row and is named in
  `resolved.warnings`, which the diff view shows above the files, and the rest of the
  comparison is kept. A section with no hunks whose path is quoted or holds ` b/` is read
  from its `diff --git` line rather than dropped.

- A file whose name Git quotes with `\a`, `\b`, `\f`, `\r` or `\v` now loads: the parser
  undid only `\n`, `\t`, `\"` and `\\`, so such a file was left out of every comparison
  and `.patch` file with a warning.
  A name that begins or ends with a space now loads alone from a comparison, where
  `file=` was stripped before it was matched.
  A tree entry Git refuses as a pathspec, such as `..` from a source that runs no fsck,
  no longer fails the whole page: the comparison runs unrestricted for it.

- A comparison’s patch runs are pinned to Git’s own `a/` and `b/` prefixes and to its
  internal diff, so a folder’s `diff.noprefix`, `diff.mnemonicPrefix` and
  `diff.external` no longer reach the parser, where `diff.noprefix` left a mode-only
  change unnamed and failed.
  `metab --diff` prints a document’s warnings above its files in text form, as the page
  shows them. A Git failure behind `diff/comparison` answers “git diff failed” or “git
  diff timed out” and logs the command; the body no longer spells every path asked for.

- A diff’s “N of M files loaded” note counts a file that could not be loaded apart from
  the loaded ones, a file that leaves the viewport after its answer arrived is rendered
  rather than asked for again, and one file’s render failing no longer stops the files
  after it from loading.
  A file whose render fails after the server answered says so where its lines would be
  and is counted the same way; before, it showed nothing and counted as loaded.

- `metab --diff` on a comparison whose whole patch is past 8 MiB answers every file,
  each file past what one run hydrates asked for alone, as the page does once a reader
  has reached every file; a file too large for one patch is listed as `too_large`, and
  `--diff-check` refuses such a comparison by name.
  Before, it answered `diff error: file 'fN' not found in the produced diff`.

- A diff draws the lines of the files on its first screen, and one screen more, when it
  opens, and each later file that came with it when the reader reaches it, from what the
  page already has, so nothing more is asked of the server.
  Every file’s bar is there at once and holds its own height, a file the reader is
  looking at stays where it is as others fill in, and a file looks the same once drawn.
  Before, a diff drew every file it was sent in one task the page waited on, at load, on
  Back, and on opening Files changed: on a 1,031-file pull request that was 114,609 page
  nodes and about 1.1 s, and it is now 23,451 nodes and a longest task of 114 to 330 ms,
  with the first line 1.4x to 2.0x sooner, measured in Chrome under load.
  A commit’s diff in a served folder and a `.patch` file’s view are the same view and
  draw the same way; a diff that fits on its first two screens is drawn whole at once,
  as before. The browser’s find in page now finds a line only in a file that has been
  drawn, as on GitHub; it still finds every file by its path, and going to the file
  draws its lines.

- Pull request messages follow the active system font when converting the reading-width
  preference to a text measure.
  Ordinary document widths are unchanged.

- A `.env` or `.env.local` that cannot be read as text no longer stops `metab` with a
  traceback in every mode.
  It is skipped with a warning naming the file, so a repository whose `.env` is not
  UTF-8 can still be browsed.

- A `.env` or `.env.local` can no longer hold `metab` before it starts.
  A FIFO, or a link to one or to a piped stdin, blocked the command, and a large file
  could take minutes to parse.
  One that is not a regular file or is larger than 64 KB is now skipped with a warning
  naming the file, and python-dotenv’s warning about a line it cannot parse is printed
  once for a file rather than once a line.
  **A value’s `${VAR}` is no longer expanded:** `METABROWSER_LOG_LEVEL=${MY_LEVEL}` now
  sets that literal text, which falls back to `INFO`, where 0.11.0 expanded it.
  Expansion is what made the parse quadratic in the file’s lines, and neither name a
  dotenv file may set needs it.

- `metab --api <route> --format json` or `--format yaml` prints the envelope alone, so
  stdout parses; a body that is not JSON is one string, and a refresh that waits prints
  only the status it ended with.
  An explicit format used to print the `api:` and `status:` lines above the envelope
  too. Without `--format`, the output is unchanged.

- Choosing with the keyboard works past the first key press.
  In Files / Bytes and Split / Unified, an arrow key changed the choice and left focus
  nowhere, so the next key did nothing.
  Focus now stays on the chosen segment.

- Controls that offer a choice answer every state the same way.
  An unselected segment of Files / Bytes or Split / Unified now raises the hover fill,
  as other chips and the menu’s segments do, and a theme or reading-font segment and a
  tab (Overview, Document, Files) show the shared focus ring under the keyboard.
  A selected theme or font segment showed no focus at all, and a tab the browser’s own.
  A commit diff’s fold controls show that focus ring too, where they showed the
  browser’s own. Nothing else on a plain-folder page changes at rest, apart from the next
  entry.

- The note that a folder’s file list is incomplete, in a folder over the file limit, is
  now the app’s warning notice, as other notes about partial content are: a
  warning-colored border on the ordinary surface, in place of the sidebar fill and
  bottom rule.

- The filter drawer’s toggle, a diff’s copy button, and a structured view’s copy button
  no longer show the browser’s tooltip beside the app’s. The drawer’s tooltip now
  follows its state, the structured view’s button has an accessible name, and Overview’s
  Show ignored has the tooltip it was written with.

- A diff in a narrow pane no longer hides its additions.
  Split needs 44 ems of width, and below that its right column was off-screen behind a
  sideways scroll, so an added line read as a blank gap.
  Such a diff now draws Unified, in a pull request’s Files changed and in a commit’s
  diff in a served folder alike, and goes back when there is room.
  The layout control shows what is drawn, and **Split** says why it is not selected.
  The remembered choice is not touched, and choosing **Split** in a narrow pane still
  draws it. A wide pane draws what it did.
  A pane opening within 20 px of the limit counts as narrow, because the pane’s
  scrollbar may not have arrived, so a reader sees one layout from the first paint.

- A served folder holding a filename with a backslash, which POSIX allows, no longer
  fails its whole index: the index progress route errored and the tree answered HTTP
  500\. The inventory now escapes the backslash as `%5C`, as it escapes a literal `%` as
  `%25`, so the file lists, opens, and has a `/view/` URL (`/view/a%5Cb.txt`); the tree
  shows its real name.
  A literal backslash in a `/view/` URL is refused, and Windows, where a backslash is a
  separator, is unchanged.

- In a trusted served folder, a Markdown link to a file whose POSIX name holds a
  backslash now opens it.
  Markdown writes the backslash escaped (`[notes](a\b.md)` links to `a%5Cb.md`, as on
  GitHub), and the link resolver and the published-route adapter now spell it `%5C`, as
  the inventory does, instead of refusing the link.
  In a Git pin such a link is still refused, and a literal backslash in a link’s
  address, which a browser reads as a separator, still is everywhere; under the
  untrusted profile the inert allowlist drops an escaped backslash from any reference.
  Wiki links refuse a backslash as before.

- `/api/plugin/structured/parsed` no longer answers with a path on the host.
  For a JSON or YAML file it could not open, such as one without read permission, 0.11.0
  answered 200 with
  `parse_error: "PermissionError: [Errno 13] Permission denied: '<the file's absolute path>'"`.
  It now answers 404 `content_unavailable` and names the served path.

- `/api/plugin/diff/document` and `/api/plugin/diff/children` no longer answer with a
  path on the host either.
  For a file they could not open, such as a patch without read permission, 0.11.0
  answered the degraded `plugin_error` envelope with
  `detail: "PermissionError: [Errno 13] Permission denied: '<the file's absolute path>'"`
  and logged a traceback.
  They now answer 404 `diff_document` or `diff_children` and name the served path.

- A compressed patch is read as the patch it holds.
  `change.patch.gz` is the `diff` kind, but 0.11.0 parsed its compressed bytes:
  `/api/plugin/diff/document` answered that it recognized no diff, and
  `/api/plugin/diff/children` and a virtual child `change.patch.gz/<path>` answered 404.
  The three now read the patch the file holds.
  A compressed file whose stream cannot be decoded within the first 8 MiB of decoded
  content, which is as far as they read, answers the same 404 as a file that cannot be
  opened. Damage past that is not reached: they answer the patch they read, marked
  truncated, as they do for an undamaged patch that long.
  `/api/file` shows a damaged file as bytes when the damage is in the first 512 KiB it
  reads. Damage past that is not seen there: an 8.5 MB patch whose gzip is cut at 80%
  still says `kind: diff`, and the Diff view shows “This file is not available.”, where
  0.11.0 showed an empty change set, as it did for every `.patch.gz`.

- A byte limit set below zero gives a typed, empty answer on every value.
  This applies to `STRUCTURED_PARSE_MAX_BYTES`, `METABROWSER_BINARY_PREVIEW_BYTES`,
  `METABROWSER_BINARY_PREVIEW_MAX_BYTES`, and
  `METABROWSER_BINARY_PREVIEW_MAX_CHUNK_BYTES`. 0.11.0 answered by accident of
  arithmetic: at -1 the binary route returned an empty chunk, at -2 it read the rest of
  the file with no bound, and at -3 or lower it answered the degraded `plugin_error`
  envelope; a compressed file answered `plugin_error` or a parse error that quoted the
  reader’s own bound check.
  Now a negative structured limit answers `truncated` for every file, a negative chunk
  size answers an empty chunk and says whether bytes remain, and a negative offset
  ceiling answers 404. Zero is unchanged for the binary settings and for a structured
  file that is not compressed, apart from a file that cannot be opened.
  At `STRUCTURED_PARSE_MAX_BYTES=0` a compressed structured file no longer answers that
  parse error, and answers as it does at any limit too small for it: `truncated` when
  the start of its stream decodes, whatever damage follows, a decompression parse error
  when it fails before that, and what an empty file answers when it holds nothing.
  A file that cannot be opened answers 404 `content_unavailable` at zero too, where
  0.11.0 answered `truncated` for an uncompressed one larger than the limit, without
  opening it.

- Load more on a large text file in a pin advances its notice and continues the text.
  A pin’s later window reported its own length as `bytes_read`, where the filesystem
  reports the cursor past the window, so after Load more the notice kept reading
  “Showing 2.0 MB of 15.2 MB” and the next Load more read from 2.0 MB again, repeating
  text. `/api/file` on a pin now reports the cursor, as a served folder does.

- In a pane too narrow for the Contents rail, the table-of-contents toggle now stays at
  the pane’s trailing edge as the document scrolls, so the drawer opens from any depth.
  It used to scroll away with the document, in a trusted folder and a mirror alike,
  because the scrolling preview pane was also the box its fixed position pinned to.
  The pane now scrolls inside a non-scrolling frame that holds the drawer, its toggle,
  and its backdrop, as KPress’s embedding contract asks.

- A tree row replaced during the tooltip’s 300 ms delay, as when its folder re-renders,
  no longer puts a tooltip at the window’s top-left corner until the next hover.
  The tooltip does not appear when its anchor has left the document, and one still up
  for another row is put away.

- A folder the inventory leaves out says why it has no totals.
  `/view/.github/` and a symbolic link to a folder keep their page and README, but File
  Overview said “Could not load file types.”
  and the header’s tally stayed pending forever.
  File Overview now says, for example, “Metabrowser does not index hidden folders, so
  this one has no file totals.”, and the header shows no tally.
  `/api/file` still answers 200 with the folder envelope, which gains `dir.not_indexed`
  (`hidden` or `symlink`) on such a folder and is unchanged on every other.

- File Overview and Treemap no longer keep a loading skeleton when the rollup cannot
  supply one. A failed or refused request, or an index that finished without the folder,
  now stops the totals’ skeleton and the Treemap’s, which says “Treemap unavailable.”;
  changing Files or Bytes or Show ignored after a failure keeps the failure’s message
  instead of bringing the skeleton back; and a refresh that fails while nothing has been
  counted says so and offers Retry where the request can be retried.
  A scan that is still running keeps its skeletons, and an answer that it is running
  brings them back after a failure.

- A JSONL log’s event rows answer the keyboard.
  Each row’s header is now a button with a tab stop and an expanded state, and Enter or
  Space opens and closes it as a click does.
  A keyboard could not reach a row in 0.11.0 either, and moving the rows off inline
  handlers in this release had also removed the clickable node the accessibility tree
  showed. A click on a row opens it as it did, and now also focuses it.

- Back or Forward onto a `/commit/` entry shows the commit.
  With a file opened in-page over a commit, Back changed the address and left the file
  showing, because the Git panel restored a commit only when the page loaded.

- A `/commit/` address with a short commit ID, or a ref name with no slash in it, now
  says it needs the full lowercase ID, in place of “Could not load this commit.”
  `/api/git/commit/<rev>` still refuses such a revision with 400, and its answer now
  carries the `revision_not_full` code.

- File Overview’s type distribution says which population it counts, in a caption such
  as “Share of Files (536 files)” or “Share of Total (8,533 files)”. The percentages
  match the Total row while Show ignored is on and the Files row while it is off, which
  a reader could otherwise tell only by comparing the numbers of two tables.
  The caption follows Show ignored and the measure, and is the table’s accessible
  caption.

- A tree that reaches the 500,000-file cap now says so.
  The file list shows “File list incomplete.”, File Overview says its summary is
  partial, and Treemap draws the indexed files under “Index capped at 500,000 files”;
  before, it stayed on its loading skeleton and nothing mentioned the cap.
  `/api/rollup` answered `index_status: "idle"` and `truncated: false` for such an
  index, and `/api/tree` and `/api/recent` answered `tally_cache_status: "idle"`, as
  0.11.0 did. They now answer `truncated`, as `/api/index/progress` and `--walk` already
  did.

- Switching between the Files and Git tabs no longer carries one list’s scroll offset
  into the other: the two share one scroller, and each now keeps its own place in it,
  where 0.11.0 carried the offset of the list last shown into the other.

## 0.11.0

Content trust:

- **A `.env` or `.env.local` file now contributes only `METABROWSER_LOG_LEVEL` and
  `METABROWSER_REQUEST_LOG`.** Every other name is read from the process environment or
  not at all.

  This closes arbitrary code execution through a browsed repository’s `.env`. The chain
  walks up from the working directory, so `cd cloned-repo && metab .` reaches that
  repository’s own file and the loader cannot tell it apart from one you wrote — and the
  environment decides which program runs.
  `BROWSER` is honored by the standard library’s browser launcher, which `metab` calls
  by default; `GIT_EXTERNAL_DIFF` is executed by the `git diff` the diff views spawn.
  Neither `--untrusted` nor any other flag helped, because the browser opens before any
  content is rendered.

  The two names that remain are the two whose values cannot do anything but what the
  knob means: one is checked against the known level names, the other is an equality
  test. That is the membership rule — a name belongs only if no value can make the
  program do something else.

  **If you keep configuration in a `.env`, move it to the environment.** Nothing else is
  read from a file any more, including the rendering budgets
  (`METABROWSER_HIGHLIGHT_MAX_BYTES` and the other `*_MAX_BYTES` names,
  `STRUCTURED_PARSE_MAX_BYTES`, `STRUCTURED_CACHE_SIZE`, `METABROWSER_SLOW_SERVER_MS`),
  `METABROWSER_PLUGINS_DIRS`, `METABROWSER_ALLOWED_HOSTS`, `METABROWSER_DEBUG`,
  `METABROWSER_INVENTORY_PROVIDER`, `METABROWSER_GCP_PROJECT`, and `HOME` — so
  `metab ~/notes` expands `~` from the process environment even when a `.env` names a
  different one. Metabrowser logs a warning naming any of its own variables it ignored,
  so a file that stops taking effect says so.

- `/raw` responses are sandboxed unconditionally.
  Every branch, including gzip passthrough, SVG, HTML, and error bodies, sends
  `Content-Security-Policy: sandbox allow-scripts allow-popups allow-forms allow-downloads`
  and `X-Content-Type-Options: nosniff`. Direct `/raw` links to HTML or SVG no longer
  execute with the application’s privileges.
  Nested iframes and framesets still load: the policy does not include
  `frame-ancestors`.

- `/api` routes require same-origin proof.
  The server accepts `Sec-Fetch-Site: same-origin`, `Sec-Fetch-Site: none` (a typed URL
  or a bookmark, which no document initiated), or a matching `Origin`; it refuses
  `Origin: null` and foreign origins, and still serves `curl` and `metab --api` (neither
  header). State-changing methods require `Content-Type: application/json`, so a
  cross-site form POST cannot reach `POST /api/kpress/export`. The guard derives the
  route the same way the router does, so it holds under an ASGI prefix mount as well as
  at the root.

- `GET /raw/{path}` serves the same bytes as `GET /raw?path=…`, so relative stylesheets,
  images, and sibling links in a browsed HTML file resolve under `/raw/`. The query form
  stays; it is the public API the image renderer uses.
  Both shapes share one resolver and the same sandbox headers.

- `--untrusted` (`METAB_UNTRUSTED=1`) is the conservative content-trust profile: it
  disables active content and keeps mutations off.
  `--no-active-content` (`METAB_ACTIVE_CONTENT=0`) drops `allow-scripts` from the `/raw`
  sandbox; it does not downgrade bodies to `text/plain`. `--allow-edits`
  (`METAB_ALLOW_EDITS=1`) publishes `mutations: true`; no write route consumes that flag
  yet. Individual flags override the profile.
  The resolved block is on `GET /api/capabilities` and
  `window.METABROWSER_SETTINGS.CAPABILITIES`.

- A flag on the command line outranks the environment in both directions: `--untrusted`
  stays conservative whatever `METAB_ACTIVE_CONTENT` or `METAB_ALLOW_EDITS` say, and
  only `--untrusted --allow-edits` lifts it.
  The `METAB_*` capability variables and `METABROWSER_ALLOWED_HOSTS` are read from the
  process environment only, so `cd cloned-repo && metab --untrusted .` cannot be talked
  out of the sandbox by that repository’s own `.env`. They are outside the dotenv
  allowlist described above, along with every other name the loader does not list.

- `.html` and `.htm` files are the `html` kind, with a sandboxed Preview tab and a
  Source tab. A 4 KiB sniff (doctype or `<html>` / `<head>` / `<body>` / `<frameset>`)
  chooses the default tab only.
  Preview uses path-shaped `/raw/{path}` and an iframe sandbox of
  `allow-scripts allow-popups allow-forms allow-downloads` with
  `referrerpolicy="no-referrer"` — never `allow-same-origin` or `allow-top-navigation`.
  `--untrusted` and `--no-active-content` omit Preview.

- Preview carries an **Open as full page** link to the same `/raw/{path}` document the
  frame is showing, so a page that wants the whole window gets it.
  It is a plain anchor, so middle-click and modifier-click behave natively, and it opens
  with `rel="noopener noreferrer"`. The tab is contained exactly as the frame is: the
  sandbox rides on the response headers, not on the iframe.

- A path carrying an embedded NUL — `/raw/a%00b`, or the same byte in a `?path=` value —
  is a 404 rather than a 500. No filesystem can hold that name, so it is a missing file
  like any other unresolvable path.

Performance:

- The catalog content identity is hashed one page at a time instead of four
  `digest.update` calls per record.
  At 300,000 rows the step drops from 62 ms to 41 ms.
  The digest is byte-identical — the same bytes in the same order — so nothing
  downstream of it changes.
  Hashing per page rather than per catalog keeps the transient bounded by the page.

## 0.10.0

Plugin SDK:

- The plugin SDK is now 0.6, a breaking change.
  A plugin manifest must declare `sdk_version = "0.6"`; manifests for 0.5 are refused at
  discovery and by `metab --doctor`.

- API paths are escaped inventory identities.
  Plugin readers, activity probes, Markdown links, browser URLs, and filename search now
  handle literal percent signs consistently.
  See [plugin path identity](docs/plugins.md#path-identity) for the conversion helpers.

- `mb.builtins.markdown.analyzeGraph()` is removed with no replacement in this release.
  It parsed Markdown separately from KPress and could disagree with the rendered
  document; a future graph surface will be a server route backed by KPress’s own link
  analysis.

- `fileCatalog.snapshot()` now includes `truncated`, which is true when the inventory
  walk finished at its file cap.
  `complete` still means every file under the root is listed, and the two are never both
  true. A plugin waiting for a final catalog should stop on either flag.
  See [Data and Navigation](docs/plugins.md#data-and-navigation).

Markdown fixes:

- An embedded note no longer times out before it starts loading.
  The 5-second transclusion allowance used to start when the first embed in a document
  resolved and was shared by every later embed, so a note whose link resolved after the
  file index finished could show “The embedded note timed out.”
  without being fetched.
  Each embed now has its own allowance from the moment it starts loading; the document,
  depth, source-size, and cycle limits remain shared.

- Wiki links in a task-list item followed by an ordinary link now convert.
  In `- [ ] Review [[Meeting Notes]] per [spec](https://example.com)`, the checkbox’s
  `[` was paired with the later link’s `](`, so the wiki link was left as literal text.
  Brackets now pair the way CommonMark pairs them, so checkboxes, shortcut references,
  and unmatched brackets no longer hide the wiki links that follow them.
  As in CommonMark, brackets that contain a link are plain text rather than a link, so
  the wiki links beside that inner link convert.

- Markdown links no longer say “Resolving link” forever in a tree larger than the
  inventory file cap. When the walk stopped at the cap, the file catalog never reached a
  final state, so basename wiki links, note embeds, and rooted extensionless links such
  as `/guide/` stayed pending, and every live file change re-ran their resolution.
  A capped walk is now a final catalog state: links that exact paths resolve still work,
  a wiki link with several indexed matches is reported as ambiguous, and links that need
  the unindexed files are disabled with the `catalog-truncated` reason in their title.
  Later changes do not re-run them unless a later walk completes, which resolves them.
  File search now says indexing stopped at the file limit instead of “Scanning
  continues.”

Features:

- J and K move down and up in the file tree (Files and Recent) and the Git history, as
  the arrow keys do. They repeat and open the row they land on, and Help lists them
  beside `↓` and `↑` for the file tree.
  They still type in text fields, do nothing with Shift, Ctrl, Alt, or Meta, and are not
  first-item or last-item shortcuts.
  Quick File, filter menus, and the folder treemap keep their current keys.

Inventory engine:

- Index progress requests that arrive while file-type tallies compute on a large tree
  answer sooner: about 40-70 ms on a 300,000-file tree, against 60-150 ms in 0.9.1. The
  tally pass and the activity tracker’s periodic scan of the index now pause every few
  milliseconds instead of holding the server until they finish.

- The directory tree’s first rows no longer wait for a scan of the whole repository.
  Metabrowser used to walk every visible directory looking for nested `.gitignore` files
  before indexing could start, so on a large repository the top-level tree appeared only
  after 10-30 s. Each directory’s `.gitignore` is now read the first time a path inside
  it is checked, and the first rows appear as soon as the root is listed.
  Nested `.gitignore` files now follow git’s rules: a pattern without a slash applies at
  any depth below its directory, an anchored pattern such as `/*` applies within that
  directory, a negation re-includes a path its parent file ignored, and nothing inside
  an ignored directory is re-included.

- Filesystem inventory now crosses one pluggable, provider-neutral contract.
  The current Python implementation remains the only shipped provider and preserves the
  existing routes and envelope shapes; the path identity change is documented below.
  Its module is named `python_inventory.py` to make ownership explicit before the fdu
  provider is added. Its public handle now exposes only the five provider operations;
  retained indexes, walking, watching, and projection helpers live behind that façade.
  Lifecycle state now distinguishes an open idle `ready` handle from one with a live
  filesystem observer.

- The shared provider conformance registry now covers coherent checkpoints, version
  pins, lossless paging, change resume and gap resets, verified refresh, lifecycle and
  session stability, and joined close against every registered backend.
  Rollup and navigation projections carry their named typed payloads instead of generic
  object mappings.

- Complete tree responses and initial browser snapshots now follow every bounded page at
  one engine version and sparse-overlay boundary.
  A connection is attached only after that snapshot, and changes already represented by
  it are suppressed, so a reconnect cannot apply an older ring-buffer delta after newer
  state. Page work is independently bounded from the much larger discovery file budget,
  and a bundled provider read has its own aggregate query bound.

- The inventory scope now applies its exact hidden-name allowlist to both walking and
  watching, distinguishes the regular-file budget from query row bounds, validates
  canonical relative paths, and reports an incompletely submitted watcher batch as a
  stale watcher gap instead of silently continuing.
  A required aggregate-repair failure likewise marks discovery failed instead of
  advertising incomplete rollups as done.
  Inert cache, traversal, symlink-following, and filesystem-boundary configuration
  fields are removed; fixed traversal and symlink semantics remain part of the contract.

- Root-summary polling now reuses the Python provider’s last coherent navigation read
  while discovery advances.
  Cache hits return that read’s original version and state and report zero entries
  visited; they never label older tallies as facts from the current engine version.

- Quick File catalog validators and retained bodies are checked with a constant-work
  provider checkpoint before catalog records are read.
  A cache miss scans the bounded Python inventory once, and catalog record flattening
  and JSON materialization stay off the request event loop.
  Catalog decorations are joined only for the activity tracker, the one consumer that
  reads them.

- Coordinator shutdown is joinable after cancellation, and stale concurrent refreshes
  cannot overwrite newer filesystem facts.
  Refreshes reject symlink ancestors under the same scope as the boot walk.
  Paginated reads retain a sparse overlay snapshot while allowing unrelated host updates
  and provider reads to proceed.

- Recent queries skip unused directory topology construction and compute their extension
  filter once. They return compact validated file records without building unused full
  entries or host decorations, and visit shared ignored ancestors only once.
  Inventory metadata counts the served root consistently with earlier releases, and
  JSON/YAML walk output honors the configured inventory provider.

- Generic JSONL views load their shared agent-log renderer through the SDK when opened.
  They no longer depend on another file kind having loaded first, and disposing a view
  cancels its pending mount.

- Filesystem changes invalidate affected lazy folder caches and stale in-flight reads.
  Already-mounted collapsed folders receive new rows, and reopening edited files
  revalidates cached previews, including deep files represented by ancestor updates.
  A superseded same-path response can no longer overwrite the newer selection’s cached
  payload or validator, and a path that changes from a file into a directory evicts its
  obsolete file payload instead of reviving it on the next open.
  Revalidation markers remain generation-owned until a response settles, so another
  same-path open cannot bypass an in-flight dirty cache and a newer filesystem event
  cannot be cleared by an older request.
  A fresh response without a validator also retires the previous validator.

- Inventory rollups now detect a concurrent topology change and retry from one coherent
  snapshot instead of mixing pre-change aggregates with post-change children.
  This prevents intermittent `/api/rollup` failures when filesystem discovery and
  summary reads overlap under free-threaded Python.
  The provider read boundary owns the retry, so one collision runs one optimistic
  attempt and one snapshot fallback and reports the discarded attempt in its work and
  timing metrics. CI now includes CPython 3.14’s free-threaded build so the shared-state
  discipline remains enforced.

- The filesystem observer is installed before initial discovery begins and stops
  cooperatively before its worker is joined.
  This closes the startup observation gap and prevents a `watchfiles` PyO3 borrow panic
  during free-threaded CLI teardown.
  Repeated shutdown requests continue joining the same Rust-backed consumer until it has
  finalized, including when the discovery budget and provider close race.
  HTTP readiness probes also close each response before its connection, eliminating
  unraisable response-finalizer errors on the same interpreter.

- Discovery-completion refreshes reconcile the standing keyed tree instead of replacing
  the complete Files region, preserving one whole-tree paint while partial inventory
  converges to its final rows.
  The startup walker also uses a timer-backed cooperative yield so provider reads can
  acquire the GIL promptly while discovery is active.

- Quick File catalog completion now also follows the lightweight index-progress poll.
  If bounded stream backpressure replaces a slow browser connection and drops the
  terminal capability event, the catalog performs one coalesced authoritative refetch
  instead of remaining incomplete until the reconnect backoff expires.
  Failed and idle providers remain incomplete; only a completed or capped walk can
  trigger that repair.

- Filesystem changes no longer emit an unconsumed `projection.invalidate` event for
  every changed path before emitting the authoritative `fs.change` batch.
  The duplicate per-path stream flooded bounded browser queues during discovery; the
  existing filesystem batch already invalidates file previews, directory projections,
  and SDK rollup watches from the same changed paths.

- The browser shell builds its two versioned KPress font URLs from locked distribution
  metadata without importing the document-rendering runtime.
  This keeps the font URLs identical while removing the renderer import from the cold
  HTML response and preserving the lazy boundary for CLI and API-only commands.

CLI and validation:

- Recent navigation filtering now applies age, type, filename, size, and ignored-file
  constraints through the provider before ranking and the response cap.
  The browser clusters complete matching leaves and never infers folder membership from
  descendants currently mounted in the DOM, so collapsed folders no longer disappear
  while the panel reports their files.
  The bounded live model now repairs itself after deep catalog changes, reconnects,
  expiry, and capped-page changes whose prior match is absent from the retained top N.
  While that repair is pending, its tally falls back to the retained-page lower bound;
  event bursts coalesce without retaining an unbounded operation log or starting one
  full provider scan per event.
  Deep file-to-directory and file-to-symlink replacements now preserve their prior-type
  transition through the inventory boundary, remove the exact Quick File candidate, and
  prune the bounded Recent overlay to a safe lower-bound tally before the same coalesced
  repair; routine directory aggregates remain absent from the catalog event and exact
  invalidations never scan descendants.
  The retained base now carries its committed request identity, so filesystem or expiry
  callbacks scheduled after a window or filter replacement cannot repaint the previous
  selection while the authoritative response is still loading or after it fails; a
  same-selection background repair still preserves and updates its owned rows.
  A nonempty API golden and a composed browserless navigation session pin the route,
  counts, clustering, bounded expansion, and repair decisions together.

- Quick File bulk snapshots remain cooperatively bounded when the inventory provider’s
  Unicode code-point order differs from the browser’s UTF-16 order.
  The browser stages naturally ordered runs and merges them within the existing work
  budget instead of repeatedly inserting near the front of a growing array; an
  adversarial 200,000-path browserless session pins the array work each slice may do.

- An authoritative inventory snapshot, including the one sent after a reconnect or a
  stream resync, retires only the Files rows it no longer contains and patches the rest
  in place, so expanded folders keep their loaded children.
  One production-module golden covers replacement, invalidation, and file-to-folder
  transitions without a browser.

- CLI parity now defines checked evidence for declared user-visible functional aspects
  as well as routes, kinds, and models.
  Data behavior must run through `metab`, browser-owned interaction behavior must have
  an executable production-module golden session, and only paint or platform behavior
  may be explicitly exempt.
  The first registry rows cover the release-critical Recent and Markdown compositions;
  migration of unchanged legacy UI behavior is tracked separately rather than presented
  as complete coverage.

- Image previews now use a manifest-owned, on-demand renderer and stylesheet through the
  shell’s generic preview compositor.
  Its browserless golden crosses asset resolution, registry lookup, mounting,
  replacement, cancellation, disposal, and accessible error handling in the exact
  production modules; the shell no longer carries a separate image rendering branch.

- Rendered Markdown keeps primary-document TOC links as fragments while preserving
  Metabrowser’s delegated navigation target, so KPress can bind headings and highlight
  the current section again.
  Embedded Markdown instead receives source-aware `/view/` fragment links, so Copy Link,
  modified clicks, and new tabs resolve against the embedded document.
  A scoped, frame-coalesced observer fallback preserves scrollspy in runtimes without
  `IntersectionObserver`, including long documents, and a browserless golden pins
  selection, the installed KPress expand-all control, native-runtime preservation, and
  disposal.

- Catalog-derived Markdown link results now reconcile through one root-scoped scheduler
  shared by the primary document and nested transclusions.
  Provisional exact hits and misses are reconsidered until the first complete immutable
  catalog revision, without mixing revisions or repeating work per nested mount.
  Ambiguities retain their exact candidate count with a deterministic 20-path preview;
  large basename and suffix lookups yield cooperatively, and replacement or disposal
  cancels queued work and releases the snapshot-owned index.
  A document with more links, media, and wiki references than one render enhances shows
  a diagnostic instead of leaving the rest unexplained.

- Obsidian wiki preprocessing and transclusion selection now run in one lazy Markdown
  Worker shared by every rendered document on the page, its nested transclusions, and
  folder README panels, instead of a Worker constructed and terminated per document.
  The worker client owns FIFO dispatch, per-request cancellation, fatal protocol errors,
  and disposal; the Worker ends with the last mounted document, a fatally failed Worker
  is replaced on the next request, and ordinary non-Markdown views never fetch the
  worker assets. Preprocessing uses source-wide monotone scans with deterministic work
  counters, and a transformed source that would exceed the KPress request limit is
  rejected atomically with an explicit diagnostic instead of returning a partial
  rewrite. If the worker cannot run, the document still renders from its authored source
  and reports that wiki processing was skipped.

- Inline and block code in KPress-backed documents now share one quiet solid border and
  square-by-default radius, while inline code uses compact padding.
  Explicit rules apply this to the pinned KPress 0.3.5 renderer; prose blockquotes and
  unrelated document surfaces keep their independent treatment.

- Rendered documents default to a **Max text width** of 102 characters.

- On-demand scripts validate their declared global before the loader retains or
  announces them. Partial and concurrent failures clear only the unsatisfied source
  latch, so the first retry resumes at the failed script without re-evaluating already
  successful modules.

- KPress render and export JSON bodies are streamed under fixed byte limits and parsed
  off the request event loop.
  Invalid UTF-8 and malformed JSON return structured 400 responses, oversized requests
  return 413, and export fields require their documented JSON types instead of coercing
  values or raising an internal error.

- `metab` gains two data modes that reach the server without a browser or a listening
  port. `--api <route>` issues any registered `/api/` route through the real application
  and prints the normalized envelope, in JSON or YAML, with `--data` for routes that
  take a POST body and a nonzero exit status when the route answers outside 2xx.
  `--show <path>` reports the four layers behind one selection: the route it resolves
  to, the kind it classifies as, the views it offers, and a summary of its model.
  It accepts browser addresses as well as paths, including `/view/<container>/<inner>`,
  `/commit/<rev>`, and `/commit/<rev>/<inner>`. Native and decoded browser paths are
  converted to the inventory identity before the API request, then converted back before
  route formatting, so literal-percent names and percent-looking siblings remain
  distinct. POSIX bytes that are not UTF-8 now retain their `%XX` route spelling through
  direct shell loads and `--show`, and a native command-line argument is rendered
  through the printable inventory identity rather than raising on its surrogateescaped
  byte. Slash-bearing Git refs are encoded as one revision segment and decoded without
  allowing slash, backslash, or NUL inside the selected inner path.
  See the [command-line guide](docs/command-line.md).
  The bundled `metabrowser` agent skill now points agents at both modes for reading view
  data without a browser.

- Every registered route the browser consumes and every built-in kind is reachable from
  `metab` and pinned by a golden transcript.
  `devtools/check_parity.py` fails the build when a route loses executable CLI evidence
  or a kind is absent from golden console output.
  Browser-owned file-selection, incremental-source, chart-request, and chart-lifecycle
  state machines now run the complete production modules in deterministic command-line
  sessions pinned by golden output.
  The table and the streaming exemptions are in
  [Views, Models, and Routes](docs/project/architecture/arch-views-models-routes.md).

Fixes:

- The preview pane shows a loading indicator while a file or folder loads, including the
  served folder’s first view, instead of “Select a file to preview.”
  That prompt now appears only when nothing is selected.
  Switching between the Files and Git tabs no longer abandons a selection that is still
  loading, and the shown file’s **Load more** keeps working after a tab switch.
  An empty folder opens to its Overview, which says it has no files to summarize.

- When the Metabrowser server has stopped, selecting a file or folder, in the tree or in
  Quick File, now says “Metabrowser is not reachable” and how to start it again, instead
  of “Could not open this file” with “Failed to fetch.”
  This includes a server that stops while a large file is still arriving.
  When the server is running again, the page retries that selection on its own, and
  Quick File clears the connection message.
  Missing files and other server errors keep their existing messages.

- Opening a file or folder again after it failed to load, from the tree or Quick File,
  now loads it again instead of leaving the error on screen.
  The same applies to a file a Git commit view has replaced.

- Text of two sizes on one line now sits on one baseline: a file tree row’s name, age,
  and size; a Git history row’s subject, author, and age; the file and folder header’s
  path, size, and summary; and a diff file bar’s path and its mode or binary note.
  The smaller text used to ride up to a pixel higher than the larger, by an amount that
  changed with zoom.

- Metabrowser installed into a virtual environment inside a Git repository, such as a
  project’s own `.venv/`, now reports its installed version.
  Since 0.7.0, `metab --version` and the `metab` server’s startup line, and since 0.7.1
  the version line in the browser menu, annotated such an install with the enclosing
  repository’s commit and uncommitted state, for example
  `metab 0.9.1 (+153 commits, 8d111f4a)` or `[dev build: …]`, even when that directory
  was gitignored. The annotation now appears only when Metabrowser runs from its own
  checkout’s tracked `src/metabrowser/`, as in an editable install; a copy committed
  into another project is not annotated either.
  In a checkout, reading that state no longer rewrites Git’s index under its lock, and a
  tag or path that is not UTF-8 no longer stops `metab` from starting.

Known limitations:

- Indexing a very large directory that holds hundreds of files per directory is slower
  than in 0.9.1. Metabrowser now delivers rows to the page while it walks, instead of
  finishing the walk and then drawing.
  On a repository-shaped tree that is a large win at every size measured: the first row
  appears in about a fifth of the time and the whole tree indexes in under half.
  On a flat tree of a few hundred thousand files in a few thousand directories, where
  that per-file delivery has no reader to benefit, the full index takes roughly 1.6x as
  long, the Quick File catalog request goes from well under a second to around two and a
  half, and the first row takes about a fifth longer to appear.
  Interaction latency and correctness are unchanged on both shapes.

## 0.9.1

Fixes:

- Inactive plugin tabs now mount their own renderer when first opened.
  The lazy callbacks shared one function-scoped binding, so every tab after the default
  invoked the last view’s renderer and left the selected panel blank.

- Folder file-type rollups accept the schema-4 registry identity shipped by the server
  and compare its complete schema, revision, and fingerprint with the browser runtime.
  The stale schema-3 check made every real folder overview fail before rendering.

## 0.9.0

File-type identity:

- The file tree takes its icon and colour from the rollup registry, so a family looks
  like itself everywhere it appears.
  There were two taxonomies: a hand-maintained table of sixteen matchers in `app.js`
  resolving to nine `ft-*` classes, and the registry’s 56 families each with a declared
  hue. Nothing kept them in step and they had drifted in both directions at once — `.js`
  and `.jsx` were one family in the registry and two different shapes in the tree, three
  of the four JavaScript extensions had no colour at all, while `.json`, `.toml` and
  `.yaml` were three families painted as one.
  The rows disagreed with the distribution bars beside them, from the same data.

- The registry declares an icon per group, which a family may override.
  That is the rule the old table already stated — the icon is the major type, the colour
  is the subtype — now enforced by where the data lives rather than by hand, which is
  what keeps 56 families down to six shapes plus a few deliberate exceptions.
  Icon names are checked against the shipped set, so a typo fails `make verify` instead
  of rendering a blank row.

- `FILE_TYPE_REGISTRY_SCHEMA` is `file-type-registry-v4`. Classification is not
  reimplemented for the tree: `MetabrowserFileTypeTaxonomy` already resolves compound
  extensions and family-to-group fallback, and a second implementation of that is the
  defect being removed.
  `window.MetabrowserFileTypes` keeps `classFor` and `iconFor` and gains `styleFor` and
  `familyFor`; `iconFor` now returns `style` beside `svg` and `cls`, because a family’s
  colour cannot travel in a class name when there are 56 of them.

Features:

- Rendered documents now read at a width the reader chooses, in characters, through
  **Max text width** in the Metabrowser menu (default 105). The setting is expressed in
  characters rather than pixels because that is the decision a reader has, and it is
  converted using each reading face’s measured average glyph advance — so switching
  between the serif and sans reading fonts holds the same characters per line rather
  than the same pixel width.
  The choice persists like the theme and font settings, and is applied before first
  paint so the column never renders at one width and reflows to another.

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
  age of the repository’s first commit, e.g. `142 commits begun 1mo ago`, the age value
  carrying the shared age hue and numerals exactly as commit rows do — styled like the
  file tree’s summary row and loaded the same way: off the render path, after the first
  page of history paints.

Fixes:

- The folder Overview’s README now renders at the same text width as the same file
  opened on its own, and follows the **Max text width** setting.
  The Overview sized its card from `--kpress-measure`, a token KPress declares on
  `:root` from a stylesheet loaded after the app’s, so host CSS read KPress’s default
  instead of the reader’s setting; the card geometry had also been written against
  KPress’s pre-0.3.4 column, which capped at the measure rather than the measure plus
  its inset. Both now derive from `--doc-measure`, the app’s own reading width.

- Loading states no longer announce themselves in words.
  The Git panel said “Loading history…” on first open, and pending tooltip cells, the
  recent-files list, and the byte preview each had a sentence of their own.
  Where the layout is known before the data, these now draw it as neutral blocks
  carrying the navigation tally’s slow pulse; the spinner is reserved for waits whose
  shape is genuinely unknown, and screen readers still get a name.
  Skeletons hold steady instead of pulsing under `prefers-reduced-motion`.

- Scrolling deep into Git history no longer nudges the view by a row.
  The virtualized window measures from the first history row, but the panel was handing
  it the shared scroller’s offset, which also includes the header tally above the graph.
  Row mounting absorbed the difference, so the visible symptom was confined to the
  jumps: a scroll position rewritten at a segment boundary, and restoring a commit from
  its URL or arrow-keying past the mounted range, each landing one row off target.

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

- One Ctrl-C stops the server, at any point in its life, and reports exit 130. It prints
  `Stopping Metabrowser.` so the press is visibly registered rather than reading as a
  hang, and it does not wait on in-flight requests: this is a local, single-user
  browser, and a reader who asks it to stop should not queue behind an open stream.
  A repeat press while the process exits used to land on Python’s default handler and
  print an `Exception ignored on threading shutdown` traceback, or kill the process
  outright for exit `-2`; it now stops the same way as the first.

  The press is no longer swallowed during startup.
  Serving brings up a filesystem watcher and worker threads, and the handler covering
  the interrupt was installed only around the server’s own run loop — so a Ctrl-C
  arriving before that, which on a large tree is the seconds spent walking the
  directory, either hit Python’s default path and blocked in interpreter shutdown
  joining those threads, or was discarded outright.
  Measured on a 150k-file tree, a press four tenths of a second after launch left the
  process alive and still serving.
  The handler now goes up at the top of serve mode, before the first thread starts.

  This extends the 0.8.0 interrupt work from startup and filesystem scans to the running
  server, and supersedes its note that a second Ctrl-C stays a forced exit.

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
