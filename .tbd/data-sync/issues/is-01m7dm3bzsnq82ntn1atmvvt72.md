---
type: is
id: is-01m7dm3bzsnq82ntn1atmvvt72
title: "Sans-serif Markdown: consistent space above and below headings"
kind: bug
status: in_progress
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m7dm3az28qmj39y5hmdq2k0v
created_at: 2026-11-14T18:11:17.624Z
updated_at: 2026-11-14T18:11:20.059Z
---
The user (2026-11-14): "For formatted Markdown content that is sans-serif like PR descriptions the padding around h2s and at the top of the text is inconsistent, especially around h2s at the top of a section, there is too little space above the h2s. Let's understand why their spacing seems inconsistent and try to be as simple as possible without any hacks. Make sure that there's appropriate space above headers when blocks of text appear like this, and below headers. Make sure that the spacing is relatively consistent with the serif, but that we depart where necessary when it comes to more Chrome-like text (like PR descriptions or any areas where we are using sans-serif-formatted Markdown)."

Done when the cause of the inconsistency is explained (margin collapsing, a first-child rule, a section wrapper, or KPress defaults), headings in sans-serif Markdown have consistent space above and below (including a heading at the top of a section and after a block of text), measured in Chrome and WebKit, the rule is one simple CSS change consistent with the serif document scale except where sans needs its own values, the design system documents it, and a test pins it.
