# File Diff Format v1

**Format version:** v1\
**Status:** Implemented draft standard

The File Diff Format is a small, reusable format for describing a change set between two
file-tree snapshots: resolved identity, a manifest of file changes, and per-file
patches. It is deliberately tool-neutral — nothing in a document references Metabrowser
concepts — so command-line tools, libraries, services, and user interfaces can share one
validated model of “what changed.”
Metabrowser hosts the reference implementations and emits the format from
`metab --diff --format json`. Sources (a `.patch` file, git, a hosted provider, a
document’s edit history) produce this format; the renderer and the CLI consume it;
nothing downstream knows which source produced a document.
Design rationale lives in the
[general diff rendering plan](../../specs/active/plan-2026-08-17-general-diff-rendering.md);
this document is the normative contract.
[Diff sources, context, and anchoring](diff-sources-and-anchoring.md) maps where
documents come from and what a repository context adds.

## Authority and Implementations

[`file-diff.schema.json`](../../../../src/metabrowser/data/file-diff-format/file-diff.schema.json)
is the contract. `metabrowser.diff.format` implements it in Python (Pydantic,
`extra="forbid"`); `static/diff_model.js` implements it in the browser.
[`file-diff-conformance.json`](../../../../src/metabrowser/data/file-diff-format/file-diff-conformance.json)
binds every implementation: each validation case states whether the document is
acceptable, and both sides must agree exactly.
A change to the model changes the schema, the corpus, and both implementations in one
commit.

**Git is the reference semantics wherever this document is silent.** Change kinds follow
git’s status letters, similarity is git’s `-M`/`-C` percentage, modes are git’s file
modes, and a pure mode change is `modified` with differing modes because that is what
git reports.

## The Document

A `ChangeSetDocument` is:

| Field | Meaning |
| --- | --- |
| `schema`, `schema_version` | `"file-diff-v1"`, `1` |
| `resolved` | Frozen identity: source, endpoints, options, a self-describing `comparison_id` |
| `manifest` | One `FileChange` per changed path, plus totals and truncation |
| `patches` | `FilePatch` by file id — only the hydrated ones |

A document with an empty `patches` map is a valid, useful thing: it is a manifest-only
response, and each file’s `availability` states why its patch is absent.

### Snapshots

A `SnapshotRef` names one side: `commit`, `tree`, `index`, `worktree`, `patch`, or
`empty`, with an immutable `id` when the source has one and a `generation` token when
the content can move underneath the comparison (index, worktree).
`symbolic` is what the user asked for and is display-only, never identity.

### File changes

`kind` is one of `added`, `deleted`, `modified`, `renamed`, `copied`, `type_changed`,
`unmerged` — git’s A D M R C T U. Side requirements are structural, enforced by schema
and both implementations:

| kind | `old` | `new` | `similarity` |
| --- | --- | --- | --- |
| added | forbidden | required | — |
| deleted | required | forbidden | — |
| modified, type_changed, unmerged | required | required | — |
| renamed, copied | required | required | required |

Each side carries `path` (a UTF-8 display projection; `path_b64` holds the exact bytes
when they are not valid UTF-8), `entry_type` (`file`, `symlink`, `submodule`), git
`mode`, a `ContentRef`, and optional `size`. A symlink’s content is its target path; a
submodule’s content is its gitlink oid.

`availability` is a declared gap in applicability, never an empty body: `ready`,
`deferred`, `binary`, `too_large`, `timed_out`, `failed`, `stale`, `unsupported`.

### Patches

A `FilePatch` is hunks of line records.
Hunk headers carry git’s four numbers and optional section heading; every line is
`context`, `add`, or `del`, stores its text without the newline, and marks git’s
`\\ No newline at end of file` with `no_newline` on the affected line.
Line bytes that are not valid UTF-8 travel in `text_b64` beside the display projection.
Semantic invariants beyond the schema, checked by both implementations:

- Hunk `old_count` equals its `context` + `del` lines; `new_count` equals `context` +
  `add` lines.
- `manifest.cursor` is non-null exactly when `truncated` is true.
- A patch’s `file_id` matches a manifest entry.

## The Apply Oracle

“Fully modeled” is testable: applying a hydrated document to its base tree must
reproduce the target tree — entries, modes, entry types, and exact bytes, including a
missing final newline.
`metabrowser.diff.apply` implements this, and the corpus `apply_cases` each carry
`base`, `document`, and `target` trees.
A document that cannot be applied because content is missing must say so through
`availability`; `apply` raising `NotFullyHydrated` on a `ready` file is a producer bug.

## Relation to Existing Formats

Git’s extended unified format is the interchange surface: GitHub serves it for any pull
request, Mercurial documents plain unified diffs as lossy and adopts git’s extension,
and Jujutsu emits it.
This format wraps that surface rather than replacing it — parsed text becomes a
validated document; a document should print back to git-applyable text (the emitter is
tracked work). What the document adds over any text patch: snapshot identity and
anchoring, availability states instead of ambiguous absence, machine-validatable
structure, and apply semantics with an oracle.
The full survey, including agent edit formats and the ingest/emit compatibility matrix,
is in the
[file patch formats research](../../research/research-2026-08-19-file-patch-formats.md).

## Conformance Corpus

`file-diff-conformance.json` contains named validation cases (`expect: valid` or
`invalid`, with an `error` code naming the violated rule) and apply cases.
The corpus is the compatibility gate: add a case with every model change, and never
change an existing case’s expectation without a schema version bump.
Both the Python tests and the browser tests run the full corpus.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
