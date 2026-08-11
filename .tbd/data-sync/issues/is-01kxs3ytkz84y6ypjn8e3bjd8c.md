---
type: is
id: is-01kxs3ytkz84y6ypjn8e3bjd8c
title: Remove ELK.js from generic core after plugin ownership migration
kind: bug
status: closed
priority: 1
version: 2
labels: []
dependencies: []
created_at: 2026-07-17T22:43:06.494Z
updated_at: 2026-08-11T16:57:07.372Z
closed_at: 2026-08-11T16:57:07.371Z
close_reason: "Already resolved in v0.1.1: ELK.js was removed from core, third-party browser assets are vendored, and the index-origin tests verify that no external CDN is loaded."
---
MetaBrowser v0.1.0 loads elkjs@0.10.0 from jsDelivr for every install even though generic core does not consume window.ELK. Remove the ELK URL from optional_script_assets, add a boundary test that index HTML contains no elkjs or elk.bundled.js reference, update the changelog, and publish a patch release. Layout consumers must ship ELK through their own packaged plugin assets in manifest order.
