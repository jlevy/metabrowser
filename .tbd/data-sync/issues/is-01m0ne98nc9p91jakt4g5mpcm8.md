---
type: is
id: is-01m0ne98nc9p91jakt4g5mpcm8
title: Derive family colors from GitHub's full color, not hue alone
kind: feature
status: closed
priority: 0
version: 3
labels: []
dependencies: []
parent_id: is-01m0ndp6h7a3hx27zbswtknk89
created_at: 2026-08-22T19:13:42.060Z
updated_at: 2026-08-22T21:14:05.653Z
closed_at: 2026-08-22T21:14:05.652Z
close_reason: Implemented on claude/release-readiness-review-idotjj; every measurement in the bead independently reproduced, and the palette looked at in a real browser in both themes. See notes.
---
Direction set in review: keep GitHub's colours but take all three attributes, adjust subtly toward more brilliance, and hold everything inside a stated brightness band.

WHY THE PRESENT RULE FAILS. color_oklch.py takes the upstream hue and replaces upstream lightness and chroma with one pair per theme. But the colliding families are separated upstream almost entirely by those two dimensions: html/svelte differ by 0.65 deg of hue and by dL 0.032 / dC 0.040; ruby/yaml by 1.13 deg and dL 0.179. Normalising L and C throws away exactly what told them apart. 56 families averages 6.4 deg of hue spacing, at or under the just-noticeable difference at fixed L and C.

PROPOSED DERIVATION, per family, from the upstream colour already recorded in linguist_color:
  hue        unchanged -- GitHub's, as today.
  lightness  theme centre + SPREAD * (2t - 1), where t is the family's RANK among
             upstream lightnesses. Rank rather than linear because upstream L is
             0.271-0.896 with half the families inside 0.492-0.687, so a linear map
             re-crowds the middle. Rank keeps GitHub's ORDER (svelte lighter than
             html) without importing its extremes.
  chroma     theme chroma * (0.75 + 0.5 * u), u = the family's normalised upstream
             chroma, then pulled into sRGB as today. Muted upstream colours stay
             muted relative to vivid ones, and the target sits high enough that the
             set reads brilliant rather than pedestrian.
Families GitHub names no colour for keep their gap hue and sit at the centre lightness with mid chroma.

CONSTANTS (measured, not guessed): LIGHT centre 0.62 spread +-0.06; DARK centre 0.75 spread +-0.06; chroma spread +-25%. Widening the band to +-0.08 buys almost nothing (light floor 0.0156 -> 0.0164), so the tighter band wins on consistency. Giving house families lightness freedom too was measured and dropped -- it moves the floor not at all, because the binding pair is GitHub/GitHub.

MEASURED RESULT, minimum pairwise Oklab dE over all 56 families:
  light  0.0020 -> 0.0156   pairs under 0.02: 41 -> 9
  dark   0.0017 -> 0.0073   pairs under 0.02: 48 -> 8   (0.0149 excluding one pair, below)
  html/svelte   0.0020 -> 0.0237   #b81608/#b81508 becomes #cb1205/#e50f03
  ruby/yaml     0.0035 -> 0.0529   #ba1411/#ba1410 becomes #8f0f0d/#c00b09
  elixir/julia  0.0022 -> 0.0513
  typescript/xml 0.0058 -> 0.0323
Painted lightness lands in 0.560-0.680 (light) and 0.690-0.810 (dark); chroma reaches 0.225 where the gamut allows, against a flat 0.180 today.

WHAT REMAINS. swift/svelte stays at dE 0.0073 in dark: #f05138 and #ff3e00 are near-identical in all three dimensions upstream, so no derivation separates them. That is the case for a declared deviation (sibling mb-oq6j), and it is a handful of families, not the whole palette.

CHECK. Replace the hue-distance floor in check_file_type_colors.py with a minimum dE floor in both themes -- one perceptual rule instead of two hue rules, and it measures the thing we actually care about. --suggest then proposes a hue and tone position.

COST. Touches color_oklch.py, file_type_registry.py, the registry TOML and its JSON projection (both copies), check_file_type_colors.py, the settings projection that ships finished colours, the browser consumers, the format doc and the registry schema version, plus tests. Note the tradeoff being accepted deliberately: lightness no longer constant means a stacked-bar segment can read slightly heavier than a neighbour of the same size, which is the property the flat tone was chosen to guarantee. The band is narrow to keep that small, but it wants a look in a real browser before it ships.

## Notes

Implemented and looked at in a real browser.

The derivation in this bead was re-derived independently before any of it was written into the package, and it reproduces every number recorded here exactly: light floor 0.0020 -> 0.0156 with pairs under 0.02 falling 41 -> 9; dark 0.0017 -> 0.0073 with 48 -> 8, and 0.0149 excluding svelte/swift; html/svelte 0.0020 -> 0.0237, ruby/yaml 0.0035 -> 0.0529, elixir/julia 0.0022 -> 0.0513, typescript/xml 0.0058 -> 0.0323; painted lightness 0.560-0.680 light and 0.690-0.810 dark; chroma reaching 0.225. The constants are therefore checked rather than trusted.

ONE CORRECTION. The hex values quoted in this bead and in mb-6g81 are not what the app renders, and they are too dark by roughly a gamma step. At the flat tone the app rendered html #dd5230 against svelte #dd5232, and ruby #de4e49 against yaml #de4f47 -- verified against a real browser's own oklch conversion, not just against our converter. The bead said #b81608/#b81508 and #ba1411/#ba1410. The delta-E measurements were right; only the illustrative hexes were wrong. The conclusion, that the two were the same colour, is unaffected -- html/svelte differed by one step of blue rather than one step of green.

WHAT SHIPPED. color_oklch.py gains TonePosition, BAND_CENTER, ToneBand (replacing Tone), band_positions(), oklab() and delta_e(). Positions are derived once for the whole registry in FileTypeRegistry.__post_init__ and read back through registry.tone_position(id), because a rank is a property of the set and not of one family. serialize_distribution_colors joins hue to position.

CHECK. The hue-distance floor is now a perceptual floor: MINIMUM_HOUSE_DELTA_E = 0.015, applied to house-placed families in both themes, which is where the old five-degree rule sat when measured at the flat tone (0.0157). Upstream-vs-upstream collisions are still reported rather than failed, and the report now lists which ones are kept. Measured margin: placed hues clear everything by 0.0164 light and 0.0160 dark.

COST PAID. Registry schema 2 -> 3 and projection file-type-registry-v3, carrying linguist_color so a downstream consumer can reproduce the palette from the published artifact. PLUGIN_SDK_VERSION 0.3 -> 0.4 with all eight built-in manifests, because schemaVersion and registryIdentity are documented plugin surface. Format doc, JSON schema, both generated copies, types.d.ts, the browser consumers, and the 0.6.0 changelog entry (amended rather than appended, since 0.6.0 has not been tagged).

THE TRADEOFF, LOOKED AT. Fifty-six equal-width segments were rendered adjacent in both themes and inspected. No segment reads heavier than its neighbours: at +-0.06 the variation reads as variety rather than as weight. The property the flat tone guaranteed is genuinely given up, and at this band width the cost is not visible.

WHAT SURVIVES. swift/svelte in dark, at 0.0073, is the one pair still plainly the same colour on screen (#ff907b against #ff9279). Light is fine (#ec4c33 against #f34519). That is the declared-deviation case in mb-oq6j. The tightest house pair is json/plain-text at 0.0164 -- above the floor, and two teals that are close but separable.
