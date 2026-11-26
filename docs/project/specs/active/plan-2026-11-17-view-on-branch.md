# Plan for View on Branch

**Date:** 2026-11-17

**Author:** Joshua Levy (github.com/jlevy) with LLM assistance

**Status:** Approved 2026-11-17; implemented on
[#511](https://github.com/jlevy/metabrowser/pull/511), in review.
Bead `mb-ej0w` tracks it.
The design below merges a survey of `origin/main` at `e442ed10d` with an independent
adversarial review of the same code; the open questions at the end are the owner’s.

## Overview

The owner asked, on 2026-11-16:

> “On the diff views, there’s a ‘View at base’ and ‘View file’ links.
> These go to some special page that doesn’t show any other further context.
> Such pages should not exist.
> We should have no standalone pages like this that don’t give context in the standard
> way. These should actually be viewing the file in the normal way, as if we had
> navigated to it at that branch under the main UI. … maybe we should call this ‘View on
> branch’ for clarity and just have one link.”

The special page is the GitHub plugin’s revision page, `GET github/pull-snapshot`
(`builtin_plugins/github/pull_snapshot.py`), a standalone HTML page with no tree, tabs,
ref selector, or navigation.
It landed on 2026-11-10 (`fe7e4c5f6`) and is in no release: `v0.12.0` does not contain
it, and its changelog entry is under Unreleased.
No compatibility is owed to it.

## What Exists Today

| Page | New side | Old side |
| --- | --- | --- |
| Pull request Changes, mirror, pin is the head | “View file”, a `/view/` link | “View at base”, the revision page |
| Pull request Changes, mirror, pin elsewhere | the revision page | the revision page |
| Pull request Changes beside a checkout | the revision page | the revision page |
| A commit’s diff on a mirror | a link if the commit is the pin, else a button that switches the pin by commit ID | “View at parent”, by the same rule |
| A commit’s diff on a folder, a patch file, the Diff summary | none | none |

Rendered Markdown in Changes also sends its relative links (`mode=document`) and its
images (`mode=image`) to the revision route (`pull_rendered_diff.py`,
`diff-markdown.js`).

The pull request page’s **Browse code** already does, for the whole tree, what the owner
asks for a file: it serves the pull request’s head and opens `/view/` (`serveHead` in
`pull-page.js`).

## Design

**View on branch is Browse code for one file.** One control per file bar, for the
change’s new side, offered only where the app can put the reader on the pull request’s
head in the main UI: the Files tab, its tree, and the ref selector naming the pull
request.

| Context | Control |
| --- | --- |
| Mirror, the page’s pin is the diff’s head | a link to `/view/<path>` |
| Mirror, the pin is elsewhere | a button: switch the pin to the head, then open the server’s `view_href` |
| Mirror, Changes shows an earlier head than the pull request’s (`headMoved`) | none: the file on the branch would not be the file in the diff |
| Checkout whose `HEAD` is the diff’s head | a link to the working-tree file |
| Checkout otherwise; a deleted file; a symbolic link or submodule; a patch file | none (Q1) |

- **Head side only.** The diff’s old side is the merge base, not the base branch’s tip,
  so it has no branch; after a merge the base branch holds the change, and a deleted
  file is absent there.
  Its honest view is a bare commit, the contextless place the owner objects to.
- **Switch by commit, carrying the pull request’s ref.** A short branch name resolves to
  `refs/remotes/origin/<name>`, so a fork’s `main` would open the base repository’s; the
  mirror’s durable name for a pull request’s head is `refs/pull/<n>/head`. Switching by
  commit keeps the label and the file at one commit, and naming the pull request’s ref
  keeps “Pull request #N” the subject when two pull requests share a head.
  When that ref is no longer at the commit, because the pull request moved on after the
  page was drawn, the pin route refuses with `409 ref_moved` and switches nothing, so
  View on branch and Browse code on that page say the head moved rather than open the
  earlier head as a bare commit.
- **One switcher.** The diff’s `switchTo` (`diff-view-file.js`) and the page’s
  `serveHead` become one, with the diff’s refusal messages; `serveHead` sends no `view`
  and shows a raw `selection_pending` code today.
- **Never a GET that switches.** The pin route stays a same-origin JSON POST, so served
  content cannot trigger it; a switching control is a `<button>`, as the text-action
  rule requires.
- **Copy.** The label is a constant, “View on branch”: the branch name is
  author-controlled, long, and on every bar.
  The tooltip says the commit and whether the pin switches:
  - link: “Open README.md at 6ac4c8b5eb94, the commit this page shows”;
  - button: “Switch to 6ac4c8b5eb94, this pull request’s head, and open README.md”;
  - checkout: “Open your working-tree copy of README.md, in this checkout whose HEAD is
    this pull request’s head”.
    A control with no target is absent, never disabled: a text action has no disabled
    form. Busy and refusal stay as they are.
- **Rendered Markdown links.** The rendered diff stays pin-independent (its cache key
  has no pin), so the client maps a validated relative target to `/view/` only when the
  page’s pin is the head, and leaves it plain text otherwise; a link that switched the
  pin would break the text-action rule.

### The Pin Is Server-Wide

This reverses a documented guarantee, that Changes never switches the pin
(`arch-github-pull-requests.md`, `arch-source-sessions-and-pins.md`), as Browse code
already does for the whole tree.
A switch makes every other tab’s data request answer `409 pin_changed` until it reloads,
and Back to Changes reloads once (measured 204 to 541 ms by the pin guard).
Two consequences to handle in this change:

- A tab rendered while the head was served keeps plain `/view/` links after another tab
  switches, and they would open the same path at the other pin.
  On `metabrowser:pin-changed`, the diff turns its links into switching buttons.
- POST then navigate is not atomic; the root cause is that a `/view/` address names no
  revision. Out of scope here; noted for the source-sessions design.

## What Is Deleted

- The revision page’s document, source, and download modes, their constants and helpers,
  `pull-snapshot.css`, `disclosure-chevron.svg` if nothing else uses it, the page’s
  preference scripts, and the diff plugin’s `snapshotHost` and `snapshotHref`.
- “View at base” and “View at parent” on pull requests (a commit’s diff keeps one “View
  file”, Q2).
- Its parity rows, goldens, and docs, changed in the same commit: the two active plans
  that specify the page (`plan-2026-08-17-general-diff-rendering.md`,
  `plan-2026-11-02-pr-review-mirror-and-checkout.md`), the two architecture documents
  above, the routes map, `docs/design-system.md` (“Diff File Bar”, and the rule that a
  pull request’s controls are always links to the revision page),
  `docs/reviewing-pull-requests.md`, `arch-parity-registry.md`, and the Unreleased
  changelog entry.

**Kept:** the route’s admission and its `mode=image` branch, which rendered Markdown’s
images use, and the envelope field that names it, renamed for what it now is (the pull
request’s image route).
`pull_snapshot_cache.py` stays while a tab on an earlier pair can still ask for an
image.

## Risk: Large Files in the Normal Viewer

The revision page bounded render work and drew plain code fences, answering measured
renders of 12 s, 17 s, and 79 s (`pull_snapshot.py`, `kpress_adapter.py`). The pinned
`/view/` viewer has neither.
Browse code already reaches it, but View on branch puts every changed file one click
away. This change keeps only the plain fences: under the untrusted profile, which a pin
always runs under, the pinned render route asks KPress for plain code, which looked the
same there because the inert render drops the highlighter’s classes.
The render-work bound is not moved (Q3, as revised): its estimate admitted multi-second
renders at its own cap and judged another text than the render route, so a bound that
works is a deadline on the render in the projection worker, bead `mb-273l`, in a
separate change.

## Tests

- `tests/dom/diff-view-file-session.js` and its golden gain the steps the design adds: a
  mirror pinned elsewhere, a checkout at the head, a checkout elsewhere, a head that
  moved, a pull request whose ref moved after the page was drawn, and a pin another tab
  changed.
- `tests/test_github_pull_snapshot.py` shrinks to admission and images; the goldens that
  carry the route’s old name change with the rename.
- `tests/test_github_pulls.py` and `tests/golden/cli-api-diff-view-file.tryscript.md`
  pin `under`: a switch served under the ref it names, and `409 ref_moved` when that ref
  is elsewhere.
- `tests/test_git_revision_content_routes.py` pins that a pin’s render reaches no lexer
  under the untrusted profile.

## Decisions

The owner answered on 2026-11-17:

- **Q1.** Where there is no in-app target (a checkout not at the head, a deleted file),
  there is no control, rather than a link to the file on GitHub.
- **Q2.** A commit’s diff drops “View at parent” and keeps one “View file”, at the
  commit, by the same link-or-switch rule as today.
- **Q3.** The large-file bounds move to the pinned viewer in this change.

On 2026-11-17 the owner revised Q3 after the review of
[#511](https://github.com/jlevy/metabrowser/pull/511): the render-work bound is removed
from this change, so the pinned viewer renders Markdown as it did before, with no size
cap, estimate, or refusal, and only the plain fences stay.
The proper fix, rendering in the projection worker under a deadline, is bead `mb-273l`,
in a separate pull request.

**Addendum, 2026-11-18.** In the [Open Modes](../../architecture/arch-open-modes.md)
design a repository folder can show the pull request’s head as a revision, so a checkout
that is not at the head has an in-app target and Q1’s first case no longer applies to
it. The owner decided that in a repository folder View on branch and Browse code go to
the head as a revision view, and that opening the working-tree copy is a separate,
labelled action
([Pull Requests in a Repository Folder](../../architecture/arch-open-modes.md#pull-requests-in-a-repository-folder)).
That is not built, and the table in [Design](#design) describes what is.

**Addendum, 2026-11-26.** A rendered link that the page does not keep at its `/view/`
address now opens the head’s file on github.com rather than staying plain text, as the
[In-App Link Resolution](plan-2026-11-26-in-app-link-resolution.md) plan decided; it
still never switches the pin.

## References

- Survey and review of `origin/main` at `e442ed10d`, 2026-11-16 and 2026-11-17.
- [Source Sessions and Pins](../../architecture/arch-source-sessions-and-pins.md)
- [GitHub Pull Requests](../../architecture/arch-github-pull-requests.md)
- [Design System: Diff File Bar](../../../design-system.md#diff-file-bar)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
