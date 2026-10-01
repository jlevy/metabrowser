---
type: is
id: is-01m3w60d071bqfnktbsvz03908
title: "First clone prints no destination and no progress: a large repository looks hung"
kind: bug
status: closed
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
delegate: claude-code@spud10.local
labels:
  - release:v0.12.0
dependencies:
  - type: blocks
    target: is-01m2k713pxra1ns2fk3pcwrpb6
parent_id: is-01m36k3w9vgwy97c9hcj2sqrs5
hold: null
hold_until: null
created_at: 2026-10-01T16:50:49.469Z
updated_at: 2026-10-01T20:24:36.128Z
started_at: 2026-10-01T16:50:55.203Z
closed_at: 2026-10-01T20:24:36.126Z
close_reason: "PR #261: a first clone names its destination (the cache directory, with ~), shows progress while it runs (redrawn in place on a terminal; a line at most every 10 s otherwise), says when it is done, and a cache hit prints one line in serve and --no-serve modes; --show, --api and --check-api stay silent on a hit; all on stderr. Only Git's exact progress shape passes, as a stage name and numbers. Independent review: no P0/P1; four P2s fixed (exit status with a closed stderr, debug logging of Git's text escaped, a loosened no-leak test restored, wiring pinned) and the P3s (remote-spoofed size, blocking writes, lazy import). All mutations caught. CI green. Not done: the first gh read for a pull-request URL is still silent until the banner."
resolution: null
duplicate_of: null
---
Reported by the user 2026-10-01 running the stack tip (373b59a9) as the global metab: 'metab https://github.com/jlevy/squares' printed 'cloning https://github.com/jlevy/squares: reading the default branch (1.3 s)' and 'cloning ...: fetching every object (2.1 s)' and then nothing for about 100 seconds while 740 MB arrived; the user took it for hung. Two gaps. (1) The lines never say where the clone goes. Say the destination once, at the start, as a path the user can act on (the application home, abbreviated with ~ where it is under the home directory), for example 'cloning https://github.com/jlevy/squares into ~/.metabrowser/cache/...'. Route and JSON responses must still never carry a store path (the existing no-leak tests stay); this is the user's own terminal. (2) No running progress during the fetch. Print progress while it runs: bytes or objects received and elapsed time, rewritten in place on a TTY and as occasional whole lines (every several seconds, measured) when stderr is not a TTY, so logs stay short. Take the numbers from what the acquisition already observes for its stall bound, or from git's own --progress output; do not poll the directory with a tree walk. Also say when it is done and what happens next (indexing, then the address being served), so there is no silent gap between the fetch ending and the browser opening. Code: src/metabrowser/cli/acquire_cli.py:120 (the echo), src/metabrowser/cache/acquire.py:358 and :405 (the phases). Acceptance: an in-process golden for a file:// acquire showing the destination line and the completion line; a test with a slow stand-in fetch showing periodic progress lines on a non-TTY and that a TTY rewrite does not flood; --no-serve, --show, --api and serve all show it on first acquire and stay quiet on a cache hit; no store path appears in any --api envelope. Related, seen the same day: a cache hit should say it is opening from the cache (one line) so a second run is visibly different from a first.
