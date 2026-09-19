# External Resources, Artifact Contracts, and Views

**Status:** Accepted design; the provider-neutral model contracts, installed contract
and resource-profile registries, and generic format inventory gate are implemented
through Phase 0C.2. Provider bindings and storage, the resource-kind registry,
addressing, and views remain planned and unregistered.

Metabrowser should be able to browse a useful object from an API or external system
without turning that provider’s response shape into a core model or building a new UI
stack for every integration.
The durable path is:

```text
external API   provider adapter   validated artifact   cached resource   registered view
     │                 │                  │                    │                 │
     └── raw input ───► normalize ───────► publish ───────────► select ─────────► render
```

GitHub pull requests are the first demanding consumer.
GitHub releases are the next named design case.
The architecture is not a GitHub abstraction: another installed plugin can map a
different API into its own contracts, resource profiles, addresses, and views while
using the same validation, cache publication, selection, rendering, navigation, and
parity machinery.

The governing qualities are flexibility, transparent formats, and compositionality.
A rich object remains inspectable as ordinary text; a view consumes a validated contract
instead of a provider payload; and common mechanics are shared without collapsing unlike
domain objects into one weak schema.

## Vocabulary

Four concepts stay distinct:

- An **entity** is a stable domain identity when the domain has one: a repository,
  change request, issue, release, or release asset.
- An **artifact** is one immutable, validated observation identified by contract ID and
  content digest. A diff or query result can be an artifact without being a domain
  entity.
- A **resource** is an addressable selection in Metabrowser.
  A resource may be an item, a container, or both, and may resolve one artifact or a
  validated bundle.
- A **view** renders a declared model for a resource.
  It does not decide which provider, route, cache file, or acquisition command produced
  that model.

“Everything is an item” therefore means that every selection reaches the same resource
and view protocol. It does not mean every persisted value inherits from a universal
`Entity/v1` record. Files retain path identity and native bytes, commits retain Git
identity, diffs remain relational change-set artifacts, and hosted objects retain
provider identity. The common layer is composition and dispatch, not an open payload
wrapper.

Item-like and container-like are capabilities rather than mutually exclusive classes.
A change request is an item whose default view is a review document and a container
whose children are changed files.
A release is an item whose default view is a release document and may be a container
whose children are release assets.
A repository-scoped Pull Requests or Releases list is a bounded collection resource.

## Transparent Artifact Profiles

The artifact profile follows the content:

| Content | Profile | Authority |
| --- | --- | --- |
| Prose-bearing external object | SoftSchema `frontmatter-md` | YAML frontmatter contains every machine-consumed value; the Markdown body contains the complete reader-facing prose |
| Structured object, index, manifest, or companion record | SoftSchema `pure-yaml` | YAML contains the complete record |
| Native repository file | Native bytes plus the validated file envelope | The file remains the source; a view does not rewrite it into an entity record |
| Derived comparison | Its domain format, such as File Diff Format | The comparison model is authoritative; source objects remain references |

The Markdown body is never parsed to recover fields.
For a pull request it is the description; for a release it is the release notes; for an
issue it may be the issue body.
It participates in snapshot identity and remains usable in raw Source and editing
workflows even when no rich view is loaded.
The rich view composes validated metadata, the shared Markdown renderer, companion
records, and other registered views such as Diff.

Every persisted record is closed at its released version.
Provider-only data enters a named companion contract with a named producer and consumer,
not an `extra` mapping.
Cached frontmatter may name its contract, envelope, and status, but it cannot name a
schema path or renderer.
The trusted installed registry is the authority that resolves those names.

## Three Trusted Registries

The system uses three linked registries rather than one mega-registry.

### Artifact contract registry

An installed plugin declares one entry per contract ID:

- envelope and `frontmatter-md` or `pure-yaml` profile;
- packaged compiled schema, registry-verified exact byte digest, and an independently
  recomputed compiler-compatible logical schema digest;
- semantic model and validator;
- parser and deterministic serializer;
- producer and named consumers;
- an explicit browser-consumption flag plus immutable self-contained browser-parser
  module bytes and digest when the browser consumes the record; and
- immutable conformance-corpus bytes, digest, record selectors, and installed-artifact
  evidence.

The evidence bytes make an installed declaration self-resolving without trusting a
source-tree path. They do not register a runtime browser asset or view; that later
binding must name the same module digest through the installed browser plugin.

Duplicate contract IDs or conflicting declarations fail plugin discovery.
Unregistered contracts fail before publication or rendering.
The host registry outranks any metadata in an untrusted artifact.

### Resource-profile registry

A resource profile declares how immutable artifacts form one publishable resource:

- namespaced, versioned profile ID;
- provider-object or provider-collection target class;
- result contract for a collection query;
- ordered collection slots;
- artifact contract and minimum/maximum cardinality for each slot;
- pagination policy for each slot; and
- which slots must be complete for a `last-complete` pointer.

`ResourceSet/v1` persists the profile ID, logical target, coverage, artifact references,
retrieval evidence, pagination, and truncation.
It does not persist its own declaration.
The installed profile registry supplies the trusted meaning, so cached data cannot
weaken cardinality, change a contract, or declare an optional collection complete.

Phase 0B.1 includes provider-neutral object and collection targets, generic collection
pages, and trusted in-plugin profile declarations.
Phase 0C moves their installation and inventory checks into the plugin loader through
the versioned `metabrowser.capabilities.v1` entry-point group.
Only installed Python distributions may contribute these capability sets.
Browser manifests and operator-supplied JavaScript plugin directories cannot register
contracts or profiles, and the capability factories never become cache data.

### Installed contract and profile inventory

The tables below register the installed format surface.
Runtime admission verifies the exact packaged schema, corpus, and browser-parser bytes
and their declared digests; the table records stable contract semantics rather than
filesystem paths or generated hashes.
A browser-parser entry is installed validation evidence, not a browser plugin, static
asset, view, kind, or runtime registration.
`server-only` means the declaration explicitly forbids browser consumption and parser
evidence. Browser-consumed declarations require parser evidence; consumer ID spelling
never selects the rule.
Parser evidence runs exact module bytes with imports and dynamic code generation
disabled.
The VM exposes only context-native `TextEncoder`, one-shot UTF-8 `TextDecoder`,
`atob`, and `btoa` browser capabilities and constructs each input in that realm; no host
object or function crosses the boundary.
Type-sensitive JSON-domain comparison accepts complete cross-realm clones without
accepting mutation, record loss, or primitive type changes.

`devtools/check_artifact_contracts.py` compares both tables with installed capability
declarations and runs the generic schema, semantic-validator, positive/negative corpus,
deterministic artifact-profile round-trip, browser-parser, and profile evidence gate.
The distribution check runs the same installed inventory against isolated wheel and
source distribution installs, so a source-tree-only declaration or evidence file cannot
pass.

| Contract ID | Artifact profile | Envelope | Producers | Consumers | Corpus | Browser parser |
| --- | --- | --- | --- | --- | --- | --- |
| `com.github.jlevy.metabrowser.activity:RepositoryActivity/v1` | `pure-yaml` | `repository_activity` | `hosted-review-provider` | `hosted-review-service` | `repository-activity-conformance[*]` | `hosted-review-model:parseRepositoryActivity` |
| `com.github.jlevy.metabrowser.review:ChangeRequest/v1` | `frontmatter-md` | `change_request` | `hosted-review-provider` | `hosted-review-service` | `change-request-conformance[*]` | `hosted-review-model:parseChangeRequest` |
| `com.github.jlevy.metabrowser.review:ChangeRequestComment/v1` | `frontmatter-md` | `change_request_comment` | `hosted-review-provider` | `hosted-review-service` | `review-records-conformance[change_request_comment]` | `hosted-review-model:parseChangeRequestComment` |
| `com.github.jlevy.metabrowser.review:ChangeRequestIndex/v1` | `pure-yaml` | `change_request_index` | `hosted-review-provider` | `hosted-review-service` | `change-request-index-conformance[change_request_index,empty_change_request_index]` | `hosted-review-model:parseChangeRequestIndex` |
| `com.github.jlevy.metabrowser.review:Check/v1` | `pure-yaml` | `check` | `hosted-review-provider` | `hosted-review-service` | `review-records-conformance[check_suite,check_run]` | `hosted-review-model:parseCheck` |
| `com.github.jlevy.metabrowser.review:CommitStatus/v1` | `pure-yaml` | `commit_status` | `hosted-review-provider` | `hosted-review-service` | `review-records-conformance[commit_status]` | `hosted-review-model:parseCommitStatus` |
| `com.github.jlevy.metabrowser.review:Review/v1` | `frontmatter-md` | `review` | `hosted-review-provider` | `hosted-review-service` | `review-records-conformance[review]` | `hosted-review-model:parseReview` |
| `com.github.jlevy.metabrowser.review:ReviewComment/v1` | `frontmatter-md` | `review_comment` | `hosted-review-provider` | `hosted-review-service` | `review-records-conformance[review_comment,review_comment_reply]` | `hosted-review-model:parseReviewComment` |
| `com.github.jlevy.metabrowser.review:ReviewThread/v1` | `pure-yaml` | `review_thread` | `hosted-review-provider` | `hosted-review-service` | `review-records-conformance[review_thread,review_thread_empty]` | `hosted-review-model:parseReviewThread` |
| `com.github.jlevy.metabrowser.provider:HostedRepository/v1` | `pure-yaml` | `hosted_repository` | `provider-adapter` | `hosted-review-service,provider-resource-store` | `hosted-repository-conformance[hosted_repository]` | `hosted-review-model:parseHostedRepository` |
| `com.github.jlevy.metabrowser.provider:ProviderBinding/v1` | `pure-yaml` | `provider_binding` | `provider-adapter` | `provider-resource-store` | `hosted-repository-conformance[provider_binding]` | `server-only` |
| `com.github.jlevy.metabrowser.provider:ProviderSyncManifest/v1` | `pure-yaml` | `provider_sync_manifest` | `provider-adapter` | `provider-resource-store` | `provider-storage-conformance[provider_sync_manifest]` | `server-only` |
| `com.github.jlevy.metabrowser.provider:ProviderViewPointer/v1` | `pure-yaml` | `provider_view_pointer` | `provider-adapter` | `provider-resource-store` | `provider-storage-conformance[provider_view_pointer]` | `server-only` |
| `com.github.jlevy.metabrowser.provider:ResourceSet/v1` | `pure-yaml` | `resource_set` | `provider-adapter` | `provider-resource-store` | `provider-storage-conformance[resource_set]` | `server-only` |
| `com.github.jlevy.metabrowser.provider:Retrieval/v1` | `pure-yaml` | `retrieval` | `provider-adapter` | `provider-resource-store` | `provider-storage-conformance[retrieval,deletion_retrieval]` | `server-only` |
| `com.github.jlevy.metabrowser.provider:Tombstone/v1` | `pure-yaml` | `tombstone` | `provider-adapter` | `provider-resource-store` | `provider-storage-conformance[tombstone]` | `server-only` |

| Profile ID | Target kind | Result contract | Collections | Pagination | Last complete |
| --- | --- | --- | --- | --- | --- |
| `com.github.jlevy.metabrowser.review:change-request-index/v1` | `provider_collection` | `com.github.jlevy.metabrowser.review:ChangeRequestIndex/v1` | `change_request_index=com.github.jlevy.metabrowser.review:ChangeRequestIndex/v1[1..1]` | `change_request_index=required` | `change_request_index` |
| `com.github.jlevy.metabrowser.provider:repository-summary/v1` | `provider_object` | — | `repository=com.github.jlevy.metabrowser.provider:HostedRepository/v1[1..1]` | `repository=forbidden` | `repository` |

### Resource-kind registry

A resource-kind declaration connects an addressable selection to presentation:

- stable kind ID;
- primary contract or model factory;
- item and container capabilities;
- default and additional views;
- address-space and route owner;
- optional virtual-collection projection; and
- CLI and browserless functional evidence.

The existing file `[[kind]]` and `[[view]]` declarations are the first implementation of
this idea, but their matcher is filesystem-specific.
Route-backed resources receive a separate `ResourceKindSpec`; they do not invent a file
extension or overload the file-type taxonomy.
The installed registry becomes the single authority for server view metadata and browser
registration, and rejects duplicate `(kind, view)` claims deterministically.

## Provider Storage Is Content-Neutral

Provider-resource foundations and the shared minimal `HostedRepository/v1` summary use
the `com.github.jlevy.metabrowser.provider` contract namespace.
Other domain records keep their own namespaces, such as `review` for change requests and
the future release namespace for releases.

The neutral `src/metabrowser/provider_resources/` package owns canonical provider kind
and instance scalars, `ProviderObjectRef`, `RepositoryRef`, `AuthorizationContextRef`,
generic object/collection targets, bindings, retrieval and publication records, the
minimal provider-neutral `HostedRepository/v1` contract and repository-summary profile,
publication validation, and the filesystem store behind `ProviderResourceStorePort`.
Domain plugins own `ChangeRequest`, `Release`, their companion records, contracts,
profiles, routes, and views; provider-specific repository companions remain in their
provider plugins. The host injects the store port through the trusted plugin lifecycle;
it never exposes a cache path or asks a domain plugin to import another domain plugin.
The `hosted_review` plugin owns change-request contracts and views, the future
`hosted_releases` plugin owns release contracts and views, and a provider plugin such as
`github` owns acquisition and normalization.
An unrelated external-system plugin can therefore publish its own registered contract
and profile without importing hosted review or reproducing cache machinery.

A `ProviderObjectRef` identifies a provider entity by provider kind, instance, native
object kind, and opaque ID. A provider-collection target identifies its normalized
result contract and a domain-separated query key.
The same `Retrieval/v1`, `ResourceSet/v1`, sync manifest, current and last-complete
pointers, authorization context, pagination evidence, and explicit tombstone proof can
therefore publish repositories, change requests, releases, issues, or another plugin’s
closed records.

Adding a record type must not add another target variant to the storage kernel.
It adds an artifact contract and resource-profile declaration.
Adding a provider must not change common views.
It adds an adapter that emits already-registered common contracts, plus named provider
companions only where a view has a real provider-specific consumer.

The cache stores normalized artifacts, not raw API responses.
Adapters discard raw payloads after bounded parsing and validation.
All publications remain authorization-scoped, immutable, atomically manifested, explicit
about partiality, and reusable offline.
A collection omission never proves entity deletion; only typed deletion evidence can
advance a tombstone.

Provider storage is global to the application home and repository-scoped.
Its logical key is provider kind, provider instance, stable repository opaque ID,
authorization context, and logical target/profile/query.
It is not nested under a generic repository cache entry or a user-owned checkout.
Conservative Git source identities and ephemeral local sessions attach many-to-one to
the stable repository identity, so two local clones and several URL spellings can reuse
the same provider observations without sharing a working tree.

The provider cache is a mirror only of enabled, validated resource profiles.
A refresh publishes another immutable observation and atomically advances a pointer; it
never edits an artifact in place.
Remote consistency remains explicit because several API endpoints may describe a
best-effort observation window rather than one provider snapshot.
The source, Git-object, attachment, locking, and multi-client rules live in
[Repository Sources and Provider Mirrors](arch-repository-sources-and-provider-mirrors.md).

## Views Compose Models

The view host receives a generic selection envelope containing the resource kind,
canonical address, available views, selected view, and validated model reference.
Provider strings never decide a renderer.

Common reusable pieces include:

- Source rendering for canonical artifact bytes;
- untrusted Markdown rendering for frontmatter bodies;
- File Diff Format for comparisons from files, commits, or change requests;
- revision-content views for immutable Git object IDs;
- bounded virtual-list paging and nav restoration;
- item/container selection and child addressing; and
- loading, unavailable, partial, stale, and offline states.

Domain plugins compose these pieces.
The hosted-review view can place PR metadata and review state around the same diff view
used for history. A release view can place release metadata and assets around the same
Markdown and revision-content views.
Core owns selection, lifecycle, arbitration, and safe rendering boundaries; it does not
own GitHub fields or release HTML.

## Canonical Hosted Addresses

The internal browser address is:

```text
/hosted/<provider-kind>/<instance-key>/<repository-key>/<resource-kind>/<resource-key>[/<inner>]
```

Provider kind and resource kind are bounded lowercase ASCII tokens.
The other keys use one canonical reversible atom codec: `encode_provider_address_atom`
writes UTF-8 bytes as unpadded base64url and prefixes the result with its declared role;
`decode_provider_address_atom` rejects padding, noncanonical spellings, invalid UTF-8,
wrong role prefixes, and decoded values outside the owning scalar bound.
The key preimages are the canonical provider instance, repository opaque ID, and
resource provider-object opaque ID, respectively.
Including provider instance prevents a public GitHub object from colliding with an
Enterprise object that uses the same native ID.

Provider web locators that are not stable object identity do not become canonical
resource keys. A GitHub PR number or slash-containing release tag remains a typed
`RepositorySelection` during URL reduction and acquisition.
After the adapter resolves the stable provider object ID, navigation formats the
canonical `object-<atom>` resource key.
The bounded index and direct acquisition therefore converge on the same address.

`provider_addresses.py` owns `encode_provider_address_atom`,
`decode_provider_address_atom`, `parse_hosted_address`, and `format_hosted_address`.
`AddressSpaceSpec`, provider URL reducers, link generation, popstate, and `metab --show`
all call those functions.
The corpus covers ports in provider instances, non-ASCII opaque IDs, percent signs,
slashes and dot segments in provider values, empty or oversized values, wrong prefixes,
padding, and noncanonical base64url.

## Mapping a New External System

An integration follows one reviewable path:

1. Name the user workflows and fields each consumer needs.
   Do not start from the full provider response.
2. Define closed provider-neutral artifacts.
   Put prose in a Markdown body and all consumed values in YAML.
3. Add valid and invalid conformance artifacts, semantic relationship tests, and a
   scrubbed provider coverage oracle that distinguishes observed, derived, optional, and
   unavailable fields.
4. Declare resource profiles with exact target, collection, contract, cardinality,
   pagination, and completeness semantics.
5. Implement a bounded provider adapter that normalizes immediately and publishes only
   validated artifacts through the common store.
6. Declare resource kinds, addresses, routes, views, and optional virtual collections.
7. Ship the contract, producer, consumer, schema, corpus, distribution evidence, CLI
   parity, browserless interaction evidence, and lifecycle/disposal checks together.

This sequence makes “support an API object” routine without making it automatic.
The difficult domain decisions—identity, lifecycle, completeness, deletion, and which
fields have consumers—remain explicit and reviewable.

## GitHub Specialization

GitHub remains deliberately excellent rather than merely generic:

- its URL reducer recognizes repository, branch, file, commit, pull-request, and later
  release URLs;
- its adapter uses fixed, bounded `gh api` requests and existing `gh` authentication;
- GitHub-only actions or badges live in GitHub companion views; and
- GitHub navigation can choose familiar labels and grouping while reading common
  resource models.

Those customizations sit above the common contracts and cache.
No common renderer branches on `provider == "github"`, and no cache path is derived
directly from a GitHub URL.

## Releases as the Next Design Case

Releases prove that the architecture is broader than code review without expanding the
initial v0.11 PR slice.

`Release/v1` is a provider-neutral `frontmatter-md` artifact.
Its YAML contains provider and repository identity, canonical URL, tag name, exact tag
revision observation, normalized title, optional author, publication state, release
stage, creation time, and optional release time.
Its body is the complete release notes.
GitHub’s `target_commitish`, generated-notes controls, mutable “latest” status, and
other presentation-specific fields do not enter the common v1 without a named consumer.

`ReleaseAsset/v1` is a separate pure-YAML record so mutable download observations do not
rewrite the release-notes artifact.
`ReleaseIndex/v1` is a bounded pure-YAML query and summary-row artifact; acquisition
coverage and pagination remain in `ResourceSet/v1`. A release-detail profile contains
exactly one Release and `0..N` ReleaseAsset artifacts, where the installed profile
declares `N`; exceeding the bound produces explicit partial/truncation evidence rather
than an unbounded collection.
A release-index profile contains exactly one ReleaseIndex artifact.
Asset bytes are fetched on demand under an explicit content policy rather than becoming
provider-cache objects by implication.

The future `release` resource kind is item-like with Release and Source views and
container-like when assets are available.
A repository-scoped Releases collection reuses the same virtual navigation contract as
Pull Requests. Tag navigation resolves through the exact observed Git object ID, not a
mutable branch name.

## Planned Implementation Seams

| Area | Primary files and functions | Responsibility |
| --- | --- | --- |
| Neutral provider resources | `provider_resources/models.py`: provider/instance scalars, identity refs, generic targets, bindings, storage records, profile types, and publication validators; `provider_resources/store.py`: `stage_snapshot`, `publish_manifest`, `read_current`, `read_last_complete`, `lease_snapshot`, `reclaim_snapshots`; `plugin_api.py`: `ProviderResourceStorePort` | Give unrelated domain and provider plugins one content-neutral, auth-scoped publication service without exposing paths or hosted-review internals; domain objects and artifact contracts stay in their owning plugins |
| Capability declarations | `plugin_loader/capability_types.py`: `ArtifactContractSpec`, `ArtifactValidationContext`, `CapabilitySet` | Expose dependency-light installed declaration types without importing schema parsing, validation, or discovery on ordinary startup paths |
| Installed capability discovery | `plugin_loader/capability_discovery.py`: `discover_capability_sets` | Load all-or-nothing `metabrowser.capabilities.v1` factories from installed distributions; reject duplicate providers and exclude operator plugin directories |
| Contract installation | `plugin_loader/artifact_contracts.py`: `build_contract_registry`, `validate_record`, `validate_artifact`, `serialize_artifact`, `contract_inventory` | Install trusted SoftSchema declarations returned as Python objects and reject missing, conflicting, or incomplete contracts |
| Resource profiles | Domain capability factories; `plugin_loader/artifact_contracts.py`: `build_resource_profile_registry`, `resolve_resource_profile`; staged `hosted_review/models.py`: `validate_resource_set_against_profile`, moving to `provider_resources/models.py` under `mb-s0gv` | Close collection contracts, cardinality, pagination, and completeness outside cached records; profiles belong to the domain capability that owns their artifact contracts |
| Resource kinds | `plugin_loader/manifest.py`: `ResourceKindSpec`; installed resource registry | Bind addressed models to item/container capabilities and views without file matchers |
| Selection host | `static/resource-context.js`, `static/view-composition.js`, and the file-specific shell extraction from `static/app.js` | Present one validated selection envelope to registered views |
| Addressing | `plugin_loader/provider_addresses.py`: `encode_provider_address_atom`, `decode_provider_address_atom`, `parse_hosted_address`, `format_hosted_address`; provider URL reducers, `AddressSpaceSpec`, mounted routers, and `show_cli.py::run_show` | Include provider instance, use one canonical typed atom codec, and share parse/format/apply rules in browser and CLI |
| Virtual navigation | plugin SDK nav registration and the generalized Git-history window mechanics | Page, select, restore, replace, and dispose repository-scoped collections |
| Repository subjects and attachments | `repository_context.py`: subject descriptors and remote discovery; `content_source.py`: source contract; `git/tree_source.py`: immutable tree/blob reads; `cache/repository_store.py`: shared object store and revision leases | Let local working trees, URL-opened repositories, branches, and hosted comparisons share cached data without a mutable checkout or entry-owned provider state |
| Enforcement | `devtools/check_artifact_contracts.py`, `devtools/check_parity.py`, distribution smoke, and goldens | Require every registered contract, profile, kind, route, and functional interaction to have evidence |

These seams are phased.
Phase 0B.1 freezes generic provider storage and built-in profiles without registering a
route or view. Phase 0C installs the contract and resource-profile registries and checks
their format inventory.
Route-backed resource kinds and the generic selection host land before direct PR views.
Release contracts, acquisition, direct views, and the Releases collection then land as
separate formal pull requests.

## Acceptance Rules

The architecture is satisfied only when:

- adding a release index does not add a storage target variant;
- adding a new provider does not change a common domain renderer;
- cached content cannot choose a schema, renderer, executable, or filesystem path;
- every structured value consumed by software is in authoritative YAML or another
  declared domain format, never recovered from presentation text;
- raw Source and rich views describe the same immutable artifact;
- attached local repositories and managed URL opens bound to the same stable provider
  repository reuse one authorization-scoped provider mirror;
- concurrent revision views read full object IDs from a shared worktree-free Git store
  without switching or materializing a checkout;
- item/container behavior, routes, views, and virtual collections share one canonical
  selection identity;
- every browser-consumed route and interaction has a `metab` equivalent and production
  JavaScript golden; and
- a registered contract or resource kind without its schema, corpus, producer, consumer,
  distribution proof, and architecture-map entry fails the build.

## References

- [Hosted Review Model and Provider Boundary](arch-hosted-review-model.md)
- [Views, Models, and Routes](arch-views-models-routes.md)
- [Nav Containers](arch-nav-containers.md)
- [SoftSchema guide](https://github.com/jlevy/softschema/blob/v0.8.1/docs/softschema-guide.md)
- [GitHub Releases API](https://docs.github.com/en/rest/releases/releases)
- [GitHub Release Assets API](https://docs.github.com/en/rest/releases/assets)
- [GitLab Releases API](https://docs.gitlab.com/api/releases/)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
