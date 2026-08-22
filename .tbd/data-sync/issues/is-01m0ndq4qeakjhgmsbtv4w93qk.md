---
type: is
id: is-01m0ndq4qeakjhgmsbtv4w93qk
title: YAML/Ruby and HTML/Svelte render as literally the same color
kind: bug
status: closed
priority: 1
version: 3
labels: []
dependencies: []
parent_id: is-01m0ndp6h7a3hx27zbswtknk89
created_at: 2026-08-22T19:03:48.206Z
updated_at: 2026-08-22T21:14:24.796Z
closed_at: 2026-08-22T21:14:24.795Z
close_reason: "Resolved by mb-0ov6: html/svelte and ruby/yaml are distinct in both themes, verified in a browser."
---
Checked at the reviewer's request, and both are worse than the TypeScript case that prompted the review.

HTML #e34c26 -> 34.85, Svelte #ff3e00 -> 34.20. 0.65 degrees apart. Light renders #b81608 vs #b81508 -- one step in the green channel. Dark renders #fc3e25 vs #fc3e26. These are the same colour.

YAML #cb171e -> 26.90, Ruby #701516 -> 25.77. 1.13 degrees apart. Light renders #ba1411 vs #ba1410 -- one step in blue. Also clojure at 2.55 and swift at 4.72.

The band 24-40 degrees holds seven families: clojure, ruby, yaml, swift, svelte, html, toml. Every one renders between #b51703 and #ba1313 in the light theme.

Root cause, and the reason this is not fixable one family at a time. The palette takes GitHub's hue and replaces GitHub's lightness and chroma with the theme's. GitHub's own colours are distinguishable largely through those two dimensions: #ff3e00 is a bright orange-red and #e34c26 a muted brick, and they differ by 0.65 degrees of hue. Normalising L and C discards exactly what separated them. 56 families on one circle averages 6.4 degrees of spacing, which is at or under the just-noticeable difference for hue at fixed L and C.

check_file_type_colors.py permits this deliberately -- 'a reader who knows Ruby is red is better served by red than by a hue moved to win a distance metric' -- and its report prints the colliding pairs. So the rule is working as written; the question is whether the rule is right. Options: let a family carry a small lightness or chroma offset alongside its hue; or keep one hue per GitHub cluster and let the crowded families take house hues.

The reviewer has asked for TypeScript specifically (sibling bead). This bead is the general case.

## Notes

Resolved by mb-0ov6, and confirmed on screen in both themes.

Light theme now renders html #e64c24 against svelte #f34519, and ruby #c54440 against yaml #e13a36. Both pairs are plainly two colours. Measured: html/svelte 0.0020 -> 0.0237 delta-E, ruby/yaml 0.0035 -> 0.0529. The wider 24-40 degree band this bead described -- clojure, ruby, yaml, swift, svelte, html, toml, every one of which rendered between #b51703 and #ba1313 -- is now spread across lightness and chroma as well as hue.

Correction to this bead's evidence, for anyone reading it later: the hexes quoted here were too dark by about a gamma step and are not what the app rendered. The real flat-tone renders were html #dd5230 / svelte #dd5232 and ruby #de4e49 / yaml #de4f47, checked against a browser's own oklch conversion. So html/svelte differed by one step of blue, not one step of green. The finding itself -- that these were the same colour -- was right.

The root cause named here is the one that was fixed: the palette took GitHub's hue and replaced GitHub's lightness and chroma, which is what told those families apart. Of the two options this bead offered, the second (house hues for crowded families) was not needed; the first, letting a family carry lightness and chroma from upstream, is what shipped, as a rank inside a theme-owned band rather than as the upstream values.

Still open, and tracked in mb-oq6j: swift/svelte in the dark theme at 0.0073, which no derivation separates because #f05138 and #ff3e00 are near-identical upstream in all three dimensions.
