# Plan: A Machine-Readable Contract for the API Envelopes

**Date:** 2026-08-30

**Author:** Joshua Levy (with LLM assistance)

**Status:** Draft. The gating decision is closed: the envelopes stay internal.

## The Gap

`/api/routes` reports which routes exist.
The parity table reports which are covered by a transcript.
Neither reports what a route *answers*, and the map document describes each envelope in
prose — “the file or folder envelope: kind, views, content window” — that nothing checks
against the response.

The shapes do exist in code: 31 `TypedDict` declarations across `wire_models.py` and
`git/wire.py`, with 12 `validate_*` functions.
That is a real contract.
It is invisible outside Python, unversioned, and unreachable from the CLI that exists to
make every model inspectable.

## The Position This Runs Into

[Views, Models, and Routes](../../architecture/arch-views-models-routes.md) states a
deliberate boundary:

> Everything else travels as an envelope on `/api/*`, versioned with the shell and the
> built-in plugins as one artifact — an internal contract, not a standard.

`AGENTS.md` says the same.
Two formats are exceptions and are built the other way: File Diff Format and File Rollup
Format each have a JSON Schema in `src/metabrowser/data/`, a conformance corpus, and an
architecture document, and both are explicitly tool-neutral.

So the question is not “should the envelopes be documented” but **which of those two
things they are**, and the answer decides the shape of the work.

## The Decision

**Publishing an OpenAPI document makes a promise the project has declined to make.**
OpenAPI is the interface description for an API other people build against.
The moment one exists, `/api/*` reads as a supported surface, and the freedom to change
an envelope in the same commit as the shell that reads it — which
[Compatibility and Legacy Code](../../../development.md#compatibility-and-legacy-code)
depends on — is what pays for it.

**The gap is real anyway**, because “internal” is a statement about who may depend on
it, not a licence for it to be undescribed.
A contract the CLI cannot show is one nobody can review.

Recommendation: **describe, do not publish.** Generate the schema from the TypedDicts
that already define these shapes, serve it from a route so `--api` reaches it like
anything else, and validate the goldens against it.
Version it with the artifact and say in the document itself that it describes an
internal contract, so a reader knows what it is before depending on it.

## Approach: Generate Where a Declaration Exists, Author Where It Does Not

An earlier draft of this section claimed the 31 existing `TypedDict`s were already the
declaration and nothing needed rewriting.
That is true of one family and false of the rest, and the difference is the actual shape
of this work.

| Surface | Declaration today | What generation yields |
| --- | --- | --- |
| `/api/git/*` | 13 `TypedDict`s, all `total=True`, six validators | A real schema. `TypeAdapter(GitRepoInfo).json_schema()` verified. |
| `/api/tree`, `/api/rollup` | 18 `TypedDict`s, but `DirNode` is `total=False` with `children: list[Any]` | **Nearly empty.** Verified: no `required`, and `children` as `{"items": {}}`. |
| `/api/file` | None. `FileNode` is a tree row, not the response envelope with `kind`, `views`, and the content window | Nothing |
| Plugin data hooks | None | Nothing |

So the generator is the cheap part and the declarations are the work.

### The loose ones are loose on purpose

`DirNode` uses `total=False` for keys whose presence varies, and `children: list[Any]`
because a child is a directory or a file and the wire contract does not discriminate.
That is a deliberate permissiveness, not an oversight, and `wire_models.py` says so.

Tightening it is therefore **a change to the contract**, not a detail of how a schema is
emitted.
It may well be right — a reader benefits from knowing a directory always carries
`total_files`, even as `null` — but it needs its own justification and its own check
that no producer violates the tightened shape.
It cannot arrive as a side effect of wanting better documentation.

### Pydantic stays out of the runtime path

Pydantic is already in `[project.dependencies]`, because `diff/format.py` and
`plugin_loader/manifest.py` validate documents with it.
This work adds no runtime use: the import is in `devtools/build_api_schema.py`, at
generation time, and what ships is the committed JSON Schema.

That matters. Tree and rollup responses sit on the measured load-time path, and
`validate_tree_node` is `assert`-based and, as `wire_models.py` says, “invoked from the
matching tests”. Nothing validates a response on the way out today, and keeping the
models out of the response path preserves that.

### Why emit JSON Schema rather than stop at Python

The browser is a second implementation in another language.
`builtin_plugins/diff/diff-model.js` validates by hand — `require`, `asObject`,
`forbidExtras` — and its comment refers to “the interchange rule the schema states”.
A Python-only declaration leaves that side describing the contract from memory, which is
what the two documented formats exist to avoid.
A committed schema also has client-side validator support, so a plugin author can check
an envelope without running Python.

### Two strictness choices, not one

`TypeAdapter` does not set `additionalProperties`, and the right value differs by
purpose:

- **The published schema** should be permissive about unknown keys, so a reader written
  against today’s build tolerates a field a newer server adds.
- **Golden validation** should be strict, or it proves nothing: a permissive schema
  accepts any envelope, and the phase that validates transcripts against it would pass
  by construction.

The generator emits both, or one with a documented strict overlay.
Deciding this as a single global flag is how that phase becomes vacuous without anyone
noticing.

### Why not SoftSchema

SoftSchema is for durable records — written now, read by a later release, which is why
the [repository cache](plan-2026-08-11-open-repo-from-git-url.md) adopts it for identity
and state. An envelope is produced and consumed by one artifact in one request.

## Phases

1. **Generator and drift check, scoped to `/api/git/*`.** `devtools/build_api_schema.py`
   emits from the 13 Git `TypedDict`s via `TypeAdapter`, the output is committed under
   `data/api-envelopes/`, and `make lint` regenerates and compares.
   Both strictness variants are produced here, and the choice is recorded.
   Git is first because its declarations are real: the generator is proved on a family
   where nothing has to be authored.
2. **Golden validation for the Git transcripts.** `cli-api-git.tryscript.md` validated
   against the strict variant.
   The transcripts are normalized, not raw responses — placeholders change types and
   elisions sit inside JSON strings — so this phase must state how it validates: most
   likely by capturing the pre-normalization envelope in the harness rather than by
   parsing the transcript back.
   If that cannot be made to work, the plan stops here and is reconsidered, because
   everything after it depends on the schema being checkable against reality.
3. **The route and its golden.** `GET /api/schema`, its parity row, and a transcript.
4. **Author declarations for `/api/file` and the plugin hooks.** This is the phase the
   earlier draft hid: these envelopes have no `TypedDict` at all, and writing them is
   ordinary design work with a real cost.
5. **Decide whether to tighten the tree and rollup declarations**, as a contract change
   argued on its own merits, with a check that no producer violates the tightened shape.
   Not a documentation task.
6. **Retire the prose**, per surface, only where a schema now covers it.

Phases 4 and 5 are where the work actually is, and they are deliberately last: the
generator, the validation mechanism, and the route should all be proved on the family
that needs none of it before anyone spends effort authoring the ones that do.

If phase 2 fails, phases 4 and 5 should not be started.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
