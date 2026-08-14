# File-Type Compatibility Contract

**Status:** Implemented reference contract

Metabrowser owns the shared description of file-type facts, classification, semantic
families, and directory breakdowns.
The contract lets the Python server, browser UI, and a future `fdu` producer exchange
the same meanings without sharing runtime code or flattening Metabrowser’s folder
rollups into `fdu`’s current report views.

The contract is split by responsibility:

- [Registry v1](registry-v1.md) defines the TOML declaration, stable identities,
  logical-extension rules, matching precedence, validation, and versioning.
- [Interchange v1](interchange-v1.md) defines file observations, classifications,
  registry projections, metric populations, and the conserved hierarchical breakdown.
- [`fdu` compatibility](fdu-compatibility.md) defines the adoption boundary, field
  mapping, export requirements, conformance process, and staged handoff.
- The
  [implementation plan](../../specs/done/plan-2026-08-13-shared-file-type-taxonomy-and-breakdowns.md)
  records design rationale, migration, testing, and acceptance criteria.

## Contract Layers

| Layer | Versioned form | Owner | Purpose |
| --- | --- | --- | --- |
| Declaration | `file-type-registry-v1` TOML | Metabrowser | Groups, families, kinds, matchers, labels, and order |
| Observation | `FileFacts` | Producing package | Basename, logical extension, byte measures, and ignore state |
| Classification | `FileClassification` | Producing package | Stable registry identities and evidence for one file |
| Aggregation | `file-type-breakdown-v1` | Producing package | UI-ready groups, parents, children, populations, and metrics |
| Verification | `file-type-conformance-v1` | Metabrowser | Shared metadata cases, invalid declarations, and conserved examples |

Facts, classification, and presentation are independent axes.
A file can be an SVG kind with markup content while appearing in the Images display
family and Media group.
Likewise, JSON Lines can retain a data content family while appearing under Log files.

## Normative Sources

Requirements use this precedence:

1. the versioned registry and interchange schemas;
2. the contract documents in this directory;
3. the shared conformance corpus;
4. the implementation plan; and
5. package-specific adapters and UI view models.

The registry payload is the source of truth for taxonomy membership.
Documents explain its schema and invariants but do not maintain a second hand-written
extension catalog.
Browser labels, colors, icons, percentages, formatted byte values, and
disclosure state are derived presentation and are not classification facts.

## Compatibility Boundary

Both packages must support the same structural model even when only Metabrowser renders
the browser UI:

```text
registry
├── ordered display groups
│   └── ordered display families
│       └── classifier kinds and declared extension members
├── analyzer content families
└── matching and version identity

breakdown
├── named metric populations
├── ordered display groups
│   └── nonempty family parents
│       └── complete extension children
├── No extension
│   ├── at most 20 basename children
│   └── exact Others remainder
└── Remaining types
    ├── at most 20 raw-extension children
    └── exact Others remainder
```

The portable schema supports named populations.
Metabrowser’s `/api/rollup` profile emits and requires `all` and `unignored`; a future
standalone `fdu` report may emit `selected`, `all`, or other documented populations.
Every row in one breakdown has the same population keys and at least the required
`files` and apparent `bytes` metrics.

## Implemented Artifacts

| Artifact | Repository path |
| --- | --- |
| Reviewed declaration | `src/metabrowser/data/file-types.toml` |
| Immutable Python loader | `src/metabrowser/file_type_registry.py` |
| Registry projection schema | `src/metabrowser/data/file-types/registry-v1.schema.json` |
| Breakdown schema | `src/metabrowser/data/file-types/breakdown-v1.schema.json` |
| Conformance schema | `src/metabrowser/data/file-types/conformance-v1.schema.json` |
| Generated projection | `src/metabrowser/data/file-types/registry-v1.json` |
| Shared corpus | `src/metabrowser/data/file-types/conformance-v1.json` |
| Empty breakdown example | `src/metabrowser/data/file-types/breakdown-empty-v1.json` |
| Drift and export tool | `devtools/file_type_contract.py` |

The repository gate checks that generated artifacts match the reviewed TOML and that the
registry, corpus, and every expected aggregate conform to their schemas.
Regenerate intentional registry changes with:

```shell
uv --config-file uv.toml run --frozen python devtools/file_type_contract.py --write
```

Create a self-contained handoff packet for `fdu` with an explicit source revision:

```shell
uv --config-file uv.toml run --frozen python devtools/file_type_contract.py \
  --export /explicit/destination \
  --source-revision SOURCE_GIT_REVISION
```

The packet includes the TOML source, normalized projection, schemas, corpus, example,
contract documents, and a `manifest.json` recording the source revision and registry
identity. It has no sibling-checkout or network dependency.

## Ownership and Distribution

Metabrowser hosts the reviewed registry, schemas, conformance cases, and these contract
documents. `fdu` later vendors a normalized registry and conformance revision, compiles
it into native Rust, and exports compatible registry and breakdown structures.
Neither package reads a sibling checkout, fetches a registry at build time, or depends
on the other package’s terminal output.

A registry revision changes only after its schemas and conformance cases pass in
Metabrowser. The `fdu` adoption change records the source Git revision, registry
revision, and normalized fingerprint.
The fingerprint detects drift and invalidates caches; the source Git revision or release
remains the supply-chain identity.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
