# Collection Format

**Status:** Built as contract `metabrowser.collection:Collection/v1`, with one carrier:
guided reviews of GitHub pull requests.
Designed, not built: collections in repository files, URL references, a Markdown form,
and the other carriers below.

A collection is an ordered list of annotated items: each item is a title, a note, and
the references it is about.
That is all the format says.
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
    - title: Inspect the request path
      note: Check that the request returns the snapshot before the worker finishes.
      references:
        - {path: src/cache.py, side: new, start_line: 42, end_line: 51}
        - {path: docs/cache.md}
```

- **`items`** are ordered, and the order is the author’s. Each has a `title`, a `note`,
  and one or more `references`, all plain text that a reader shows as typed.
- **A reference** is a `path`, optionally with a `side` and an inclusive line range.
  A carrier decides what a path names and whether a range means anything: in a guided
  review it is a changed file and a range of its diff.
- **`comparison`** pins the change the references resolve against.
  v1 requires it, because its one carrier is a pull request’s description, which is not
  versioned with the code it describes.
  A carrier without a change, such as a file versioned with what it lists, makes it
  optional, and that is not a break: a required field made optional is compatible
  ([Contracts](../specs/active/plan-2026-11-14-object-data-model-and-views.md#contracts)).
- **A collection has no prose of its own.** The document that carries it introduces it,
  as a pull request’s description introduces its guide.

The
[compiled schema](../../../src/metabrowser/builtin_plugins/github/collection-v1.schema.yaml)
is generated from the Pydantic models (`Collection` and its parts in
`builtin_plugins/github/guided_review.py`), and `tests/test_guided_review.py` fails when
they drift. `MAX_ITEMS` and `MAX_REFERENCES` there bound a record, each with the
measurement that set it.

## Format and Carrier

The split keeps the format small enough to share:

| Belongs to the format | Belongs to the carrier |
| --- | --- |
| The contract ID, the envelope, the fields and their types | Where the record is written, and how it is found there |
| Item order, and a note and references per item | What a path names, and the base it is relative to |
| `MAX_ITEMS` and `MAX_REFERENCES` | Whether `comparison` is required |
|  | How each reference resolves: its state, address, and excerpt, and their budgets |
|  | When the record is stale, and what the reader shows |

**Guided reviews** (`guided_review.py`, `guided-review.js`) are the carrier built today.
The record is a `guided-review` fence in a pull request’s description; `comparison` is
required, its `merge_base` must be where Git leaves its `head`, and its head a commit; a
path is a changed file and a range lies in one hunk of its diff; excerpts are bounded by
`MAX_EXCERPT_BYTES` and `MAX_STEP_PATCH_BYTES`; the record is stale when the pull
request’s comparison moves.
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

- **Other review scenarios.** A guide to a commit, to a comparison of two branches or
  tags, or to a working tree’s uncommitted changes would pin `comparison` as a guided
  review does and resolve paths against that diff.
  A review of a set of documents would cite files without a change.
- **Collections in repository files** (mb-2sft): a YAML file in the served tree, read by
  a built-in `collection` plugin that takes over the format module, with Rows, Table,
  and Source views. Paths are relative to the file, and `comparison` is optional.
- **URL references** (mb-1rte): a `{url}` reference, `https` only and never fetched, so
  a guide can cite a design document or an issue.
- **A Markdown form** (mb-tzbp): a Markdown link list whose headings are groups and
  whose links are items, read into the same record.
- **Later uses** (mb-z9ox): object references, cards, and a Documents view.

#679’s research brief, `research-2026-11-22-annotated-collections-and-guided-pr.md`,
records the design and the owner’s decisions behind this split.
Moving the models out of the GitHub plugin is a module move: the contract ID already
names the `collection` plugin that will own it, so it does not change.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
