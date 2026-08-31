# Review: Repository Library Phasing and GitHub Content Model

**Date:** 2026-08-26

**Author:** Metabrowser maintainers

**Status:** Complete.
The active plan incorporates the findings below.

**Scope:** The `docs/repo-cache-and-git-url` branch, including its merge of upstream
Metabrowser through v0.8.0; the repository-cache research; the active repository-library
plan at `e28ad9`; the relevant Git, diff, trust, cache, and format boundaries on
upstream; and SoftSchema v0.7.0 plus documentation-only `main` head `97b7c31`.

## Verdict

The repository-library direction is sound, but the previous phase plan was not ready to
implement.
Its first feature phase combined application-home migration, persistent record
design, Git acquisition, background backfill, URL resolution, provider coordination, and
serving untrusted content.
The same plan deferred the GitHub payload shape until a PR view while already fixing its
path and envelope. That would make the generic cache hard to land and make provider
records difficult to evolve safely.

The revised design is ready for phased implementation after Phase 0 closes its remaining
measurement and state-machine decisions.
It makes generic URL-open independent of GitHub, adds a schema-only GitHub
browsing-model phase, and gives provider refresh an immutable-snapshot and
atomic-manifest boundary.
SoftSchema is a suitable format layer if Metabrowser binds packaged schemas through its
host registry and stays inside the measured enforced-schema subset.

## What Was Reviewed

The review checked the plan against the repository as it exists after v0.8.0 rather than
against the branch’s original August 11 assumptions:

- Git history, direct revision navigation, commit detail, and Git-backed diff rendering
  already exist.
- Revision selection starts comparison work that needs blobs, so the older blobless
  timing does not describe the full current click path.
- The Git process runner is already the hardened subprocess boundary and should gain
  policies instead of being bypassed.
- URL-fetched roots are untrusted content and remain gated on the explicit trust
  profile.
- The server, browser shell, and built-in plugins ship together, while provider schemas
  and views still belong behind plugin contribution boundaries.

The SoftSchema review covered its pure-YAML profile, portable value restrictions,
contract registry, Pydantic and compiled-schema validation layers, schema hash, artifact
metadata precedence, enforced undeclared-property behavior, composition support matrix,
offline resource graph, and versioning guidance.
It also examined the design review that led to v0.7.0’s conservative composition rules
rather than assuming any valid Draft 2020-12 schema can be safely hardened by
transformation.

## Findings and Disposition

| ID | Severity | Finding | Disposition in revised plan |
| --- | --- | --- | --- |
| R1 | High | The first usable phase was not independently landable | Split format foundation (1A) from generic URL-open (1B), then moved catalog and chooser to later phases |
| R2 | High | One `repo.yml` mixed stable identity with frequently changing operational state | Split `repository.yml` from atomically replaced `state.yml` |
| R3 | Medium | Generic refresh depended on a provider stage before a provider contract existed | Made Phase 2 Git-only; provider jobs register after the provider framework lands |
| R4 | High | `github-pr-f01` deferred its payload as `data: {}` | Replaced it with a closed inventory of per-resource SoftSchema contracts |
| R5 | High | The plan jumped from an opaque envelope to PR rendering without a GitHub domain-model phase | Added a no-network schema and fixture phase before API acquisition or views |
| R6 | High | Mutable multi-file provider refresh had no coherent publication point | Added immutable object snapshots, completed sync manifests, and atomic current pointers |
| R7 | High | Application-home format and individual record schemas shared an informal `*-f01` version convention | Kept layout `f01` separate from immutable SoftSchema contract IDs and schema digests |
| R8 | High | A cache file could potentially select its own schema, and enforced model-only validation could remain open | Omitted document schema paths, made host registry binding authoritative, and required compiled plus semantic validation |
| R9 | Medium | “Full GitHub object model” had no bounded completion criterion | Defined a GitHub repository-browsing v1 and explicitly excluded unrelated account and administration APIs |
| R10 | Medium | Generic source normalization applied GitHub-like equivalence to unknown hosts | Preserved path case, `.git`, and transport distinctions; provider aliases may be recorded later without merging entries |
| R11 | Medium | Provider records lacked pagination, absence, deletion, and permission semantics | Added collection completeness, retrieval metadata, tombstones, and distinct unavailable outcomes |
| R12 | Medium | Stacked PRs were named as future data without identity or provenance rules | Made stacks derived projections with evidence, algorithm version, conflicts, and cycles |

### R1: The first delivery crossed too many boundaries

The prior Phase 1 was simultaneously a config migration, persistent store, Git clone
manager, URL parser, CLI contract change, background worker, trust-profile integration,
and user-visible feature.
A review failure in any one boundary would hold all the others.
It also made it difficult to tell whether a format was being designed for generic cache
needs or for later provider work.

The format foundation is now Phase 1A. It can establish layout `f01`, SoftSchema
registration, atomic YAML, locks, quarantine, and distribution checks with no network or
Git clone. Phase 1B then has one outcome: a supported clone URL publishes or reuses one
pinned generic repository and enters the existing serve path under the untrusted
profile. GitHub is absent from its records and acceptance criteria.

### R2: Stable identity and mutable state need different write paths

The proposed `repo.yml` stored source digest and creation facts beside `last_opened_at`,
fetch state, pending revision, and backfill progress.
Every open would rewrite the record that proves a slug belongs to a source.
A torn or future-format operational write could therefore make an otherwise valid cached
repository impossible to identify.

`repository.yml` now contains source identity and acquisition facts and is immutable
during ordinary operation.
`state.yml` carries active revision, object state, last open, fetch time, pending
promotion, and last operation.
Publication validates both against HEAD. Catalog scanning can report an incomplete pair
without guessing which source a directory represents.

### R4 and R5: An opaque envelope defeats the format goal

The earlier `github-pr-f01` example fixed an outer envelope, then left all meaningful
provider state in `data: {}` until a view was designed.
That is not a strict format.
It cannot answer which fields are stable identities, which are observations, how reviews
anchor to Git, whether a missing list is empty or unfetched, or which changes require a
version bump.

It also puts transport and UI decisions in the wrong order.
If the first fixture corpus comes from one API query, its response shape tends to become
the model. If the first consumer is a PR page, fields needed by issues, repository
summaries, stack projection, or offline refresh tend to be bolted on later.

Phase 4 now lands the entire browsing-domain contract inventory with no network code.
It covers provider storage, repositories, issues, issue comments, timeline events, pull
requests, reviews, review threads and comments, checks, commit statuses, and stacks.
Its fixtures include ordinary and adverse states.
API adapters in Phase 5 map into that model; views in Phase 6 consume it.

### R6: Atomic files are not enough for an atomic refresh

Replacing each YAML file atomically still allows one UI read to combine a new pull
request with old reviews and half of a newly paginated comment set.
A refresh can fail after publishing some files, and absence has no trustworthy meaning
until every page has completed.

The revised design treats normalized object snapshots as immutable and publishes a
completed sync manifest.
Object IDs hash the contract and domain payload; retrieval metadata stays in the
manifest, so a conditional response can reuse unchanged content.
A small current resource-set record switches to the completed manifest in one atomic
write. The exact sharding remains subject to Phase 4 measurements, but the consistency
model does not. A partial acquisition may be preserved for diagnosis without replacing
the previous current view.

### R7 and R8: Layout version, payload contract, and schema selection differ

The earlier format used `f01`, `repo-f01`, and `github-pr-f01` as related naming
conventions without defining their compatibility relationship.
A home-directory change, an optional provider field, and a source identity change have
different upgrade and recovery consequences.

The revision keeps `f01` for directory semantics and gives every payload a namespaced
SoftSchema contract.
Each contract ID maps to one deterministic compiled-schema digest.
Metabrowser takes a conservative rule for enforced cache records: a structural
accept-set change that an older reader may reject gets a new contract version, even if
the field is optional.

SoftSchema’s host registry is the right authority for application data.
Records identify their contract and envelope but omit a schema path.
The installed application binds the contract to its packaged compiled schema and strict
Pydantic model. This prevents a tampered cache record from choosing what validates it.
Both layers are required because `status: enforced` with only a default Pydantic model
does not itself guarantee rejection of undeclared fields.

### R9: “Full GitHub” must mean a specific product domain

GitHub’s APIs include organizations, permissions, Projects, Actions, releases, packages,
security, billing, discussions, and other products.
Modeling all of GitHub is not a phase.
The requested product needs the subset that supports browsing repositories, issues, code
review, commit signals, and stacks.

The plan calls this the GitHub browsing content model v1 and names both included record
families and excluded surfaces.
Future families can be added without pretending the v1 claim covered them.

### R10: Generic identity must not guess provider equivalence

Lowercasing all paths, stripping `.git`, or equating SSH and HTTPS can be valid for one
provider and false for another Git server.
Wrong equivalence is worse than a duplicate cache because it may open content from a
different source under an existing identity.

The generic layer therefore performs only syntax-level normalization and preserves
provider-dependent distinctions.
It rejects query and fragment forms in the first usable phase because they are ambiguous
and may contain credentials.
A later provider binding can record proven aliases, but it does not merge two existing
generic entries.

### R11: Missing data needs a state model

A fast offline view must distinguish an empty collection from a collection that was not
requested, truncated by a bound, interrupted mid-pagination, hidden by permissions, or
deleted. The earlier envelope had only `fetched_at` and `etag`.

The revised contracts give each collection an explicit completeness state and bounded
continuation metadata.
Provider timestamps stay on domain objects; HTTP validators, query identity, API
version, normalization version, and fetch time stay in retrieval metadata.
Confirmed deletion is a tombstone.
Authentication and permission failures do not manufacture one.

### R12: Stacks are derived, not provider facts

There is no single native GitHub stack object.
Branch topology, explicit metadata, and third-party tools may disagree.
A cache format that stores only an ordered PR list would hide how that order was
obtained and become stale when any member changes.

The stack contract stores directed relationships, evidence, derivation algorithm and
version, input snapshot IDs, conflicts, cycles, and missing members.
It is modeled with the other provider records in Phase 4 but produced only in Phase 7.
Source PR snapshots remain unchanged when a projection is recomputed.

## SoftSchema Adoption Assessment

SoftSchema fits this work for concrete reasons:

- It defines a portable pure-YAML profile and rejects YAML features that differ across
  Python and TypeScript readers.
- Its contract IDs separate payload identity from implementation classes and file paths.
- Its compiled schema supplies a portable structural boundary, while Pydantic can add
  semantic validation.
- Its registry precedence lets the application pin trusted schemas while records remain
  self-identifying.
- Deterministic compilation, schema hashes, structured validation errors, and corpus
  validation give CI useful drift checks.

The adoption has boundaries:

- Use the released v0.7.0 package, not the inspected source checkout.
- Review the first-party frontmatter-format upgrade and update the dependency lock.
- Keep enforced schemas to simple closed objects and local definitions unless a composed
  shape is explicitly in the support matrix and has cross-runtime fixtures.
- Never rely on `format: date-time` alone for lexical timestamp validation.
- Do not use schema field metadata unless an actual Metabrowser consumer reads it.
- Do not make SoftSchema responsible for locating companion records or publishing
  multi-file snapshots; those are host application rules.

The SoftSchema Codex skill was installed from the reviewed repository so implementation
turns can load its complete workflow.
Installation does not add a runtime dependency to Metabrowser; that remains Phase 1A
work with the normal dependency review.

## Required Gates Before Implementation

Phase 0 still has two material obligations:

1. Re-run acquisition measurements through the current history, commit, manifest, and
   patch paths, then choose the initial clone and backfill policy.
2. Freeze state-transition fixtures for identity claim, clone staging, publication,
   interruption, quarantine, trash, and promotion.

Phase 1A must then prove the format boundary in an installed wheel before Phase 1B
writes a released cache.
Phase 4 must prove the GitHub schema inventory and measured storage layout before Phase
5 writes provider snapshots.
Those gates are narrow enough that the generic repository cache can progress without
waiting for the GitHub model.

## References

- [Repository library and open from a Git URL](../specs/active/plan-2026-08-11-open-repo-from-git-url.md)
- [Repository-cache research](../research/research-2026-08-11-repo-cache-and-git-url-open.md)
- [SoftSchema v0.7.0 guide](https://github.com/jlevy/softschema/blob/v0.7.0/docs/softschema-guide.md)
- [SoftSchema v0.7.0 specification](https://github.com/jlevy/softschema/blob/v0.7.0/docs/softschema-spec.md)
- [SoftSchema composition research](https://github.com/jlevy/softschema/blob/main/docs/project/research/research-2026-08-23-json-schema-composition-and-enforcement.md)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
