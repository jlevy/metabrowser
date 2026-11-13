---
type: is
id: is-01m78tvwd225prdsp5q367gzwq
title: "PR #379 D3: layer 3 leaves 114 bytes of eager budget, and phase 2 plans an eager addition"
kind: bug
status: closed
priority: 3
version: 4
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m78ttv874k855zfx1arvd5vm
hold: null
hold_until: null
created_at: 2026-11-12T21:33:20.150Z
updated_at: 2026-11-13T07:44:01.259Z
started_at: 2026-11-12T21:33:45.514Z
closed_at: 2026-11-13T07:44:01.257Z
close_reason: "Resolved: #387 reset startup_script_transfer_kb to 220 KB from measured cost, and stack #376 merged at 8f84ed6 with the restored comments and annotations, 45,612 bytes under the new gate."
resolution: null
duplicate_of: null
---
Low. PR #379, review D (https://github.com/jlevy/metabrowser/pull/379#pullrequestreview-5881899935). check_startup_scripts at 9129aac: 179,597 bytes, 114 under the 175 KB gate; layer 3 added about 1,005 compressed eager bytes (app.js +880, plugin-sdk.js +125), and f168ccae dropped the @type annotations on app.js's shellKeymap and keyReveal. Phase 2 plans mb.shortcuts.attach() and its queue in the eager plugin-sdk.js (spec:1322-1323).

## Notes

Deferred, waiting on the separate session re-measuring what startup JavaScript costs, which will reset the startup_script_transfer_kb gate in explorations/performance-loop/performance-budgets.toml from that measurement (the user's direction: do not change the budget here).

Done in PR #379 on the user's direction: restored the @type annotations f168ccae dropped (6b94b4ff); moved layer 3 code that cannot act before the registry out of the eager scripts (6b94b4ff: pane, filter bar, and copy read in shell-keymap.js; d6e65fe2: lent Copy into MetabrowserShellKeymap.attachHeaderCopy(), selector handle into MetabrowserSourceRefSelector.mounted()); restored the comments f168ccae trimmed for bytes (89431194).

Figures (gzip level 6; app.js / plugin-sdk.js / check_startup_scripts total, headroom): base 6531296 90,431 / 16,872; 9129aac 91,311 / 16,997 / 179,597, 114 under; 6fb23e7d 91,262 / 16,968 / 179,519, 192 under; 89431194 91,728 / 17,040 / 180,057, 346 over. At 89431194, make lint-check fails only check_startup_scripts, and tests/test_check_startup_scripts.py fails 9 tests for the same reason.

Eager layer 3 code that remains: view tab bar role/aria-selected/data-view-key and data-kbd-badge-anchor markup; selectPreviewTab() and toggleFilterMenu() (shared with clicks); shellKeymapShell()'s three activation paths; the shellKeymap/keyReveal variables, creation, disposal, and bindShortcuts(null); render-site sync calls; focusFilesRow; plugin-sdk.js copyFromControl() around its private copy delegate. Phase 2's eager attach() queue in plugin-sdk.js depends on the same budget decision (spec 7adc990a on claude/shift-key-reveal-spec).
