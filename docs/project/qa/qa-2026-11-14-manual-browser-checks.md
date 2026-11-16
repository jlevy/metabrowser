# Manual Browser Checks

**Status:** Current checklist as of 2026-11-14; run it before each release.

These are the checks only a person in a real browser can judge.
Each behavior with a deterministic contract also has an automated test, as
[End-to-End Testing](../../e2e-testing.md) describes; a check here never stands in for
one.

## The Manual Corpus

Serve the public-safe manual corpus:

```shell
uv --config-file uv.toml run --frozen metab ./tests/manual-fixtures --no-open
```

It holds Markdown with frontmatter, structured JSON, JSONL events, source code, an SVG
image, and an opaque file large enough to exercise the binary view.
Keep these fixtures generic and free of copied production data.

Open the printed URL and check:

- first paint appears before a large tree finishes indexing;
- Markdown, structured data, source, JSONL, image, and binary views render;
- the binary Bytes view loads a second chunk on **Load more**, appends without
  re-rendering the bytes already shown, and wraps without horizontal overflow at narrow
  and wide panes in both themes;
- a binary file above the preview ceiling renders a bounded prefix and says where the
  preview is cut off;
- changing and deleting files updates the tree and Recent;
- a direct `/view/<path>` address opens its file independently of the tree crawl, and a
  fragment identifies a location in it, such as a heading or a source line;
- when the served root is in a Git repository, opening a commit that changes the root
  renders its changed-file diff in a fresh browser session;
- light and dark themes, narrow panes, keyboard focus, and print output stay usable;
- the console and Network panel show no unexpected errors or missing assets.

## Markdown Reading Layout

Open a long Markdown file with a table of contents in the built-in browser.

- The document card border starts at the leftmost tab’s outer edge.
  In Source, check the pane gutter and the line-number column.
- At a preview width of 75 rem or more, the table of contents sits to the right of the
  prose, and a heading link follows.
  A thumbnail and a wide table sit where they should beside the rail.
- Narrow the preview through tablet and phone widths.
  Scroll past the first section, open the table of contents with its icon, and follow a
  heading; reopen the overlay and dismiss it with Escape.
- Open a short file, then reopen it after a warm read: the start edge is the same.
- In Folder Overview, the README’s prose edge matches the same file opened directly, and
  the section rules and panel borders line up along the stack.
- In a wide pane, compare paragraph widths in Markdown and a PR conversation at the
  default **Max text width** and at 80, then restore the setting.
- KPress keeps its normal left and right padding inside the card; prose does not have to
  align with the tab label.
  Both views keep the shared outer pane padding, and the card’s inner padding does not
  conceal an absent outer gutter.

## Shared Content Layout and Stack Navigation

Compare a Markdown document, its Source and Raw views, a folder README, a commit with a
description, and a PR with comments, at wide and narrow pane widths.

- Card borders and source surfaces begin at the first display tab’s outer edge.
- The document card keeps KPress’s inset, with the contents rail on the right on a wide
  pane and the contents icon and drawer on a narrow one.
- A wide table stays reachable by horizontal scrolling without widening the pane.
- Commit descriptions and PR prose share one sans size, ink, and neutral bordered
  surface. Author, action, and age share a baseline, and branch chips stay smaller.

On a PR in a known stack, open the position menu:

- check titles, ordinal and PR number, the current-member mark, focus, Escape, an
  outside click, and keyboard selection;
- on a Mac, Control-P moves toward the base and Control-N toward the top, with and
  without Shift, and a held chord walks once, keeping the selected PR tab and clearing
  the old file selection;
- `N` alone does nothing there, `P` alone focuses the Pulls list rather than walking the
  stack, and Help and the Shift strip write the chords `⌃N` and `⌃P`;
- with a Pulls row focused, Shift+`J` and Shift+`K` move the row and not the stack;
- the stack’s endpoints consume the key without moving, an editor or an open dialog
  keeps its keys, and Control-N and Control-P in Quick Search’s field move its caret on
  macOS;
- on Windows and Linux, Help and the Shift strip list neither chord, Ctrl+N opens a new
  window and Ctrl+P the browser’s Print, and the position menu walks the stack.

## Quick Search and Main Tabs

Open the same public GitHub repository in a checkout and in a managed mirror.

- From Files or a selected commit, press `T` and type `#`: the list shows recent PRs
  across states. Add title text, then replace it with a number prefix: both show only PR
  options, an exact number first, with title, number, state, and an accessible option
  name.
- Enter opens Conversation in one history step, and Back returns to the previous view.
- With an isolated cache, search before opening Pulls: a catalog refresh starts once,
  and later queries read the local catalog.
  Reopen a cached result with `gh` unavailable.
- In a plain folder, the dialog still says Quick Search and searches only files.

After Git discovery:

- Help lists Files, Pulls, and Commits in that order with their letters, and no `⌘`
  beside them;
- `F`, `P`, and `H` open each tab with and without Shift, `R` opens nothing, and Command
  or Ctrl with a letter or digit is left to the browser, but for Control-N and Control-P
  on a stack’s pull request on a Mac, so Command or Ctrl with a digit still switches
  browser tabs;
- in a plain folder, `F` still opens Files and `P` and `H` leave the selection alone.

[Keyboard Shortcuts](../../keyboard-shortcuts.md) has the full scheme.

## Pulls Watch and Reconnect

The [watch verification plan](../specs/done/plan-2026-11-06-pr-watch-and-reconnect.md)
covers incremental provider updates, cached use during an outage, connection recovery,
and Reload in both repository modes.

## Pulls Paging

Use a repository, or a seeded catalog, with more matching PRs than the list first reads
(`DISPLAY_ROWS` in `builtin_plugins/github/pulls-panel.js`).

- Start in Pulls and check the initial window.
- Scroll near its end: the next window appears without a click.
  Repeat through the final partial window.
- Watch the selected row, and switch filters while a page is in flight.
- For a partial catalog, the same interaction joins the metadata refresh and continues
  when rows arrive.

## Pull Request Checks

In a checkout and in a managed repository, open a PR with checks.

- Select **Checks** and check the status summary and detail links.
- Go to Conversation and Changes, then Back and Forward restore the selected tab.
- Reload `/pull/<n>/checks` directly.
- Repeat with an empty check list and with a pending PR record, for each loading and
  empty state. On a cached PR, all three tabs use the same record.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
