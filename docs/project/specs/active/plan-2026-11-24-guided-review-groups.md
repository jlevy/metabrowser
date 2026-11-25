# Feature: Guided Review Groups, Rationale, Rendered Documents, and Stack Rollups

**Date:** 2026-11-24 (last updated 2026-11-24)

**Author:** Joshua Levy (github.com/jlevy) with LLM assistance

**Status:** Phases 1 and 2 in progress under epic `mb-bxff`; phase 3 is designed here
and not yet built.

## Overview

A guided review
([Reviewing Pull Requests](../../../reviewing-pull-requests.md#guided-review)) is a flat
list of steps today.
The skill already asks for steps organized by concern (keystone decisions, key
documents, each area of change, ambiguity, testing, future work), but the page shows
them as one numbered list, so the agenda’s shape is only in the titles.
This plan adds four things:

1. **Groups.** An optional, one-level grouping of steps, so a guide reads as the agenda
   the skill recommends: Decisions, Documents, Changes, Open questions, Testing, Future
   work.
2. **Rationale.** A concise step beside the key decisions that says why each was made:
   the alternative rejected, the constraint or measurement that decided it.
3. **Rendered documents.** A step that cites a whole Markdown, YAML, or JSON file draws
   it as the Changes and Docs tabs do, through the diff view’s rendered layer and its
   chooser, instead of as source hunks only.
4. **Stack rollups.** A design for walking a whole stack’s guides as one, which this
   plan does not build but which phases 1 and 2 shape their data for.

## Goals

- A guide can group its steps, and a guide without groups reads as it does today.
- The skill recommends the groups and the rationale step, and stays concise: a group
  never needs a note, and a step never repeats the description.
- A document a step cites whole is readable rendered, with the same Full, Concise, and
  Source choices the diff view offers, from the same code.
- Nothing in phases 1 and 2 has to be undone to build a stack rollup.

## Non-Goals

- Groups inside groups in a written guide.
  The record allows one level; only a derived rollup (phase 3) nests.
- Rendering a *range* of a document.
  Projection blocks carry no source lines yet, so a ranged reference keeps its source
  hunk (`mb-8viy`).
- Building the rollup (`mb-ri96`).

## Phase 1: Groups and Rationale (`mb-enj3`, `mb-szxu`)

### The Record

An entry of `items` is either a **step**, as today (`title`, `note`, `references`), or a
**group**: a `title`, an optional `note`, and its own `items`, which are steps only.

```yaml
collection:
  comparison: {merge_base: "<id>", head: "<id>"}
  items:
    - title: Decisions
      items:
        - title: "Keystone: one route answers every step"
          note: Check that the page asks nothing the route does not answer.
          references:
            - {path: src/route.py, side: new, start_line: 40, end_line: 58}
        - title: "Rationale: why not one answer for the whole guide"
          note: |-
            A whole-guide answer hydrated every excerpt at once: 4.1 s on a 30-step guide.
            Per step, the first answer took 90 ms.
          references:
            - {path: src/route.py, side: new, start_line: 12, end_line: 30}
    - title: Changes
      items:
        - title: The route
          note: …
          references: [{path: src/route.py}]
```

- A group and a step are told apart by their fields: a group has `items` and no
  `references`, a step `references` and no `items`. The models enforce it (a tagged
  union on whether an entry has `items`), and the compiled schema states it as an `if`
  on `items`, whose `then` is a group and `else` a step.
  The plan first said a `oneOf`, which is what pydantic writes for the union, but
  jsonschema places a `oneOf`’s refusal at the entry alone, so a range starting at 0
  would have been refused at `items.0` rather than at `items.0.references.0.start_line`;
  the `if` keeps every refusal’s place as precise as before groups.
- Groups and ungrouped steps may mix at the top level, in any order.
- An empty group is refused, as an empty `items` is today.
- `MAX_ITEMS` bounds every entry, steps and groups together, since its measured cost is
  the parse per entry, so a group holds at most `MAX_ITEMS - 1` steps.
  No one list’s bound states the total, so the models enforce it, and the shape walk
  that runs before the schema (`_outside_shape`) refuses it in words of its own, since
  the schema admits such a block and a refusal in its name would not say what is wrong.
- **It stays `Collection/v1`.** Every record v1 accepts today is still accepted and
  means the same. The widened entry type is read by one consumer, the server and page
  that ship together. Guides already published in pull-request descriptions are the
  released data, and none of them changes meaning.
  [Contracts](plan-2026-11-14-object-data-model-and-views.md#contracts) counts removal,
  renaming, and retyping as breaks; widening an entry to a union with a new shape is
  none of those. The cost is in the other direction: a release before groups refuses a
  grouped guide at `items.N`, so its reader needs this release or later.
  A `Collection/v2` would not help that reader, whose release refuses v2 as well, so the
  guide stays v1. A reviewer should confirm this reading (it is in the guide’s Open
  questions).
- **Groups are optional, and that is the compatibility.** A guide without groups is the
  record shape v1 had: it parses the same, the route answers it as before apart from the
  added `outline` and `group`, and the page draws it as before.
  There is no version switch and no legacy path.

### Steps Stay Flat

Steps are numbered 1 to `step_count` in reading order, through groups, so the route’s
`step=<k>`, the page’s step addresses, the stale check’s `changed_steps`, and
`createGuideNavigation` keep their meaning.
A group is not a step: the reader never lands on a group alone.

### The Route’s Answer

Every answer that has steps gains an **`outline`**: a tree of nodes in reading order.

```json
"outline": [
  {"kind": "group", "title": "Decisions", "note": null, "children": [
    {"kind": "step", "step": 1, "title": "Keystone: one route answers every step"},
    {"kind": "step", "step": 2, "title": "Rationale: why not one answer for the whole guide"}
  ]},
  {"kind": "group", "title": "Changes", "note": null, "children": [
    {"kind": "step", "step": 3, "title": "The route"}
  ]}
]
```

- `titles` stays, the flat list the step pager reads.
- A step’s answer names its `group`, the index of its group in `outline`, or null.
- The tree is the groundwork for phase 3: a rollup is the same tree one level deeper.

### The Page

- The step list shows each group as a heading above its steps, with no number.
  Steps keep their flat numbers, so “Step 5 of 12” still matches the list.
- A step’s card shows its group’s title before its place (“Decisions · Step 2 of 12”).
- A group’s note, when it has one, shows above the card of the group’s first step, not
  in the step list, which stays a list of names.
- A guide without groups draws exactly as before.

### The Skill’s Recommendation

`skills/metabrowser/SKILL.md` recommends these groups, in this order, for a guide of
more than about six steps.
A guide of about six steps or fewer stays flat, even when it covers several concerns,
since its step titles name them, and a small change merges or omits groups.
The skill shows both a flat skeleton and a grouped one:

| Group | Steps |
| --- | --- |
| Decisions | Key decisions: the few choices everything follows from, each in a line or two. Rationale: one step, with a line or two for each key decision, the alternative rejected and the constraint, measurement, or requirement that decided it; split only when it would run long. |
| Documents | One step per spec, plan, architecture document, or guide added or rewritten, cited whole. |
| Changes | One step per area, in dependency order, saying what to verify. |
| Open questions | Ambiguity and uncertainty a person should decide or check. |
| Testing | Automated, agent-checked, and needs-a-person, each its own step or line, never merged. |
| Future work | Deferred work with its tracker IDs, and what needs more planning. |

**Rationale stays concise.** The rationale step states each key decision’s *why* in a
line or two: what else was considered, and the fact that decided it (a measurement, a
constraint, a requirement, a precedent).
It does not retell the design, and it cites the lines or the document where the decision
is recorded at length.
A decision with an obvious reason needs no rationale line.

## Phase 2: Rendered Documents in Steps (`mb-qgz1`)

### What Changes

A reference that names a whole file (a path alone) of a format the diff view renders
(`renderedFormat` in `diff/diff-markdown.js`: Markdown, YAML, JSON) draws that file as
the Changes tab draws it: the file’s bar, the rendered layer, and its chooser.
Every other reference draws as today: a range keeps its source hunk, and a whole file of
another format its patch.

### Reuse, Not a Copy

The step mounts the diff plugin’s own file view for that one file, from the comparison
route’s one-file answer (`file=<id>`, which deferred files already use).
That brings the chooser, the projection route, sanitizing, place keeping, and, once
`mb-qn7e` lands, the Full | Concise | Source modes and windowed drawing, with no code of
the guide’s own. The diff plugin exports one entry point for it beside `mountFilePatch`,
and the guide loads it through the plugin module it already loads.

**Coordination with `mb-qn7e`.** That work rewrites the chooser and the rendered layer
inside `diff-markdown.js` and `diff-view.js`; this phase touches neither file’s
internals, only the diff plugin’s exported entry point in `diff/index.js`, so the two
merge without conflict in the code that matters, and whichever lands second takes the
other’s behavior for free.
Until `mb-qn7e` lands, a document shows **Rendered | Source**. After it, a step’s
document opens as the Docs tab opens one: Full when it is small enough, Concise
otherwise.

### Bounds

The rendered answer keeps its own route’s bounds (`_MARKDOWN_PAIR_MAX_BYTES` and
`_MAX_HTML_BYTES` in `pull_rendered_diff.py`), and a refused file keeps its chooser with
Rendered unavailable, saying why, as in Changes.
The step’s source excerpt budgets (`MAX_STEP_PATCH_BYTES`) still bound what the guided
route hydrates for that reference.

## Phase 3: Stack Rollups (`mb-ri96`, Designed Only)

A stack’s layers each carry their own guide, pinned to their own comparison.
A reviewer of the whole stack wants to walk them as one.

### Approaches Considered

| Approach | How | For | Against |
| --- | --- | --- | --- |
| A. One hand-written guide on the top layer | The top layer’s guide cites the stack’s cumulative diff | Works today | Duplicates every layer’s guide and drifts from them; references lose which layer changed a line; `MAX_ITEMS` caps it |
| B. Nested by reference | A record’s entry includes another pull request’s guide, as `{include: {pull: 765}}` | One source of truth per layer | A new reference kind, cross-PR reads inside one record, and an author must keep the list of layers current by hand |
| C. A derived rollup | The route builds the rollup from the stack the plugin already knows, one group per layer, each the layer’s own outline | No new record, no drift, each layer stale or current on its own pins | Needs a stack-level preface for decisions that span layers |

**Recommended: C, with an optional preface.** The route answers a rollup for a stack’s
top pull request: its `outline` has one node per layer, in stack order, whose children
are that layer’s own outline (its groups and steps), and steps are numbered flat across
the whole rollup. Each step resolves its references against its own layer’s comparison
and is stale against its own layer’s pins.
Decisions that span the stack go in an optional **Stack** group in the bottom layer’s
guide, which the rollup shows first.
B stays possible later as an additive field if a rollup needs layers the stack does not
list.

### What Phases 1 and 2 Lay Down

- **The outline is a tree**, so a rollup is one more level of the same nodes.
- **Steps are numbered flat** and navigation reads only step numbers, so the pager and
  `createGuideNavigation` work over a rollup unchanged.
- **A step answer carries what resolves it**: its references and their states, so a
  rollup’s step can come from another layer’s route answer.
  Phase 3 adds the step’s pull request number to each node.
- **Staleness is per guide** (`stale` on each answer), so per layer in a rollup.
- **Groups have no comparison of their own today.** If B is ever needed, a group gains
  an optional `comparison`, which is additive.

### Open Questions for Phase 3

- Where the rollup lives: the top layer’s Guided Review tab with a stack toggle, or a
  page of its own for the stack.
- Whether a layer without a guide shows as one step that cites its whole diff, or is
  skipped with a note.
- How the rollup’s step addresses read in a URL (a flat number, or a layer and a step).

## Implementation Plan

1. Phase 1, one layer: the format’s group model and compiled schema, the route’s
   `outline` and per-step `group`, the page’s grouped outline, the skill’s groups and
   rationale step, the format reference, goldens and tests.
2. Phase 2, stacked on phase 1: the diff plugin’s one-file entry point, the guide’s
   rendered references, tests, and the architecture and reviewing documents.
3. Phase 3: build the rollup after both land and `mb-qn7e` has settled the chooser.

## Testing Strategy

- Route goldens for a grouped guide, a mixed guide, a longer guide of two groups of two
  steps (which tells numbering through the groups from numbering by entry), a refused
  empty group, a refused nested group, a guide refused past `MAX_ITEMS`, and the
  `outline` of an ungrouped guide
  (`tests/golden/cli-github-guided-review.tryscript.md`). The stand-in’s guides stay
  ungrouped, so every golden written before groups changes only by the added `outline`
  and `group`; the grouped and mixed guides are written over a cached description by the
  fixture’s `--describe`, keeping the pins of the guide it replaces.
- A real ungrouped guide, four steps of one this repository published (#785), kept byte
  for byte in `tests/fixtures/guided-review/`, parses unchanged and answers each step
  `ready` with a flat outline.
- Model tests for the group and step shapes, the outline’s numbering through groups of
  two steps, and the schema drift check (`tests/test_guided_review.py`).
- A browserless session of the grouped outline and its navigation against the production
  `guided-review.js`, which checks that each group’s list is named by its heading, and a
  Chrome check of the grouped list’s layout.
- The skill’s command checks (`tests/test_skill_commands.py`) on both skeletons: the
  flat one has no group, and the grouped one has one.
- For phase 2, a Chrome check that a whole-file Markdown reference draws rendered with
  its chooser, and that a ranged one draws source.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
