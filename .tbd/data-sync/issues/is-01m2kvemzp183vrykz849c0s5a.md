---
type: is
id: is-01m2kvemzp183vrykz849c0s5a
title: "Provider resources: neutral artifact publication and cache port"
kind: feature
status: open
priority: 1
version: 5
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - release:v0.11.0
  - provider-resources
dependencies:
  - type: blocks
    target: is-01m2ktnwpapx26rybv4w3pbshk
  - type: blocks
    target: is-01m2h9jm62mjccx6x3bx0nct2a
  - type: blocks
    target: is-01m2kw2bvjj5kcsczkz40cmhqx
parent_id: is-01m10xd666fefs5z7ft5m58zj0
created_at: 2026-09-16T00:56:44.789Z
updated_at: 2026-09-16T01:24:56.852Z
---
Before provider schemas and storage implementation become durable, extract provider-content-neutral identity and publication ownership from builtin_plugins/hosted_review into src/metabrowser/provider_resources/. Move provider kind/instance scalars, ProviderObjectRef, RepositoryRef, AuthorizationContextRef, generic object/collection targets, ProviderBinding, Retrieval, ResourceSet, manifests, pointers, tombstones, profile types, the shared minimal HostedRepository/v1 contract, and its repository-summary profile without compatibility aliases because they are unreleased. Define ProviderResourceStorePort in plugin_api with stage_snapshot, publish_manifest, read_current, read_last_complete, lease_snapshot, and reclaim methods; inject it through trusted lifecycle registration. Keep ChangeRequest, Release, their companions, routes, and views in their domain plugins. Prove an unrelated external-system plugin can register a contract/profile and publish/read a resource without importing hosted_review. mb-i3xc implements the filesystem store kernel behind the port.
