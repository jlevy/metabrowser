---
type: is
id: is-01m7b26fbed9w4tnxv32mcggf9
title: "Keyboard shortcuts: letters for known meanings, numbers for one-offs, none on ancillary items"
kind: feature
status: closed
priority: 1
version: 7
labels: []
dependencies: []
created_at: 2026-11-13T18:19:56.137Z
updated_at: 2026-11-13T20:41:12.653Z
closed_at: 2026-11-13T20:41:12.652Z
close_reason: "Merged in #402: letters for known meanings (F/R/H main tabs, V/S views, J/K, N/P, U), numbers 1-9 by place for situational items, no ancillary keys, Shift reveal fade with --motion-reveal and reduced motion, one Keyboard Shortcuts reference. Follow-up: mb-ndcc."
resolution: null
duplicate_of: null
---
The user, 2026-11-13: refine the keyboard shortcuts. (1) No shortcuts on ancillary items such as copying a hash. (2) Shortcuts on major tabs and major buttons wherever possible. (3) A fairly consistent set of letters for common tabs or buttons (letters for known meanings); numbers for one-off actions that don't fit known patterns. (4) Main tabs: 1 -> F for Files, 2 -> H for commit History, 3 -> P for Pull requests. The keymap is in static/keymap.js, main-tabs.js, and the plugin shortcut surface (#383, PR tabs C/G/H); spec in docs/project/specs/done/plan-2026-11-11-shift-key-reveal-and-keymap.md. Resolve letter collisions (e.g. H) with one documented scheme.

## Notes

2026-11-13, the user: J/K and N/P are reusable semantics (vim-like): J/K always down/up, N/P always next/previous at a higher level. Asked P = Pulls vs P = previous, the user chose P = previous; the Pulls tab gets another letter (to be proposed and confirmed). F = Files and H = History stand. Tab order Files, Pulls, Commits (mb-y7py).


2026-11-13, the user: Pulls = U or R; coordinator chose R (U is the shell Parent folder key, a reusable "up" meaning). Main tabs F = Files, R = Pulls, H = History, ordered Files, Pulls, Commits. The R view keys (agent_log and unknown_jsonl Raw JSON, structured Tree) move to free letters. Y (copy path/revision) proposed for removal as ancillary.


2026-11-13, the user: U stays Up (Parent folder), so Pulls = R. Situational items (links, one-off actions) get numbers 1-9 in sequence by visual order, and stop at 9 (nothing past the ninth gets a key). Letters for known meanings; ancillary actions get no key.


2026-11-13, the user: the help must make clear 1-9 are not fixed. Help shows one positional entry for the digits (the numbered items on this screen, in order), generated from a registry flag, with a test that no digit has a fixed meaning in the help.


2026-11-13: the user confirmed the #402 key table as proposed ("Looks good"): F/R/H main tabs (order Files, Pulls, Commits), V for rendered views and S for source/Raw JSON, Checks E, Y removed, filters and PR header links numbered 1-9 by place.
