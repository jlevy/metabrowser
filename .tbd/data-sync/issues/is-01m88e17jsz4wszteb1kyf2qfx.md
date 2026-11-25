---
type: is
id: is-01m88e17jsz4wszteb1kyf2qfx
title: Killed test processes leave small temp dirs pytest never prunes
kind: task
status: open
priority: 3
version: 1
labels: []
dependencies: []
parent_id: is-01m2gb3gpn7vcsw0as4xa243tg
created_at: 2026-11-25T04:04:45.776Z
updated_at: 2026-11-25T04:04:45.776Z
---
Found while measuring for mb-rsyh (PR #819). These live outside pytest's basetemp, so its retention policy never reaches them. Each is small but they accumulate in $TMPDIR across runs:
- empty com.google.Chrome.* singleton dirs left when a test Chrome is SIGKILLed (about 2,200 seen);
- leftover metab-test-chrome-* profiles (3 seen, 19.5 MiB);
- empty metabrowser-git-history-* dirs from the TemporaryDirectory in src/metabrowser/git/history.py when a server is killed (143 seen);
- metabrowser-parity-* dirs from devtools/check_parity.py (62 seen, 13 MiB);
- tryscript-* dirs (26 seen, 3.5 MiB).
Done when each source either cleans up on the kill paths the suite uses or writes under a directory the suite removes, with a test for each that it fixes.
