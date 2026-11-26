# Feature: Whole-Stack Review

**Date:** 2026-11-24

**Author:** Joshua Levy (github.com/jlevy) with LLM assistance

**Status:** Phases 0 (`mb-mxcm`, `mb-kkib`), 1 (`mb-vad1`), 2 (`mb-9dmv`), and 3
(`mb-ri96`) are built.
Phase 2 addresses a `{pull, path}` this copy cannot read at the file in that pull
request’s Changes, which loads it, rather than at the pull request alone.
Phase 3’s `stack` answer names the guide’s member and its record revision only while the
stack is current, since a member not read yet may carry a block, so the page keeps the
guide it showed while the stack is pending, as it keeps the drawn comparison.
Once the stack moves, the guide is read at the pair the page draws, the current one or
one the stack route gave and keeps (`retained_stack_pair`), until the reader takes the
new comparison. A pair the route never gave answers `stack_moved`, as does a kept pair
the guide’s pins are past, since its carrier moved and was pinned again
(`_pinned_past`); while the drawn pair is not current, the page reads a step answer for
another revision as that step’s `stack_moved`, keeping the outline.
The skill’s stack recipes are held by its command checks, not run by
`cli-skill-recipes.tryscript.md`, whose stand-in has no stack.
Phase 1 leaves out the Pulls tab’s **Stack #N** heading as an entry point, since that
heading is the stack row’s disclosure toggle, and the Chrome measurement of Docs that
[Bounds](#bounds) asks for.
**View on GitHub** opens the top pull request, since the plugin knows no address for
GitHub’s own page of a stack.
Epic `mb-bxff`. The owner’s decisions of 2026-11-24 are under [Decisions](#decisions).
This plan replaces the stack rollup that
[Guided Review Groups](plan-2026-11-24-guided-review-groups.md#phase-3-stack-review)
designed.

## Overview

A stack of pull requests is one change delivered in layers.
Metabrowser shows it a layer at a time: each layer’s page, and each layer’s guide,
pinned to that layer’s comparison.
A reviewer who wants to know what the whole stack does has to add the layers up.

This plan adds four things, each usable without the next:

1. **Concise guides.** The skill’s per-pull-request guides get shorter, and a guide’s
   notes render as Markdown.
2. **A stack page.** Every file the stack changes as one consolidated diff, with a Docs
   view over it, cached until a member moves.
3. **Three reference kinds** in the collection format: a pull request, a file as a pull
   request changes it, and a commit.
4. **A stack guide.** One collection for the whole stack, read top-down, carried in a
   member’s description.

The frame for all four is the owner’s: do not overdesign, stay flexible, and reuse the
[collection format](../../architecture/arch-collection-format.md) everywhere.
A collection stays a list of items, each a title, a note, and references; what grows is
what a reference may point at and, later, how much of its comparison a collection pins.

## Goals

- A reviewer opens a stack and reads its whole change: the files, the consolidated diff,
  and the documents as they now are.
- A stack’s page never shows a stale comparison and never recomputes one that has not
  moved.
- One record, `Collection/v1`, carries a pull request’s guide and a stack’s, and every
  guide published today is still accepted.
- A stack guide is about ten steps on the end state, and a layer’s guide is short enough
  that the two do not repeat each other.
- An agent writes and refreshes a stack guide from `metab` and `gh` alone.

## Non-Goals

- A “This pull request | Whole stack” switch on a pull request’s page.
  [The Page](#the-page) says why.
- Deriving a stack’s guide from its layers’ guides.
  [Where the Stack Guide Is Carried](#where-the-stack-guide-is-carried) says why.
- Composing a tree from the layers’ patches.
  It would show content that exists in no commit, could not open with View on branch,
  and could conflict.
- Collections in repository files (`mb-2sft`), URL references (`mb-1rte`), the Markdown
  form (`mb-tzbp`), and cards (`mb-z9ox`). [Later](#later-loose-and-pinned-collections)
  says what this plan leaves them.
- A stack-specific size limit before a browser measurement asks for one.
- Changing a stack. Metabrowser reads stacks and never changes them.

## Background

### What Exists

- **The stack snapshot.** `pull_stacks.py` keeps each native stack’s ordered members,
  and `stack-change` accumulates the members’ changed-file lists for the Pulls tab’s
  heading (`pull_stack_change.py`), under the owner’s earlier decision that a stack is
  the set of pull requests it consists of, merged or open.
- **A comparison of any two commits.** The diff plugin’s `comparison_at`
  (`builtin_plugins/diff/sidekick.py`) answers one, takes a manifest loader from its
  caller, and already filters by `group=type:docs`, `types=`, and `file=`.
- **One kept manifest for each pull request** (`pull_manifest.py`), replaced by any
  other comparison of it.
  A stack’s comparison filed under its top member would evict that member’s own.
- **Admission by pair.** `pull-rendered-diff`, `pull-image`, and `pull-size` open only
  the record’s own pair or a retained one (`_decide` in `pull_snapshot.py`), so a
  stack’s pair is refused today.
- **Guided reviews.** One `guided-review` block for each description, resolved against
  the pull request’s current comparison (`_step_references` in `guided_review.py`) and
  stale when its pins are not that comparison (`_staleness`). Groups and the outline
  (#807) and whole documents drawn as Docs draws them (#806) are built.

### Why the Plain Two-Commit Diff Is Wrong

Measured 2026-11-24 on a reader’s cache of this repository, for eight of its stacks: the
diff from the bottom member’s merge base to the top member’s head, against the union of
each member’s own diff (`git diff --name-only` on the store, by path, from the cached
stack snapshot and pull records).

| Stack | Layers | Files the layers change | Files in base to top | In no layer | In two or more layers | Documents | Patch |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 579 | 5 | 39 | 39 | 0 | 15 | 11 | 0.33 MB |
| 443 | 4 | 65 | 65 | 0 | 7 | 11 | 0.90 MB |
| 770 | 4 | 79 | 79 | 0 | 21 | 30 | 0.74 MB |
| 682 | 9 | 81 | 81 | 0 | 17 | 21 | 1.07 MB |
| 657 | 8 | 269 | 269 | 0 | 67 | 59 | 2.27 MB |
| 794 | 6 | 92 | 183 | 91 | 31 | 30 | 0.44 MB |
| 725 | 13 | 95 | 151 | 56 | 40 | 38 | 0.78 MB |
| 710 | 9 | 183 | 173 | 0 | 83 | 69 | 1.48 MB |

Documents are the layers’ `.md`, `.txt`, and `.rst` files, an approximation of the Docs
group, and Patch is the base-to-top patch of the layers’ files.

- **The plain diff is not the stack’s change** once a layer has merged its base branch
  in or been retargeted: 91 of 183 files in stack 794, and 56 of 151 in 725, belong to
  no layer.
- **The top head does not always contain every layer.** In stack 710 six members’ heads,
  three open and three merged, are not ancestors of the top’s, and 10 of the layers’
  files are missing from the diff.
- **The bottom merge base was an ancestor of the top head in all eight.**
- **Which layer changed a file is information.** A tenth to nearly half of the files are
  changed by two or more layers.
- **The listing is cheap.** `git diff --raw --numstat -M` from base to top took 0.3 to
  2.1 s in two runs at load averages near 330 and 440, so those are upper bounds.
- Across the 43 stacks cached that day, the median had 3 members and the largest 46.

Eight stacks of one repository, all merged with merge commits, are a small sample.
[Open Questions](#open-questions) lists what it leaves unmeasured.

## Design

### Phase 0: Concise Guides (`mb-mxcm`, `mb-kkib`)

**The skill writes shorter per-pull-request guides** (`mb-mxcm`). In **Write a Guided
Review** of `skills/metabrowser/SKILL.md`:

- The description opens with a summary of the end state, three to five lines.
  That is the guide’s orientation, and no step repeats it.
- “Every changed file belongs to some step” goes.
  It forces a file inventory, which the Changes tab already is.
  A guide cites what a reviewer must read.
- One step for each area of the change, never one for each file or commit, and a step
  for each concern that has something to say; a concern with nothing to say is left out,
  except testing. In a grouped guide a concern of two steps or more is a group, and a
  concern of one step stays a step of its own, so no group holds a single step.
- A note is one to three sentences: what is true now, and what to check.
- A stacked layer states its place in one line and points at its neighbors or the stack
  guide, without explaining the stack again.
- The refresh recipe stops asking for a step for each file a push added.

The groups, the rationale step, and the three-way testing split stay as
[Guided Review Groups](plan-2026-11-24-guided-review-groups.md) set them.

**Notes render as Markdown** (`mb-kkib`), in every guide, the ones published today
included.

- A step’s note and a group’s note render as a pull request’s description does: KPress
  in its sanitized trust mode, then `harden` in `inert_html.py`, in the server’s
  Markdown child under its deadline (`pull_text_render.py`). Raw HTML is cleaned, never
  trusted, and nothing in a note chooses what the page loads.
- The route answers the rendered note beside its source, so a step is still one read,
  and the render is kept with the parse for the record’s revision.
- A note whose render is refused shows as plain text with the line that says why, as a
  description does (`textRefusalNote` in `pull-page.js`): the route answers the
  refusal’s code beside the null render (`note_refusal`, `group_note_refusal`), and the
  page keeps no answer whose renderer was busy or could not start, so the step is read
  again.
- Titles stay plain text.
- It stays `Collection/v1`: no field is removed, renamed, or retyped.
  A note written as plain text reads the same unless it used Markdown syntax, which now
  renders as its author likely meant.
- The skill and
  [Reviewing Pull Requests](../../../reviewing-pull-requests.md#guided-review) stop
  saying Markdown prints literally.

A stack guide’s overview is its first steps’ notes, so this lands before the stack guide
does.

### Phase 1: The Stack Page (`mb-vad1`)

#### The Combined Comparison

- **Old side:** the bottom member’s merge base, `comparison.base` of its record.
- **New side:** the top member’s head.
- **Files:** the entries of that diff that a layer changes: those with a path, on either
  side of a rename, that an included member’s own manifest names.
  Each member’s manifest is kept after its fetch (`prepare_pull_manifest`), so the
  filter and the attribution usually run no Git.
- **Merged members stay in**, as the Pulls tab’s change line counts them.
  A merged pull request’s pins never move, so the view survives merging.
- **A member the top head lacks** is one whose head, or merge commit once merged, is not
  an ancestor of the top head (`git merge-base --is-ancestor`, the call `_pins_compare`
  makes). It contributes no files.
  The view still shows base to top, and one line names those members and says to open
  each for its changes.
- **Not linear.** When the bottom merge base is not an ancestor of the top head, the
  route answers `absent` with the reason `not_linear`, and the page says to open each
  pull request.
- **Known limit.** A stack’s file that the base branch also changed, in a span a layer
  merged in, shows those lines too.

#### Cache and Invalidation

- **The key** is the store, the build, both commits, and a digest of every member’s
  number, merge base, and head, in stack order.
- **Invalidation is the key changing.** A member’s record moving, or the member list
  changing, names a new comparison.
  Nothing is invalidated by hand and nothing stale can be served.
- **Kept in three places**, each an existing pattern: the process’s comparison cache
  (`comparison_cache.py` in the diff plugin); one kept manifest for each stack beside
  the store, as `pull_manifest.py` keeps one for each pull request; and the browser,
  since the comparison’s address names everything its answer depends on.
- **The restricted manifest has its own identity.** The digest is in the cache key and
  the entity tag, so it never shares an entry with the unrestricted comparison of the
  same two commits.
- **Recomputed on demand,** at the first read after a change.
  Phase 1 prefetches nothing.
- **Totals** (files, lines added and removed) come from the kept manifest.
  `pull-size` is left out: its pushed size would count base-branch commits merged into
  layers.

#### Routes

| Route | Answers |
| --- | --- |
| `GET /api/plugin/github/stack?number=<n>` | The pointer, which changes as members move: the members with their state, title, and place; the comparison’s two commits and its key; the members the top lacks; the members still `pending`; the totals; each path’s layers; whether a member carries a stack guide; and the address of the comparison below |
| `GET /api/plugin/github/stack-comparison?…` | The comparison document, immutable at its address, through `comparison_at` with the stack’s manifest loader, so `group=type:docs`, `file=`, `types=`, and `view=types` work as on a pull request |
| `pull-rendered-diff`, `pull-image` | Take `stack=<n>` in place of `number`, and `_decide` admits the stack’s current pair, computed as the `stack` route computes it, and the earlier pairs the `stack` route answered that are still kept |

- `stack` is `current`, or `pending` while a member has no record, or `absent` with a
  reason (`not_github`, `not_stacked`, `not_linear`), following `stack-change`.
- A `GET` runs no `gh`, as every route of the plugin.
  The page asks `pull-refresh` for each pending member, under that route’s existing
  gates.
- Both routes arrive with a row in the
  [Parity Registry](../../architecture/arch-parity-registry.md), a golden, a row in the
  plugin’s route table
  ([GitHub Pull Requests](../../architecture/arch-github-pull-requests.md#routes)), and
  the [map](../../architecture/arch-views-models-routes.md).

#### The Page

`/stack/<n>` is a page of its own, registered beside `PULL_ROUTE_TABS` in
`view_routes.py`. Its number is GitHub’s label for the stack, which does not change when
a layer is added.
**View on GitHub** was to open the stack’s page there; phase 1 does not
build that, and opens the top pull request, since the plugin knows no address for
GitHub’s own page of a stack.

- **Header:** the stack’s name and base branch, its members from top to base with state
  and title as the stack menu lists them, the totals, and the line about members the top
  lacks, when there are any.
- **Files** (`/stack/<n>/files`): every file the stack changes, in the shell’s
  changed-files tree (`static/changed-files-tree.js`), which a diff’s Diff summary draws
  too. A file opens Changes at that file.
- **Docs** (`/stack/<n>/docs`): the stack’s documents as the top head has them, drawn
  with the options a pull request’s Docs has (`DOCS_DRAWING` in `diff-drawing.js`, which
  `pull-page.js` shares), so it opens on Current.
- **Changes** (`/stack/<n>/changes`, and `/stack/<n>/changes/<path>` at one file): the
  consolidated diff, mounted with the diff plugin’s `mountDiffView` on the one
  comparison, as a commit’s page mounts its own, with the choices and preferences a pull
  request’s Changes has.
- **Guided Review** (`/stack/<n>/guided`), built in phase 3.
- **The front page** `/stack/<n>` is Guided Review when the stack has a guide, and Files
  otherwise. The `stack` answer says which, from the server’s reading of the
  descriptions, so the page needs no hint of its own.
- **Entry points:** a first row, **Stack Overview**, in each member’s stack menu.
  The Pulls tab’s **Stack #N** heading was planned as one too; phase 1 does not build
  it, since that heading is the stack row’s disclosure toggle.
  Opening a GitHub stack link with `metab` or in the app, as a pull request’s link
  opens, is left for later.
- **Layer chips.** Each file’s row and file bar names the layers that change it by their
  place, such as “2/4”, and each chip opens that file in that layer’s Changes
  (`/pull/<n>/files/<path>`). There is no filter by layer: a layer’s own page is that
  view.
- **A new comparison while reading** is offered, not swapped in under the reader, as a
  pull request’s page offers a new head.
  The drawn one stays while a member is fetched, and the server keeps answering it after
  the stack moves, as it keeps a pull request’s earlier pairs
  (`pull_stack_retained.py`).

**Since built (mb-cm31).** The page became a pull request’s page for the whole stack
([The Stack Page](../../../design-system.md#the-stack-page)): it has no Files tab, since
the header’s Diff summary lists the files as on a pull request’s page, and
`/stack/<n>/files` is no route; its front page without a guide is Changes; no file row
or bar carries layer chips, and the diff view’s `fileMarks` hook that drew them is gone;
View on GitHub opens GitHub’s `stack/<n>`, the address the counterpart route answers;
and the Pulls tab lists the page as each open stack’s last row, **Stack Overview**,
which mb-4gcj moved to the stack’s first row, the stack menu’s place for it.

**Why a page and not a switch on each pull request.** A pull request’s Changes and Docs
carry a state machine that follows one comparison’s head (`filesAction`, `followedFrom`,
and `rememberedChanges` in `pull-page.js`); a scope switch would double every state.
A stack is also no single pull request, so its address should not be one’s.

#### Staying Current

The page reads `stack` again on its poll, as a pull request’s page reads `pull`. Members
move through the catalog: a member whose row names a head its record lacks is `pending`,
and the page asks `pull-refresh` for it at that head.
It asks for a member with no record as the reader’s own open of it (`retry`), as a pull
request’s page opened by a link does, since an automatic ask refreshes only a record the
server holds. An ask the server refuses, which it does past `MAX_PULL_JOBS` fetches at
once, or whose fetch ends with the member still pending, is sent again after a backoff
(`ASK_BACKOFF_MS` in `stack-page.js`); a member with no record whose fetch ended without
one is named, with a Retry.
While a stack’s page is all that is open, it sends a visible pull request page’s
automatic ask for its top member, which keeps the repository’s list probed
(`attend_list` in `pull_list_route.py`), so the catalog keeps reporting every member’s
head. The page adds no probe of its own and, as a pull request’s page, reads nothing
while hidden;
[Pull Request Update Cadence](plan-2026-11-22-pull-request-update-cadence.md#cadence-by-what-is-visible)
has the cadences it inherits.

#### Bounds

The existing bounds apply unchanged: `MAX_MANIFEST_FILES` (`diff/adapters/git.py`) on
the listing, `INITIAL_PULL_FILES` (`builtin_plugins/github/sidekick.py`) on first
hydration with the rest deferred, and `_MARKDOWN_PAIR_MAX_BYTES` and `_MAX_HTML_BYTES`
(`pull_rendered_diff.py`) on each rendered document.

Stack Docs is where cost concentrates: the measured stacks hold 11 to 69 documents, and
`mb-qn7e` measured one large document freezing the Docs tab.
Docs follows that work’s windowed drawing.
Stacks the size of 657 and 710 are measured in headless Chrome before any stack-specific
limit is added, and the measurement goes beside the constant if one is.

### Phase 2: Reference Kinds (`mb-9dmv`)

```yaml
references:
  - {path: docs/plan.md}                # today: a file in the collection's comparison
  - {path: src/a.py, side: new, start_line: 40, end_line: 58}  # today: a range of it
  - {pull: 805}                         # new: a pull request
  - {pull: 805, path: src/a.py}         # new: that file as that pull request changes it
  - {commit: "<full commit ID>"}        # new: a commit
```

| Kind | Resolves against | Answers | Draws as |
| --- | --- | --- | --- |
| `{pull}` | The cached record, or the catalog’s row | Number, title, state, place in its stack, and address; `not_cached` when this copy knows neither | A row, as the stack menu lists a member |
| `{pull, path}` | That pull request’s kept manifest, the one its Changes reads, at its record’s comparison | As a `{path}` alone does today: the whole patch, or the document; `not_cached` when this copy has no record or no kept manifest | As a `{path}` alone, with the pull request named |
| `{commit}` | The store, and a served checkout for its address | Subject, date, and address; `commit_unavailable` when the store lacks it, and no address when the checkout does | A row, as the Commits tab lists one |

- **Valid in every carrier**, a pull request’s guide included, so a layer’s guide can
  cite its neighbors.
- **Nothing is fetched** to resolve a reference.
- **`{pull, path}` takes no range** in this phase.
  It follows that pull request’s comparison, which the collection does not pin, and a
  range into a moving file would come to point at other lines.
  [Later](#later-loose-and-pinned-collections) gives it pins.
- **A reference to a pull request or a commit is never stale,** a `{pull, path}`
  included, which follows that pull request.
  Only a file of the collection’s own comparison counts toward a stale guide’s
  `changed_steps`: a `{path}`, or a `{pull, path}` that names the guide’s own pull
  request, which reads as its `{path}`.
- **A step still needs a reference,** which may now be a pull request or a commit, so a
  step no longer has to cite a changed file it is not about.
- **Rows, not cards.** The collections research reserves cards for the shared card frame
  (`mb-z9ox`), so these draw with the rows the page already has.
- **It stays `Collection/v1`.** `path` stops being required of a reference and two
  optional fields join it; every record v1 accepts still means the same.
  This is the reading of
  [Contracts](plan-2026-11-14-object-data-model-and-views.md#contracts) that groups
  took. The compiled schema states which fields each kind takes without losing a
  refusal’s place, as groups’ `if` on `items` does.
- **`MAX_REFERENCES` stays one bound.** The worst step of each kind is measured beside
  it in `guided_review.py`. A `{pull, path}` is the costliest, one run of the diff
  source for each pull request it names, though it reads only a kept manifest and never
  lists a comparison; a `{pull}` reads a record and a catalog row, and a step’s
  `{commit}` references share one `git log`. Whether a `{pull, path}` needs a smaller
  bound of its own is a person’s call.
  A layers step for a stack longer than the bound cites the layers a reviewer should
  open; the header lists them all.

### Phase 3: The Stack Guide (`mb-ri96`)

#### Where the Stack Guide Is Carried

| Carrier | Buys | Costs | Verdict |
| --- | --- | --- | --- |
| A. A rollup derived from the layers’ guides | Nothing to write | No overview; inherits every layer’s detail, so four layers of ten steps is forty; needs a tree deeper than the record allows | Rejected |
| B. A `stack-review` block in a member’s description | The existing parser, route, and page; an edit moves no head, so no CI run, no stale layer guide, and no new stack comparison; exact pins; readable after merge | A second fence name; not diffable as a file | **Chosen** |
| C. A review-only pull request on top, whose description is the guide | Nothing B lacks | A commit to exist, a layer to keep on top and skip at merge, CI on a no-op | Allowed by B, never required |
| D. A collection file in the repository | Versioned, diffable, and the long-term home of collections | Every refresh is a commit that moves the head it describes, restarts CI, stales the layer’s own guide, and re-keys the stack’s comparison; it cannot pin its own commit; it needs `mb-2sft`’s plugin | Later, as a second home |

What a repository file offers (one record, references to files, pull requests, and
commits, readable after merge) belongs to the record, which every carrier shares.
The carrier sets only what a refresh costs, and a description edit is free where a
commit is not. Moving a guide to a file later is copying the block.

#### Mechanics

- **The block.** A top-level `stack-review` fence holding a `Collection/v1` record, read
  by the parser that reads a `guided-review` block (`_guide_fence` takes the fence’s
  name). A description may hold one of each; two of either is refused.
- **Which member.** The skill writes it in the top member’s description.
  The stack’s guide is the block of the top-most member that has one, so a layer added
  above it leaves the guide found, and out of date until it is refreshed.
- **Pins.** `merge_base` is the stack’s base and `head` the top member’s head, both from
  the `stack` answer.
- **The route.** `guided-review?stack=<n>&step=<k>` answers it in the envelope a pull
  request’s guide has: `_step_references` reads the stack’s kept manifest, and
  `_staleness` compares the pins with the stack’s pair.
  It reads at the pair the page draws (`left`, `right`, `key`), the current one or a
  kept one, as the stack’s Diff summary, Docs, and Changes do.
  A pair the route never gave, or a kept pair the guide’s pins are past, answers
  `stack_moved`: there the guide was written for a later comparison, and reading it at
  the old pair would report it rewritten.
- **The page.** `guided-review.js` mounts on the stack’s page, with #807’s groups and
  outline and #806’s whole documents as they are.
- **No description of its own.** The member’s description introduces that member, not
  the stack, so the stack guide’s overview is its Orientation group: the tab opens on
  the step list with the first step under it.
  The description’s render leaves the block out, as it does a guide’s, and Conversation
  puts a card that opens the stack’s guide in its place.
- **After a merge** that keeps history, the pair does not move and the guide stays
  current.

#### What a Stack Guide Says

| Group | Steps | The note says | References |
| --- | --- | --- | --- |
| Orientation | What this stack does | The problem and the outcome, in five lines | The plan, whole |
|  | The system after it | The parts and how they connect | The architecture document, whole |
|  | The layers | One line for each, bottom up | `{pull}` for each |
| Decisions | Key decisions and why | Up to five: decided X because Y, which rules out Z | Where each is recorded |
| Documents | One for each document a reviewer must read | What it now promises | The file, whole |
| Areas | Three to five, by subsystem, in dependency order | What it does now and what to verify | Up to three ranges that matter, and the layer’s `{pull}` |
| Open questions | One | What a person must decide | The code in doubt |
| Testing and merging | One or two | Automated, agent-checked, and needs a person; the merge order; deferred work with its tracker IDs | Tests, the plan |

- Eight to twelve steps.
- A note of at most five lines, in the present tense, about the end state.
- At most three references a step, the layers step excepted.
- Never: narration by layer or by commit, a file inventory (the Diff summary is one),
  anything a layer’s guide says (cite its `{pull}`), how the design evolved, review
  rounds, commit IDs, or counts the header shows.

The skill gains **Write a Stack Guide** with this table, a skeleton held to the parser
by `tests/test_skill_commands.py`, and the recipe below.

#### The Agent’s Recipe

```shell
<invocation> <url> --api '/api/plugin/github/stack?number=<s>' --format json  # members, pins, each path's layers
<invocation> <url> --api '<comparison route>&group=type:docs' --format json   # the stack's documents
gh pr edit <top> --body-file <tmp>/body.md    # the description, with its stack-review block
<invocation> <url> --no-serve                 # refresh the record the route reads
<invocation> <url> --api '/api/plugin/github/guided-review?stack=<s>&step=<k>' --format json
```

- **Inputs:** the `stack` answer, each layer’s description and guide, and the stack’s
  plan and architecture documents.
- **Pins** come from the `stack` answer, so the recipe runs no `git merge-base`.
- **Confirming:** `state` is `ready` and every reference is `ready`, step by step, as
  for a pull request’s guide.
- **After a push or a restack:** read `.state` and `.stale.changed_steps`, fix those
  steps, move the pins, and publish again.
- **A new top layer** needs no move: the block is still found, and reads out of date
  until refreshed.

### Later: Loose and Pinned Collections

Not built by this plan, and designed here so the phases above do not close it off.
It waits for the first carrier that implies no comparison, a repository file
(`mb-2sft`).

```yaml
collection:
  comparison:              # optional, and every field in it optional
    base: main             # the base branch; default the carrier's, else the default branch
    branch: claude/top     # the head branch; default the carrier's
    merge_base: "<id>"     # today's field: pins the old side
    head: "<id>"           # today's field: pins the new side
  items: …
```

- **Sides.** The new side is `head` if given, else the tip of `branch`. The old side is
  `merge_base` if given, else the merge base of `base` and the new side.
- **Today’s guides are the fully pinned case,** valid and unchanged.
  Fields become optional and gain siblings, which
  [Contracts](plan-2026-11-14-object-data-model-and-views.md#contracts) does not count
  as a break, so there is no new version and no alias.
- **Staleness follows from what is filled.** A side pinned to a commit is stale when its
  branch has moved off it, with today’s warning and `changed_steps`. A side left to its
  branch follows it and is never stale.
- **A line range needs both pins.**
- **A reference may override the collection.** A file reference may carry the same four
  names. Its comparison is its own, else its `pull`’s, else the collection’s, else the
  carrier’s. That is also what lets a `{pull, path}` reference take a range.
- **A stack guide needs none of this:** its carrier implies the stack’s comparison, and
  today’s two pins name the commits.

### Earlier Decisions Kept or Revised

The collections research on [#679](https://github.com/jlevy/metabrowser/pull/679)
(branch `claude/collection-documents`, not merged) records the owner’s decisions of
2026-11-23. This plan keeps them except where it says so:

| The research says | This plan |
| --- | --- |
| One contract, `Collection/v1`, with no family and no second reader | Kept |
| One way to write a reference, with no shorthand | Kept: each new kind has one spelling. The research’s later `{object: {type, id}}` form (`mb-z9ox`) would cover types without one, and would not respell these |
| All text is plain text, drawn as typed | **Revised** by the owner: notes are sanitized Markdown, and titles stay plain |
| No fences in repository Markdown | Kept: the stack guide is a fence in a description, and a repository collection is a YAML file |
| No cards before the shared card frame | Kept: object references draw as rows |
| No `pin` union | Kept: `comparison` stays one mapping, whose fields become optional |
| A repository file refuses `comparison`, and no revision pin is proposed until someone needs a past state | **Revised, later:** `comparison` becomes optional there, loose by default |
| The fence appears only in a pull request’s description | Kept, and a second fence name, `stack-review`, joins it there |
| Each carrier keeps its own route | **Read as:** a stack guide is the description carrier with another comparison, so `guided-review` answers both, by `number` or by `stack` |

## Decisions

The owner decided these on 2026-11-24, on the design this plan records:

1. **Merged layers stay in the stack’s view.** A stack is its pull requests, merged or
   open, as the Pulls tab’s change line already counts it.
2. **A guide’s notes render as sanitized Markdown,** inert and through the path rendered
   Markdown takes, in every guide and not only a stack’s.
3. **The stack guide is a `stack-review` block in the top member’s description now,**
   and a collection in a repository file later.
4. **The stack page’s first tab is Guided Review when the stack has a guide, and Changes
   otherwise (since mb-cm31).**
5. **The skill’s “every changed file belongs to some step” rule goes,** and
   per-pull-request guides become concise, as phase 0 sets out.

The owner’s constraints frame the rest:

- Do not overdesign, stay flexible, and reuse the collection format everywhere: a list
  of items, each a title, a note, and references.
- A reference points at a file (often on a branch, optionally at a commit, so a diff
  against a base can be drawn), a pull request, or a commit.
- A collection may name its base branch or base commit, defaulting to the default
  branch. One tied to a commit names its commits and base, as today’s pins do.
  A loose collection follows its branches and is never stale; a pinned one can be.
- The stack page’s default is the consolidated diff of every file the stack changes,
  cached, and recomputed whenever a member moves, with a Docs view over it.

[Approach C of the groups plan](plan-2026-11-24-guided-review-groups.md#the-superseded-rollup-design),
a rollup derived from each layer’s guide, is rejected: it has no overview, inherits each
layer’s detail, and needs a tree deeper than the record’s one level of groups.

## Implementation Plan

Each phase is a layer of one stack and usable alone.

| Phase | Beads | Changes | Reuses |
| --- | --- | --- | --- |
| 0 | `mb-mxcm` | The skill’s concision edits for per-pull-request guides | `tests/test_skill_commands.py` |
| 0 | `mb-kkib` | Notes rendered inert by the route, drawn by the page; the skill and the user guide | `pull_text_render.py`, `inert_html.py` |
| 1 | `mb-vad1` | The `stack` and `stack-comparison` routes; stack admission in `pull_snapshot.py`; the kept stack manifest; the page with Files, Docs, and Changes; the entry points; layer chips; the line about members the top lacks; parity rows, goldens, the route table, and the map | The diff view, `group=type:docs`, Diff or Current, the changed-files tree, `mb-qn7e`’s windowed drawing |
| 2 | `mb-9dmv` | `{pull}`, `{pull, path}`, and `{commit}` in the models and the compiled schema, the route’s answer, the step’s rows, and the format reference | `_step_references` and the models in `guided_review.py` |
| 3 | `mb-ri96` | The `stack-review` block; `guided-review?stack=`; the Guided Review tab on the stack’s page; the skill’s **Write a Stack Guide** | #807’s groups and outline, #806’s whole documents |
| Later | `mb-2sft`; the comparison fields and overrides have no bead yet | Optional comparison fields, per-reference overrides, and collections in repository files | — |

Related work this plan leans on and does not own: `mb-enj3` and `mb-szxu` (#807, groups
and rationale), `mb-qgz1` (#806, rendered documents), `mb-8viy` (a rendered excerpt for
a range), `mb-qn7e` (Full, Concise, and Source, and windowed drawing), and `mb-uqwl`
(the draft check of
[Guided Reviews in the Agent Skill](plan-2026-11-24-guided-reviews-skill.md)).

## Testing Strategy

- **Phase 0.** `tests/test_skill_commands.py` still parses both skeletons, and the
  values the skill and the user guide state stay pinned
  (`tests/test_user_guide_values.py`). For notes: a route golden of a note holding raw
  HTML, a script, and an image, rendered inert; the real guide kept in
  `tests/fixtures/guided-review/` renders; a refused render falls back to text; and a
  browserless session of the step’s note.
- **Phase 1.** A stack on the GitHub stand-in (`tests/github_pull_fixture.py`) of three
  layers: one merges its base branch in, so the plain diff holds a file no layer
  changed; a file is renamed in one layer and changed in another; and one layer is one
  the top lacks. Goldens for `stack` (current, pending, not stacked, not linear, a member
  the top lacks) and `stack-comparison` (whole, `group=type:docs`, `file=`,
  `view=types`); for `pull-rendered-diff` and `pull-image` with `stack=`, an admitted
  pair and a refused one.
  A test that the key changes when any member’s base or head moves, and when the member
  list does. A browserless session of the front page’s choice of tab and of a new
  comparison offered while reading.
  The Chrome measurement of Docs that [Bounds](#bounds) asks for.
- **Phase 2.** Model tests and the schema drift check (`tests/test_guided_review.py`); a
  golden for each kind and each refusal; the real guide still parses unchanged.
- **Phase 3.** Goldens for `guided-review?stack=`: ready, stale after a member moves,
  two blocks refused, a block on a member below the top.
  The description’s render without the block.
  The skill’s command checks on the stack guide’s skeleton and recipe.
  The stack that builds this plan carries a stack guide written by that recipe.

## Open Questions

1. **Base-branch lines.** How often a stack’s file also carries lines the base branch
   changed is unmeasured.
2. **Squash and rebase merges.** The eight stacks all keep merge commits.
   How often a repository that squashes or rebases reaches `not_linear`, and whether the
   merge-commit test finds its merged members, is unmeasured.
3. **Docs in a browser.** Stack Docs at 59 to 69 documents is unmeasured.
4. **A long stack opened cold** starts one record refresh for each member this copy
   lacks; the largest cached stack has 46. Measure before deciding whether merged
   members’ files should come from their cached lists, as `stack-change` reads them.
5. **Line breaks in a note.** Answered in phase 0: a note follows the description’s
   render, measured through the Markdown child, so a single line break joins two lines
   into one paragraph and a list needs no blank line before it.
6. **Changes’ address.** Settled by mb-cm31. On a pull request `/pull/<n>/files` is
   Changes; the stack’s page had a Files tab too, so this plan gave Changes a `changes`
   segment. The Files tab and `/stack/<n>/files` are gone, and `changes` stays:
   `/stack/<n>/changes/<path>` is a file in Changes.
7. **The contract reading.** A reviewer should confirm that widening a reference, and
   reading a note as Markdown, stay within v1, as the groups plan asks of groups.
8. **The draft check** (`mb-uqwl`) reads a `guided-review` block.
   Whether it also checks a `stack-review` block belongs to that plan once phase 3
   exists.

## References

- [Collection Format](../../architecture/arch-collection-format.md) and
  [GitHub Pull Requests](../../architecture/arch-github-pull-requests.md)
- [Guided Review Groups](plan-2026-11-24-guided-review-groups.md) and
  [Guided Reviews in the Agent Skill](plan-2026-11-24-guided-reviews-skill.md)
- [Reviewing Pull Requests](../../../reviewing-pull-requests.md#stacks) and
  [the agent skill](../../../../skills/metabrowser/SKILL.md)
- [Pull Request Update Cadence](plan-2026-11-22-pull-request-update-cadence.md),
  [The Diff | Current Chooser](plan-2026-11-23-diff-current-chooser.md), and
  [General Diff Rendering](plan-2026-08-17-general-diff-rendering.md)
- [Rendering large content](../../../large-content-rendering.md)
- The collections research on [#679](https://github.com/jlevy/metabrowser/pull/679):
  Annotated Collections, Collection Documents with its design memo, and their technical
  review
- #807 (groups and rationale) and #806 (rendered documents in steps)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
