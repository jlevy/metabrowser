---
type: is
id: is-01m3w45xk0kkbxtrnhwqbzhb1s
title: "Displayed Git paths and refs: replace Unicode spaces and separators, restore display speed, and escape the serve banner's ref"
kind: bug
status: in_progress
priority: 2
version: 3
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
created_at: 2026-10-01T16:18:53.138Z
updated_at: 2026-10-01T16:19:10.067Z
started_at: 2026-10-01T16:19:10.060Z
---
From the independent review of PR #244 (2026-10-01), at the stack tip 373b59a9. (1) display_segment (src/metabrowser/git/tree_source.py:181-190) and hidden_at (src/metabrowser/invisible_chars.py:79-95) leave 18 Unicode space and line-separator characters raw (U+00A0, U+1680, U+2000-U+200A, U+2028, U+2029, U+202F, U+205F, U+3000), though the URL reducer refuses them raw as whitespace and its own hint leads a user to the encoded form: 'metab .../blob/topic/README%E2%80%8A.md --no-serve' prints a name that reads as README.md, and %E2%80%A8 puts a raw U+2028 in the error line, which splits the line for a consumer that honours Unicode line breaks. Fix: also replace Zs/Zl/Zp other than the ASCII space; add golden lines for %C2%A0, %E2%80%8A, %E2%80%A8. Decide and state what happens to unassigned and private-use code points, which the reducer refuses raw and display prints. (2) display_segment is about 6-11x slower on a name with any non-ASCII character than before #244 (156-172 ns/char -> 1,680-1,859 ns/char; back-to-back pairs), called once per entry in the rollup and listings (git/content_routes.py:159,761,778; up to INVENTORY_MAX_FILES). Fix: precomputed frozensets tested before hidden_at; the reviewer's variant was 8-10x faster than the tip with zero output mismatches over every code point in four contexts. Record the measurement beside the code. (3) Pre-existing: the serve banner prints a URL-selected ref raw (src/metabrowser/cli/git_pin_cli.py:529-539, f'Revision: {revision}'), while the 'pin:' line goes through display_segment; is_valid_ref_name accepts names with a C1 CSI or an invisible character, so a hostile repository's branch name reaches the terminal. Fix: pass it through the same display path. Each fix needs a test that fails without it.
