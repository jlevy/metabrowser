---
type: is
id: is-01kxs0qax5mms717byf9e3sxbc
title: Recognize signed percentages as numeric table cells
kind: bug
status: in_progress
priority: 2
version: 2
labels:
  - ui
dependencies: []
created_at: 2026-07-17T21:46:35.300Z
updated_at: 2026-07-17T21:46:42.105Z
---
Automatic numeric alignment in rendered Markdown tables handles some signed values such as +12% but misses values such as the Unicode-minus form −45.1%. Treat strict numeric strings as numeric when they use ASCII plus/minus or Unicode minus, optional decimal/group separators, and an optional percent suffix, while rejecting mixed text and malformed punctuation.
