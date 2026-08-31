# Plan: A Machine-Readable Contract for the API Envelopes

**Date:** 2026-08-30

**Author:** Joshua Levy (with LLM assistance)

**Status:** Draft — one decision open, stated below

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

## Approach: Derive, Never Duplicate

The TypedDicts are the source of truth and stay that way.
A second hand-written schema would be a copy that drifts, which is the failure the two
existing formats avoid by generating their conformance corpus rather than typing it.

| Piece | What it is |
| --- | --- |
| `devtools/build_api_schema.py` | Walks the wire modules and emits JSON Schema per envelope |
| `src/metabrowser/data/api-envelopes/` | The generated schemas, committed, beside the two existing format directories |
| `GET /api/schema` | Serves them, so `metab . --api /api/schema` is the CLI view |
| Drift check in `make lint` | Regenerates and compares, the way compiled-schema drift is checked for the cache contracts |
| Golden validation | Each transcript’s envelope validates against its schema |

That last row is what ties the CLI and the API to one structure, which is the point: a
golden already captures a real response, so validating it against the generated schema
proves the schema describes what the server actually sends — not what someone believed
it sent.

### Why not SoftSchema here

SoftSchema is for durable records — data written now and read by a later release, which
is why the [repository cache](plan-2026-08-11-open-repo-from-git-url.md) adopts it for
identity and state. An API envelope is not durable: it is produced and consumed by one
artifact in one request.
JSON Schema describes it adequately and adds no dependency, and the two formats this
repository already documents use exactly that.

If SoftSchema lands for the cache, the question can be revisited with the dependency
already paid for.

## Open Decision

**Does `/api/*` stay an internal contract?** The recommendation above assumes yes, and
everything follows from it: no OpenAPI document, no compatibility promise, a schema that
describes rather than specifies.

If the answer is no — if `/api/*` should become a surface others may build against —
then this plan is the wrong one.
That version needs versioned routes, a deprecation policy, and an OpenAPI document as
the published artifact, and it should be planned as that rather than reached by adding a
schema file and discovering the promise later.

## Phases

1. **Generator and drift check.** `build_api_schema.py`, the committed output, and the
   `make lint` check. No route yet; the schemas are reviewable on their own.
2. **The route and its golden.** `GET /api/schema`, its parity row, and a transcript —
   which the parity rule requires anyway.
3. **Golden validation.** Each existing transcript’s envelope checked against its
   schema, so the description is bound to observed responses.
4. **Retire the prose.** The map’s per-route descriptions point at the schema instead of
   restating a shape that can drift from it.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
