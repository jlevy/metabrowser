# `fdu` File-Type Compatibility

This document is the handoff boundary for adopting Metabrowser’s file-type registry and
breakdown contracts in `fdu`. It describes compatible inputs and outputs without
requiring `fdu` to copy Metabrowser UI code or abandon its analyzer-oriented reports.

## Adoption Outcome

An adopted `fdu` revision:

- compiles the reviewed Registry v1 TOML into native Rust;
- passes the same metadata and invalid-registry conformance corpus;
- retains `fdu`’s richer evidence, content analysis, and flat report views;
- builds the same conserved group, family, extension, and fallback hierarchy;
- exports Registry v1 and Breakdown v1 through Rust, CLI JSON/YAML, grouped human, and
  Python surfaces; and
- includes registry revision and fingerprint in provenance and affected cache keys.

Metabrowser remains the reference owner of product taxonomy and interchange semantics.
`fdu` can propose registry or format improvements, which are reviewed in Metabrowser and
then synchronized as a new version or revision.

## Adopted Artifacts

| Metabrowser artifact | `fdu` destination or consumer |
| --- | --- |
| `src/metabrowser/data/file-types.toml` | `crates/fdu/rules/file-types.toml` |
| `registry-v1.schema.json` and `registry-v1.json` | `build.rs` validator, Rust API, and projection goldens |
| `breakdown-v1.schema.json` and `breakdown-empty-v1.json` | Query types and JSON/YAML serializers |
| `conformance-v1.schema.json` and `conformance-v1.json` | Rust classifier, parser, and aggregate tests |
| Contract Markdown files | `fdu` architecture and compatibility references |
| Packet `manifest.json` | Source revision, registry identity, and adopted-file hashes |

Synchronization accepts an explicit source checkout or release artifact.
It never reads an implicit sibling path or fetches the network during build.
Both repository diffs are reviewed, and `fdu` records the source Git revision.

Create the reviewed packet from the Metabrowser checkout with:

```shell
uv --config-file uv.toml run --frozen python devtools/file_type_contract.py \
  --export /explicit/destination \
  --source-revision SOURCE_GIT_REVISION
```

The destination is self-contained.
`fdu` copies or compiles only packet contents and verifies the manifest before adopting
them; its build never reaches back into a Metabrowser checkout.

## Semantic Mapping

| Shared concept | Existing `fdu` concept | Adoption rule |
| --- | --- | --- |
| `kind_id` | `FileTypeId` | Preserve stable kind identity; extend generated declarations as needed |
| `content_family` | `ContentFamily` | Keep analyzer semantics unchanged |
| `family_id` | no equivalent display axis | Add optional display family independent of `ContentFamily` |
| `group_id` | no equivalent display axis | Add display group; never reuse `ContentFamily` |
| `logical_extension` | derived extension | Implement Registry v1’s case, dotfile, and two-component algorithm |
| `canonical_extension` | exact matched type extension | Preserve the registry member that won after compound and suffix matching |
| `detection_source` | classifier source | Retain `fdu`’s richer evidence enum and map shared metadata tiers exactly |
| `confidence` | classifier confidence | Preserve existing semantics and serialize a stable value |
| generated/vendored/docs flags | existing classification flags | Remain orthogonal to display grouping |
| Breakdown populations | query selection | Emit `selected`; add `all` only when the denominator is retained |
| apparent `bytes` | current size metric | Required shared metric |
| `allocated_bytes` | physical size metric | Optional additive metric; excluded from shared child ranking |

`fdu`’s analyzer `families` view remains a view over `ContentFamily`. The shared display
family is a separate field and report axis; renaming or silently changing the current
view would conflate analysis with UI organization.

## Registry Compilation

`crates/fdu/build.rs` parses and validates the synchronized TOML before code generation.
It generates immutable tables for groups, families, kinds, extensions, basenames,
shebangs, order, and match priority, plus normalized registry identity.

The build must:

- reject every invalid Registry v1 fixture with the expected stable code;
- make runtime classification independent of TOML parsing;
- normalize and fingerprint fields exactly as Metabrowser does;
- use exact compound matching before longest component-suffix matching; and
- retain native, potentially non-Unicode basename handling.

A focused TOML parser is acceptable if it supports the entire documented v1 subset and
passes the shared fixtures.
Adding a general parser dependency requires `fdu`’s normal supply-chain review.

## Classification Integration

`crates/fdu/src/classify.rs` applies the shared metadata cascade before optional bounded
content evidence. Existing `FileTypeId`, `ContentFamily`, source, confidence, and flags
remain available. Shared accessors add display family, display group, logical extension,
canonical extension, and registry identity.

Content evidence can identify a kind that Metabrowser cannot identify from metadata.
Breakdown placement still follows the shared order: extensionless files remain under No
extension; files with an extension and display family join that family; other extension
values join Remaining types.

## Breakdown Integration

The Rust query model adds typed equivalents of:

- `FileTypeMeasure` and named population metrics;
- `FileTypeGroupBreakdown`;
- `FileTypeFamilyBreakdown`;
- `FileTypeExtensionBreakdown`;
- `FileTypeFallbackBreakdown` and Others; and
- `FileTypeBreakdown`.

The builder is pure over retained file observations or exact aggregate inputs.
It preserves apparent files and bytes for every population, emits complete family
children, and applies the shared 20-child selection independently to No extension
basenames and Remaining types extensions.

The first implementation can traverse retained entries when an explicit breakdown is
requested. It must not store an unbounded basename map at every directory ancestor
without measurement.
A later bounded mergeable structure is valid only if it continues to produce exact
parents and an exact Others remainder.

## Report Surfaces

The existing `types`, `extensions`, `families`, `languages`, and `documents` views
remain compatible. A new grouped file-type view serializes Breakdown v1 rather than
changing an existing schema silently.

| Surface | Requirement |
| --- | --- |
| Rust | Expose typed registry identity, projection, classification accessors, and breakdown builder |
| JSON/YAML | Serialize the Registry v1 projection and Breakdown v1 without parsing human output |
| Human CLI | Render registry group and family order with `fdu`’s established byte formatting |
| `fdu-py` | Return the same stable nested structure as ordinary Python values or typed bindings |

The planned view label is `file-types`, subject to `fdu`’s existing view-axis naming
rules. It belongs in the view enum and parser rather than a one-off flag.

## Consumer Verification

Before direct integration, Metabrowser will test captured `fdu` machine reports as
fixtures:

1. load the bundled Registry v1 projection;
2. verify revision and fingerprint;
3. validate the Breakdown v1 shape and conservation;
4. render the captured result through the same Files summary model; and
5. compare navigation and Treemap identities against native Metabrowser rollups.

These tests prove interchange compatibility without making Metabrowser depend on an
unpublished `fdu` checkout.
Direct in-process adoption is a later engine decision, not a prerequisite for compatible
output.

## Adoption Stages

### Stage 1: Registry

- synchronize the reviewed TOML and conformance corpus;
- compile groups, families, kinds, and matching tables;
- expose schema, revision, and fingerprint; and
- keep all existing report behavior green.

### Stage 2: Classification

- align logical-extension derivation and metadata matching;
- add display family, group, and canonical extension accessors;
- retain optional content evidence; and
- pass every shared metadata case.

### Stage 3: Breakdown

- add typed populations and measures;
- implement conserved family and special-parent hierarchy;
- implement deterministic caps and exact Others; and
- prove conservation over ignored, selected, empty, and high-cardinality inputs.

### Stage 4: Exports

- add Rust, JSON/YAML, human, and Python surfaces;
- add schema labels and provenance;
- add goldens and cache invalidation; and
- publish captured compatibility fixtures for Metabrowser.

### Stage 5: Integration Decision

- compare native Metabrowser and `fdu` performance and output;
- choose direct Breakdown v1 output or adaptation from lower-level exact tallies;
- retain Metabrowser’s product contract either way; and
- remove compatibility paths only after one supported transition cycle.

## Acceptance Checklist

- Registry bytes, revision, and fingerprint agree.
- Python, browser JavaScript, and Rust pass the metadata conformance corpus.
- Unknown, extensionless, uppercase, dotfile, compound, and suffix cases agree.
- Root, family, No extension, Remaining types, and Others metrics conserve.
- Every row has identical population keys within one breakdown.
- Optional allocated bytes do not change selected children.
- Existing `fdu` content-family semantics and flat views remain compatible.
- Registry and Breakdown v1 are available through Rust, machine CLI, and `fdu-py`.
- Metabrowser renders captured `fdu` output without a package-specific translation
  layer.
- Both repositories pass their full validation and supply-chain gates.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
