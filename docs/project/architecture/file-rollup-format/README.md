# File Rollup Format in This Repository

**Status:** Built. Metabrowser is the reference implementation of
[File Rollup Format v0.1](file-rollup-format.md), and this directory holds the format
and a generated copy of its recommended definitions.

[`file-rollup-format.md`](file-rollup-format.md) defines the application-independent
classification and aggregation contract.
[`recommended-file-types.toml`](recommended-file-types.toml) is a generated copy of the
packaged source at
`src/metabrowser/data/file-rollup-format/recommended-file-types.toml`. Edit the packaged
source, never the copy.

## Changing the Definitions

For a definitions-only change, increment `registry_revision` in the packaged TOML. Use
the version boundaries in the format’s [Evolution](file-rollup-format.md#evolution)
section when a change affects the registry structure, a serialized component, or the
overall rollup semantics.
Stable IDs are compatibility keys and are never reassigned to a different meaning.

Regenerate the documentation copy, projected registry, conformance corpus, and empty
example after changing the definitions or their reference behavior:

```shell
uv --config-file uv.toml run --frozen python devtools/file_type_contract.py --write
```

Review every generated diff, then run the checker without a mode to prove that every
checked artifact matches the source and validates against its JSON Schema:

```shell
uv --config-file uv.toml run --frozen python devtools/file_type_contract.py
uv --config-file uv.toml run --frozen pytest \
  tests/test_file_type_contract.py \
  tests/test_file_type_registry.py \
  tests/test_file_type_taxonomy_js.py
```

A family’s hue, its `linguist` provenance, and any declared deviation follow the rules
in the design system’s [File-Type Colors](../../../design-system.md#file-type-colors),
which `devtools/check_file_type_colors.py` holds in `make lint`.

## Exporting a Packet

To hand the format to another implementation, export a self-contained packet into an
explicit destination and record the reviewed source revision:

```shell
uv --config-file uv.toml run --frozen python devtools/file_type_contract.py \
  --export /explicit/destination/file-rollup-format \
  --source-revision SOURCE_GIT_REVISION

uv --config-file uv.toml run --frozen python devtools/file_type_contract.py \
  --verify /explicit/destination/file-rollup-format
```

Export replaces stale packet contents and verifies the result.
The manifest pins the source revision, registry schema and data revisions, normalized
registry fingerprint, exact file list, and SHA-256 digest of every artifact.
Verification rejects unsafe paths, symbolic links, missing or extra content, duplicate
entries, and hash mismatches.
The packet has no network, sibling-repository, or package-import dependency: the format
document, recommended definitions, schemas, conformance cases, and empty example are the
whole adoption boundary.
This README is not part of it.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
