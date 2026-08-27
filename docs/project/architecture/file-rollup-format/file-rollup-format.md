# File Rollup Format

**Status:** Implemented draft standard, format version v0.1

The File Rollup Format is a small, reusable format for classifying files and reporting
directory totals by file type.
It gives command-line tools, libraries, services, and user interfaces the same
deterministic hierarchy for file counts, byte totals, semantic file families, exact
extensions, extensionless files, and unknown types.

The format separates three concerns:

- **type definitions** describe known groups, families, kinds, and matching evidence;
- **classification** assigns one file to those definitions without adding aggregate or
  presentation state; and
- **rollups** conserve counts and byte measures across groups, families, exact
  extensions, and bounded fallback rows.

The format does not prescribe a user interface, report envelope, programming language,
filesystem crawler, or storage engine.
An implementation can render tables or charts, emit JSON or YAML, retain native typed
values, or embed the values in a larger report.

## Version Model

File Rollup Format v0.1 versions the overall semantics in this document: observations,
classification, hierarchy, conservation, deterministic bounding, and compatibility
rules.

The recommended type definitions are versioned separately.
Updating a language, extension, label, or semantic family does not require a new File
Rollup Format version.
The recommended definitions carry their own schema version, data revision, and
normalized fingerprint so producers and consumers can prove that they used the same
taxonomy.

The current JSON components retain these established schema identifiers:

| Component | Schema identifier | Clear artifact name |
| --- | --- | --- |
| Type-definition projection | `file-type-registry-v3` | `recommended-file-types.json` |
| Directory rollup | `file-type-breakdown-v1` | `file-rollup.schema.json` |
| Conformance cases | `file-type-conformance-v1` | `file-rollup-conformance.json` |

The component identifiers are wire compatibility values, not the File Rollup Format
version. Their filenames state their purpose and do not repeat an ambiguous version
suffix.

## Concepts

- **File facts:** Filesystem observations used for classification and aggregation,
  including basename, logical extension, apparent bytes, optional allocated bytes, and
  optional ignore state.
- **Logical extension:** A normalized extension of at most two dotted components,
  derived from the final basename.
- **Kind:** The most specific stable classifier identity, such as JavaScript, JSON
  Lines, or an archive container.
- **Display family:** A user-facing aggregate that can contain several kinds or
  extensions, such as JavaScript, C/C++, Log files, or Images.
- **Display group:** An ordered top-level section such as Code, Documentation, Data,
  Archives, Media, or Other.
- **Content family:** An analyzer-oriented identity such as code, prose, markup, data,
  binary, or unknown. It is independent of display placement.
- **Population:** A named set of files measured by one rollup, such as `all`,
  `unignored`, or `selected`.
- **Measure:** Nonnegative file and byte totals for one population.
- **Rollup:** A conserved directory partition containing totals, groups, families, exact
  extension children, extensionless basenames, and other extensions.

A file can therefore have an SVG kind and markup content family while appearing under
the Images display family and Media group.
JSON Lines can retain a data content family while appearing under Log files.

## Format Artifacts

The format directory is self-contained for reading and reuse:

| Artifact | Purpose |
| --- | --- |
| `file-rollup-format.md` | Overall File Rollup Format v0.1 contract |
| `recommended-file-types.toml` | Recommended, independently versioned type definitions |

A reference implementation can additionally publish these machine-readable artifacts:

| Artifact | Purpose |
| --- | --- |
| `file-type-registry.schema.json` | JSON Schema for a projected type registry |
| `recommended-file-types.json` | Generated projection of the recommended TOML definitions |
| `file-rollup.schema.json` | JSON Schema for one directory rollup |
| `file-rollup-conformance.schema.json` | JSON Schema for the shared conformance corpus |
| `file-rollup-conformance.json` | Metadata, invalid-definition, and aggregate cases |
| `empty-file-rollup.json` | Small valid example for an empty directory |

The Markdown contract and recommended TOML listing can move together into a standalone
repository later. Paths and package names are not part of the standard.

## Recommended File-Type Definitions

[`recommended-file-types.toml`](recommended-file-types.toml) is the recommended listing
of common file groups, families, kinds, extensions, exact basenames, and interpreter
aliases. It is useful as a shared default, but it is not frozen to File Rollup Format
v0.1.

An implementation can:

- use the recommended definitions unchanged;
- add or replace definitions under a new registry revision and fingerprint; or
- use another registry that satisfies the same structural and classification rules.

Every rollup identifies the registry that produced it.
A consumer must not combine a rollup with labels or membership from a different registry
identity.

### TOML Shape

The recommended source uses standard TOML with top-level scalars and ordered arrays of
tables:

```toml
schema_version = 3
registry_revision = 1
max_extension_components = 2

[[group]]
id = "code"
label = "Code"
order = 10

[[family]]
id = "javascript"
label = "JavaScript"
group = "code"
order = 100
linguist = "JavaScript"
linguist_color = "#f1e05a"
hue = 102.08

[[kind]]
id = "javascript"
family = "javascript"
content_family = "code"
extensions = ["js", "jsx", "mjs", "cjs"]
filenames = []
shebangs = ["node", "deno", "bun"]
priority = 100

[[kind]]
id = "build-file"
group = "code"
content_family = "code"
extensions = []
filenames = ["makefile", "dockerfile"]
shebangs = []
priority = 100

[[kind]]
id = "json-lines"
family = "log-files"
content_family = "data"
extensions = ["jsonl", "ndjson"]
filenames = []
shebangs = []
priority = 100
```

### Root Fields

| Field | Type | Requirement |
| --- | --- | --- |
| `schema_version` | positive integer | Definition-file structure; `3` for the recommended listing |
| `registry_revision` | positive integer | Monotone data revision included in projections and cache identity |
| `max_extension_components` | positive integer | `2` for this format profile |

Changing the definition-file structure or a field’s meaning requires a new registry
schema version. Adding, removing, relabeling, or reassigning declarations increments the
registry revision.
Neither change automatically changes File Rollup Format v0.1: a rollup
records the registry schema version it was produced under, and the rollup schema accepts
any of them.

### Group Fields

| Field | Type | Requirement |
| --- | --- | --- |
| `id` | string | Stable lowercase identifier matching `[a-z][a-z0-9-]*` |
| `label` | string | Nonempty human label |
| `order` | integer | Deterministic order, unique among groups |

The recommended order is Code, Documentation, Data, Archives, Media, and Other.
Other contains deliberately miscellaneous families such as Log files and the structural
No extension and Other types parents.
It should not absorb an ordinary known family merely to avoid making a taxonomy
decision.

### Family Fields

| Field | Type | Requirement |
| --- | --- | --- |
| `id` | string | Stable aggregate identity |
| `label` | string | Nonempty human label |
| `group` | group ID | Existing display group |
| `order` | integer | Deterministic order within the group |
| `hue` | number | Family color as an oklch hue, in `[0, 360)` degrees |
| `linguist` | string or absent | Language in GitHub’s linguist the hue was taken from |
| `linguist_color` | hex string or absent | That language’s upstream color; present exactly when `linguist` is. Provenance for the hue, and the source of the family’s tone rank |
| `deviation` | string or absent | Why this family does not paint where its upstream color puts it. Present exactly when it departs deliberately |
| `lightness_rank` | number or absent | Where the family sits in the consumer’s lightness band, overriding its upstream rank. Outside `[0, 1]` places it outside the band and requires a `deviation` |

Several kinds can map to one display family.
A nonempty family remains independently addressable even if only one extension
contributes to a particular rollup.

A family ID can also define a shared presentation key such as `family:javascript`.
Icons, byte formatting, and disclosure state remain outside the type registry.

#### Why a hue and not a color

A hue is tool-neutral and a color is not.
Lightness and chroma are properties of the surface a consumer paints on — a light
background wants one range, a dark background another, and a printed page a third — so a
registry that named finished colors would be naming one consumer’s theme.
A hue is the part that identifies the family, and it is the same everywhere.

Two rules govern the hue, and `devtools/check_file_type_colors.py` holds both:

- A family that names a `linguist` language takes that language’s color converted to
  oklch, hue unchanged, including where two of GitHub’s own colors are close together.
  Moving a familiar hue to win a distance metric costs more than the collision does.
- A family GitHub names no color for takes a hue whose painted color is clear of every
  other family’s by a stated perceptual distance.
  `--suggest` prints the widest gap for a new one.

#### Why `linguist_color` is not only provenance

A hue on its own cannot carry a palette this size.
Fifty-six families average 6.4 degrees of spacing, at or under the just-noticeable
difference when lightness and chroma are held constant, and GitHub’s own colors are
separated mostly by the two dimensions a constant tone discards: html and svelte differ
by 0.65 degrees of hue but by 0.032 of lightness and 0.040 of chroma.
Painted at one tone they come out as the same color.

So a consumer is expected to state a lightness *band* and a chroma *band* rather than
one value of each, and to place each family inside them using `linguist_color`: the
family’s **rank** among the upstream lightnesses, and its normalized position among the
upstream chromas. Rank rather than a linear map, because upstream lightness piles up in
the middle of its range and a linear map would re-crowd the palette where it is already
tightest. Ranking keeps the order GitHub chose without importing its extremes.
A family with no `linguist_color` sits at the centre of both bands; its hue was chosen
to be clear, so it needs no help from the other axes.

Bands are the consumer’s to choose, and the trade they make is explicit: a stacked-bar
segment can read slightly heavier than a same-size neighbour, which a constant tone
prevented, so a band should be narrow enough to keep that small.
Where the sRGB gamut cannot hold the chosen chroma at some hue, reduce chroma rather
than accepting a browser’s own gamut mapping, which moves lightness and hue.

#### Declared deviations

Deriving from GitHub’s colour separates most of what a fixed tone collapsed, and not all
of it.
Two languages can be near-identical upstream in all three dimensions, and GitHub’s
own placement can put a family the reader looks at constantly on top of a better-known
neighbour.
For those, a family may depart from where its upstream colour puts it, and the
departure is a declaration rather than a silent edit.

A deviating family keeps `linguist` and `linguist_color`, so its provenance stays
auditable, and adds `deviation`: prose saying why it left.
It may also set `lightness_rank`, which replaces the rank its upstream colour would earn
and may fall outside `[0, 1]` to leave the band altogether.
`lightness_rank` without `deviation` is refused, because leaving the band is exactly the
change that should never read as a typo.

The rule a deviating family trades into is the one a house hue already has: its painted
colour must clear every other family by the consumer’s perceptual floor, in every theme.
It does not get to be closer to something else than a colour chosen from a free gap
would be.

### Kind Fields

| Field | Type | Requirement |
| --- | --- | --- |
| `id` | string | Stable classifier identity |
| `family` | family ID or absent | Optional display family |
| `group` | group ID or absent | Required without `family`; inherited from a family otherwise |
| `content_family` | enum | `code`, `prose`, `markup`, `data`, `binary`, or `unknown` |
| `extensions` | string array | Normalized matchers without a leading dot |
| `filenames` | string array | Exact basenames compared ASCII-case-insensitively |
| `shebangs` | string array | Optional interpreter aliases |
| `priority` | integer | Tie-breaker within one evidence tier; higher wins |

A kind without a family still has one authoritative display group.
A kind owned by a family inherits that family’s group and cannot declare a conflicting
group.

The registry does not define icons, syntax renderers, MIME types, view plugins, chart
colors, or disclosure state.
Those systems consume stable registry identities.

### Recommended Coverage

The recommended definitions intentionally cover common, unambiguous formats rather than
attempting to name every language or extension.
They include:

| Group | Representative families and behavior |
| --- | --- |
| Code | Common languages and related extensions, including JavaScript, TypeScript, CSS, and C/C++ |
| Documentation | Common prose and markup documents |
| Data | Structured and tabular data formats |
| Archives | Common compressed streams and containers, including exact `.tar.*` compounds |
| Media | Images, video, audio, and fonts; SVG retains markup content |
| Other | Log files (`.log`, `.jsonl`, and `.ndjson`) plus structural fallback parents; JSON Lines retains data content |

The TOML file, not this summary, owns the complete recommended member list.

### Definition Validation

A conforming validator rejects:

- unsupported or nonpositive registry versions;
- duplicate or invalid IDs;
- ambiguous group or family order;
- unknown group, family, or content-family references;
- empty labels;
- extensions with a leading dot, uppercase ASCII, empty or ineligible components, or
  more than two components;
- duplicate exact extension or filename evidence;
- empty families;
- kinds without supported evidence; and
- equal-priority evidence that can select different kind IDs.

A validation error should expose a stable code and structured context naming the invalid
declaration and conflicting field.

### Normalization and Fingerprint

The normalized registry fingerprint covers the schema version, registry revision, and
every ordered semantic field.
It excludes TOML whitespace and comments.
Implementations using the same definitions must produce the same lowercase hexadecimal
digest.

The fingerprint is a drift and cache identity, not a security primitive.
A source revision, signed release, or artifact digest provides provenance.
A classification cache includes the registry schema version, revision, and fingerprint
in its validity key.

## File Facts and Classification

### File Facts

`FileFacts` contains filesystem observations independent of classification:

| Field | Type | Requirement |
| --- | --- | --- |
| `basename` | host filename value | Final path component using the host’s lossless filename encoding |
| `logical_extension` | string or null | Result of the logical-extension algorithm |
| `apparent_bytes` | nonnegative integer | Logical file length |
| `allocated_bytes` | nonnegative integer or null | Optional physical allocation |
| `ignored` | boolean or null | Optional scope fact; null when unavailable |

Paths, modification times, ownership, and permissions can remain in a host inventory,
but they are not metadata classification inputs.

### Logical Extension

A metadata-only producer derives a logical extension from the final basename:

1. Inspect only the final basename.
2. Treat a leading dot as part of the basename, not an extension separator.
   A later dot can introduce an extension: `.gitignore` has none and `.eslintrc.json`
   has `.json`.
3. Consider at most the final two dotted components.
4. ASCII-lowercase each considered component.
5. Retain consecutive trailing components that are nonempty, alphanumeric, and at most
   12 characters each.
6. Return no extension if the final component is ineligible.
7. Include the leading dot in runtime and serialized values.

| Filename | Logical extension |
| --- | --- |
| `bundle.js.map` | `.js.map` |
| `bundle.umd.min.js.map` | `.js.map` |
| `types.d.ts.map` | `.ts.map` |
| `bundle.umd.min.js` | `.min.js` |
| `archive.tar.gz` | `.tar.gz` |
| `release.v2.zip` | `.v2.zip` |
| `Photo.JPEG` | `.jpeg` |
| `.gitignore` | none |
| `.eslintrc.json` | `.json` |

The component cap controls vocabulary cardinality.
Producers must not add longer filename-specific exceptions.

### Matching Precedence

Metadata classification follows one deterministic cascade:

1. declared basename, compared ASCII-case-insensitively;
2. complete logical extension, so `.tar.gz` wins before `.gz`;
3. longest declared suffix on a component boundary, so `.min.js` can match `.js`;
4. higher `priority` only within the same evidence tier; and
5. unknown when no declaration wins.

A producer can continue with bounded shebang, modeline, signature, or content evidence
after the shared metadata cascade.
It must preserve which evidence won and must match the metadata conformance cases when
metadata decides the result.

### Classification Value

`FileClassification` records one decision without aggregate or presentation state:

| Field | Type | Requirement |
| --- | --- | --- |
| `logical_extension` | string or null | Preserved observation |
| `canonical_extension` | string or null | Declared extension that matched |
| `kind_id` | string or null | Stable classifier kind |
| `family_id` | string or null | Optional display family |
| `group_id` | string | Display group; `other` fallback |
| `content_family` | enum | Analyzer class; `unknown` fallback |
| `detection_source` | string | Evidence tier that won |
| `confidence` | string | Producer-defined stable confidence value |
| `registry_revision` | positive integer | Definition revision |
| `registry_fingerprint` | string | Normalized registry identity |

Classification and rollup placement are distinct:

1. A file without a logical extension contributes to No extension, even if its basename
   or content identifies a known kind.
2. A file with a logical extension and family contributes to that family.
   Its child key is the canonical extension when present and otherwise the logical
   extension.
3. A file with a logical extension and no family contributes to `remaining_types` under
   its logical extension.
   A user interface can label that parent **Other types**.

This order makes family parents fully explainable by exact extension children while No
extension remains a complete partition of extensionless files.

## Registry Projection

Validated definitions project into JSON-compatible runtime data:

```json
{
  "schema": "file-type-registry-v3",
  "schema_version": 3,
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
      "extensions": [".js", ".jsx", ".mjs", ".cjs"],
      "hue": 102.08,
      "linguist": "JavaScript",
      "linguist_color": "#f1e05a"
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

Projection extensions include leading dots because they are runtime identities.
Array order is authoritative.
Native compiled matchers and private evidence tables need not appear in the projection.

## Directory Rollup

### Scalar Rules

- IDs are lowercase registry IDs and compare exactly.
- Extensions include the leading dot and are ASCII-lowercase.
- File counts and byte measures are nonnegative integers.
- Apparent `bytes` is required.
- `allocated_bytes` is optional and never changes required ranking.
- Arrays follow registry order or the deterministic ranking defined below.
- Absent classification identities use JSON `null`, not empty strings.
- Readers ignore unknown additive object fields within the current component schema.

### Populations and Measures

Every rollup declares one or more named populations.
Every row in the rollup carries the same population keys:

```json
{
  "all": {"files": 150, "bytes": 10485760},
  "unignored": {"files": 145, "bytes": 9437184}
}
```

Each population requires `files` and apparent `bytes`. Additional nonnegative integer
measures belong in the same measure object.
A host documents names beyond common values such as `all`, `unignored`, and `selected`.

### Rollup Shape

The current component schema serializes a complete directory rollup as
`file-type-breakdown-v1`:

```json
{
  "schema": "file-type-breakdown-v1",
  "registry": {
    "schema_version": 3,
    "revision": 1,
    "fingerprint": "normalized-registry-identity"
  },
  "metrics": {
    "all": {"files": 200, "bytes": 20971520}
  },
  "groups": [
    {
      "id": "code",
      "families": [
        {
          "id": "javascript",
          "metrics": {
            "all": {"files": 150, "bytes": 10485760}
          },
          "extensions": [
            {
              "extension": ".js",
              "metrics": {
                "all": {"files": 150, "bytes": 10485760}
              }
            }
          ]
        }
      ]
    }
  ],
  "no_extension": {
    "metrics": {
      "all": {"files": 20, "bytes": 1048576}
    },
    "filenames": [
      {
        "basename": "Makefile",
        "metrics": {
          "all": {"files": 20, "bytes": 1048576}
        }
      }
    ],
    "others": null
  },
  "remaining_types": {
    "metrics": {
      "all": {"files": 30, "bytes": 9437184}
    },
    "extensions": [
      {
        "extension": ".bin",
        "metrics": {
          "all": {"files": 30, "bytes": 9437184}
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
No extension and `remaining_types` use named root members because their children use
different keys.

### Rollup Records

| Record | Required fields | Meaning |
| --- | --- | --- |
| `FileTypeBreakdown` | `schema`, `registry`, `metrics`, `groups`, `no_extension`, `remaining_types` | One complete directory partition |
| `FileTypeGroupBreakdown` | `id`, `families` | Ordered nonempty display section |
| `FileTypeFamilyBreakdown` | `id`, `metrics`, `extensions` | Semantic parent and complete extension children |
| `FileTypeExtensionBreakdown` | `extension`, `metrics` | Canonical or preserved logical extension child |
| `FileTypeFallbackBreakdown` | `metrics`, typed children, `others` | One bounded fallback parent |
| `FileTypeOthersBreakdown` | `metrics`, `omitted_distinct_values` | Exact remainder, never a claimed type |

These names define responsibilities and serialized meaning.
An implementation can use compact counters or other native representations internally.

### Conservation

For every emitted population and metric:

1. Root equals every family parent across all groups plus No extension plus
   `remaining_types`.
2. Each family equals all emitted extension children.
   Family children are complete and never capped.
3. No extension equals its bounded basename children plus optional Others.
4. `remaining_types` equals its bounded raw-extension children plus optional Others.
5. Each file contributes to exactly one root partition row.
6. Children explain their parent and are not added again at the root.

Selecting another population changes the visible measure.
It does not require another crawl or change which bounded children are present.

### Bounded Fallback Children

No extension basenames and `remaining_types` extensions use one deterministic ranking.
For each candidate, calculate its file-count and apparent-byte share in every emitted
population, then rank by:

1. greatest share across those measures;
2. greatest byte share;
3. greatest file share; and
4. stable key.

The recommended default and maximum are 20 candidates per fallback parent.
A profile can request a lower limit, including zero.
Others contains the exact sum of every omitted candidate and its
`omitted_distinct_values` count.
Optional allocated bytes do not affect ranking, so consumers supporting only the
required metrics choose the same children.

### Recommended Interactive Projection

The producer bound and the display bound solve different problems.
A conforming producer keeps up to 20 exact fallback children so consumers have a useful,
bounded projection. An interactive renderer should show at most 10 direct children
initially and represent the rest with one **N more** row whose metrics equal those
hidden children. Expanding that row reveals the already-serialized children; it does not
alter the producer’s optional Others aggregate for values beyond the 20-child
interchange bound.

Apply the 10-child presentation bound consistently to every direct list, including
family extensions and fallback children.
Sort each list by the selected display measure descending, then by the other required
measure descending, then by stable identity.
Changing the selected measure may reorder siblings but never changes classification,
conservation, or the serialized record.

### Snapshot Consistency

A `FileTypeBreakdown` is one complete directory generation.
A consumer must not combine groups, fallback children, or measures from different
generations or present a partial generation as a completed breakdown.
A host envelope can expose independently cached directory totals before the detailed
breakdown is ready, provided those totals carry their own revision or snapshot boundary
and are labelled as general directory context rather than as children of the pending
breakdown.

### Filename Encoding

A producer retains native filenames internally and uses a documented lossless encoding
in machine output. A basename child must round trip through its host envelope.
Replacing undecodable values or merging distinct native names is invalid.

A human renderer can use a display-safe representation but must not expose that string
as the machine key.

## Host Envelopes

The format defines composable values, not an entire report.
A host can publish a registry projection once and many rollups later, or bundle both in
a standalone report:

```json
{
  "schema": "example-report-v1",
  "file_rollup": {
    "type_definitions": {"schema": "file-type-registry-v3"},
    "rollup": {"schema": "file-type-breakdown-v1"}
  }
}
```

A consumer rejects or refreshes a rollup whose registry revision or fingerprint differs
from its loaded projection.
It never guesses labels or membership from IDs alone.

## Producer and Consumer Requirements

A conforming producer:

- implements the logical-extension and metadata-matching rules;
- identifies the exact type-definition registry used;
- emits the same population keys on every row;
- preserves required files and apparent bytes as nonnegative integers;
- emits complete family children;
- bounds only the two fallback child lists; and
- proves every conservation invariant before publishing a rollup.

A conforming consumer:

- validates supported component schema identifiers;
- verifies registry identity before applying labels or order;
- ignores unknown additive fields but rejects missing required fields and unknown
  required enum values;
- treats Others as an exact remainder rather than a file type; and
- keeps presentation concerns outside classification and aggregate semantics.

An implementation can add analyzer evidence, metrics, populations, or host-envelope
fields when the additions preserve these requirements.

## Conformance

The shared conformance corpus contains:

- metadata cases with basename, expected logical and canonical extensions, kind, family,
  group, content family, detection source, and confidence;
- invalid TOML definitions with stable expected error codes; and
- aggregate cases containing file facts and one exact expected rollup.

Metadata cases cover every recommended declaration, uppercase suffixes, dotfiles, one-
and two-component limits, longer dotted names, exact compound precedence, suffix
fallback, JSON versus JSON Lines, SVG, C/C++, extensionless files, and unknown
extensions.

Invalid cases cover every definition-validation class.
Aggregate cases include an empty directory and a mixed high-cardinality directory that
exercises semantic families, multiple populations, both fallback caps, and exact Others
remainders.

Implementations using different definitions can retain the format-level cases and
replace registry-specific expected identities with cases for their own registry.

## Evolution

Changes use the narrowest applicable version boundary:

- **Registry revision:** Add, remove, relabel, or reassign recommended type definitions
  without changing their structure or matching semantics.
- **Registry schema version:** Change the TOML or projected registry structure or the
  meaning of a registry field.
- **Component schema identifier:** Remove or redefine a serialized field or required
  enum value in that component.
- **File Rollup Format version:** Change cross-component semantics such as logical
  extension derivation, placement, conservation, required ranking, or identity rules.

Readers fail closed on unknown schema identifiers or unsupported structural versions.
Within a supported component schema, readers ignore unknown additive object fields.
Stable IDs are compatibility keys and must never be reused for a different meaning.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
