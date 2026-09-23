# Hosted Review Model and Provider Boundary

**Status:** Accepted design; the no-network record families, source-based provider
bindings, provider revision observations, the non-persisted local object-availability
report, scrubbed GitHub coverage oracle, installed enforced contracts and resource
profiles, and generic format inventory gate are implemented.
No provider adapter, cache, route, kind, or view is implemented yet.

Hosted review is a domain above Git history and File Diff Format.
A pull request or merge request has Git endpoints and can produce a comparison, but it
also has a lifecycle, participants, reviews, threads, checks, merge state, and provider
freshness that neither Git nor a patch can express.

The general artifact, resource, registry, cache, and view composition rules live in
[External Resources, Artifact Contracts, and Views](arch-external-resources-and-views.md).
Hosted review is their first demanding consumer, not the definition of the general
framework.

The first adapter targets GitHub.
The durable model remains provider-neutral so a future GitLab adapter can produce the
same documents without teaching views about GitHub or weakening the contracts into
provider payloads.

## Layers

```text
GitHub API and refs                 future GitLab API and refs
          │                                      │
          ▼                                      ▼
GitHub provider adapter                 GitLab provider adapter
          │                                      │
          └──────────────┬───────────────────────┘
                         ▼
              Hosted Review Format
        repository, change request, review,
         thread, comment, checks, freshness
                         │
              ┌──────────┴──────────┐
              ▼                     ▼
 Repository Activity Format   Hosted-review views
 commits and change requests  summary and discussion
              │                     │
              └──────────┬──────────┘
                         ▼
       Git history, File Diff Format, and
               revision-content views
```

The dependency direction only points down.
Provider adapters may produce hosted-review documents and ask the repository service to
fetch selected refs through a non-secret authorization identity and a short-lived opaque
Git credential lease for the same authorization context that observed those refs.
Hosted-review views may resolve a document’s comparison reference through File Diff
Format. Git, diff, inventory, and the shell never import a GitHub model.

Repository and branch opening sit below this diagram.
A provider URL reducer may turn a GitHub web URL into a generic clone source plus a
selection, but the repository library resolves the branch to a full object ID and serves
it from a shared worktree-free Git store.
The provider adapter is not required to browse repository content or branches.
The complete source, store, and attachment contract is in
[Repository Sources and Provider Mirrors](arch-repository-sources-and-provider-mirrors.md).

## The Clean Format Boundary

Hosted Review Format is a closed, versioned, tool-neutral contract with the same
discipline as File Diff Format:

- deterministic schema and conformance fixtures;
- structural and semantic validation in both producer and consumer implementations;
- explicit identity, completeness, partiality, freshness, and unavailable states;
- immutable observations and atomic current-manifest pointers;
- no raw provider response, open extension mapping, or renderer-only field; and
- provenance that names the provider and retrieval without making its transport shape
  part of the domain model.

The format uses SoftSchema conventions so the Python producer, browser consumer, CLI
inspection path, and future provider adapters share one compiled structural contract.
Contract IDs name provider-neutral payloads, schemas ship with the hosted-review plugin,
and the host registry outranks any schema path found in cached content.
Exploratory notes may use permissive schemas, but every checked-in conformance artifact
is enforced from its first machine-checked version.
Undeclared fields fail consistently in Python and each declared browser parser.
The serializer accepts only a closed, validated `ChangeRequest` and performs no
filesystem write. Its enforced marker records that Pydantic boundary; durable cache
publication remains planned behind the provider store.

The v0.12.0 record set is deliberately PR-first, while the provider-storage vocabulary
is content-neutral:

| Record | Describes | Does not contain |
| --- | --- | --- |
| `ProviderBinding/v1` | An auth-independent link from one conservative repository source identity to a stable hosted-repository identity | A cache-entry requirement, local path, mutable owner/name coordinates, or credentials |
| `AuthorizationContextRef` | The stable, non-secret namespace that determines which hosted objects a publication may expose | Login, scopes, validators, rate limits, or observation time |
| `Retrieval/v1` | One immutable provider observation, including transport, outcome, validators, rate limits, and display auth facts | Tokens, raw headers, raw arguments, response bodies, or environment values |
| `HostedRepository/v1` | Provider-neutral repository identity, coordinates, URLs, visibility, default branch, and timestamps | Git objects or an API response |
| `ChangeRequestIndex/v1` | A normalized query and its bounded, deterministically ordered discovery rows | Retrieval times, pagination transport, full bodies, reviews, threads, checks, or fetched refs |
| `ChangeRequest/v1` | A pull or merge request’s identity, lifecycle, participants, labels, base/head, merge readiness, and aggregate state | Patch bodies or transport pagination |
| `ChangeRequestComment/v1` | One top-level conversation comment, author, timestamps, visibility state, and human URL | A diff anchor or rendered HTML as authority |
| `Review/v1` | One review act, its normalized disposition, and an optional reader-facing summary body | Provider-specific review payload |
| `ReviewThread/v1` | A bounded discussion anchored to an immutable comparison identity | A guessed current line |
| `ReviewComment/v1` | One comment, author, timestamps, state, and anchor | Rendered HTML as authority |
| `Check/v1` and `CommitStatus/v1` | CI and status conclusions attached to an immutable revision | Git commit content |
| `ResourceSet/v1` | The exact immutable snapshots and coverage for one logical repository, change-request, or query resource | Retrieval observations or publication state |
| `ProviderSyncManifest/v1` | Transaction state, retrieval evidence, failures, and the resource sets acquired together | Secret material or mutable object bodies |
| `ProviderViewPointer/v1` | A small `current` or `last-complete` reference to one resource set and its committed manifest | Embedded snapshots or mutable acquisition state |
| `Tombstone/v1` | A provider-object deletion backed by a typed event or deleted marker for the exact target | A conclusion inferred from one not-found response or authorization failure |

`GitFetchCredentialLease` is deliberately absent from this record set.
It is an unforgeable process-local handle into a core registry entry that binds one
authorization context and principal to bounded HTTPS Git sources, not a format, durable
identity, provider record, or cache value.

`ChangeRequest/v1` and its index row preserve a null author when the provider no longer
exposes an account. `RevisionRef.repository_id` is also nullable because GitHub can
retain a head ref and object ID after its fork repository becomes unavailable.
The base revision of a selected change request still belongs to its non-null owning
repository; normalization never copies that identity onto an unknown head.

### Provider Revision Observation and Local Object Availability

`RevisionRef`, `GitObjectRef`, and the change-request merge commit record what the
record’s producer observed, not what a local Git store holds.
For hosted records the producer is the provider; for a `RepositoryActivity/v1` commit
item it is the validated local Git history that supplied the commit.
`RevisionObservation` is `observed`, `unavailable`, or `not_requested`: `observed`
carries the producer-supplied full object ID, `unavailable` records that acquisition
requested the object but the producer did not supply it, and `not_requested` records
that acquisition deliberately omitted it.
The object ID is present exactly when the observation is `observed`; the merge commit
uses `merge_commit_observation` with the same rule.

Local availability is a separate fact with a separate vocabulary.
`LocalObjectAvailability` is `not_requested`, `present`, `missing_fetchable`,
`fetch_failed`, `unavailable`, or `outside_bound`, and `LocalGitObjectAvailability`
reports one full object ID with one of those states.
The plain report model requires a full object ID but cannot know where that ID came
from. The observation-guarded constructors enforce the provider-observed rule:
`local_git_object_availability` accepts only a `RevisionRef` or `GitObjectRef` whose
observation is `observed`, and `local_merge_commit_availability` accepts only a
`ComparisonRef` whose `merge_commit_observation` is `observed`. Code that reports local
state for a provider record uses those constructors rather than building the model from
an arbitrary object ID.

The report is a service projection, not an artifact contract: it has no schema, corpus,
route, kind, view, or cache path, and every provider record schema is closed, so no
provider artifact can embed it.
Its consumer is core’s selected-ref service (`mb-jlon`), and core never imports a domain
plugin, so `mb-jlon` moves `LocalObjectAvailability` and `LocalGitObjectAvailability`
into `provider_resources/models.py` together with `AuthorizationContextRef` and
`authorization_context_key`; the observation-guarded constructors stay here beside the
revision records they read.
Fetching an object changes the report, never the immutable provider snapshot that
observed its ID; the store-level contract is in
[Repository Sources and Provider Mirrors](arch-repository-sources-and-provider-mirrors.md#coordinated-hosted-views).
`tests/test_hosted_review_contracts.py` checks that no installed contract schema names
the local vocabulary and that every schema object is closed.

Issue and timeline records are the next domain extension, tracked by `mb-9rrc`. Release
records are a sibling extension with `Release/v1` frontmatter, a structured asset
record, and a bounded index; their separate phased epic follows the general resource
architecture and does not widen the initial PR contracts.
Stacked-change projections are later derived records, tracked by `mb-glxc`. They extend
the registry with closed contracts; they do not add an `extra` object to the v0.12.0
records.

### Artifact profiles

`ChangeRequest/v1`, `ChangeRequestComment/v1`, `Review/v1`, and `ReviewComment/v1` use
SoftSchema’s `frontmatter-md` profile.
Their YAML envelopes hold every value software consumes: identity, lifecycle, actors,
timestamps, links, anchors where applicable, and bounded-collection membership.
The Markdown body is the reader-facing provider prose: the PR description, a top-level
conversation comment, an optional review summary, or an inline review comment.
No index, route, or view parses prose or tables from it to recover structured values.
All persisted timestamps use a canonical RFC 3339 UTC representation with seconds and
`Z`. Zero milliseconds are omitted; a nonzero fraction contains exactly three digits.
Provider adapters convert offsets to UTC and truncate finer precision toward the earlier
millisecond before validation so Python and browser ordering have identical precision.
The format asserts ordering only between timestamps Metabrowser writes from its own
clock: retrieval start and finish, rate-limit and pagination observation, manifest, and
tombstone times. Provider-supplied timestamps are recorded as observed and never ordered
against each other or against the local clock, because providers do emit anomalous
records and a rule would force an adapter to drop or alter one.
Which timestamps a lifecycle state carries remains a structural rule.
The one deliberate exception is tombstone evidence, which refuses a provider deletion
event that predates the previous live observation: that interlock guards a destructive
step and fails closed by keeping the live record.
Provider links use an ASCII canonical HTTPS spelling: lowercase DNS host, no
credentials, no default port, and uppercase hexadecimal percent escapes.
Every structured string is bounded; only Markdown bodies are unbounded content.
Identifiers refuse control characters, line separators, zero-width characters, and
bidirectional formatting controls, so nothing can hide in or visually reorder a value
that is compared, hashed, and joined into derived IDs.
Single-line display text such as titles, names, labels, and refs refuses control
characters and line separators but keeps bidirectional marks, which right-to-left text
legitimately carries.
The bounds are envelopes over the providers the neutral model must admit, not one
provider’s exact limits; each constant in `models.py` records its basis, and lengths
count Unicode code points in both runtimes.
The exception is the stable tokens we name ourselves rather than admit from a provider —
adapter and operation IDs, resource-collection names, and capability tokens — whose
tighter bound is an envelope over our own naming.
Readers accept finite integral JSON numbers, while the serializer writes integer YAML;
all persisted integers remain within JavaScript’s exact range.

This makes one cached PR both application data and an ordinary document.
The Markdown plugin can render the description under the untrusted-content profile,
while the hosted-review plugin composes validated metadata, review state, navigation,
and the resolved File Diff Format around it.
The serializer uses frontmatter-format’s YAML and fence-delimiter primitives, preserves
the provider body as content, and computes snapshot identity from the complete
normalized artifact.
Because that identity hashes bytes, a typed artifact validator accepts only the exact
bytes the serializer writes for the validated record and body.
A YAML comment, alternate quoting or spacing, reordered keys, a tagged scalar, or an
integral float spelling is refused rather than given a second identity, and model
strings are never coerced from another type.
Enumerated values are spelled as strings and are not coerced either: an enum field is
not a string schema, so the rule lives on a shared enum base rather than on each field,
and a registry-wide test fails on an enum that does not carry it.

Indexes, sync manifests, retrieval records, tombstones, threads, checks, and status
records use `pure-yaml` because their entire content is structured or they only refer to
a separately stored comment artifact.
A later issue artifact may use `frontmatter-md` for the same reason as a change request;
that decision belongs to `mb-9rrc` and does not alter the v0.12.0 PR contract.

### Review, Signal, and Activity Contracts

The review family uses closed v1 records rather than a generic event or provider
payload. Every provider-owned entity carries `id`, `provider_ref`, and `repository`;
children also carry the domain IDs needed to resolve their parent records.
A bundle validator resolves those IDs and rejects provider, repository, comparison,
thread, and reply relationships that cross scopes.

| Record | Required fields beyond shared identity |
| --- | --- |
| `ChangeRequestComment/v1` | `change_request_id`, nullable `url` and `author`, `state`, `created_at`, `updated_at` |
| `Review/v1` | `change_request_id`, `url`, nullable `author`, `disposition`, requested immutable `revision`, `created_at`, nullable `submitted_at`, `updated_at` |
| `ReviewThread/v1` | `change_request_id`, typed `anchor`, `state`, nullable `resolved_by`, provider-observed `comment_count` |
| `ReviewComment/v1` | `change_request_id`, nullable `review_id`, `thread_id`, nullable `in_reply_to_id`, nullable `url` and `author`, `state`, typed `anchor`, `created_at`, `updated_at` |
| `Check/v1` | nullable `parent_check_id`, `kind`, observed immutable `revision`, nullable `name`, `status`, nullable `conclusion`, `url`, `started_at`, and `completed_at`; runs require `name` |
| `CommitStatus/v1` | observed immutable `revision`, `context`, `state`, nullable `description` and `target_url`, `created_at`, `updated_at` |

`CommentState` is `visible`, `minimized`, `deleted`, or `unknown`. An author may be null
when provider identity is unavailable, independently of content state; only a deleted
comment may omit its human URL. The record has no synthetic `deleted_at`: provider
deletion timing and proof belong to retrieval and tombstone evidence.
The Markdown body may be empty, but an immutable artifact is not required to erase prose
observed before deletion.

`ReviewDisposition` is `pending`, `commented`, `approved`, `changes_requested`,
`dismissed`, or `unknown`. Pending reviews have no `submitted_at`; every other known
disposition requires it.
The author may be null when provider identity is unavailable.
The reviewed `GitObjectRef` is a requested revision: normally `observed`, but explicitly
`unavailable` when a force push or garbage collection removed the object; it is never
`not_requested`.

Checks distinguish `suite`, `run`, and `unknown` kinds.
A run resolves its parent to a suite for the same immutable revision in the same bundle.
Only a completed check carries a conclusion.
Completed runs require their provider completion time.
GitHub check suites expose neither a name nor start/completion timestamps, so those
fields stay null rather than copying the application slug or substituting
`created_at`/`updated_at` with different semantics.
Check and commit-status revisions are observed immutable Git object references; they are
not restricted to the base repository or current head because providers also report
fork, merge, and synthetic revisions.

#### Review Anchors

`ReviewAnchor` is a discriminated `file`, `line`, or `range` union.
Every variant owns:

- display `path` plus nullable `path_b64`, matching File Diff Format’s lossless Git path
  convention;
- the complete `ComparisonRef` observed with the discussion;
- a requested `original_revision`, either `observed` or explicitly `unavailable`, and a
  `current_revision` with its own explicit observation; and
- `current`, `outdated`, `unresolved`, or `unmappable` state.

A file anchor adds no side or line.
A line anchor adds `base` or `head` side and one positive line.
A range adds ordered `start` and `end` endpoints, each with its own side and positive
line. Independently sided endpoints preserve provider ranges without comparing base and
head line numbers as if they occupied one numeric axis.
When both endpoints use one side, the start line precedes the end line; one-line
locations use the line variant.
When `path_b64` is present, it is canonical standard base64 of the exact non-NUL Git
path bytes, and `path` is their UTF-8 replacement-decoded display.
This preserves non-UTF-8 repository paths without making display text authoritative.

Original revisions are always requested, but the provider may report that the original
commit is unavailable.
They are never `not_requested`. Current, outdated, and unmappable anchors also have an
observed current revision that matches the observed comparison head.
The original and current revisions may differ when a provider remaps a still-current
comment after the change-request head advances.
An unresolved anchor may declare its current revision unavailable or not requested.
The UI may render the original location or an unresolved state; it never invents a
current line.

Review comments resolve their review, thread, and optional parent comment inside the
bundle when those identifiers are present.
A provider comment may have no owning review.
Reply graphs are acyclic, replies stay within one thread, and comment/thread anchors
share the selected change request’s comparison and path.
The observed review-comment count never exceeds the thread’s provider count; equality is
required only when the collection is complete.
Collection cardinality belongs to the trusted resource profile rather than an arbitrary
limit repeated in each record.

#### Repository Activity Projection

`RepositoryActivity/v1` is a recomputable selection/session projection, not a provider
store artifact. Its `repository_id` is the generic repository selection identity, so a
local Git history does not need a fictional `RepositoryRef`. Hosted change-request items
retain their provider and repository references in their detail target and join to the
generic repository through `ProviderBinding/v1`.

The record declares:

- a nonempty, sorted set of included `commit` and `change_request` kinds;
- an explicit `max_items` bound and fixed `event_at_desc_id_asc` order;
- `complete` or `partial` coverage;
- unique activity items; and
- an optional opaque continuation plus required truncation evidence for partial pages.

An `item_bound` truncation names `max_items` and is valid only when the projection
actually reaches that bound.

Each activity item carries stable identity, title, source-neutral actors, event and
update times, primary revision, optional base and head revisions, a
`comparison_observed` flag, a typed detail target, and freshness.
Actors are a closed union: local commit items use Git name plus nullable email, while
hosted change requests use a provider `ActorRef`. A commit item belongs to the enclosing
generic repository.

Commit freshness is `immutable`. Provider-derived change-request freshness is `observed`
with a snapshot ID and observation time.
A change-request item may use `not_requested` revision observations when projected from
a bounded index. Its base repository remains the selected hosted repository, while the
head and primary revision repository IDs remain null when a deleted or inaccessible fork
cannot be identified.
`comparison_observed` is true exactly when the provider observed both base and head
object IDs, and a commit item never claims it.
The flag reports provider evidence only; it keeps activity navigation useful without
claiming that the objects exist in a local store, which
[local object availability](#provider-revision-observation-and-local-object-availability)
reports separately.

## GitHub Coverage Oracle

The no-network oracle under `tests/fixtures/github/oracle/` is evidence about the first
adapter, not another provider model.
Its manifest records exact bounded REST and GraphQL requests, variables, public
resources, reductions, and prose scrubbing.
Each GraphQL document has a request-specific captured root set, and the test requires
the selected root aliases to match that response exactly.
The recorded set covers repository visibility, direct and indexed pull requests, list
continuation and exhaustion, review counts and full review metadata, a same-side range
thread and reply, top-level comment minimization fields, checks, classic statuses, and
the schema nullability that cannot be proven by one successful object response.

`field-inventory.json` starts from the ten normalized records the GitHub mapping will
produce and closes mechanically over every nested Pydantic model and value state.
Every field names its consumers and is classified as observed, deterministically
derived, Metabrowser-owned, or explicitly optional/unavailable.
Consumers are separately marked as current validated code or planned adapter/view work;
an inventory entry is not evidence that a planned consumer already exists.
Observed and derived fields carry mechanically resolved response/request JSON pointers
or validated normalized inputs rather than a capture-level assertion alone.
Closed enum and literal values carry the same disposition-specific evidence.
Structured identity recipes pin the complete provider, instance, repository, canonical
ID kind, number, and provider-object inputs used by each relationship.
Canonical ID kinds remain distinct from provider-object kinds where the formats differ.
`ChangeRequest/v1` verifies its `id` at construction in both runtimes: it must equal
`provider:instance:repository_opaque_id:id_kind:number` for the record’s own
`repository` and `number`, with a separator-free lowercase `id_kind` token.
The ID is matched against those fields and never parsed, because an instance may carry a
port and an opaque ID may contain the separator.
Every other domain ID is opaque to readers, which compare it and never split it.
For a check run, the recorded numeric `check_suite.id` must join exactly one captured
suite database ID before the suite `node_id` becomes the normalized parent ID. The
inventory does not claim the single recorded thread proves file or line anchors,
outdated or resolved threads, nullable actors, nullable review/commit relationships, or
minimized comments. Those states remain explicitly unavailable until evidence supports
them.

`tests/test_github_coverage.py` is the only executable consumer.
It verifies exact model and enum closure, capture provenance, public-safe scrubbing,
closed reduced-response shapes, strict RFC 6901 evidence pointers, GraphQL variable and
root identity, list exhaustion, executable identity derivations, the evidence-driven
nullable boundaries, and separation of hostile synthetic values from recorded evidence.
Secret and private-data checks cover the manifest, inventory, request documents,
recorded responses, and README; every URL-shaped recorded field is HTTPS and belongs to
the explicit public-host and public-resource allowlist.
Runtime code does not import or read the oracle.
The wheel packages only `src/metabrowser`; the source distribution may retain the
directory as repository test evidence.

## Provider Identity Without Provider-Shaped Views

Every durable provider object carries a minimal `ProviderObjectRef` with:

- provider kind, such as `github`;
- provider instance, so public GitHub and an enterprise host do not collide;
- provider object kind; and
- stable opaque provider ID.

Provider kinds are lowercase ASCII tokens.
Provider instances use lowercase DNS `host[:port]` spelling, without a scheme,
credentials, path, or the default HTTPS port, and with a DNS host no longer than 253
ASCII bytes. Canonical provider HTTPS URLs apply the same host bound.
The same scalar validators apply to `ProviderObjectRef`, `RepositoryRef`, and every
storage record, so namespace spelling cannot fork auth, query, or pointer identities.

Repository identity, repository-local number, and canonical human URL remain fields on
the owning domain record.
They are not repeated inside `ProviderObjectRef`, which keeps the same provider identity
usable for repositories, change requests, reviews, checks, and future host types without
turning the reference into a partial copy of each record.

Every provider observation also carries a stable `AuthorizationContextRef` in its
retrieval record and sync manifest: provider kind, provider instance, `anonymous` or
`authenticated` mode, a stable opaque principal ID for authenticated publications, and
an optional `sha256:<lowercase-hex>` capability-partition fingerprint only when those
capabilities change which objects the principal may observe.
Display login, observed scopes or capabilities, and observation time are retrieval
observations, not authorization-context identity.
Neither record carries a token, credential-store path, environment-variable value, or
command output.
An authenticated adapter that cannot resolve a stable opaque principal ID
returns a typed authorization-unavailable state instead of publishing into a shared
authenticated namespace.
Current pointers are scoped by an opaque digest of only the stable context fields so
repeat observations for one principal advance together, while validators and a
permission denial from one principal cannot overwrite another principal’s view.
A last-known observation from another context may be shown only as an explicit offline
fallback labeled with the context that fetched it; it is never treated as fresh or used
to infer deletion.

Normalized lifecycle values use the hosted-review vocabulary.
When GitHub returns a new enum value, the adapter maps it to `unknown` and may retain
the bounded original value in a declared provenance field.
When a GitHub concept has no honest provider-neutral meaning, it receives a closed
GitHub companion record with a named producer and consumer; it does not enter an opaque
extension bag or distort the common contract.

This boundary is reusable without pretending all hosts are identical.
The future GitLab adapter (`mb-51uj`) is a named consumer that justifies neutral
identity and lifecycle terms.
It does not justify fields for GitLab behavior that the implementation has not yet
measured.

### Phase 0B.1 storage record contracts

Phase 0B.1 freezes a no-network record kernel.
These records are closed, frozen Pydantic models with portable JSON fixtures, compiled
SoftSchema contracts, and browser parsers for browser-consumed records.
They remain dormant because no provider adapter, store, route, kind, or view is
registered.

`AuthorizationContextRef` contains exactly `provider`, `instance`, `mode`,
`principal_opaque_id`, and `visibility_partition_digest`. Authenticated contexts require
a principal opaque ID. Anonymous contexts require both the principal and visibility
partition to be null.
The authorization-context key is `sha256:` plus the lowercase SHA-256 digest of the
UTF-8 bytes of this compact, domain-separated JSON array:

```text
["AuthorizationContextRef/v1",provider,instance,mode,principal_opaque_id,visibility_partition_digest]
```

The hash input rejects lone Unicode surrogates rather than relying on runtime-specific
replacement behavior.
Changing display login, capabilities, validators, rate-limit state, or observation time
therefore cannot create another publication namespace.

`Retrieval/v1` owns the exact authorization context and a closed logical request target:
a provider object within a repository, a provider collection identified by normalized
result contract and query key, or a provider binding with conservative source and stable
repository identity.
It also owns adapter ID, `provider_cli`, `direct_http`, or `unknown` transport,
sanitized operation ID, a digest of the exact credential-free provider request, start
and finish times, optional API version, normalization version, named HTTP validators,
optional rate-limit observation, optional display login, and a capability observation
whose state is `observed`, `unavailable`, or `not_requested`. The manifest requires
every retrieval target to match its repository, and every collection retrieval to match
the resource set’s exact logical target.
Its closed tagged outcome is `succeeded`, `not_modified` with a reused collection
artifact, `not_found_under_context`, `explicitly_deleted` with the exact provider
object, repository, evidence kind, and provider event identity and time, or `failed`
with a reason of `permission_denied`, `rate_limited`, `transport_unavailable`,
`provider_error`, `malformed_response`, `output_bound`, `cancelled`, or `unknown`.
Authorization unavailable before a stable authenticated principal is known is an
adapter/service result, not a durable retrieval under a fabricated context.

`ProviderBinding/v1` contains one credential-free `source_id`, one `RepositoryRef`, and
optional typed provenance that names the retrieval snapshot establishing the binding.
The source ID uses the repository library’s conservative normalized-source identity; it
does not prove that two different sources are one repository.
Provenance resolution requires a successful provider-binding retrieval whose `source_id`
and `repository` exactly match the binding; the retrieval target carries the same
`source_id` scalar. The record is independent of authorization, cache-entry existence,
local paths, and mutable repository coordinates.
Several source IDs may bind to the same repository, while a conflicting attempt to bind
one source ID to a different `RepositoryRef` — provider kind, instance, or opaque ID —
fails closed as an explicit rebind conflict.
Changing a repository owner or name updates `HostedRepository/v1`; changing the opaque
repository ID is an explicit rebind conflict.
The conflict is a recoverable state, not a permanent refusal:
[Explicit Rebind](#explicit-rebind) specifies the only path that moves a source to
another `RepositoryRef`.

`validate_provider_binding_successor` accepts a republished binding only when its
`source_id` and `repository` are unchanged.
A binding for another source is a separate binding, not a successor.
Provenance is evidence rather than identity, so a successor may cite a newer
establishing retrieval or omit provenance; this lets a re-resolution record fresh
evidence without pinning the first retrieval forever, and a consumer that requires
evidence resolves the successor’s own provenance, which fails closed when it is absent.
`validate_provider_bindings` validates one binding set: it accepts many sources bound to
one repository, rejects a source bound to different repositories as a rebind conflict,
and rejects any second record for the same source, because a set holds exactly one
current binding per source.
`HostedRepository/v1` contains `provider_ref`, an actor-valued owner, name, canonical
web and clone URLs, visibility, an explicit default-branch availability and name, and
provider creation and update times.
It has no second domain ID, and its provider-native `object_kind` is not forced to the
English word `repository`. Its `RepositoryRef` is the exact projection of the provider
kind, instance, and opaque ID from `provider_ref`.

`ResourceSet/v1` is one immutable logical publication target.
It identifies the repository, authorization context, a provider-object or
provider-collection target, a namespaced versioned profile ID, and uniquely named
collections.
Its persisted shape is structural; a trusted installed `ResourceProfileSpec`
supplies the exact target class, normalized result contract, ordered collection slots,
artifact contracts, minimum and maximum cardinality, pagination policy, and
required-for-`last-complete` status.
Cached content cannot provide that declaration, and an unknown profile fails.
Each collection owns its exact artifact and retrieval snapshot references,
`not_requested`, `partial`, `complete`, or `unavailable` coverage, pagination evidence,
optional truncation, and optional failure retrieval.
An empty exhausted collection is complete when the profile permits zero artifacts or
when its typed index artifact contains no rows.
The repository and change-request-index profiles each require exactly one artifact;
future detail profiles may declare a bounded `0..N` companion collection without
changing the storage kernel.
Partial coverage requires a reason but need not have a continuation; unavailable
coverage requires a typed failure; not-requested coverage proves no attempt.
A complete collection accepts only successful or matching not-modified retrievals.
An unavailable collection cites exactly one typed failure or same-context not-found
attempt, has no pagination, and publishes no artifact.
`provider_failure`, `malformed_response`, and `cancelled` partial truncations cite
exactly one failed retrieval whose closed failure reason agrees with the truncation;
item, page, byte, time, and provider-limit truncations do not cite a failed retrieval.
A resource set is eligible for `last-complete` only when every mandatory collection in
its closed profile is complete and no collection is partial or unavailable.

Pagination evidence contains generic collection pages: contiguous one-based pages,
tagged cursor or page-number continuations, a distinct retrieval snapshot for each page,
observed provider IDs, explicit provider exhaustion, first and last observation times
equal to the first and last page retrieval finish times, and a closed remote-consistency
claim. Page retrieval times are nondecreasing in continuation order.
`provider_snapshot` requires one non-secret token shared by every page;
`best_effort_window` claims only the recorded observation window; `unknown` makes no
snapshot claim. Opaque cursors are bounded URL-free ASCII tokens and cannot be absolute,
protocol-relative, path-relative, rootless-relative, or query-only URLs.
Raw next URLs are never persisted.
Page snapshot tokens are null unless the consistency claim is `provider_snapshot`.

`ProviderSyncManifest/v1` owns an immutable transaction observation: manifest and
transaction identity, repository and authorization context, `staged`, `committed`, or
`failed` state, start and optional finish time, exact retrieval and resource-set
snapshot references, and an optional typed transaction failure.
Resource-set pagination references provide per-page provenance without putting retrieval
times, validators, rate limits, or display auth facts into reusable index or repository
snapshots. Only a committed manifest can back a pointer; committed transactions may
honestly contain partial or unavailable collections.
Staged and failed records remain diagnostics and never advance a pointer.
Each immutable staged, committed, or failed record has its own snapshot ID while sharing
the transaction ID.

`ProviderViewPointer/v1` contains its `current` or `last_complete` role, repository,
authorization-context key, logical target, resource-set snapshot ID, and committed
manifest snapshot ID. Pointer validation resolves maps by those exact snapshot IDs, then
checks every identity field.
A current pointer may select a valid committed resource set only when every collection
required for complete fallback has an attempted outcome: complete, partial, or
unavailable. A `not_requested` optional collection remains valid, but a no-attempt
required collection cannot displace the useful current observation.
A last-complete pointer may select only one complete under its declared
required-collection profile.

Index query keys use a domain-separated compact JSON array and the same UTF-8 SHA-256
rule. The state-filter element is `["all"]` or `["selected",state_1,...,state_n]`, with
selected state values sorted by their ASCII spelling.
The complete hash preimage is:

```text
["ChangeRequestIndexQuery/v1",provider,instance,repository_opaque_id,state_filter,sort_field,sort_direction,"provider_opaque_id",max_items,max_pages,max_bytes,max_duration_ms]
```

The query projection therefore contains provider and repository identity, the closed
state filter, `created_at` or `updated_at` sort and direction, the fixed ascending
provider-opaque-ID tie-breaker, and declared positive safe-integer item, page, byte, and
duration bounds.
It excludes authorization, cursors, results, retrievals, validators, and
observation times. `ChangeRequestIndex/v1` owns only the normalized query, key, and
ordered summary rows.
The enclosing resource-set collection owns coverage and acquisition evidence; the
manifest closes over the referenced retrievals and resource set.
Persisted rows are unique by stable provider ID and sort by the declared primary field,
then provider opaque ID by unsigned UTF-8 byte order ascending; duplicate resolution
belongs to provider normalization before validation.
Invalid UTF-8, including lone surrogates, is rejected even when an index has only one
row.

`Tombstone/v1` names a previous live snapshot and an explicit-deletion retrieval.
Resolution proves the prior snapshot represented the same provider object, repository,
and authorization context.
A deletion event carries its provider event time and must follow that prior live
observation; a deleted marker uses its retrieval finish time as the evidence
observation. The deletion retrieval must have the `explicitly_deleted` outcome for the
exact request target and repository, and both the retrieval and tombstone observation
must fall within the committed manifest transaction.
The evidence validator rejects a lone not-found observation, authentication or
permission failure, rate limiting, cross-context evidence, and a resource never fetched.
Corroborated absence is deferred until a later contract introduces a profile-defined
exhaustive collection; a pull-request discovery index is filtered and cannot provide
that proof.

#### Explicit Rebind

A binding is immutable, so a source whose hosted repository is replaced would otherwise
fail closed forever.
A GitHub repository that is deleted and recreated, or an old name that is registered
again after a transfer, answers at the same URL with a new opaque provider ID. The
source ID is unchanged, the observed `RepositoryRef` differs, and
`validate_provider_binding_successor` correctly refuses the change.
Explicit rebind is the one path that resolves that refusal.
It is designed here and implemented with the Phase 3A binding and store kernel; nothing
in Phase 0 implements it.

**Detection.** Binding resolution that observes a different `RepositoryRef` for a bound
source publishes nothing and reports a typed `rebind_required` state carrying the source
ID, the bound `RepositoryRef`, the observed `RepositoryRef`, and the observing retrieval
snapshot ID. While a source is in that state, provider refresh for it is refused with
the same state. Snapshots already published under the bound repository stay readable and
are labeled stale with the reason, so the conflict never blanks a view that was working.

**Who may trigger it.** Only an explicit action by the local user.
No adapter, refresh job, URL open, plugin, or provider-supplied content may rebind,
because a new opaque ID at an old URL is also exactly what a re-registered namespace
under a different owner looks like.
The format can prove that identity changed; only the user can decide that the new
repository is the one they mean.

**Evidence.** A rebind is one transaction that validates, under the provider/resource
lock, all of the following:

- a fresh `succeeded` provider-binding `Retrieval/v1` whose target carries the same
  `source_id` and the successor `RepositoryRef`, which becomes the successor binding’s
  provenance;
- a retrieval addressed to the previous repository by its opaque ID, whose outcome
  classifies the previous identity as `explicitly_deleted` (a typed deletion event or
  marker), `moved` (it still exists and its `HostedRepository/v1` successor now names
  other coordinates), or `unresolved` (`not_found_under_context`, which by the tombstone
  rule is not proof of deletion);
- the user’s confirmation naming both the expected previous and the expected successor
  `RepositoryRef`, applied as a compare-and-swap so a stale confirmation cannot bind a
  third identity observed later; and
- the same provider kind and instance on both sides.
  A source that now answers from another provider or instance is detached and bound
  afresh rather than rebound.

All three dispositions permit the rebind, because providers rarely expose a deletion
event for a repository and a rebind destroys nothing.
A failed, rate-limited, or unauthorized retrieval on either side permits nothing: the
transaction fails with the retrieval’s reason and the source stays `rebind_required`.

**Record.** `ProviderBinding/v1` stays immutable per source and repository.
The transaction publishes an append-only `ProviderBindingRebind/v1` record holding the
source ID, previous and successor `RepositoryRef`, the previous-identity disposition,
both retrieval snapshot IDs, and the local confirmation time, then replaces the source’s
binding file by compare-and-swap under the source-alias lock followed by the
provider/resource lock.
`validate_provider_binding_successor` keeps refusing a changed repository; a separate
rebind validator accepts the change only when a resolved rebind record links exactly
those two bindings. The new contract arrives with its schema, corpus, inventory row, and
parity evidence like any other registered contract.

**Cached state bound to the previous repository.** Provider state is keyed by hosted
repository identity, not by source, so a rebind moves and rewrites nothing.

- The previous repository’s objects, manifests, and pointers stay where they are, and
  the successor starts empty.
  No snapshot is re-parented: a `ChangeRequest/v1` ID embeds its repository’s opaque ID,
  so a previous change request cannot be read as the successor’s.
- Reader leases on previous snapshots stay valid until released.
  A session already serving a previous bundle keeps serving it, labeled superseded, and
  new resolution of the source uses the successor binding.
  The rebind takes no exclusive generation lock, so it neither waits on nor breaks a
  reader.
- A sync transaction staged under the previous binding fails at publication, because
  publication revalidates the source binding under lock; it moves no pointer.
- The repository store is untouched.
  Private refs and objects that previous snapshots reference stay reachable for as long
  as those snapshots are retained, and selected-ref acquisition for the successor
  verifies full object IDs as it always does.
- Retention follows the disposition.
  After `moved`, the previous repository is still live and any other source bound to it
  is unaffected. After `explicitly_deleted`, a previous repository that no source still
  binds becomes eligible for ordinary reachability reclamation once its bounded
  diagnostic retention passes.
  After `unresolved`, it is retained as a detached repository and reclaimed only by
  explicit purge, because absence under one context is not deletion.
  Cache inspection lists every detached repository with its size so that retention is
  visible rather than silent, and archival pins hold in every case.

**Command line.** The surface is routes, so `metab --api` reaches it by construction and
each response has a golden.
A binding inspection route lists every source binding with state `bound`,
`rebind_required`, or `detached`, and for `rebind_required` both `RepositoryRef` values,
the observing retrieval, and its time.
A rebind action route takes the source ID and the expected previous and successor
`RepositoryRef` as a `--data` body and returns the rebind record or a typed refusal:
`no_conflict`, `expectation_mismatch`, `cross_instance_refused`, or the failed
retrieval’s reason. The hosted-review view shows the same recovery state and invokes the
same route; neither surface ever rebinds as a side effect of opening or refreshing.

## Activity Is a Projection, Not a Second History Authority

Repository Activity Format is a bounded view model over references to source records.
It lets the existing history navigation pattern present commits, change requests, or a
grouped combination without making a PR look like a commit.

Each activity item contains only what a paginated history surface needs: stable item
identity, kind, title, source-neutral actors, event and update times, concise state,
primary revision, optional base/head revisions, comparison capability, detail target,
and source freshness.
Git commit actors use name and optional email; hosted actors keep their provider
identity. The full change-request document remains the authority for review state and
discussion; the Git history session remains the authority for commit ordering and graph
lanes.

Adapters project existing sources into this format:

- the Git history adapter projects commit summaries without changing `/api/git/log`;
- the hosted-review adapter projects `ChangeRequestIndex/v1` rows; and
- a composition service may group or interleave pages only when it can state a stable
  ordering and honest continuation rules.

The initial v0.12.0 view may use separate Commit and Pull Request groups if a stable
mixed cursor would require unbounded reads.
Shared view mechanics do not require a fabricated global order.

## Navigation Containers and Panels

The hosted-review plugin registers a Pull Requests nav panel backed by the bounded
`ChangeRequestIndex/v1`, not by DOM rows or live API data.
It reuses the proven Git-history interaction structure: paged loading, virtualization,
roving selection, explicit loading and stale states, and deterministic restoration.

The collection and its entries use the existing item-like/folder-like roles:

- **Pull Requests collection:** a virtual folder-like root whose children are cached
  change-request summaries; its overview reports query, freshness, completeness, offline
  state, and refresh diagnostics.
- **Change-request row:** item-like because selection opens the PR document and views;
  folder-like because expansion reveals its changed files after the selected bundle and
  comparison manifest are available.
- **Changed-file row:** an ordinary comparison child that opens the shared Diff view and
  the existing base/head revision-content views.

Rows may show only the compact values the index contract guarantees: PR number, title,
nullable author, draft/open/merged/closed state, base and head labels, and updated time.
Description, review and check summaries, full review details, threads, and file changes
remain in the selected bundle and load only after selection.
Counts and folder visibility come from the complete bounded index model, never from the
currently mounted page.

The initial panel may group open, draft, merged, and closed entries or expose a query
control, but the selected query and its bounds are part of the index identity.
Changing the filter cannot relabel a cached page as though it answered another query.

## View and Plugin Ownership

All hosted-review UI consumes clean formats, never a GitHub response:

- a provider plugin recognizes URLs, authenticates, acquires provider data, normalizes
  it, and publishes snapshots;
- a hosted-review plugin validates the common documents and owns activity, repository,
  change-request, review, thread, and status projections;
- the diff plugin renders the resolved comparison as File Diff Format;
- existing revision-content views render a changed file at base or head; and
- the shell supplies routing, plugin mounting, navigation containers, and lifecycle, but
  no provider schema or renderer.

A GitHub-only badge or action belongs to a GitHub companion view registered by the
provider plugin. The common hosted-review renderer neither branches on
`provider == "github"` nor reads provider-specific fields.

The host discovers provider adapters through a closed capability registry.
An installed plugin declares a `ProviderAdapterSpec` with its provider and instance
claims plus a trusted factory callable.
Discovery rejects duplicate claims; application lifespan constructs adapters with only
provider-neutral repository, job, clock, and storage ports and awaits cancellation and
`close()` during root replacement and shutdown.
No server, cache, route, or renderer imports the GitHub adapter.

For v0.12.0, the provider port has one implementation: `gh api` behind the GitHub
adapter (`mb-p4sw`). The port owns repository resolution, auth diagnosis, one bounded
index page, selected PR acquisition, reviews/checks, and rate-limit observations.
It does not expose command output or GitHub response dictionaries to the format or view
layers. A later direct-HTTP or GitLab implementation may satisfy the same port without
changing the stored contracts or renderers.

## Ports and Addresses

Four provider-neutral ports keep URL parsing, acquisition, addressing, and rendering
independently replaceable:

- `ProviderUrlReducer.reduce(raw_url)` returns `NotApplicable`, `Reduced`, or
  `Rejected`. Each reducer declares the schemes and hosts it claims.
  Exactly one reducer may claim an input; overlapping scheme/host claims fail plugin
  discovery, and `Rejected` is terminal rather than falling through to another parser.
  `Reduced` carries a credential-free Git clone source plus a `RepositorySelection`. A
  selection may name ref/path candidates, a line range, or a provider object target.
  GitHub implements the first reducer; the cache only sees its output.
- `HostedReviewProvider` returns common repository, change-request, review, check, and
  index records plus typed retrieval outcomes.
  `GitHubGhAdapter` implements it through `gh api`; no route or renderer imports the
  adapter.
- `AddressSpaceSpec` declares a browser prefix plus its parser, formatter, selection
  application, preview claim, startup, popstate, root-replacement, and disposal hooks.
  The shell arbitrates address ownership before startup, refuses reserved or duplicate
  claims, and uses the same spec for href generation, browser navigation, and
  `metab --show`.
- the core repository service accepts a source or stable repository identity and an
  explicit ref, then returns a leased immutable repository subject pinned to a full Git
  object ID. Provider plugins may request selected PR refs through this port with a
  non-secret `AuthorizationContextRef` and opaque `GitFetchCredentialLease`, but cannot
  inspect credentials, run Git, select an ambient credential helper, or receive a cache
  filesystem path. The port derives the canonical authorization-context key and maps the
  record exactly once to the core `ProviderPrincipal` job identity, including provider
  kind, instance, principal, and optional visibility partition.
  The lease is an unforgeable handle into a core-owned registry; core reads its bound
  identity, expiry, revocation, cancellation generation, and exact credential-free HTTPS
  sources from that registry before job lookup.
  A provider-principal request fails closed rather than falling back to ambient Git
  auth; the isolation rules are in
  [Repository Sources and Provider Mirrors](arch-repository-sources-and-provider-mirrors.md#fetch-and-credentials).

The common hosted-resource address is
`/hosted/<provider-kind>/<instance-key>/<repository-key>/<resource-kind>/<resource-key>[/<inner>]`
and its resource routes live behind a mounted plugin sub-router.
Instance, repository, and resource keys use the canonical typed base64url atom codec in
[External Resources, Artifact Contracts, and Views](arch-external-resources-and-views.md);
raw opaque IDs, PR numbers, and slash-containing tags never become path segments.
The kind registry identifies the validated model and views; GitHub’s `/pull/<number>`
reducer resolves to a `change-request` resource without making the address PR-only.
The bounded index and a direct URL must produce the same record identity, so navigation
never needs an index-specific route.

Mounted routers and browser address spaces are separate plugin-host capabilities, not
hosted-review exceptions.
Each installed plugin declares a validated mount and router callable for HTTP plus an
`AddressSpaceSpec` for browser navigation; the host preserves methods, streaming,
headers, and honest status codes while the address owner controls parse/format/apply and
mounted-preview lifecycle.
Exact data hooks remain the smaller surface for one-segment model endpoints.
Operator-directory plugins remain JavaScript-only, and all mounted state has a shutdown
and root-replacement path.

## Cache Lifetimes

Four caches remain distinct:

1. the repository library durably owns shared worktree-free Git objects, private refs,
   and immutable revision leases;
2. the provider store durably owns repository-scoped, authorization-scoped hosted-review
   snapshots and current manifests;
3. archive and other non-Git projections remain owned by the subsystem that creates
   them, keyed by immutable identity and protected by leases; and
4. activity pages, tree indexes, diff manifests, file patches, and browser projections
   are bounded, recomputable session caches.

Only the second layer is the cache of PR-domain state.
It references the first by repository-store identity and object ID, never uses a mutable
working tree as authority, and never promotes the fourth into a released on-disk
contract. Review anchors are domain data in the second layer, not materialized bytes in
the third. The full ownership contract, including attached local checkouts, is in
[Repository Sources and Provider Mirrors](arch-repository-sources-and-provider-mirrors.md).

Provider publication has two independent axes.
A sync transaction is `staged`, `committed`, or `failed`; each collection inside a
committed manifest is separately `not_requested`, `partial`, `complete`, or
`unavailable`. An interrupted, invalid, or failed transaction cannot move a current
pointer. A structurally valid partial observation may become the newest current
observation so the UI can report what was observed, while a separate `last-complete`
pointer preserves the newest complete fallback.

Index observations also declare remote consistency: `provider_snapshot` when one
provider snapshot token covers every page, `best_effort_window` when pages were fetched
against moving state, or `unknown` when the provider cannot prove either.
They record first and last observation times, stable sort and tie-break rules, per-page
provenance, and deduplication by stable provider ID. `complete` means the provider
reported the requested query exhausted before any item, page, byte, or time bound was
hit. Hitting a bound yields `partial` plus its truncation reason and continuation.
Index completeness never means that separately hydrated PR resources are complete.

Provider storage uses a fixed lock order:

1. the application-home lock only for layout migration and global sweeps;
2. the source-alias lock for alias creation and compare-and-swap repointing;
3. repository-store locks in ascending store-ID order for ref publication, Git
   maintenance, object transfer, and object-database work;
4. a provider/resource lock for binding, staged publication, current-pointer changes,
   and provider reclamation.

No network process runs while any of those locks is held.
Publication reacquires the required alias and repository-store locks when Git state is
part of the transaction and then the provider/resource lock, revalidates the object,
profile, generation, and authorization context, then moves the manifest and pointer by
compare-and-swap. Readers hold shared OS-lock-backed snapshot leases; reclamation takes
the exclusive generation lock before moving state to trash, so process exit releases a
crashed reader without a stale durable lease.
The provider store retains current, `last-complete`, one bounded diagnostic predecessor,
and any explicit archival pin regardless of source availability; it sweeps older
unreachable objects but never automatically removes the last validated reachable
observation.

Everything kept under the application home is owner-only, and Metabrowser refuses remote
acquisition or provider publication when it cannot verify that;
[owner-only storage](../specs/active/plan-2026-08-11-open-repo-from-git-url.md#owner-only-storage)
states the enforced rules.
This refusal does not prevent read-only browsing of an ordinary local path outside the
application home or attaching it to a shared provider mirror without mutating it.

## Acceptance Rules

The first GitHub slice is complete only when:

- GitHub API fixtures normalize into provider-neutral records before any view consumes
  them;
- no common record, route, or hosted-review renderer contains a GitHub-only field or
  branches on GitHub;
- a bounded PR index and a directly addressed PR both produce the same
  `ChangeRequest/v1` identity and selected bundle;
- top-level conversation comments and diff-anchored review comments remain distinct
  artifacts, and anchors cover file-level, single-line, and range forms without
  inventing a line;
- list acquisition fetches no PR Git refs, while selection fetches only the requested
  base, head, and optional merge refs;
- any advertised and authorized branch opens at its resolved full object ID through an
  immutable Git-tree subject without changing a checkout or creating a worktree;
- a user-owned checkout can enable and reuse provider resources without first becoming a
  managed repository-cache entry, and refresh never writes its files or `.git` state;
- two sessions can browse different object IDs from one repository store concurrently,
  while source aliases and local clones bound to one `RepositoryRef` reuse one provider
  mirror;
- a change request opens the same File Diff Format renderer as a commit comparison,
  while its review, check, thread, merge, and freshness details remain available in the
  hosted-review document and views;
- offline reuse preserves the last validated complete or explicitly partial provider
  observation; and
- every browser-consumed hosted-review record passes the packaged browser validator;
- hostile provider strings remain text or untrusted Markdown and provider links accept
  only validated HTTPS URLs; and
- every new format, route, persisted state, address lifecycle, and functional
  interaction appears in the architecture map and exact production-path goldens.

## Decisions for This Design Review

This design PR asks reviewers to accept or reject these boundaries before
implementation:

1. `ChangeRequest`, not GitHub Pull Request, is the durable common domain object; the
   provider-native kind remains explicit provenance.
2. `ChangeRequest/v1`, `ChangeRequestComment/v1`, `Review/v1`, and `ReviewComment/v1`
   are enforced SoftSchema `frontmatter-md` artifacts: YAML is the machine authority and
   the Markdown body is the untrusted provider prose, optional for a review summary.
3. Hosted Review Format, Repository Activity Format, Git, File Diff Format, and revision
   content stay separate and compose through references rather than a union document.
4. The neutral `provider_resources` service owns publication records and store
   mechanics; a hosted-review plugin owns change-request models and views; a GitHub
   provider plugin owns URL recognition, `gh api`, auth, normalization, and GitHub-only
   companion records.
5. The Pull Requests nav panel is a virtual folder-like collection backed by a bounded
   cached index; a selected PR is also a folder-like change container.
6. Durable Git objects, durable provider snapshots, local working-tree attachments, and
   recomputable session caches have different owners and retention rules; revision views
   read objects directly and never require a detached worktree.
7. `gh api` is the only v0.12 transport, behind a provider port that can later support a
   direct GitHub or GitLab adapter without changing formats or views.
8. Provider URL reducers and mounted plugin routers are general host capabilities;
   GitHub URL syntax and hosted-review routes remain plugin-owned.
9. Direct PR acquisition and viewing ship before the bounded PR index and virtual nav
   collection; discovery is additive rather than a prerequisite for addressing.
10. Provider observations and validators are scoped by a non-secret authorization
    context; transaction state, collection coverage, and remote consistency are three
    separate claims.
11. Provider adapters and browser address spaces are general installed-plugin
    capabilities with duplicate-claim arbitration and awaited lifecycle, not implicit
    imports or router side effects.
12. Provider reclamation is reachability- and lease-based: current, last-complete, one
    diagnostic predecessor, and archival pins survive, while older unreachable objects
    remain bounded even for offline or deleted sources.
13. Artifact contracts, resource profiles, and resource kinds are separate trusted
    registries; no universal entity payload or cached registry declaration is added.

Implementation evidence still decides concrete page and collection bounds, exact REST
versus GraphQL queries, whether the initial activity panel groups commits and PRs or can
support an honest mixed cursor, and the measured worktree-free Git and physical snapshot
layouts. Those decisions may tune cost and presentation; they may not collapse the
accepted format, plugin, identity, or cache boundaries.

The implementation plan and release scope live in
[Hosted Review Model and GitHub Provider](../specs/active/plan-2026-08-27-github-provider-and-pull-requests.md).
The lower layers live in
[Git and Comparison Sources](arch-git-and-comparison-sources.md) and
[File Diff Format v1](file-diff-format/file-diff-format.md).

## References

- [SoftSchema v0.8.1 guide](https://github.com/jlevy/softschema/blob/v0.8.1/docs/softschema-guide.md)
- [frontmatter-format](https://github.com/jlevy/frontmatter-format)
- [Nav Containers](arch-nav-containers.md)
- [Views, Models, and Routes](arch-views-models-routes.md)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
