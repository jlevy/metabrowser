# Plan for the Diff | Current Chooser

**Date:** 2026-11-23

**Author:** Joshua Levy (github.com/jlevy) with LLM assistance

**Status:** Planned 2026-11-23; implemented as one stack on #759, beads `mb-wexb`,
`mb-wd9o`, `mb-256j`, `mb-ubs0`, `mb-yt73` and `mb-o8gd` under the feature `mb-iw3x`.
Revised the same day after the owner tried it (`mb-s5ui`): the chooser moved from the
file bars to the diff’s toolbar, and each surface got its own default and preference.
This plan is `mb-93t2`. The
[diff presentation plan](plan-2026-11-25-diff-presentation.md) supersedes its controls,
labels, and defaults.

## Overview

The owner asked, on 2026-11-23, for a second chooser beside every **Rendered** |
**Source** chooser: **Diff** | **Current**. **Diff** is the view a diff draws today.
**Current** shows the new version alone:

- **Rendered**, changed and added items marked green, with no deleted items and no
  redlines.
- **Source**, the unified diff without its deleted lines, each remaining line in the
  color it has in the new file.

The first version put the chooser at each file bar’s end, before **Rendered** |
**Source**. After trying it, the owner asked on the same day to “move the Diff | Current
to be on the diff as a whole, next to Split | Unified on the Changes tab and in a
similar place on the Docs tab”, with Changes opening on **Diff** and Docs on **Current**
(`mb-s5ui`). So the chooser is in the diff’s toolbar, right-aligned beside **Split** |
**Unified**, and a file bar’s end group is `[spinner] [Rendered | Source]` again.

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

| Surface | Diff \| Current | Opens on | Why |
| --- | --- | --- | --- |
| Changes | In the toolbar, beside Split \| Unified | Diff | The owner’s first surface, and Current is one choice for the diff (below), so it means the same on a code file as on a document |
| Docs | In the toolbar, alone, where Changes has both | Current | Reading documents as they now are is what Current is for |
| A commit’s page | In the toolbar, beside Split \| Unified; Source Current | Diff | Current is a projection of the hunks every diff has, so it needs no rendered route |
| A patch or diff document | In the toolbar, beside Split \| Unified; Source Current | Diff | The same projection of the same hunks |
| Guided Review excerpts | No | — | An excerpt shows the lines a step of the guide cites, deletions among them, and has no toolbar to hold a chooser; its module is on #677 and is not changed here |
| Rendered Markdown | Yes | — | Removed blocks and removed front matter keys are left out; added blocks keep their fill and their `<ins>` marks |
| Rendered YAML and JSON | Yes | — | The merged tree without its removed entries; added entries keep their fill |
| A file with no text diff: binary, too large, failed, unsupported, or a change with no content (a rename or a mode change) | Shows the same either way | — | Both choices show the same sentence; its Rendered \| Source, where it has one, stays as it is |

A file whose Rendered is unavailable shows Source, as today, and in Current shows Source
Current; its Rendered chip stays unavailable for its reason.

A stack’s page, planned in
[Whole-Stack Review](plan-2026-11-24-stack-review.md#the-page), mounts the same view for
its Docs and Changes, each with the default and the preference a pull request’s has.

### Placement

The chooser is in the diff’s toolbar (`.diff-toolbar`), right-aligned, before the layout
control, so **Split** | **Unified** keeps the far end where readers know it, and the two
whole-diff choosers share one line:

```
[File type ...]                                  [Diff | Current] [Split | Unified]
```

Docs has no layout control, so its toolbar holds **Diff** | **Current** alone, at the
same end. #759 left Docs with no toolbar when it held nothing; it has one again for this
chooser. The place is the toolbar’s right end, not a position across the two tabs: on
Docs the chooser sits where **Split** | **Unified** does on Changes (review A of #765,
A10). A file bar’s end group is `[spinner] [Rendered | Source]`, as before the chooser:
what is chosen for one file is on its bar, and what is chosen for the whole diff is in
its toolbar.

The two choosers are one group, and the toolbar wraps: where they do not fit beside the
File type control, as at 380 px once a type is chosen, they take the next line together,
still at the right, and nothing scrolls sideways (review A of #765, A2).

| Where | Before `mb-s5ui` | After |
| --- | --- | --- |
| Changes | Each bar with a text diff: `[Diff \| Current] [Rendered \| Source]` | Toolbar: `[File type] [Diff \| Current] [Split \| Unified]`; bars: `[Rendered \| Source]` |
| Docs | Each document’s bar; no toolbar | Toolbar: `[Diff \| Current]`; bars: `[Rendered \| Source]` |
| A commit’s page and a patch | Each bar with a text diff | Toolbar: `[Diff \| Current] [Split \| Unified]`, after a patch’s Diff summary |

### One Choice for the Diff

Diff | Current is one choice for the whole diff, as the layout is, not one per file as
Rendered | Source is, which is why it belongs in the toolbar beside the layout.
Choosing, by the chooser or the key, redraws every file.

- **It is the layout’s kind of choice.** It says how a change is drawn, the same for
  every file, where Rendered | Source says what one file can offer, which is per file
  because each file’s Rendered may be unavailable.
- **A key needs one target.** The design system gives no key to a per-file affordance,
  of which a page has many (“No key on an ancillary item”); a choice for the whole diff
  is one control, and its key has one meaning.
- **Reading the new version is a task for the whole change.** A reader reading a pull
  request’s documents as they now are would otherwise choose Current on each of them.

The reader’s place stays on the screen while the files redraw, whether the reader
clicked the chooser or pressed the key: the line or rendered block at the pane’s top
keeps its offset, or, where the choice leaves that row out, the next row it draws
(review A of #765, A3, where the file’s own top had moved the row being read by the
height of every removed row above it).
The view’s `holdPlace` puts that row back once per batch where the redraw runs in
batches, and again as a long file’s folded runs materialize, until the reader moves; a
file with no such row keeps its own top, and a file a jump pinned keeps the pane’s top
instead.

### Composition with Split | Unified

Current is one column whatever the layout: each line once, at its new line number.
While Current is chosen the layout control keeps its place and shows the stored layout,
and both its chips are `aria-disabled` with a tip and an accessible name saying that
Current shows one column and Diff shows the layout; choosing either, or pressing `L`,
changes nothing. The stored layout is not touched, and the view keeps following the
width, so Diff returns in the layout the width allows.
A host that fixes the layout, as Docs fixes Unified, has no layout control, and Current
is the same one column there.

### Defaults by Surface and What Is Remembered

Each surface opens on its own default and remembers its own choice, so choosing Current
on Changes does not change what Docs opens on, and choosing Diff on Docs does not change
Changes:

| Surface | Opens on | Preference |
| --- | --- | --- |
| A pull request’s Changes, a commit’s page, a patch or diff document | Diff | `diff.show` |
| A pull request’s Docs | Current | `github.docs.show` |

The mounting context says which, as #759 had Docs pass `layout: "unified"`: the diff
plugin’s `render` passes the context’s `show` (`"diff"` or `"current"`) and
`showPreference` to `mountDiffView`, which opens on `show` unless the reader stored a
choice under `showPreference`, and stores each choice there.
Without them it opens on Diff and uses `diff.show`. Docs passes `show: "current"` and
`showPreference: "github.docs.show"` (`DOCS_SHOW_PREFERENCE` in `github/pull-page.js`),
so the diff plugin knows nothing of GitHub; the key is named for its owner, the GitHub
plugin, as `diff.show` and `diff.layout` are for the diff plugin.
Changes, a commit’s page, and a patch share `diff.show`, as they share `diff.layout`.

A stored value is `"diff"` or `"current"`, through `api.prefs`, read at every mount and
written at every choice, so it holds across diffs, pages, and served folders.
A missing value, or a stored value other than `"diff"` or `"current"`, reads as the
surface’s default, Diff on Changes and Current on Docs, and is not rewritten until the
reader chooses. Rendered | Source stays per file and unremembered.

The stored choice could hide deletions on a diff the reader opens later.
The toolbar then shows **Current** selected, and each bar’s stats still count the
deleted lines, so the choice is in view wherever it applies.

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
  select in the toolbar’s chooser, as `L` is on the layout control’s, and moves to the
  new chip when the chooser is drawn again.
  It works wherever the pane is scrolled; the first version moved it to the bar of the
  file at the pane’s top, which `mb-s5ui` removed with the per-bar choosers.

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
whose session `tests/dom/diff-current-session.js` mounts a comparison of six files and
recorded rendered answers through the production `diff-view.js`, `diff-markdown.js`, and
`diff-structured.js`, as Changes mounts it and as Docs does, and whose golden
`tests/golden/cli-ui-diff-current.tryscript.md` prints, for each step, what each file
draws, what the toolbar holds, what each bar’s end group holds, `N`, and what was stored
under which preference.
Its data input is the rendered route its recorded answers come from; the stored choice
is browser state, as `diff.layout` is.
That the toolbar’s two choosers share a line at its right end is layout, a paint-exempt
row with a headless Chrome check.

## Implementation

One stack on #759, one commit per bead:

- [x] `mb-93t2`: this plan.
- [x] `mb-wexb`: the diff-wide choice, its chooser in the bars of rendered-format files,
  and Rendered Current for Markdown.
- [x] `mb-wd9o`: Source Current for those files.
- [x] `mb-256j`: Rendered Current for YAML and JSON.
- [x] `mb-ubs0`: the chooser on every bar with a text diff, and the layout control while
  Current is chosen.
- [x] `mb-yt73`: `diff.show`, `N` and its row in the keyboard reference, the browserless
  session and its golden, and the parity row.
- [x] `mb-o8gd`: the design system’s file bar and chooser vocabulary, the pull request
  review guide, and the Chrome check of the end group.
- [x] `mb-s5ui`: after the owner tried it, the chooser in the diff’s toolbar beside
  Split | Unified, alone on Docs, which has a toolbar again; Changes, a commit’s page
  and a patch opening on Diff under `diff.show`, and Docs on Current under
  `github.docs.show`; `N` on the toolbar’s chooser; the file bar’s end group back to
  Rendered | Source alone; and the session, golden, Chrome check, design system, review
  guide, parity rows, and changelog to match.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
