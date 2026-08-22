---
type: is
id: is-01m0ne98nc9p91jakt4g5mpcm8
title: Derive family colors from GitHub's full color, not hue alone
kind: feature
status: open
priority: 0
version: 1
labels: []
dependencies: []
parent_id: is-01m0ndp6h7a3hx27zbswtknk89
created_at: 2026-08-22T19:13:42.060Z
updated_at: 2026-08-22T19:13:42.060Z
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
