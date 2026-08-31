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

## Approach: The TypedDicts Are Already the Declaration

The envelopes are declared once, in the 31 `TypedDict`s that exist today, and they stay
that way. Nothing is rewritten and no second declaration is introduced.

`pydantic.TypeAdapter(GitRepoInfo).json_schema()` emits JSON Schema **directly from an
existing TypedDict** — verified against `metabrowser.git.wire` before this was written.
So the generator is a devtool that imports the wire modules, walks their TypedDicts, and
writes the result.

### Pydantic stays out of the runtime path

Pydantic is already in `[project.dependencies]`, because `diff/format.py` and
`plugin_loader/manifest.py` validate documents with it.
This work adds no runtime use of it at all: the import happens in
`devtools/build_api_schema.py`, at generation time, and what ships is the committed JSON
Schema.

That matters beyond dependency hygiene.
Tree and rollup responses sit on the measured load-time path, and `validate_tree_node`
is `assert`-based and, as `wire_models.py` says, “invoked from the matching tests”.
Nothing validates a response on the way out today.
Keeping the models out of the response path preserves that, and any future decision to
validate at runtime would need its own measurement rather than arriving as a side effect
of documenting the shapes.

### Why emit JSON Schema rather than stop at Python

The browser is a second implementation in another language.
`builtin_plugins/diff/diff-model.js` validates by hand — `require`, `asObject`,
`forbidExtras` — and its own comment refers to “the interchange rule the schema states,
and the Pydantic side’s” behaviour.
A Python-only declaration leaves that side describing the contract from memory, which is
the arrangement the two documented formats exist to avoid.
A committed schema also has client-side validator support, so a plugin author can check
an envelope without running Python.

| Piece | What it is | Ships? |
| --- | --- | --- |
| The existing `TypedDict`s | The declaration, unchanged | yes, as today |
| `devtools/build_api_schema.py` | Imports the wire modules, emits schema via `TypeAdapter` | no |
| `src/metabrowser/data/api-envelopes/` | The generated schemas, committed | yes |
| `GET /api/schema` | Serves them, so `metab . --api /api/schema` is the CLI view | yes |
| Drift check in `make lint` | Regenerates and compares | no |
| Golden validation | Each transcript’s envelope validated against its schema | no |

The last row is what ties the CLI and the API to one structure: a transcript already
holds a real response, so checking it against the generated schema proves the schema
describes what the server sends rather than what someone believed it sent.

### One choice the generator has to make

`TypeAdapter` does not set `additionalProperties` for a TypedDict, so the emitted schema
is permissive about unknown keys unless the generator says otherwise.
Strict is right for a *format* — it is what `forbidExtras` enforces for File Diff Format
— and permissive is right for a *reader*, which should tolerate a field a newer server
added. The generator should set it explicitly rather than inherit a default, and the
phase that adds it should say which and why.

### Why not SoftSchema

SoftSchema is for durable records — written now, read by a later release, which is why
the [repository cache](plan-2026-08-11-open-repo-from-git-url.md) adopts it for identity
and state. An envelope is produced and consumed by one artifact in one request, so the
problem it solves does not arise here.

## Phases

1. **Generator and drift check.** `devtools/build_api_schema.py` emits schema from the
   existing TypedDicts via `TypeAdapter`, the output is committed under
   `data/api-envelopes/`, and `make lint` regenerates and compares.
   The `additionalProperties` choice is made and recorded here.
   Nothing else changes, so the schemas are reviewable on their own.
2. **Golden validation.** Every existing transcript’s envelope checked against its
   schema. This is the phase that would expose a generator that describes the wrong
   thing, so it comes before anything depends on the output.
3. **The route and its golden.** `GET /api/schema`, its parity row, and a transcript,
   which the parity rule requires of a new route anyway.
4. **Retire the prose.** The map’s per-route descriptions point at the schema instead of
   restating a shape that can drift from it.

Phase 2 sits before phase 3 deliberately.
A schema nothing checks is a second description that can drift from the first, which is
the failure this plan exists to fix; validating the goldens first means the artifact is
known to match real responses before a route offers it to anyone.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
