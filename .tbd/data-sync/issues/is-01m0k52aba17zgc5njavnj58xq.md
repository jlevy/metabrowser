---
type: is
id: is-01m0k52aba17zgc5njavnj58xq
title: Match GitHub's file-type colors where a reader would expect them
kind: task
status: closed
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-08-21-file-type-source-of-truth.md
labels: []
dependencies: []
parent_id: is-01m0k63zme8wetezbbq59ys3k8
created_at: 2026-08-21T21:54:08.361Z
updated_at: 2026-08-21T23:49:45.037Z
closed_at: 2026-08-21T23:49:45.036Z
close_reason: 35 of 56 families carry GitHub's linguist hue unchanged, including where two of GitHub's own colors are close (html/svelte 0.65 deg, ruby/yaml 1.13 deg) — moving a familiar hue to win a distance metric costs more recognizability than it buys.
---
File-type colors should agree with GitHub's where a reader would expect them to. Someone who knows JavaScript is yellow and Go is cyan from every repository page should not have to relearn the vocabulary here.

The source is github-linguist/linguist, `lib/linguist/languages.yml`: every language block carries an optional `color:` field, and that file is what paints GitHub's repository language bar and file icons. Clone it with the standard third-party recipe:

    git clone --depth 1 https://github.com/github-linguist/linguist.git attic/linguist

Measured against our registry (56 families):

- 688 languages in linguist carry a color.
- 38 of our 56 families map to one directly, including every family a reader is likely to recognise: python #3572a5, javascript #f1e05a, typescript #3178c6, css #663399, html #e34c26, go #00add8, rust #dea584, java #b07219, ruby #701516, php #4f5d95.
- 18 need house colors because they are not languages: plain-text, pdf, word, rich-text, open-document, epub, parquet, arrow, avro, orc, protocol-buffers, sqlite, archives, images, videos, audio, fonts, log-files.

Two things to decide rather than assume:

Linguist's colors were not chosen for a dark theme or for contrast against our surfaces. JSON is #292929 and Lua is #000080, both near-black; several are close in hue at small sizes. This repository states every color in oklch with no hue drift between themes, so adopting a hex list wholesale would break that. The likely shape is: take linguist's hue as the identity, then fit lightness and chroma to our own ramp per theme, so a family is recognisably GitHub's color while still legible on both surfaces.

Licensing: linguist is MIT, and the color list is data rather than code, but the derivation should be recorded in NOTICE.md the way other third-party material is.

Depends on the palette becoming identity-based rather than slot-assigned: see the sibling bead. Colors keyed to a language mean nothing while a family's color is decided by a hash and a pool of twelve.
