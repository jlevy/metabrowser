---
type: is
id: is-01m87kjamkxy7hpkk0dyj5f737
title: Write Metabrowser's threat model and derive its security policies from it
kind: epic
status: closed
priority: 1
version: 6
delegate: claude-code@spud10.local
labels: []
dependencies:
  - type: blocks
    target: is-01m87krme84dgxwmvhz446663e
  - type: blocks
    target: is-01m87ks05m6tw50mvp4v4s19f8
child_order_hints:
  - is-01m87kraqyx8r1p46h9vn5j2f4
hold: null
hold_until: null
created_at: 2026-11-24T20:22:14.413Z
updated_at: 2026-11-24T22:14:39.375Z
started_at: 2026-11-24T21:44:50.382Z
closed_at: 2026-11-24T22:14:39.371Z
close_reason: "arch-threat-model.md, PR #797"
resolution: null
duplicate_of: null
---
A clear threat model that the security policies follow from. Assets: the reader's local files, the API and its mutations, the macOS app's privileges (opening files, the host descriptor), credentials Metabrowser reaches (gh), and the cache. Adversaries: authors of browsed content (a malicious repository, pull request, or file in a folder), a network observer of --remote serving, other local processes and users, and a malicious or compromised plugin. Trust boundaries and entry points: the trusted and untrusted profiles, /raw and its sandbox, the shell's content policy, the Markdown sanitizer, the API origin proof, the app's isolated content world and open-file bridge, server-side parsing of browsed bytes. For each threat: the policy that answers it, the evidence (test or golden) that holds it, and the residual risk accepted, with the reason. Lands as an architecture document linked from SECURITY.md and arch-server-and-content.md's Content Trust Model; every later policy change cites the threat it answers.
