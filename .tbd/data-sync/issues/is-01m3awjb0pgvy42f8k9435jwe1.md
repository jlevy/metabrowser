---
type: is
id: is-01m3awjb0pgvy42f8k9435jwe1
title: Path errors print default-ignorable characters such as U+3164 raw
kind: bug
status: in_progress
priority: 4
version: 2
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
delegate: claude-code@spud10.local
labels:
  - release:v0.12.0
dependencies: []
parent_id: is-01m36k3w9vgwy97c9hcj2sqrs5
hold: null
hold_until: null
created_at: 2026-09-24T23:38:46.165Z
updated_at: 2026-09-24T23:49:52.541Z
started_at: 2026-09-24T23:49:52.540Z
---
Found in the v0.12 acceptance rerun on PR #243 (head 7d91c8f4, installed wheel 0.11.1.dev412+7d91c8f4), row M02b.

The reducer now refuses a raw default-ignorable character in a GitHub URL (U+3164, for example) and names its encoded spelling, and display_segment replaces format characters (Cf) with U+FFFD. U+3164 HANGUL FILLER is category Lo, not Cf, so display_segment passes it through. Following the refusal's own hint prints it raw:

  metab 'https://github.com/jlevy/metabrowser/blob/main/README%E3%85%A4.md' --no-serve
  Error: README<U+3164>.md is not in https://github.com/jlevy/metabrowser at main (path_not_found)

In most fonts U+3164 renders blank, so the message reads like 'README .md' or 'README.md', the confusion the reducer refusal exists to prevent. The same encoded URL for U+202E prints U+FFFD, as intended.

Cause (inferred): display_segment in src/metabrowser/git/tree_source.py checks only C0, DEL, C1, and category Cf, not the Default_Ignorable_Code_Point set the reducer uses.

Acceptance: display_segment also replaces the reducer's default-ignorable set (and U+2800 if intended), and the URL golden pins the path_not_found line for README%E3%85%A4.md.
