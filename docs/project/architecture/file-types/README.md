# File-Type Compatibility Contract

**Status:** Design contract for the active implementation plan

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
  [active implementation plan](../../specs/active/plan-2026-08-13-shared-file-type-taxonomy-and-breakdowns.md)
  defines repository work, migration, testing, and acceptance criteria.

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

During implementation, requirements use this precedence:

1. the versioned registry and interchange schemas once they are checked in;
2. the contract documents in this directory;
3. the shared conformance corpus;
4. the active implementation plan; and
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

Metabrowser emits `all` and `unignored` populations.
`fdu` may emit `selected`, `all`, or other documented populations.
Every row in one breakdown has the same population keys and at least the required
`files` and apparent `bytes` metrics.

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
