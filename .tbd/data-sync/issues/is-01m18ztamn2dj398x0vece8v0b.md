---
type: is
id: is-01m18ztamn2dj398x0vece8v0b
title: "Swift deviation decided in PR #73 is not in the tree"
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
created_at: 2026-08-30T09:25:41.141Z
updated_at: 2026-08-30T17:20:42.733Z
---
The Swift deviation decided and measured in PR #73 is not in the tree. `hue = 52.3` never appears in the file's history, so it was dropped during that PR's review rework rather than landed and reverted -- and no reason is recorded either way, which is why this is a bead and not a silent re-apply.

WHAT THE PALETTE LOOKS LIKE TODAY, from devtools/check_file_type_colors.py:

    light closest pair    0.0156  html / swift
    dark  closest pair    0.0073  svelte / swift
    under 0.02            0.0073 svelte/swift, 0.0156 html/swift,
                          0.0179 html/svelte, 0.0181 clojure/swift

Swift is the nearest neighbour in three of the four pairs under the perceptual floor. Four upstream brands independently chose the same orange-red -- swift 31.62, svelte 34.20, html 34.85, clojure 24.35, with ruby at 25.77 -- so moving Swift resolves three collisions where moving any of the others resolves one. That is the argument, and it does not depend on which language is better known.

WHAT #73 MEASURED. At hue 52.3 Swift cleared every other family by 0.0257 in both themes against 0.0073, taking the palette's closest pair to 0.0160 and leaving one pair under 0.02 rather than four. It stayed orange -- #aa2400 light, #ff4c12 dark. The blue end of the circle had more room still, near 265.8 clearing 0.0380, and was refused because a blue Swift is no longer recognisably Swift and the whole point of taking GitHub's colour is that readers already know it.

NOT RE-APPLIED HERE. The mechanism survives -- Markdown still carries its declared deviation, and the checker still reports it -- so this is one TOML edit whenever someone wants it. But a change that was removed during review should not come back without the reviewer's reason being known, and re-landing it silently is how a decision gets made twice by accident.

TO CLOSE: either re-apply the deviation with the reason above, or record why GitHub's 31.62 is kept and accept that four pairs sit under the floor. Both are defensible; leaving it undecided is what is not. Re-verify the hue against the current registry first -- families have been added since, and the brute-force search over 3,600 hues is slow enough to want a coarse pass first.

## Notes

RESOLVED: swift moves to hue 52.3 with a declared deviation.

FIRST, THE QUESTION THIS BEAD LEFT UNANSWERED. Swift was not broken. `check_file_type_colors.py` passed with swift at GitHub's 31.62, and correctly: the registry's rule is that a family carrying GitHub's own hue is kept even when tight, and the perceptual floor applies only to the 21 hues placed into free gaps. Filing this as "still the nearest neighbour in three of four pairs" without saying the check passed made it read as a defect. It was a judgement call, not a failure.

WHAT MADE IT WORTH CHANGING ANYWAY. Four upstream brands independently chose nearly the same orange-red -- swift 31.62, svelte 34.20, html 34.85, clojure 24.35 -- so faithfulness produced swift and svelte at dE 0.0073 in the dark theme. That renders #ff4733 against #ff4a31: three apart in green, two in blue, one colour to the eye. A palette whose purpose is telling families apart does not get to call that acceptable merely because the rule that produced it is consistent. The rule was right and the outcome was not.

WHY SWIFT AND NOT SVELTE, which is the part that makes this a principled choice rather than a preference. Swift is the hub of the crowd, not a member of it: counting appearances in sub-0.02 pairs across both themes gives swift 5, word 4, html 3, svelte 3. Moving swift resolves three collisions -- svelte, html, clojure -- where moving any of the others resolves one.

MEASURED, whole palette, before and after:

    closest pair, dark     0.0073 svelte/swift   ->  0.0160 audio/word
    closest pair, light    0.0156 html/swift     ->  0.0164 json/plain-text
    pairs under 0.02, dark      7                ->  4
    pairs under 0.02, light     8                ->  6
    pairs kept as sub-floor     4                ->  1

Every surviving pair clears MINIMUM_HOUSE_DELTA_E. The one that remains, html/svelte at 0.0179, is GitHub's own and above the floor, so it is kept under the same rule that used to keep four.

WHY 52.3 AND NOT THE WIDEST GAP. Swift renders #ab2300 light and #ff4c13 dark there -- still orange, so what a reader recognises about Swift survives the exact hue no longer matching. The widest gap on the whole circle is near 265.8 and clears 0.0380, half again as much room, and is refused: a blue Swift is not recognisably Swift, and the entire reason for taking GitHub's colours is that readers already know them. Provenance is kept in `linguist` and `linguist_color` either way, so the deviation is auditable in one diff.

The reason is written into the TOML beside the hue, because a deviation is a judgement someone made and the next reader needs it to tell a decision from a mistake.
