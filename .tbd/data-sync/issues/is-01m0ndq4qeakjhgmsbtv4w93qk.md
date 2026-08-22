---
type: is
id: is-01m0ndq4qeakjhgmsbtv4w93qk
title: YAML/Ruby and HTML/Svelte render as literally the same color
kind: bug
status: open
priority: 1
version: 1
labels: []
dependencies: []
parent_id: is-01m0ndp6h7a3hx27zbswtknk89
created_at: 2026-08-22T19:03:48.206Z
updated_at: 2026-08-22T19:03:48.206Z
---
Checked at the reviewer's request, and both are worse than the TypeScript case that prompted the review.

HTML #e34c26 -> 34.85, Svelte #ff3e00 -> 34.20. 0.65 degrees apart. Light renders #b81608 vs #b81508 -- one step in the green channel. Dark renders #fc3e25 vs #fc3e26. These are the same colour.

YAML #cb171e -> 26.90, Ruby #701516 -> 25.77. 1.13 degrees apart. Light renders #ba1411 vs #ba1410 -- one step in blue. Also clojure at 2.55 and swift at 4.72.

The band 24-40 degrees holds seven families: clojure, ruby, yaml, swift, svelte, html, toml. Every one renders between #b51703 and #ba1313 in the light theme.

Root cause, and the reason this is not fixable one family at a time. The palette takes GitHub's hue and replaces GitHub's lightness and chroma with the theme's. GitHub's own colours are distinguishable largely through those two dimensions: #ff3e00 is a bright orange-red and #e34c26 a muted brick, and they differ by 0.65 degrees of hue. Normalising L and C discards exactly what separated them. 56 families on one circle averages 6.4 degrees of spacing, which is at or under the just-noticeable difference for hue at fixed L and C.

check_file_type_colors.py permits this deliberately -- 'a reader who knows Ruby is red is better served by red than by a hue moved to win a distance metric' -- and its report prints the colliding pairs. So the rule is working as written; the question is whether the rule is right. Options: let a family carry a small lightness or chroma offset alongside its hue; or keep one hue per GitHub cluster and let the crowded families take house hues.

The reviewer has asked for TypeScript specifically (sibling bead). This bead is the general case.
