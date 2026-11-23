# Plan for the Diff | Current Chooser

**Date:** 2026-11-23

**Author:** Joshua Levy (github.com/jlevy) with LLM assistance

**Status:** Planned 2026-11-23; implemented as one stack on #759, beads `mb-wexb`,
`mb-wd9o`, `mb-256j`, `mb-ubs0`, `mb-yt73` and `mb-o8gd` under the feature `mb-iw3x`.
This plan is `mb-93t2`.

## Overview

The owner asked, on 2026-11-23, for a second chooser beside every **Rendered** |
**Source** chooser: **Diff** | **Current**. **Diff** is the view a diff draws today.
**Current** shows the new version alone:

- **Rendered**, changed and added items marked green, with no deleted items and no
  redlines.
- **Source**, the unified diff without its deleted lines, each remaining line in the
  color it has in the new file.

The chooser is right-aligned at the file bar’s end, as **Split** | **Unified** and
**Rendered** | **Source** are, and **Rendered** | **Source** stays at the far right, so
the end group reads `[Diff | Current] [Rendered | Source]`.

## What Exists Today

Every diff is one mount of `mountDiffView` (`builtin_plugins/diff/diff-view.js`), drawn
by the diff plugin’s `render` (`builtin_plugins/diff/index.js`) for four hosts:

| Host | Who mounts it | Rendered \| Source | Split \| Unified |
| --- | --- | --- | --- |
| A pull request’s Changes | `pull-page.js` | Markdown, YAML, and JSON files, through the comparison’s `rendered_route` | In the toolbar, `L`, stored as `diff.layout` |
| A pull request’s Docs | `pull-page.js`, `group: type:docs`, `unfold`, `layout: "unified"` | Every document | None: the host fixes Unified |
| A commit’s page | `git-panel.js` | None: no rendered route | In the toolbar |
| A patch or diff document | the `diff` kind’s view | None | In the toolbar |

Guided Review’s excerpts (`mountFilePatch`) are on #677, not on `main`: they draw a
file’s hunks with no file bar, in Unified.

Rendered | Source is per file and unremembered: each file opens in Rendered, and a file
whose Rendered cannot be shown shows Source with its Rendered chip `aria-disabled`,
saying why (`createMarkdownViews` in `diff-markdown.js`). Split | Unified is one choice
for the whole diff, stored through `api.prefs` as `diff.layout` and read at every mount
(`readLayoutPreference`).

In Rendered, a changed Markdown block is a removed block, its deleted words in `<del>`,
followed by an added block, its inserted words in `<ins>`
(`diff/markdown_projection.py`); a changed YAML or JSON value is a removed entry and an
added entry of the merged tree (`diff/structured_projection.py`). So every redline is in
a removed item, and leaving out the removed items leaves the new version with its
changes marked.

## Design

### Where It Shows

| Surface | Diff \| Current | Why |
| --- | --- | --- |
| Changes, every file with a text diff | Yes | The owner’s first surface, and Current is one choice for the diff (below), so it means the same on a code file as on a document |
| Docs, every document | Yes | Reading documents as they now are is what Current is for |
| A commit’s page, every file with a text diff | Yes, Source Current | Current is a projection of the hunks every diff has, so it needs no rendered route |
| A patch or diff document | Yes, Source Current | The same projection of the same hunks |
| Guided Review excerpts | No | An excerpt shows the lines a step of the guide cites, deletions among them, and has no file bar to hold a chooser; its module is on #677 and is not changed here |
| Rendered Markdown | Yes | Removed blocks and removed front matter keys are left out; added blocks keep their fill and their `<ins>` marks |
| Rendered YAML and JSON | Yes | The merged tree without its removed entries; added entries keep their fill |
| A file with no text diff: binary, too large, failed, unsupported, or a change with no content (a rename or a mode change) | No | Both choices would show the same sentence, so there is nothing to choose; its Rendered \| Source, where it has one, stays as it is |

A file whose Rendered is unavailable shows Source, as today, and in Current shows Source
Current; its Rendered chip stays unavailable for its reason.

### Placement

The chooser is the first item of the bar’s end group (`.diff-file-end`), so **Rendered**
| **Source** keeps the far end:

```
[name group ...]                     [spinner] [Diff | Current] [Rendered | Source]
```

The Rendered spinner stays at the start of the end group, before both choosers, so the
two sit at the end group’s gap, and the spinner, which keeps its place while hidden,
still moves neither.
A bar with a chooser wraps as a bar with Rendered | Source does today: the name’s group
keeps the first line, the end group takes the next at the bar’s end, and where the end
group alone is wider than the bar its choosers wrap, each line at the bar’s end.

### One Choice for the Diff

Diff | Current is one choice for the whole diff, as the layout is, not one per file as
Rendered | Source is.
Every bar that has the chooser shows the same value, and choosing in any bar, or with
the key, redraws every file.

- **It is the layout’s kind of choice.** It says how a change is drawn, the same for
  every file, where Rendered | Source says what one file can offer, which is per file
  because each file’s Rendered may be unavailable.
- **A key needs one target.** The design system gives no key to a per-file affordance,
  of which a page has many (“No key on an ancillary item”); a choice for the whole diff
  is one control drawn in many places, and its key has one meaning.
- **Reading the new version is a task for the whole change.** A reader reading a pull
  request’s documents as they now are would otherwise choose Current on each of them.

The file whose chooser was clicked keeps its place on the screen while the files around
it redraw, and the key keeps the place of the file at the pane’s top, by the view’s
`holdPlace`, once per batch where the redraw runs in batches.

### Composition with Split | Unified

Current is one column whatever the layout: each line once, at its new line number.
While Current is chosen the layout control keeps its place and shows the stored layout,
and both its chips are `aria-disabled` with a tip and an accessible name saying that
Current shows one column and Diff shows the layout; choosing either, or pressing `L`,
changes nothing. The stored layout is not touched, and the view keeps following the
width, so Diff returns in the layout the width allows.
A host that fixes the layout, as Docs fixes Unified, has no layout control, and Current
is the same one column there.

### What Is Remembered

The choice is stored as the layout is: `diff.show`, `"diff"` or `"current"`, through
`api.prefs`, read at every mount and written at every choice, so it holds across files,
diffs, pages, and served folders.
A missing or unusable stored value is Diff, so a reader who never chose sees today’s
view. Rendered | Source stays per file and unremembered.

The stored choice could hide deletions on a diff the reader opens later.
Every bar then shows **Current** selected, and the bar’s stats still count the deleted
lines, so the choice is in view wherever it applies.

### The Key

`N`, from curre*n*t and *n*ew: one press switches the diff between Diff and Current,
through the same path as a click.

- `C`, `U`, `R`, `E`, and `T` are the other letters of the word: `C` is Conversation on
  a pull request page, `U`, `T`, and `E` are taken, and `R` stays free for a rendered
  view (`test_p_is_the_pulls_tab_in_every_kind_and_r_is_free`).
- `N` is in no reserved table, no manifest, and no built-in plugin’s attachment;
  `test_next_and_previous_are_chords_that_reserve_no_letter` holds that Control-N leaves
  it free.
- It is attached once per diff, through the SDK’s shortcut surface, on the chip it would
  select in the bar of the file at the pane’s top, which is sticky and so always in
  view, and it moves when that file changes or the chooser is drawn again.

`tests/test_keymap.py` reads the letter beside `diff.show` in `diff-view.js`, as it
reads `diff.layout`’s, and `docs/keyboard-shortcuts.md` gets its row.

### Accessible Names

- The group is a joined chip group (`filterControls.groupHtml`) named “Diff or current
  version”, one tab stop with arrow keys, as every exclusive choice is.
- Its chips are **Diff** and **Current**, each with a tip: “Show what changed, removals
  included” and “Show the new version alone, its changes marked”.
- While Current is chosen, the layout chips read “Split, unavailable.
  Current shows the new version in one column; choose Diff for Split or Unified.”, and
  Unified the same.
- A removed block’s screen-reader label goes with the block; an added block keeps its
  “Added:” label.

### Source Current

The unified rows without the deleted lines, from the same render model, so syntax and
intraline marks need no new work:

- An added line keeps its fill, its gutter, and its intraline marks; context stays
  plain; the `+` marker stays, so the change is not said by color alone.
- One line-number column, the new side’s.
- Each hunk keeps its header bar, the gap between excerpts of the new file, naming the
  new side’s range alone: `@@ +12,7 @@ heading`.
- A long changed run folds by the same rule as in Diff, counting the rows Current draws,
  and a fold has one state in both: opened in one, it is open in the other, as it is
  across layouts. Docs, which unfolds, unfolds Current too.

### Rendered Current

- **Markdown**: the projection’s blocks, removed ones hidden, by the `hidden` attribute
  the format controller sets, so which blocks show is decided in JavaScript and not by a
  selector. Added blocks keep their fill and `<ins>` marks; no `<del>` is drawn, since
  every one is in a removed block.
  Front matter shows its new keys: a removed key and a wholly removed front matter are
  hidden, an added one keeps its fill.
  Folds of unchanged blocks are Diff’s, so a run that a removal parted stays two runs.
- **YAML and JSON**: the merged tree’s rows without its removed entries, drawn again
  from the tree (`diffRows`), so a “more” row counts only what Current draws.
  Paths stay the merged tree’s, so what the reader opened in Diff stays open in Current.

### Added, Deleted, and Empty Files

- **An added file** draws in Current what it draws in Diff: every line or block is
  added.
- **A deleted file** has no current version, so Current shows one sentence in its body,
  “This file was deleted, so it has no current version.”, and a deleted Markdown, YAML,
  or JSON file shows that body in Current whichever of Rendered or Source is chosen.
- **A file left empty** shows “This file is empty now.”

### Route and CLI Equivalent

Current adds no data: it selects, from what the comparison route
(`/api/plugin/diff/comparison`) and the rendered route
(`/api/plugin/github/pull-rendered-diff`) already answer, the rows of the new side, as
Unified and Split are projections of the same hunks.
So it adds no route; one that answered the same selection would repeat in Python the
rule the browser draws by, which
[CLI and Functional UI Parity](../../../development.md#cli-and-functional-ui-parity)
rules out. It is an interaction row of the
[parity registry](../../architecture/arch-parity-registry.md), `diff.show-current`,
whose session `tests/dom/diff-current-session.js` mounts conformance documents and
recorded rendered answers through the production `diff-view.js`, `diff-markdown.js`, and
`diff-structured.js`, and whose golden `tests/golden/cli-ui-diff-current.tryscript.md`
prints, for each step, what each file draws, the chooser, the layout control, `N`, and
what was stored. The stored choice is browser state, `local-only` as `diff.layout` is.
That the end group’s two choosers share a line at the bar’s end is layout, a
paint-exempt row with a headless Chrome check.

## Implementation

One stack on #759, one commit per bead:

- [x] `mb-93t2`: this plan.
- [x] `mb-wexb`: the diff-wide choice, its chooser in the bars of rendered-format files,
  and Rendered Current for Markdown.
- [x] `mb-wd9o`: Source Current for those files.
- [x] `mb-256j`: Rendered Current for YAML and JSON.
- [x] `mb-ubs0`: the chooser on every bar with a text diff, and the layout control while
  Current is chosen.
- [ ] `mb-yt73`: `diff.show`, `N`, the browserless session and its golden, and the
  parity row.
- [ ] `mb-o8gd`: the design system’s file bar and chooser vocabulary, the pull request
  review guide, the keyboard reference, and the Chrome check of the end group.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
