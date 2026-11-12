---
type: is
id: is-01m78fd6qtdddnj789ffpe9r30
title: Main's transition-instrument Chrome checks fail CI intermittently
kind: bug
status: closed
priority: 1
version: 5
labels: []
dependencies: []
created_at: 2026-11-12T18:13:04.889Z
updated_at: 2026-11-12T22:35:34.493Z
closed_at: 2026-11-12T22:35:34.492Z
close_reason: "Fixed in jlevy/metabrowser#381 (8b7674a5): test-only; reviews A then B (approve); CI green. Merges on the user's word."
resolution: null
duplicate_of: null
---
At main 27ea216c (after #373), CI's test (3.14) job fails in tests/test_transitions_instrument.py on 'a subject shown during the hover, before the press, refuses' (DOM work after the subject (taskLoop) is settle time, not readiness: painted ready 198.7). Five PR branches that merged that main failed the same file on 'a long ready frame counts its own rendering', each about 10 ms short (447.4 vs 457, 463.9 vs 473.2, 413.9 vs 425.4, 397.3 vs 409.1, 447.5 vs 456.9); reruns passed. The checks run the recorder (explorations/performance-loop/transitions-recorder.mjs) in a real headless Chrome through tests/dom/transitions-recorder-chrome.mjs. Fix the cause in its own PR to main, without loosening numbers blindly, and show stability with repeated runs under load.

## Notes

2026-11-12: fixed in jlevy/metabrowser#381 (claude/fix-transitions-instrument-flake, head 39d5acc2, CI green). Cause: the checks assumed more than the recorder's definitions guarantee. Painted ready is read on the rAF grid, while Chrome's Event Timing presentation also includes commit, raster, and GPU work (5.5-13.3 ms after the long frame under load, 23-43 ms with CPU throttled 4x), so the old lower bound (presentation - 9 ms) failed correct runs. Also the press and release are separate CDP calls, so a frame could fall between press and click. Fix is test-only, plus README Limits; the recorder and exp-058 are unchanged. Stress, with 12 busy loops: frames2 old 29/35, new 35/35; with 4x throttle, old 0/8, new 8/8. One coverage loss: a recorder that reports the next frame's begin time is caught 1/5 in Chrome (still 100% by the browserless test). The recorder edge is filed separately.

2026-11-12: review A (1 Medium, 1 Low) fixed in 8b7674a5, with a disposition reply; review B approves with no findings. Stress at 8b7674a5, 12 busy loops: 15/15 in every group, against main's 8/15, 9/15, 13/15, 15/15. CI green. Ready to merge on the user's word.
