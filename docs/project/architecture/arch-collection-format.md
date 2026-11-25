# Collection Format

**Status:** Built as contract `metabrowser.collection:Collection/v1`, with one carrier:
guided reviews of GitHub pull requests, whose notes render as Markdown, and whose
references name a file, a pull request, a file as a pull request changes it, or a
commit. Designed, not built: a stack’s guide, collections in repository files, URL
references, a Markdown form, and the other carriers below.

A collection is an ordered list of annotated items, which may be gathered in titled
groups: each item is a title, a note, and the references it is about.
What the references point at, how they resolve, and what a reader sees are decided by
the **carrier**, the place a collection is written and read.
A guided review is the first carrier: a code-review guide in a pull request’s
description. The format is not tied to pull requests or to review, so other review
scenarios and other kinds of lists use the same record.

## The Record

The contract is a SoftSchema record with the envelope key `collection`:

```yaml
softschema:
  contract: metabrowser.collection:Collection/v1
  envelope: collection
  status: enforced
collection:
  comparison:
    merge_base: "<full commit ID>"
    head: "<full commit ID>"
  items:
    - title: The cache
      note: Read the request before the worker.
      items:
        - title: Inspect the request path
          note: Check that the request returns the snapshot before the worker finishes.
          references:
            - {path: src/cache.py, side: new, start_line: 42, end_line: 51}
    - title: Read the cache’s guide
      note: Check that it describes the snapshot.
      references:
        - {path: docs/cache.md}
        - {pull: 805}
        - {pull: 805, path: docs/plan.md}
        - {commit: "<full commit ID>"}
```

- **`items`** are ordered, and the order is the author’s. Each entry is an item or a
  group. An item has a `title`, plain text that a reader shows as typed, a `note`,
  Markdown that a reader renders inert, and one or more `references`. Notes were plain
  text when v1 was first built and became Markdown within it: no field is removed,
  renamed, or retyped, so by
  [Contracts](../specs/active/plan-2026-11-14-object-data-model-and-views.md#contracts)
  this is no break. A note written as plain text reads the same unless it used Markdown
  syntax, which now renders as its author likely meant, or a single line break, which
  now joins its two lines into one paragraph.

- **A group** has a `title`, an optional `note`, and its own `items`, at least one,
  which are items only: groups nest one level.
  A group’s note is Markdown as an item’s is.
  An entry with `items` is a group and one without is an item; the models tell them
  apart that way (`_entry_kind` in `guided_review.py`), and the compiled schema states
  it as an `if` on `items`. Groups and items outside a group mix in any order.
  A reader reads the items in order through the groups, so a carrier that numbers them,
  as a guided review numbers its steps, numbers them 1 to n. Groups arrived within v1:
  every record v1 accepted before still means the same, and
  [Contracts](../specs/active/plan-2026-11-14-object-data-model-and-views.md#contracts)
  counts only a field removed, renamed, or retyped as a break, which widening an entry
  to a group or an item is not.
  The cost is that a release before groups refuses a grouped record at `items.N`, so its
  reader needs a release with groups; a `Collection/v2` would not help that reader,
  whose release refuses v2 as well.

- **A reference** is one of four kinds, which its fields name (`kind` on
  `CollectionReference` in `guided_review.py`):
  - a file, `path`, optionally with a `side` and an inclusive line range: a file of the
    collection’s comparison, or a range of its diff;
  - a pull request, `pull`;
  - a pull request’s file, `pull` and `path`: that file as that pull request changes it;
  - a commit, `commit`, its full ID.

  A carrier decides what each names and how it resolves: in a guided review a path is a
  changed file and a range a range of its diff, and the other three are read from what
  is cached ([Format and Carrier](#format-and-carrier)). A pull request’s file takes no
  range: it follows that pull request’s comparison, which the collection does not pin,
  so a range into it would come to point at other lines.
  A commit is cited alone.
  The compiled schema states which fields each kind refuses, as an `if` on `commit` and
  then on `pull` (`_REFERENCE_KINDS`), so a refusal names the field that does not
  belong. The models enforce the rules it does not express: a path is a normalized
  relative path (no `./`, `..`, or trailing `/`), checked as the pull route forms an
  address; a range needs `side` and both line numbers, in order, so every v1 range is a
  range of a diff; and a reference names a file, a pull request, or a commit.
  A carrier without a change, which cannot cite lines that way, relaxes the range rule,
  as it does `comparison`. The three kinds past a file arrived within v1, as groups did:
  `path` stopped being required and two optional fields joined it, so every record v1
  accepted before means the same, and a release before them refuses a record that uses
  them at its reference.

- **`comparison`** pins the change the references resolve against.
  v1 requires it, because its one carrier is a pull request’s description, which is not
  versioned with the code it describes.
  A carrier without a change, such as a file versioned with what it lists, makes it
  optional. That keeps v1, since
  [Contracts](../specs/active/plan-2026-11-14-object-data-model-and-views.md#contracts)
  counts only a field removed, renamed, or retyped as a break.

- **A collection has no prose of its own.** The document that carries it introduces it,
  as a pull request’s description introduces its guide.

The
[compiled schema](../../../src/metabrowser/builtin_plugins/github/collection-v1.schema.yaml)
is generated from the Pydantic models (`Collection` and its parts in
`builtin_plugins/github/guided_review.py`), and `tests/test_guided_review.py` fails when
they drift. `MAX_ITEMS` and `MAX_REFERENCES` there bound a record: `MAX_ITEMS` counts
every entry, a group and each item in it alike, which no one list’s bound in the schema
states, so the models enforce the total.
Both were measured on guided-review costs (the parse per item, and a step’s diff
hydration), each beside its constant; a later carrier measures its own costs before it
keeps or changes them.

## Format and Carrier

The split keeps the format small enough to share:

| Belongs to the format | Belongs to the carrier |
| --- | --- |
| The contract ID, the envelope, the fields and their types | Where the record is written, and how it is found there |
| Item order, groups, and a note and references per item | What a path names, and the base it is relative to |
| `MAX_ITEMS` and `MAX_REFERENCES` | Whether `comparison` is required |
|  | How each reference resolves: its state, address, and excerpt, and their budgets |
|  | When the record is stale, and what the reader shows |

**Guided reviews** (`guided_review.py`, `guided-review.js`) are the carrier built today.
The record is a `guided-review` fence in a pull request’s description; `comparison` is
required, its `merge_base` must be an ancestor of its `head`, and its head a commit; a
path is a changed file and a range lies in one hunk of its diff; excerpts are bounded by
`MAX_EXCERPT_BYTES` and `MAX_STEP_PATCH_BYTES`; a note renders as the description does,
through the same inert render (`render_text` in `pull_markdown.py`), and shows as typed
when that render is refused; the record is stale when the pull request’s comparison
moves. A pull request is read from its cached record or else its row in the list of pull
requests, and placed in its stack from the stack snapshot; a pull request’s file is read
at that pull request’s current comparison, as a path is at the guide’s; and a commit is
read from the store.
Nothing is fetched to resolve one, and none of the three is ever stale: only a path
counts toward what a push to the pull request changed.
The `guided-review` route answers it, and the pull page’s Guided Review tab draws it
([GitHub Pull Requests](arch-github-pull-requests.md#guided-review),
[Reviewing Pull Requests](../../reviewing-pull-requests.md#guided-review)).

The fence names the carrier, not the format, so the same record could be written
elsewhere under its own marker.
Each carrier keeps its own route; the format has no generic collection route of its own
until a second carrier needs one.

## Other Carriers

None of these is built.
Each would reuse the record and add only its carrier’s rules:

- **A stack’s guide** (mb-ri96): a `stack-review` fence in the description of a stack’s
  top member, holding the same record pinned to the stack’s combined comparison, its
  bottom member’s merge base and its top member’s head.
  It is the description carrier with another comparison, so the `guided-review` route
  answers it and the stack’s page draws it
  ([Whole-Stack Review](../specs/active/plan-2026-11-24-stack-review.md#phase-3-the-stack-guide-mb-ri96)).
- **Other review scenarios.** A guide to a commit, or to a comparison of two branches or
  tags, would pin `comparison` as a guided review does and resolve paths against that
  diff. A working tree’s uncommitted changes have no commit for `head`, so a guide to
  them needs a pin of another kind.
  A review of a set of documents would cite files without a change.
- **Collections in repository files** (mb-2sft): a YAML file in the served tree, read by
  a built-in `collection` plugin that takes over the format module, with Rows, Table,
  and Source views. Paths are relative to the file, and `comparison` is optional.
  A stack’s guide could move to one later, by copying its block.
- **URL references** (mb-1rte): a `{url}` reference, `https` only and never fetched, so
  a guide can cite a design document or an issue.
- **A Markdown form** (mb-tzbp): a Markdown link list read into the same record, each
  heading a group and each link an item.
  Groups nest one level, so the form reads one level of headings.
- **Later uses** (mb-z9ox): references to other types of object, cards, and a Documents
  view.

The research brief on [#679](https://github.com/jlevy/metabrowser/pull/679) records the
design and the owner’s decisions behind this split, and
[Whole-Stack Review](../specs/active/plan-2026-11-24-stack-review.md#earlier-decisions-kept-or-revised)
says which of them it keeps and which it revises.
Moving the models out of the GitHub plugin is a module move: the contract ID already
names the `collection` plugin that will own it, so it does not change.

### Planned Changes to the Record

[Whole-Stack Review](../specs/active/plan-2026-11-24-stack-review.md) plans this, and it
is not built. It keeps v1, since it removes, renames, or retypes no field.

- **Loose and pinned comparisons**, with collections in repository files: `comparison`
  becomes optional and gains an optional `base` and `branch` beside its two pins.
  A side pinned to a commit can be stale; a side left to its branch follows it and never
  is. A line range needs both pins, and a reference may override the collection’s
  comparison. Today’s guides are the fully pinned case.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
