---
type: is
id: is-01m8akjdy146agcfsfcf73v201
title: "Proposal: a Docs view for .lean files (doc-gen4 style, from source alone)"
kind: feature
status: open
priority: 3
version: 1
spec_path: docs/project/specs/active/plan-2026-11-25-lean-language-support.md
labels: []
dependencies: []
parent_id: is-01m8ahev7t0174z3a2vhhnpw81
created_at: 2026-11-26T00:20:01.089Z
updated_at: 2026-11-26T00:20:01.089Z
---
A built-in lean plugin view beside Source: module doc (/-! -/) and declaration doc comments rendered through KPress (Markdown + math), declarations listed with attributes, kind, name, and signature, each linking to its #Lstart-Lend range in Source. Modeled on doc-gen4's page layout (mathlib4_docs). Needs no .olean files or Lean toolchain. Not scheduled: awaiting the owner's decision. See the plan's Lean's Documentation Tools section.
