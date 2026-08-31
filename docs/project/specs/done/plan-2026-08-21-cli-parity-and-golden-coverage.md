# Feature: CLI Parity and Golden Coverage

**Date:** 2026-08-21

**Author:** Metabrowser maintainers

**Status:** Delivered.
All twelve beads under epic `mb-u29h` are closed.
The parity table stands at 22 covered and 2 exempt with no gaps, and
`devtools/check_parity.py` rejects a `gap` row outright.

## Overview

Every model the browser draws should be reachable from the command line, and every one
that is reachable should be pinned by a golden transcript.
This plan states that as a rule, adds the two CLI modes that make it achievable, and
puts a check in `make verify` so the rule holds itself up instead of relying on anyone
remembering it.

The principle is deliberately not “every UI feature has a CLI equivalent”.
Expansion motion, roving focus, and hover prefetch have no CLI shape and never will, and
a rule that pretended otherwise would be gamed within a month.
The honest version follows the layering this codebase already has — route, kind, model,
view — and draws the line where that architecture already draws it:

> **Parity principle.** Every route, kind, and model the browser consumes is reachable
> from `metab` without a browser or a listening port, and is covered by a golden
> transcript. Only the view layer — how a model is drawn, and how it responds to pointer
> and keyboard — is exempt, and its behaviour is pinned in `tests/dom/` instead.

Two clauses were added on 2026-08-28, when
[CLI-first delivery](../active/plan-2026-08-28-cli-first-delivery-map.md) applied this
principle to work that persists state rather than only serving it:

> **State clause.** Every state the system persists is reachable from `metab` as a
> normalized model and pinned by a golden transcript.
> Cache layout, entry identity, entry state, and reclamation outcomes are read through
> `/api/cache/*` like any other model, not through a bespoke inspection command.

> **Prefer a route to a CLI mode.** `--api` reaches every registered route by
> construction, so a surface exposed as a route is inspectable and golden-pinned for
> free. A surface exposed only as a CLI mode needs its own flag, its own normalizer path,
> and its own golden.

The state clause is what the original principle missed: the repository cache writes an
application home, layout, per-entry records, locks, staging, quarantine, and trash, and
none of that appears in a response envelope.
A `--api` transcript would have proved nothing about any of it.

## Goals

- State the parity principle where it is binding, and enforce it with a check rather
  than with prose
- Give every data route a CLI equivalent that goes through the real request stack, so a
  transcript proves the wire and not only the library beneath it
- Make “what would the browser do with this selection” answerable in one command: route,
  kind, views, and model summary
- Record parity per surface in the map document that already fails the build when it
  drifts, so a new route arrives with its CLI equivalent or does not arrive
- Normalize unstable fields once, in one place, so goldens are reviewable diffs rather
  than churn

## Non-Goals

- Rendering views in the terminal.
  A CLI equivalent produces the *model* a view draws, not an approximation of the
  drawing.
- Replacing `tests/dom/`. The view layer keeps its headless suites; this plan makes
  their scope explicit rather than shrinking it.
- Browser automation. If a behaviour genuinely needs a real browser, it belongs in the
  exemption list with its reason, not in a Playwright suite this repository does not
  have.
- Mutation. Every mode added here is read-only, like the rest of `metab`.

## Background

### What the layering already gives us

A selection travels four layers, described in
[Views, Models, and Routes](../../architecture/arch-views-models-routes.md):

```text
route  ──►  kind  ──►  model  ──►  view
```

Three of those four are data.
A route resolves an address, a kind classifies what was found, and a model is validated
data. None of them needs a screen.
Only the view does. That is why parity at the model layer is achievable in full, and why
the exemption for the view layer is principled rather than an excuse.

### Where we actually stand

Counting the data routes the browser consumes, and asking of each whether a `metab`
command produces the same model and whether a golden pins it:

| Surface | Drives | CLI today | Golden |
| --- | --- | --- | --- |
| `/api/tree` | Nav tree, filters, tallies | `--walk` (text/json/yaml, streaming, filters); `--check-api` | `cli-walk`, `cli-walk-filter` |
| diff model | Diff view, commit view | `--diff` (report/json/yaml, `--diff-patch`, `--diff-check`) | `cli-diff` |
| `/api/stream` | Live tree updates | `--walk --stream` emits the same records | `cli-walk` |
| `/api/recent` | The recency source | `--check-api` reports a count and nothing else | one line |
| `/api/file` | **Every selection**: kind, views, content window | none | none |
| `/api/rollup` | Folder Overview, Treemap | none | none |
| `/api/git/repo`, `refs`, `log`, `commit` | The whole Git panel | none | none |
| `folder/*`, `binary/chunk`, `agent-log/charts`, `structured/parsed` hooks | Four kinds’ models | none | none |
| `/api/kpress/render`, `/api/kpress/export` | Markdown Document view, export | none | none |
| `/api/activity` | Active-file badges | none | none |
| Browser routes (`/view`, `/commit`, `/compare`) | Address resolution | none | none |

Two of eleven surfaces have real parity.
Both of them — the tree and the diff — are where this project has recently done its
hardest debugging, which is the argument for the rule rather than a coincidence.

The gap that stands out is `/api/file`. It carries the kind and the view list for every
selection, so the tabs a reader sees are decided there, and nothing outside a browser
currently proves that `README.md` opens as `markdown` with Document and Source.

### Library parity is not wire parity

`--walk` calls `_build_inventory_tree` directly; `--diff` calls `metabrowser.diff`
directly. Both prove the model and neither touches the route.
Only `--check-api` drives the ASGI stack, which is why a route can accept a parameter
the library never sees, or drop an envelope key, with every existing golden still green.

That is not hypothetical.
The nav filter shipped as query parameters on `/api/tree` whose parsing, clamping, and
envelope shape no transcript covered until a golden was written for them.

So parity has two levels, and the map should say which one a surface has:

- **Model parity** — a command produces the validated data.
  Fast, readable, the right level for reviewing a behavioural diff.
- **Wire parity** — a command produces it *through the route*, proving parameters,
  envelope keys, status codes, and bounds.

A surface wants both.
Model parity alone leaves the route untested; wire parity alone produces envelopes too
noisy to review as a diff.

### Why golden transcripts rather than more integration tests

`tbd guidelines golden-testing-guidelines` argues the case: capture a broad, stable
slice of what a system does, keep it in the repository, and read the diffs.
This codebase is already set up for it — `tryscript` runs the transcripts,
`golden_fixup.py` restores elision patterns, and the fixtures pin mtimes so sizes and
timestamps are deterministic.

What that guidance asks for and we do not yet have is a *session schema*: a stated list
of which fields are stable and which are normalized away.
Today each golden solves it locally, with `touch -t` in one fixture and a regex in
another. One normalizer, stated once, is what lets a general-purpose `--api` mode be
diffable at all.

## Design

### Approach

Three moves, in dependency order:

1. **`--api <route>`** — issue any GET through the real in-process ASGI stack and print
   the normalized envelope.
   One mode, complete by construction for every route that exists now and every route
   added later. This is the wire-parity backbone.
2. **`--show <path>`** — the four layers for one selection, as a readable report: the
   route it resolves to, the kind it classifies as, the views it offers, and a summary
   of its model. This is the single most valuable missing command, and it is what a
   golden for the kind and view registry looks like.
3. **A parity column and a check** — record each surface’s CLI equivalent in the map
   document, and fail the build when a registered route, kind, or view has no entry, no
   golden, or an entry naming a command that does not exist.

Readable reports beyond `--show` are added only where a raw envelope is too noisy to
review as a diff. `--walk` and `--diff` already are those reports for their surfaces.

### Components

**`metabrowser/cli/api_cli.py`** — the `--api` mode.
Reuses the `_InProcessClient` already in `check_api.py`, which is lifted to a shared
module since two callers now need it.
Takes a route with its query string, waits for the index when the route needs it, and
prints JSON or YAML.

```bash
metab . --api '/api/file?path=README.md'
metab . --api '/api/rollup?path=src&depth=2'
metab . --api '/api/git/log?limit=5'
metab . --api '/api/plugin/structured/parsed?path=package.json'
```

**`metabrowser/cli/show_cli.py`** — the `--show` mode, one selection through the four
layers:

```console
$ metab . --show README.md
show: README.md
route: /view/README.md
kind: markdown
views: rendered (default), source
model: file envelope; size=13386 lines=284 truncated=false
```

**`metabrowser/normalize.py`** — the session schema the golden guideline asks for.
One table naming every unstable field and what replaces it: absolute paths under the
served root become `[ROOT]`, mtimes become `[MTIME]` unless the fixture pinned them, git
revisions become `[REV]`, durations and byte counts that vary by platform become
`[ELAPSED]`. Applied by `--api` and `--show`; `golden_fixup.py` keeps only the
sandbox-path rewriting that belongs to tryscript rather than to us.

**`devtools/check_parity.py`** — the enforcement, run by `make lint` and
`make lint-check` beside `public_hygiene` and `check_supply_chain`. It:

1. Enumerates registered routes from `server.py`, `git/routes.py`, and every manifest’s
   `[[data_hook]]`; enumerates kinds and views from the manifests.
2. Reads the parity table from the map document.
3. Fails when a registered surface has no row; when a row names a `metab` invocation
   that the CLI does not accept; when a row’s command appears in no golden transcript;
   or when a row claims an exemption without a reason.

**The map document** gains a parity column, and its existing check
(`tests/test_views_models_routes.py`) already fails the build when the tables drift — so
parity lands in the one place that cannot silently rot.

### The exemption list

Exemptions are enumerated with reasons, never blanket.
A surface is exempt only when it has no model to produce:

| Exempt | Reason | Where it is tested instead |
| --- | --- | --- |
| `/static/*`, `/plugin-static/*`, `/kpress-static/*` | Asset serving; the bytes are the file | `tests/test_browser_assets.py` |
| `/_debug/tasks` | Diagnostic, not a browser surface | not tested |
| View drawing: disclosure motion, roving focus and ARIA, selection painting, tooltips, hover prefetch | No model; these are the drawing itself | `tests/dom/` |

The third row is the honest boundary.
It is a list, not a category, so adding to it is a visible decision rather than a shrug.

### API Changes

No changes to `/api/*` or to `window.metabrowser`. Two new CLI modes, one new devtools
check, one new column in an architecture document, and a rule in `AGENTS.md` that points
at the check rather than restating it:

> Every route, kind, and model the browser consumes has a `metab` equivalent and a
> golden transcript. `devtools/check_parity.py` enforces it and names what is missing;
> the exemption list and its reasons are in
> `docs/project/architecture/arch-views-models-routes.md`.

## Implementation Plan

### Phase 1: The mechanism and the rule

- [ ] Lift `_InProcessClient` out of `check_api.py` into a shared CLI module
- [ ] Add `metabrowser/normalize.py` with the stable/unstable field table, and a test
  that every field it names is either normalized or documented as stable
- [ ] Add `--api <route>` with `--format json|yaml`, wired through the ASGI stack
- [ ] Add `--show <path>` reporting route, kind, views, and model summary
- [ ] Goldens: `cli-api.tryscript.md` and `cli-show.tryscript.md` over a fixture that
  covers one file of each built-in kind
- [ ] Add the parity column to the map document, with today’s gaps entered as explicit
  `gap` rows so the table is honest on the first day
- [ ] Add `devtools/check_parity.py`; wire it into `make lint` and `make lint-check`;
  allow `gap` rows for now and report their count
- [ ] Add the rule to `AGENTS.md` and the reasoning to `docs/development.md`
- [ ] Regenerate `cli-surface.tryscript.md` for the two new modes

### Phase 2: Close the gaps

- [ ] Goldens for `/api/file` across every built-in kind, proving the kind and the view
  list each one offers
- [ ] Goldens for `/api/rollup`, including a truncated subtree and a pending one
- [ ] Goldens for `/api/git/repo`, `refs`, `log`, and `commit` against a fixture
  repository with pinned revisions
- [ ] Goldens for the `folder/*`, `binary/chunk`, `agent-log/charts`, and
  `structured/parsed` hooks
- [ ] Golden for `/api/recent` that reports rows rather than only a count
- [ ] Golden for `/api/activity`
- [ ] Extend `--show` to resolve `/commit/<rev>` and container inner paths, giving the
  URL grammar its first end-to-end coverage
- [ ] Flip every `gap` row to a command and a golden; make `check_parity.py` reject
  `gap` rows entirely

## Testing Strategy

The plan is itself a testing change, so what matters is that the new machinery is not
trusted on its word:

- `check_parity.py` gets tests that feed it a map with a missing row, a row naming a
  command the CLI does not accept, and a row whose command appears in no golden — each
  must fail with the surface named.
- The normalizer gets a round-trip test: a payload carrying every unstable field
  normalizes to a value containing none of them.
- Every new golden runs under `make test` with the rest, and CI is the gate.
- Determinism is verified by running the new goldens twice in one CI job; a transcript
  that differs between runs is a normalizer gap, not a flake to retry.

## Rollout Plan

Both phases land on a branch and merge together or not at all — a parity check that
permits `gap` rows forever is a check nobody reads.
Phase 1 alone is still shippable if Phase 2 has to slip, because it makes the debt
visible and machine-counted rather than implicit.

No user-facing behaviour changes.
`CHANGELOG.md` records the two new CLI modes, since a `metab` user can observe them.

## Open Questions

**Closed 2026-08-28: `--api` accepts POST bodies.** `InProcessClient` carries `post`
from the day it is lifted, and `--data <file>` supplies the body.

The premise needs one correction the first draft got wrong: `/api/kpress/render` is
registered `GET` *and* `POST` and renders on either, so only `/api/kpress/export` was
ever POST-only.
The cost is still a few lines at lift time, and export would otherwise be
permanently exempt for a reason the exemption list could not state honestly.
Both branches of `render` are pinned, because the POST path reaches different handler
code than the query form.

Still open:

- Should `--show` follow a container into its children, or is that `--api`’s job through
  the `children` hook?
  Following would make the container contract golden-testable in one command, at the
  cost of a mode that recurses.
- Does the parity table belong in the map document or in its own file?
  The map document already has a check and a reader; a separate file would be longer but
  would not make someone adding a route read the parity rule.

## References

- [Views, Models, and Routes](../../architecture/arch-views-models-routes.md) — the four
  layers this principle is drawn on, and the home of the parity table
- `tbd guidelines golden-testing-guidelines` — sessions, stable fields, and why
  transcripts beat integration suites for systems like this
- `tbd guidelines general-testing-rules` — the minimal-tests-maximum-coverage rule this
  serves
- [CLI-first delivery](../active/plan-2026-08-28-cli-first-delivery-map.md) — the state
  clause, the route-over-mode rule, and the file-level map of what this principle is
  used to build
- [Development](../../../development.md) — where the reasoning behind the rule lives
- [tryscript](https://github.com/jlevy/tryscript) — the transcript runner

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
