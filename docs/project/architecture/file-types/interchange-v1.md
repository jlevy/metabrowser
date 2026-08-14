# File-Type Interchange v1

The interchange contract defines JSON-compatible values shared by Metabrowser’s Python
server, browser SDK, captured fixtures, and future `fdu` Rust, CLI, and Python outputs.
It does not require one wire envelope: applications can send a registry projection once
and many directory breakdowns later, or bundle both in a standalone report.

## Shared Scalar Rules

- IDs are lowercase registry IDs and are compared exactly.
- Extensions include the leading dot and are ASCII-lowercase.
- File counts and byte measures are nonnegative integers.
- Apparent `bytes` is required.
  `allocated_bytes` is optional and never changes the required cross-package ranking
  rule.
- Arrays are ordered by the registry or the deterministic ranking rule stated here.
- Absent classification identities use JSON `null`, not empty strings.
- Unknown additive object fields are ignored within schema v1.

## File Facts

`FileFacts` contains filesystem observations independent of classification:

| Field | Type | Requirement |
| --- | --- | --- |
| `basename` | host filename value | Final path component using the host’s lossless filename encoding |
| `logical_extension` | string or null | Result of Registry v1 derivation |
| `apparent_bytes` | nonnegative integer | Logical file length |
| `allocated_bytes` | nonnegative integer or null | Optional physical allocation |
| `ignored` | boolean or null | Metabrowser ignore state; null if the producer has no such scope |

Paths, modification times, ownership, and permissions can remain in the host inventory
but are not file-type classification inputs.

## File Classification

`FileClassification` records one decision without aggregate or UI state:

| Field | Type | Requirement |
| --- | --- | --- |
| `logical_extension` | string or null | Preserved observation |
| `canonical_extension` | string or null | Declared extension that matched |
| `kind_id` | string or null | Stable classifier kind |
| `family_id` | string or null | Optional display family |
| `group_id` | string | Display group; `other` fallback |
| `content_family` | enum | Analyzer class; `unknown` fallback |
| `detection_source` | string | Evidence tier that won |
| `confidence` | string | Producer-defined stable confidence enum |
| `registry_revision` | positive integer | Registry data revision |
| `registry_fingerprint` | string | Normalized registry identity |

Metabrowser uses metadata evidence.
`fdu` can emit more specific classifications using bounded content evidence, but it
preserves the same field meanings and passes all metadata conformance cases.

## Registry Projection

Validated TOML is projected into JSON-compatible runtime data:

```json
{
  "schema": "file-type-registry-v1",
  "schema_version": 1,
  "revision": 1,
  "fingerprint": "normalized-registry-identity",
  "max_extension_components": 2,
  "groups": [
    {"id": "code", "label": "Code", "order": 10}
  ],
  "families": [
    {
      "id": "javascript",
      "label": "JavaScript",
      "group_id": "code",
      "order": 100,
      "extensions": [".js", ".jsx", ".mjs", ".cjs"]
    }
  ],
  "kinds": [
    {
      "id": "javascript",
      "family_id": "javascript",
      "group_id": "code",
      "content_family": "code",
      "extensions": [".js", ".jsx", ".mjs", ".cjs"],
      "filenames": [],
      "shebangs": ["node", "deno", "bun"],
      "priority": 100
    }
  ]
}
```

Projection extensions include leading dots because they are runtime and UI identities.
Array order is authoritative.
Native-only compiled matchers and evidence tables need not be sent to the browser unless
the public SDK promises them.

## Metric Populations

Every breakdown declares named populations.
Every row in that breakdown carries the same keys:

```json
{
  "all": {"files": 150, "bytes": 10485760},
  "unignored": {"files": 145, "bytes": 9437184}
}
```

The portable schema permits named populations.
Metabrowser’s current `/api/rollup` profile emits and validates exactly `all` and
`unignored`. A future standalone `fdu` report can emit `selected` and can also emit
`all` when it retains the denominator.
A host documents the meaning of additional population names.
Each population requires `files` and `bytes`; additive metrics belong in the same
measure object.

## Directory Breakdown

`file-type-breakdown-v1` is the conserved, UI-ready directory hierarchy:

```json
{
  "schema": "file-type-breakdown-v1",
  "registry": {
    "schema_version": 1,
    "revision": 1,
    "fingerprint": "normalized-registry-identity"
  },
  "metrics": {
    "all": {"files": 200, "bytes": 20971520},
    "unignored": {"files": 190, "bytes": 19922944}
  },
  "groups": [
    {
      "id": "code",
      "families": [
        {
          "id": "javascript",
          "metrics": {
            "all": {"files": 150, "bytes": 10485760},
            "unignored": {"files": 145, "bytes": 9437184}
          },
          "extensions": [
            {
              "extension": ".js",
              "metrics": {
                "all": {"files": 150, "bytes": 10485760},
                "unignored": {"files": 145, "bytes": 9437184}
              }
            }
          ]
        }
      ]
    }
  ],
  "no_extension": {
    "metrics": {
      "all": {"files": 20, "bytes": 1048576},
      "unignored": {"files": 18, "bytes": 1048576}
    },
    "filenames": [
      {
        "basename": "Makefile",
        "metrics": {
          "all": {"files": 20, "bytes": 1048576},
          "unignored": {"files": 18, "bytes": 1048576}
        }
      }
    ],
    "others": null
  },
  "remaining_types": {
    "metrics": {
      "all": {"files": 30, "bytes": 9437184},
      "unignored": {"files": 27, "bytes": 9437184}
    },
    "extensions": [
      {
        "extension": ".bin",
        "metrics": {
          "all": {"files": 30, "bytes": 9437184},
          "unignored": {"files": 27, "bytes": 9437184}
        }
      }
    ],
    "others": null
  }
}
```

Labels and ordering come from the matching registry projection.
Empty groups are omitted.
Group nodes are structural and do not repeat metrics.
No extension and Remaining types use named root members because their children have
different keys; the registry places both under Other when rendered.

## Breakdown Types

| Type | Required fields | Meaning |
| --- | --- | --- |
| `FileTypeBreakdown` | `schema`, `registry`, `metrics`, `groups`, `no_extension`, `remaining_types` | One complete directory partition |
| `FileTypeGroupBreakdown` | `id`, `families` | Ordered nonempty display section |
| `FileTypeFamilyBreakdown` | `id`, `metrics`, `extensions` | Semantic parent and complete extension children |
| `FileTypeExtensionBreakdown` | `extension`, `metrics` | Canonical or preserved logical extension child |
| `FileTypeFallbackBreakdown` | `metrics`, typed children, `others` | One bounded special parent |
| `FileTypeOthersBreakdown` | `metrics`, `omitted_distinct_values` | Exact remainder, never a claimed type |

An implementation can use compact native counters internally.
These names define responsibilities and serialized meaning, not generated source
sharing.

## Conservation

For each emitted population and metric:

1. Root equals every family parent across all groups plus No extension plus Remaining
   types.
2. Each family equals all emitted extension children.
   Family children are complete and never capped.
3. No extension equals its at most 20 basename children plus optional Others.
4. Remaining types equals its at most 20 raw-extension children plus optional Others.
5. Each file contributes to exactly one root partition row.
6. Children explain their parent and are not added again at the root.

Changing visible population selects another emitted measure.
It does not fetch another crawl or change which bounded children are present.

## Bounded Child Selection

No extension basenames and Remaining types extensions use one deterministic ranking.
For each candidate, calculate its file-count and apparent-byte share in every emitted
population. Rank by:

1. greatest share across those measures;
2. greatest byte share;
3. greatest file share; and
4. stable key.

Keep at most 20 candidates.
Others contains the exact sum of all omitted candidates and their
`omitted_distinct_values` count.
Optional allocated bytes do not affect ranking, so a consumer implementing only required
metrics selects the same children.

The default and hard maximum are 20. A lower requested limit, including zero, remains
valid if Others conserves the omitted metrics.

## Filename Encoding

Metabrowser uses its safe wire-path encoding.
`fdu` retains native filenames internally and uses its established lossless
machine-output encoding.
A basename child must round trip through its host envelope; replacing undecodable values
or merging distinct native names is invalid.

Human renderers can use a display-safe representation but must not expose that string as
the machine key.

## Host Envelopes

Metabrowser can publish the registry once in bootstrap settings and return only registry
identity with each rollup.
A standalone `fdu` report can bundle both:

```json
{
  "schema": "fdu-report-vN",
  "file_types": {
    "registry": {"schema": "file-type-registry-v1"},
    "breakdown": {"schema": "file-type-breakdown-v1"}
  }
}
```

A consumer rejects or refreshes a breakdown whose registry revision or fingerprint does
not match its loaded projection.
It never guesses labels or membership from IDs alone.

## Conformance Corpus

The checked `src/metabrowser/data/file-types/conformance-v1.json` corpus contains three
fixture classes:

- exhaustive metadata cases containing basename, expected logical and canonical
  extension, kind, family, group, content family, detection source, and confidence; and
- invalid TOML declarations with stable expected error codes; and
- aggregate cases containing file facts and one exact expected Breakdown v1 value.

Required metadata cases cover every declaration, uppercase suffixes, dotfiles, one- and
two-component limits, longer dotted names, exact compound precedence, suffix fallback,
JSON versus JSON Lines, SVG, C/C++, extensionless files, and unknown extensions.

Invalid cases cover every Registry v1 validation class with an expected stable error
code. Human error text can be package-specific, but the code and offending declaration
identity agree. Aggregate cases include an empty directory and a mixed, high-cardinality
directory that exercises semantic families, ignored populations, both 20-child caps, and
exact Others remainders.
The contract tool validates every expected aggregate against `breakdown-v1.schema.json`
before publishing or exporting it.

## Versioning

Unknown schema IDs and structural versions fail closed.
Additive object fields are ignored within v1. Removing or redefining a field, changing
conservation, changing required ranking, or changing identity semantics requires a new
schema version.

A registry revision can change declarations without changing these interchange
structures. Every captured report records both registry and interchange identities.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
