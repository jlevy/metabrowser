# File-Type Registry v1

**Schema ID:** `file-type-registry-v1`

The registry is a declarative TOML file containing stable classifier kinds, user-visible
families, top-level display groups, and analyzer content families.
It is the only hand-maintained source of extension and basename membership shared by
Metabrowser and `fdu`.

## Source Shape

The reviewed source uses standard TOML with top-level scalars and ordered arrays of
tables:

```toml
schema_version = 1
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

Metabrowser’s packaged path is `src/metabrowser/data/file-types.toml`. The adopted `fdu`
path is `crates/fdu/rules/file-types.toml`. The normalized files must have the same
schema version, registry revision, fingerprint, and classification behavior.

## Root Fields

| Field | Type | Requirement |
| --- | --- | --- |
| `schema_version` | positive integer | Must be `1`; unsupported structural versions fail closed |
| `registry_revision` | positive integer | Monotone data revision included in projections and cache identity |
| `max_extension_components` | positive integer | Must be `2` in v1 |

Changing matching semantics or a field’s meaning requires a new schema version.
Adding, removing, or reassigning declarations requires a registry revision.
Label-only changes also increment the revision because projections and human reports
change.

## Group Fields

| Field | Type | Requirement |
| --- | --- | --- |
| `id` | string | Stable lowercase identifier matching `[a-z][a-z0-9-]*` |
| `label` | string | Nonempty human label |
| `order` | integer | Deterministic order; unique among groups |

The initial order is Code, Documentation, Data, Logs, Archives, Media, and Other.
Other is the fallback section for the No extension and Other types UI parents; the
interchange member for the latter remains `remaining_types`. It does not collect
unrelated ordinary families merely to avoid a taxonomy decision.

## Family Fields

| Field | Type | Requirement |
| --- | --- | --- |
| `id` | string | Stable lowercase aggregate and palette identity |
| `label` | string | Nonempty UI and human-report label |
| `group` | group ID | Existing display group |
| `order` | integer | Deterministic order within the group |

A display family is a presentation aggregate, such as JavaScript, Log files, Images, or
C/C++. It is not an analyzer class.
Several kinds can map to one family, and every nonempty family remains disclosable even
when only one extension contributes in the selected directory.

The family ID also defines the shared distribution key `family:<id>`. Color values and
icons remain presentation metadata outside the registry.
Extension children share the parent family’s distribution key but keep their exact file
icon identities.

## Kind Fields

| Field | Type | Requirement |
| --- | --- | --- |
| `id` | string | Stable classifier identity |
| `family` | family ID or absent | Optional display placement |
| `group` | group ID or absent | Required when `family` is absent; a family-owned kind inherits and must not contradict its family group |
| `content_family` | enum | `code`, `prose`, `markup`, `data`, `binary`, or `unknown` |
| `extensions` | string array | Normalized matchers without a leading dot |
| `filenames` | string array | Exact basename matchers, compared ASCII-case-insensitively |
| `shebangs` | string array | Optional interpreter aliases used by `fdu` |
| `priority` | integer | Tie-breaker within one evidence tier; higher wins |

A kind can exist without a display family, but it still has one authoritative display
group.
This keeps broad filtering deterministic for filename-only and raw-extension kinds
while leaving them under Other types in an extension-oriented breakdown.
C and C++ can retain distinct kind IDs while sharing C/C++. SVG can retain a markup
content family while joining Images.
JSON Lines can retain data while joining Log files.

The registry does not declare icons, syntax renderers, MIME types, plugin kinds, chart
colors, or disclosure state.
Those systems consume stable registry identities.

## Required Initial Coverage

The registry carries forward Metabrowser’s implemented Code, Docs, and Data families and
adds these product groups:

| Group | Required families | Required seed behavior |
| --- | --- | --- |
| Logs | Log files | `.log`, `.jsonl`, and `.ndjson`; JSON Lines retains data content |
| Archives | Archives | Common compressed streams and containers, including exact `.tar.*` compounds |
| Media | Images, Videos, Audio, Fonts | Common interoperable formats; SVG remains markup |
| Other | System parents only | No extension and Other types are breakdown structures, not kinds |

The source TOML, not this table, owns the complete member list.
New declarations should favor common, unambiguous formats.
The registry is deliberately smaller than GitHub Linguist and does not promise to name
every language or extension.

## Logical Extension

All metadata-only producers implement the same basename algorithm:

1. Inspect only the final basename.
2. Treat a leading dot as part of the basename, not an extension separator.
   A later dot can introduce an extension: `.gitignore` has none and `.eslintrc.json`
   has `.json`.
3. Consider at most the final two dotted components.
4. ASCII-lowercase each considered component.
5. Retain consecutive trailing components that are nonempty, alphanumeric, and at most
   12 characters each.
6. Return no extension if the final component is ineligible.
7. Include the leading dot in runtime and interchange values.

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
It is not a list of special filenames, and producers must not add longer
filename-specific exceptions.

## Matching Precedence

Metadata classification follows this deterministic cascade:

1. declared basename, ASCII-case-insensitive;
2. complete logical extension, so `.tar.gz` wins before `.gz`;
3. longest declared suffix on a component boundary, so `.min.js` can match `.js`;
4. higher `priority` only within the same evidence tier; and
5. unknown if no declaration wins.

The result preserves the logical extension, canonical matched extension, kind ID, family
ID, group ID, content family, detection source, confidence, registry revision, and
fingerprint. `fdu` may continue with bounded shebang, modeline, signature, or content
evidence, but metadata-only cases must match Metabrowser exactly.

## Breakdown Placement

Classification and extension breakdown placement are distinct:

1. A file without a logical extension contributes to No extension, even if its basename
   or content identifies a known kind.
2. A file with a logical extension and family contributes to that family.
   The child key is its canonical extension when present and otherwise its logical
   extension.
3. A file with a logical extension and no family contributes to `remaining_types` under
   its logical extension; the UI labels that parent Other types.

This order makes every family parent fully explainable by extension children while No
extension remains a complete partition of extensionless files.

## Validation

Python and Rust validators reject:

- unsupported or nonpositive versions;
- duplicate or invalid IDs;
- ambiguous group or family order;
- unknown group, family, or content-family references;
- empty labels;
- extensions with a leading dot, uppercase ASCII, empty or ineligible components, or
  more than two components;
- duplicate exact extension or filename evidence;
- empty families;
- kinds without any supported evidence; and
- equal-priority evidence that can select different kind IDs.

An error has a stable code and structured context naming the invalid declaration and
conflict. Metabrowser loads and validates the packaged registry before serving requests.
The browser consumes the resulting immutable projection rather than parsing TOML. `fdu`
fails during its future build-time registry compilation.

## Normalization and Fingerprint

The normalized fingerprint covers the schema version, registry revision, and every
ordered semantic field.
It excludes TOML whitespace and comments.
Both implementations produce the same lowercase hexadecimal digest for the same
declarations.

The generated `registry-v1.json` projection and `conformance-v1.json` corpus pin that
digest for Python, browser JavaScript, and future Rust parity tests.

The digest is a drift and cache identity, not a security primitive.
A source Git revision or released artifact records provenance.
Any classification cache includes the registry schema, revision, and fingerprint in its
validity key.

## Forward Compatibility

Readers fail closed on an unknown schema ID or schema version.
Within v1, readers ignore unknown additive projection fields but reject unknown required
enum values and invalid registry declarations.
Stable IDs are compatibility keys; labels may change only with a registry revision.
Reusing an ID for a different meaning is forbidden.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
