---
type: is
id: is-01kxhw35zc74apb3vwkmn67xjs
title: Implement first-class bounded zlib artifact support
kind: feature
status: open
priority: 1
version: 2
spec_path: docs/specs/metabrowser-v0.1.0.md
labels: []
dependencies:
  - type: blocks
    target: is-01kxgmnvg1heqtbjjc3bnz1pxk
parent_id: is-01kxgmkc6gb2e8s23jf409j4bv
created_at: 2026-07-15T03:10:59.563Z
updated_at: 2026-07-15T03:11:03.225Z
---
Add transparent core support for zlib-compressed artifacts without a third-party dependency. Define the supported suffix and wire contract; preserve logical extensions; stream decompression off the event loop; enforce compressed-input, decompressed-output, CPU, preview, render, and export bounds; cover malformed streams and decompression bombs; and keep format-specific binary interpretation in external plugins.
