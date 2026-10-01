# GitHub Coverage Oracle

This directory contains reduced, scrubbed structural evidence from public GitHub API
responses. It answers whether GitHub can supply each field in the provider-neutral
hosted-review mapping.
It is not a provider payload model, a runtime input, a replay cassette, or a conformance
corpus.

`manifest.json` records the exact public request and every reduction or scrub applied to
the checked-in response.
`field-inventory.json` is the closed mapping inventory.
Its field evidence resolves each observed or derived common field to an exact response
or request JSON pointer, validated normalized input, or existing Git-history input.
It also records disposition-specific value evidence, distinguishes current consumers
from planned ones, and gives executable recipes for canonical and relationship IDs.
`hostile-synthetic.json` is deliberately synthetic so adversarial strings never acquire
the status of recorded provider evidence.

The dedicated `test_github_coverage.py` check reads these files without a network.
It enforces exact reduced-response shapes, request-to-response GraphQL roots, strict
JSON Pointers, public URL allowlists, and secret/private-data hygiene across every
non-synthetic file in this directory.
The wheel packages only `src/metabrowser`, so the oracle is absent from installed
artifacts and runtime imports.
The source distribution may contain the directory as repository test evidence;
production code must never read it.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
