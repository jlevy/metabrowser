---
type: is
id: is-01m0ndq4en94cfqm99tg6m0fyt
title: Declared deviation for swift/svelte, the one pair the derivation cannot separate
kind: task
status: closed
priority: 3
version: 6
labels: []
dependencies: []
parent_id: is-01m0ndp6h7a3hx27zbswtknk89
created_at: 2026-08-22T19:03:47.925Z
updated_at: 2026-08-23T07:11:40.051Z
---
Reported in QA: Python and TypeScript look like the same blue.

Measured. Python is linguist #3572a5 -> hue 246.50; TypeScript is #3178c6 -> hue 253.30. They are 6.80 degrees apart and share the theme's lightness and chroma, so light renders #0042bf vs #033dda. Distinguishable, but only just, and only if the two bars are adjacent.

TypeScript is in worse company than Python. Its nearest neighbour is xml at 1.86 degrees (#033dda vs #013ed9 -- the same colour), then powershell at 4.84. Seven families sit inside 243-264 degrees.

Decision from the review: move TypeScript purple-ward and stop taking GitHub's hue for it. That needs a declared-deviation concept, because check_file_type_colors.py currently requires a hue within 0.02 degrees of the linguist colour whenever linguist is set. Proposal: keep linguist and linguist_color for provenance, add a reason field recording why we left GitHub, and hold a deviated hue to the same 5 degree floor a house hue gets.

The constraint to settle first. Only three arcs on the whole circle clear 5 degrees on both sides: 308.37-309.22, 228.85-228.90, and 238.90-238.94. Only the first is purple. Putting TypeScript at 308.80 clears python by 62 degrees but lands 5.43 from css and 5.42 from julia, rendering #601fad against #5721b9 and #6a1da1 -- which trades one near-collision for two. A gentler move (268 or 276) reads as purple but sits about 4 degrees from lua or php, under the floor.

So this bead is blocked on the parent problem in its sibling: at one fixed lightness and chroma the circle has no room left. Worth deciding that first.

UPDATE after the palette measurement (mb-0ov6). Python/TypeScript was never the worst pair perceptually: at fixed tone they are dE 0.0275, already above the 0.02 mark, while html/svelte sat at 0.0020. Deriving from GitHub's full colour takes the pair to 0.0316 on its own.

So the deviation mechanism is probably NOT needed for TypeScript. Where it is still needed is swift/svelte, which stays at dE 0.0073 in the dark theme because #f05138 and #ff3e00 are near-identical upstream in all three dimensions.

Decide after mb-0ov6 lands and the new palette has been looked at in a browser: if TypeScript still reads as Python's blue, deviate it then, with the mechanism this bead describes.

## Notes

DECIDED and DONE in #73: swift moves to hue 52.3 with a declared deviation. Svelte keeps its brand orange.

THE ARGUMENT THAT SETTLED IT was not which language is better known -- the reasoning used for Markdown -- but which family is the hub. Swift was the nearest neighbour in three of the four pairs still under the perceptual floor: svelte 0.0073 in dark, html 0.0156 in light, clojure 0.0181 in dark. Four upstream brands independently chose the same orange-red (swift 31.62, svelte 34.20, html 34.85, clojure 24.35, ruby 25.77 within eleven degrees). Moving swift resolves three collisions; moving svelte would resolve one.

MEASURED. At 52.3 swift clears every other family by 0.0257 in both themes, against 0.0073 before. Palette-wide:

    closest pair, light   0.0156 html/swift   ->  0.0164 json/plain-text
    closest pair, dark    0.0073 svelte/swift ->  0.0160 audio/word
    pairs under 0.02      4                   ->  1 (html/svelte at 0.0179)

Every pair now clears MINIMUM_HOUSE_DELTA_E. The one remaining sub-0.02 pair is GitHub's own and is kept for that reason.

WHY NOT THE BLUE END. The widest gap on the whole circle is near 265.8, clearing 0.0380 -- half again as much room. Refused: swift renders #aa2400 light and #ff4c12 dark at 52.3, still recognisably the orange readers associate with it, and the entire point of taking GitHub's colour is that they already know it. Trading recognition for 0.012 of perceptual distance is the wrong side of the trade.

The deviation prose in the TOML records all of the above, so the next reader can tell when the reason stops applying.
