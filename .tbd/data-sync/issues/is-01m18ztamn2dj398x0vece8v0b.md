---
type: is
id: is-01m18ztamn2dj398x0vece8v0b
title: "Swift deviation decided in PR #73 is not in the tree"
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
created_at: 2026-08-30T09:25:41.141Z
updated_at: 2026-08-30T09:25:41.141Z
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
