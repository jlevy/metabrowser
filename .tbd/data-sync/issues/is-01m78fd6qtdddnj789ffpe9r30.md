---
type: is
id: is-01m78fd6qtdddnj789ffpe9r30
title: Main's transition-instrument Chrome checks fail CI intermittently
kind: bug
status: open
priority: 1
version: 1
labels: []
dependencies: []
created_at: 2026-11-12T18:13:04.889Z
updated_at: 2026-11-12T18:13:04.889Z
---
At main 27ea216c (after #373), CI's test (3.14) job fails in tests/test_transitions_instrument.py on 'a subject shown during the hover, before the press, refuses' (DOM work after the subject (taskLoop) is settle time, not readiness: painted ready 198.7). Five PR branches that merged that main failed the same file on 'a long ready frame counts its own rendering', each about 10 ms short (447.4 vs 457, 463.9 vs 473.2, 413.9 vs 425.4, 397.3 vs 409.1, 447.5 vs 456.9); reruns passed. The checks run the recorder (explorations/performance-loop/transitions-recorder.mjs) in a real headless Chrome through tests/dom/transitions-recorder-chrome.mjs. Fix the cause in its own PR to main, without loosening numbers blindly, and show stability with repeated runs under load.
