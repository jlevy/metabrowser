# Feature: One File-Type Source of Truth

**Date:** 2026-08-21

**Author:** Metabrowser maintainers

**Status:** Implemented

## Overview

What a file *is* — its family, its label, its color, the extensions and basenames that
identify it — should be declared once and read from everywhere.
Most of that already lives in `recommended-file-types.toml`. The part a reader notices
first does not: color is decided in the browser by hashing a family name into a pool of
twelve slots, for 56 families.

This plan puts color in the registry beside everything else, takes its *hue* from
GitHub’s language colors so the vocabulary is one a reader already knows, and derives
lightness and chroma from one stated rule so the whole set looks like a set.

The aim is a mnemonic match, not a copy.
JavaScript should read as GitHub yellow and Go as GitHub cyan; whether our yellow is
exactly `#f1e05a` matters much less than whether the palette is beautiful and coherent
on both themes.

## Goals

- One document a maintainer reads end to end to see every file-type decision
- Hue borrowed from `github-linguist/linguist` wherever a reader would expect it, and
  the correspondence recorded in the data rather than in someone’s memory
- Lightness and chroma from a stated rule, applied to every family alike, so the set
  reads as one palette instead of 56 independent choices
- A stable color per family that does not change between directories
- “No two families look alike” as a check, not something noticed in a screenshot
- Colors in oklch throughout, with gamut handling stated rather than implied

## Non-Goals

- **Moving the source off TOML.** An earlier draft proposed YAML to mirror linguist’s
  own `languages.yml`. TOML stays: it is what the loader, schemas, generator,
  conformance corpus, and format documentation already speak, it is first-class in the
  Rust tooling this project may move to, and the real gap was never the file format — it
  was that color was not in the file at all.
- Copying linguist’s hex values.
  See Design; several are unusable as-is, and fidelity is not the point.
- Vendoring linguist or depending on it at runtime.
  The correspondence is recorded here and checked against a clone.
- Language detection beyond the registry’s current inputs.
  Extensions, basenames, and shebangs stay; linguist’s heuristics and classifier are not
  in scope.
- Changing File Rollup Format v0.1. The registry is versioned independently.

## Background

### Where color actually comes from

`builtin_plugins/folder/category_palette.js` hashes the family key with FNV-1a, takes
the remainder against a slot count, and probes linearly for a free slot.
`DISTRIBUTION_PALETTE_SLOTS` is 12. The registry has 56 families.

Three consequences, all measured on this repository’s root:

- **Collisions.** The probe exhausts the pool and falls back to `start + 1` without
  reserving, so two live families share a color.
  `family:json` and `family:audio` both painted `oklch(0.604 0.145 151.1)`;
  `family:python` and `family:log-files` both painted `oklch(0.575 0.1601 276.22)`.
- **Near-collisions.** Adjacent slots sit close in hue: `css` at 137 against `json` at
  151, `markdown` at 38.6 against `yaml` at 54.1.
- **Instability.** The slot depends on which other families are present, so a family is
  a different color in a different directory.
  A reader cannot learn that yellow means JavaScript, because it does not.

### What linguist offers, converted to oklch

688 languages upstream carry a `color:`. **38 of our 56 families** map to one — though
only 35 end up with a usable hue, because three of those upstream colors are greys.
The other 18 are not languages — `plain-text`, `pdf`, `word`, `rich-text`,
`open-document`, `epub`, `parquet`, `arrow`, `avro`, `orc`, `protocol-buffers`,
`sqlite`, `archives`, `images`, `videos`, `audio`, `fonts`, `log-files` — and need hues
of our own.

Converted from sRGB hex to oklch, the upstream values look like this:

| language | hex | L | C | H |
| --- | --- | --- | --- | --- |
| JavaScript | `#f1e05a` | 0.896 | 0.153 | 102.1 |
| Python | `#3572a5` | 0.535 | 0.102 | 246.5 |
| TypeScript | `#3178c6` | 0.567 | 0.140 | 253.3 |
| Markdown | `#083fa1` | 0.404 | 0.168 | 261.4 |
| CSS | `#663399` | 0.440 | 0.160 | 303.4 |
| Go | `#00add8` | 0.695 | 0.130 | 223.9 |
| YAML | `#cb171e` | 0.537 | 0.209 | 26.9 |
| JSON | `#292929` | 0.281 | **0.000** | — |
| Lua | `#000080` | 0.271 | 0.188 | 264.1 |

Three things fall out of that table, and they shape the whole design.

**The lightness is all over the place.** Markdown at 0.404 and Lua at 0.271 are far
darker than anything our distribution ramp uses; JavaScript at 0.896 is far lighter.
Used literally, the set would not read as a set, and several members would fail contrast
on one theme or the other.

**Some upstream colors have no hue at all.** JSON is `#292929`, pure gray, chroma 0.000.
There is nothing to borrow, so JSON needs a house hue like the 18 non-languages do.

**Some upstream hues collide with each other.** Python is 246.5° and TypeScript is
253.3° — **6.8° apart** — and HTML and Svelte are closer still, at 0.65°. This looked at
first like the defect the work exists to fix, and it is not.
The defect is CSS and Markdown landing on nearly the same color for no reason anyone
chose; two languages GitHub itself paints alike is a decision a reader has already
absorbed, and undoing it would cost more recognizability than it buys distinctness.
See [The rule for hue](#the-rule-for-hue).

### What the current ramp already does, unstated

The eight distribution categories sit at wildly different lightnesses — 0.569 to 0.729 —
which looks arbitrary until you compare each against the most chroma sRGB can hold at
that lightness and hue:

| slot | L | C | max C at that L and hue | share of max |
| --- | --- | --- | --- | --- |
| cat-7 (yellow, 92°) | 0.729 | 0.145 | 0.149 | 97% |
| cat-3 (orange, 54°) | 0.666 | 0.159 | 0.167 | 95% |
| cat-6 (cyan, 206°) | 0.610 | 0.097 | 0.104 | 93% |
| cat-2 (green, 151°) | 0.604 | 0.145 | 0.162 | 90% |
| cat-1 (blue, 254°) | 0.569 | 0.157 | 0.180 | 87% |
| cat-5 (red, 16°) | 0.593 | 0.191 | 0.237 | 81% |

So the ramp is already, roughly, *as vivid as the gamut allows near each hue*.

The tempting reading is that lightness follows the gamut cusp per hue, and a rule could
be derived from it. That reading does not survive measurement: across the twelve slots,
lightness correlates with cusp lightness at **r=0.44**, which is noise wearing a
pattern. What the table actually shows is one lightness band and a chroma target the
gamut cuts into at some hues — which is the rule this plan states, with the numbers
written down instead of implied by twelve literals.

## Design

### Hue is borrowed; lightness and chroma are ours

A family declares **one number**: its hue.
Where linguist names a color for the language, the hue is that color converted to oklch,
unchanged. Where it does not — the 18 non-languages, plus achromatic cases like JSON and
reStructuredText, whose upstream color is a grey and carries no hue at all — we choose
one.

Lightness and chroma never come from upstream, and never vary by family.
Each theme states one pair for the whole set, which is what makes it read as a set and
what keeps every member inside the same contrast behavior on both themes.

### The rule for hue

Two rules, and no third:

- A family that names a `linguist` language takes that language’s hue exactly —
  **including** where two of GitHub’s own colors land close together.
  HTML and Svelte are 0.65° apart upstream, Ruby and YAML 1.13°, and they stay that way.
  A reader who knows Ruby is red is better served by red than by a hue we moved to win a
  distance metric, and GitHub’s crowded regions are GitHub’s to redistribute, not ours.
- A family GitHub names no color for takes a hue at least five degrees clear of every
  other declared hue. The floor is low on purpose: 56 families cannot be spread evenly
  around a circle whose crowded regions are fixed.
  `check_file_type_colors.py --suggest` hands out the widest remaining gap, so the
  families placed so far clear the floor with room to spare (5.6° at the tightest).

An earlier draft of this plan separated close upstream pairs and derived lightness from
the sRGB cusp per hue.
Both were dropped. The separation traded recognizability for a metric; the cusp rule was
fitting noise — the existing hand-tuned ramp’s lightness correlates with cusp lightness
at r=0.44.

### The rule for lightness and chroma

One lightness and one chroma per theme, applied to every family:
`LIGHT_THEME = Tone(0.62, 0.180)` and `DARK_THEME = Tone(0.75, 0.150)` in
`color_oklch.py`. Lightness comes from the ramp these replace, whose light slots
centered on 0.60 and dark on 0.77 after many iterations by eye.

Chroma is a **target**, not a constant.
A target low enough for every hue to reach exactly does exist — 0.1055 light and 0.1275
dark, both set by the cyan-blue band, which holds roughly half what red does — and
produces a perfectly even set that reads as washed out.
The shipped targets sit well above it, so most hues reach them and the cyans come in
under: the same trade the old ramp made when it gave its teal slot 0.09 against 0.15
elsewhere.
Lightness is the half that never varies, and it is the half that matters for a
stacked bar: no segment looks heavier than its size because its neighbor is darker.

### The pullback happens in Python, not CSS

Composing the color in CSS — `oklch(var(--lightness) var(--chroma) var(--hue))`, one
declaration, hue as the only per-family value — was the obvious design and does not
work. When the target chroma is outside sRGB at some hue, a browser clips rather than
reducing chroma. Measured in Chromium: `oklch(62% 0.18 206)` paints as lightness 0.652,
chroma 0.115, **hue 214.6** — 8.6° of drift, more than the five-degree separation the
palette is built on.

So the server resolves both themes and ships finished colors.
The registry keeps only the hue, which is the tool-neutral part; the theme’s tone lives
in Metabrowser and reaches the browser through `METABROWSER_SETTINGS`, which is the
documented channel for exactly this.

### Components

**`recommended-file-types.toml`** gains three fields per family, and stays TOML:

```toml
[[family]]
id = "css"
label = "CSS"
group = "code"
order = 130
linguist = "CSS"                 # upstream correspondence, or omitted where there is none
linguist_color = "#663399"       # its color, so the check needs no clone
hue = 303.37                     # oklch hue; L and C belong to the theme
```

`linguist_color` is recorded beside the name so a family’s provenance is auditable in
one diff and checkable without a clone of linguist or a network call.

**`file_type_registry.py`** parses and validates all three and exposes them on
`FileTypeFamily`; the projection carries `hue` and `linguist`.
**`file_type_filters.serialize_distribution_colors`** joins hue to tone and is what the
browser receives.

**`devtools/check_file_type_colors.py`**, in `make lint`, holds: every `linguist`
family’s hue matches its recorded upstream color; every chosen hue clears the floor; and
every painted color keeps its lightness and hue and lands inside sRGB. `--suggest`
prints a free hue for a new family.

**`category_palette.js`** stops hashing families.
The slot pool, the per-folder session, the reservation table, and
`DISTRIBUTION_PALETTE_SLOTS` all go.
A hash remains for the extensions inside **Other types**, which are unfamilied by
definition and only need telling apart from each other.

### API Changes

`schema_version` becomes 2, the projection schema `file-type-registry-v2`, and
`registry_revision` 3 — which changes the registry fingerprint and therefore rollup
identity. Consumers already refuse to combine rollups across identities.

The rollup and conformance schemas stop pinning the registry schema version to 1. The
format document has always said the registry versions independently; the `const`
contradicted it.

## Implementation Plan

### Phase 1: Declare the colors

- [x] Add `hue`, `linguist`, and `linguist_color` to all 56 families: 35 carrying
  GitHub’s hue, 21 placed in free gaps
- [x] `schema_version` 2, `registry_revision` 3; regenerate the projection, schemas, and
  conformance corpus
- [x] `devtools/check_file_type_colors.py`, wired into `make lint` and `make lint-check`
- [x] Update the format document’s definitions section and version-model note

### Phase 2: Everything reads from it

- [x] `serialize_distribution_colors` joins hue to tone; `category_palette.js` reads it
- [x] Overview and Treemap take color from the same field; hash, probe, and slot pool go
- [x] Tests that a family’s color is the same in any palette and does not depend on
  which other families are present, and that the shipped colors match the registry
- [x] `CHANGELOG.md` and `docs/design-system.md` for the visible change

## Testing Strategy

- `tests/test_color_oklch.py` holds the conversion against values a maintainer can check
  in dev tools, and the tone: one lightness at every hue, chroma never above target,
  never outside sRGB, and chroma the only thing the pullback moves.
- `tests/test_file_type_taxonomy.py` binds the shipped colors to the registry: one entry
  per family, in registry order, each stating the theme’s lightness and the family’s
  hue.
- `check_file_type_colors.py` is itself the check for the two hue rules, and reports the
  close upstream pairs it deliberately permits.
- Classification results must not move: the conformance corpus is regenerated and
  reviewed as a diff, and nothing but the registry identity should appear in it.
- `tests/dom/folder_overview_models_behavior.js` holds the palette properties the old
  allocator could not give.

## Rollout Plan

Both phases landed together.
Phase 1 alone leaves declared colors that nothing reads, which is dead data in the
document whose whole claim is to be the source.

## Open Questions

- Does the icon belong here too?
  It is display metadata like color and label, and leaving it in `icons.js` keeps a
  family’s identity in two places.
  Against: an icon is a glyph reference rather than a value, and the format is meant to
  stay tool-neutral.
- Is `linguist` the right field name, or a general `upstream` naming its source, so
  another registry could be referenced later?
- Display-p3 under `@media (color-gamut: p3)` would let the cyan band reach the target
  chroma the rest of the palette already does.
  Worth measuring against a real display before deciding it is worth a second set of
  colors.

## References

- [File Rollup Format](../architecture/file-rollup-format/file-rollup-format.md) — the
  format this registry belongs to and its version model
- [github-linguist/linguist](https://github.com/github-linguist/linguist) —
  `lib/linguist/languages.yml`, MIT; clone with
  `git clone --depth 1 https://github.com/github-linguist/linguist.git attic/linguist`
- [Design System](../../design-system.md) — the distribution ramp, and the rule that hue
  does not drift between themes

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
