---
type: is
id: is-01m76cd12z5wpxyzfqnwtn3zvr
title: Swift app code meets the tbd coding guidelines
kind: task
status: open
priority: 1
version: 14
spec_path: docs/project/specs/active/plan-2026-11-10-native-macos-app.md
labels: []
dependencies:
  - type: blocks
    target: is-01m76cd0j37s7vbfjfwtw1ey7n
  - type: blocks
    target: is-01m76h3hdcp0ek254274recmn5
  - type: blocks
    target: is-01m748xtr995frd3pgx5zbq2nt
  - type: blocks
    target: is-01m76cd1gt43frv3avt96fwqhh
  - type: blocks
    target: is-01m74919x10s489egs2q6hfn22
  - type: blocks
    target: is-01m75sajkrdqname9cgrtcf9jf
  - type: blocks
    target: is-01m75sahhp1nbm15h57bjb9bvp
  - type: blocks
    target: is-01m75saj4h7s3trg7kt812fbya
  - type: blocks
    target: is-01m748xta3y5hxhf6kx1n8psja
  - type: blocks
    target: is-01m76cd1ysrge9arg7a773j3ff
  - type: blocks
    target: is-01m748xs18re0g14ge32270n3e
  - type: blocks
    target: is-01m748xswj3y4wnc6bfb60kmp6
parent_id: is-01m748xpx7bjg68tfaf3q4nxmj
created_at: 2026-11-11T22:42:04.510Z
updated_at: 2026-11-12T00:04:27.469Z
---
No Swift guideline exists in tbd, so apply the language-neutral ones to apps/macos: general-coding-rules, general-comment-rules, error-handling-rules (no swallowed errors; preserve causes; handle only what the layer can), general-testing-rules and general-tdd-guidelines (decision logic in ShellCore with tests; app-target code thin), filesystem-rules (atomic writes, safe paths), release-engineering-rules and supply-chain-hardening for scripts, backward-compatibility-rules (no speculative layers). Record anything deliberately left, with its reason, in apps/macos/README.md.
