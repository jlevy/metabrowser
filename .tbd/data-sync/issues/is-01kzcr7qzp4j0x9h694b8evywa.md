---
type: is
id: is-01kzcr7qzp4j0x9h694b8evywa
title: "Chrome typography: sans file paths and a keyboard-key component"
kind: epic
status: closed
priority: 1
version: 7
labels: []
dependencies: []
child_order_hints:
  - is-01kzcr84h6v3y8hdksmk3y5vwq
  - is-01kzcr84s67b3vq28xt30z9fgn
  - is-01kzcr8h2zz8xvdvspzn0aq7vk
  - is-01kzcr8har7zzndq9vtnz0xb1e
  - is-01kzcrhppdvvskvzy5g38vycs1
created_at: 2026-08-06T23:58:46.261Z
updated_at: 2026-08-07T00:10:02.186Z
closed_at: 2026-08-07T00:10:02.185Z
close_reason: All child beads complete.
---
Design-system pass over Metabrowser chrome, from review of the Quick File palette (PR #22).

Two rules are currently violated in several places:

1. File paths in chrome — including parent/ancestor path segments — must use the sans UI face, in the same style the Navigator and other chrome use. Several surfaces render them monospaced.
2. Key names and other suggestion text in chrome must be sans, not monospace, and keyboard keys need one consistent component rather than ad-hoc text.

Keyboard keys get a real design-system component: always ALL CAPS, bold, with a thin consistent border. Applied rigorously everywhere a key is shown.

Rendered code and structured document content (code blocks, Markdown inline code, raw log JSON, syntax-highlighted source) stay monospaced. This is about chrome, not content.
