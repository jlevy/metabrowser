# Feature: One File-Type Source of Truth

**Date:** 2026-08-21

**Author:** Metabrowser maintainers

**Status:** Draft

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

688 languages upstream carry a `color:`. **38 of our 56 families** map to one; the other
18 are not languages — `plain-text`, `pdf`, `word`, `rich-text`, `open-document`,
`epub`, `parquet`, `arrow`, `avro`, `orc`, `protocol-buffers`, `sqlite`, `archives`,
`images`, `videos`, `audio`, `fonts`, `log-files` — and need hues of our own.

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
253.3° — **6.8° apart**. Borrowing hue faithfully would put two of the most commonly
co-occurring families in a repository almost on top of each other, which is precisely
the defect this work exists to fix.

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

So the ramp is already, roughly, *as vivid as the gamut allows near each hue’s peak*.
Yellow sits high because yellow can only be vivid when it is light; blue sits low for
the same reason in reverse.
That is the right instinct and it is nowhere written down, which is why the numbers look
like 56 independent decisions waiting to happen.

## Design

### Hue is borrowed; lightness and chroma are ours

A family declares **one number**: its hue.
Where linguist has an opinion, the hue is its color converted to oklch and rounded.
Where it does not — the 18 non-languages, plus achromatic cases like JSON — we choose
one.

Lightness and chroma never come from upstream.
They are derived for every family by the same rule, which is what makes the set coherent
and what keeps every member inside our own contrast requirements on both themes.

### The rule for lightness and chroma

For a given hue, sRGB’s most saturated point sits at a particular lightness — the cusp —
and both the achievable chroma and that lightness move with hue.
The rule follows the cusp rather than fighting it:

- find the cusp for the hue: the lightness at which chroma peaks;
- take the family’s chroma as a fixed fraction of that peak;
- take its lightness as the cusp lightness, pulled toward a mid target so the extremes
  do not run away.

Two constants — the chroma fraction and how hard lightness is pulled toward the middle —
are the entire tuning surface, they apply to all 56 families equally, and they are
measured and recorded beside the ramp the way this repository requires of every bound.
The table above says roughly where they will land: something near 0.9 of peak chroma
reproduces the current ramp’s character.

Each theme derives its own pair from the same declared hue, which is how hue stays
constant across themes — the property the design system already holds.

### Approximate, deliberately

Two families whose borrowed hues land within the distinctness floor get separated: the
better-known one keeps its hue, the other moves by the smallest amount that clears the
floor, and the deviation is recorded beside the declaration with its reason.
Python and TypeScript at 6.8° apart are the case that forces this.

A reader recognizing “blue-ish means TypeScript” is worth far more than TypeScript being
exactly 253.3°, and a palette where two common languages are indistinguishable is worth
nothing at all.

### Modern color practice

- Colors are stated in oklch and only in oklch, which is what makes a perceptual
  distinctness floor meaningful and what makes the cusp rule computable.
- Derived states — hover, dimmed, ignored — come from `color-mix()` against the declared
  color rather than from separate literals, so a family has one definition and its
  states follow. Relative color syntax (`oklch(from …)`) is worth evaluating for the
  theme variants; the stylesheet uses none today.
- Gamut is stated, not assumed: every derived color is verified inside sRGB, with
  display-p3 as progressive enhancement under `@media (color-gamut: p3)` if the extra
  chroma proves worth it.

### Components

**`recommended-file-types.toml`** gains two fields per family, and stays TOML:

```toml
[[family]]
id = "css"
label = "CSS"
group = "code"
order = 130
linguist = "CSS"     # upstream correspondence, or omitted where there is none
hue = 303            # oklch hue; L and C are derived
```

**`file_type_registry.py`** exposes `hue` and `linguist`. **`file_type_contract.py`**
resolves hue to the per-theme oklch pair and emits it in the projection, so the browser
receives finished colors and holds no second table.

**`devtools/check_file_type_colors.py`**, in `make lint`, holds three rules: no two
families within the distinctness floor; every declared hue either matches its linguist
correspondence or records why it deviates; and every derived color sits inside sRGB.
Upstream agreement is skipped when no clone is present, so the check never needs the
network.

**`category_palette.js`** stops hashing.
The slot pool and `DISTRIBUTION_PALETTE_SLOTS` go, and with them the collisions and the
instability.

### API Changes

The registry projection gains a color per family — additive, on an internal contract
versioned with the shell and built-in plugins as one artifact, noted in `CHANGELOG.md`.

Adding fields changes the definition-file structure, so `schema_version` becomes 2 and
`registry_revision` 3, which changes the registry fingerprint and therefore rollup
identity. Consumers already refuse to combine rollups across identities.

## Implementation Plan

### Phase 1: Declare the colors

- [ ] Derive the cusp rule and fix its two constants against the current ramp, recording
  the measurement beside them
- [ ] Add `hue` and `linguist` to all 56 families: 38 converted from upstream, 18
  chosen, every deviation from an upstream hue recorded with its reason
- [ ] Resolve hue to per-theme oklch in the generator; `schema_version` 2,
  `registry_revision` 3; regenerate the projection, schemas, and conformance corpus
- [ ] `devtools/check_file_type_colors.py` with all three rules, wired into `make lint`
- [ ] Update the format document’s definitions section and version-model note

### Phase 2: Everything reads from it

- [ ] `category_palette.js` reads the declared color; hash, probe, and slot pool go
- [ ] Overview, Treemap, and navigation file icons take color from the same field
- [ ] A DOM test that no two families resolve to the same color, and that a family’s
  color does not depend on which other families are present
- [ ] `CHANGELOG.md` for the visible change

## Testing Strategy

- The cusp rule is tested as a function: given a hue it returns a color inside sRGB, at
  the stated fraction of peak chroma, on both themes.
- The three lint rules are each tested with an input that must fail — two families too
  close, a hue that silently disagrees with upstream, a color out of gamut — and each
  must name the family.
- Classification results must not move: the conformance corpus is regenerated and
  reviewed as a diff, and nothing but color should appear in it.
- Phase 2 adds the DOM test above and a visual check of a directory rich enough to paint
  most families at once.

## Rollout Plan

Both phases land together.
Phase 1 alone leaves declared colors that nothing reads, which is dead data in the
document whose whole claim is to be the source.

## Open Questions

- What is the distinctness floor, in oklch terms?
  It is a claim about telling two segments apart in a bar a few pixels tall, so it wants
  measuring against real rendered output rather than picking a number from a paper.
- Does the icon belong here too?
  It is display metadata like color and label, and leaving it in `icons.js` keeps a
  family’s identity in two places.
  Against: an icon is a glyph reference rather than a value, and the format is meant to
  stay tool-neutral.
- Should the 18 house hues be chosen to fill the gaps the borrowed 38 leave, so the
  whole set is evenly spaced?
  That is more beautiful and less mnemonic, since the house families would no longer sit
  where a reader might guess.
- Is `linguist` the right field name, or a general `upstream` naming its source, so
  another registry could be referenced later?

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
