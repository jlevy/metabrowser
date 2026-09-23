---
type: is
id: is-01m2h9jjh45d8db9rbd0qtscf7
title: "Plugin SDK: installed plugin address spaces and browser navigation lifecycle"
kind: feature
status: open
priority: 1
version: 8
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - release:v0.12.0
dependencies:
  - type: blocks
    target: is-01m2h7hrjt6yzb16neh8g2zvsd
  - type: blocks
    target: is-01m2ktkve5n2fztx8smd6n9vja
  - type: blocks
    target: is-01m2kw2cra83fyszkrptvhfead
parent_id: is-01m10vgwqwn8gjdv8fm183vztr
created_at: 2026-09-15T01:05:50.112Z
updated_at: 2026-09-23T00:21:41.289Z
---
Add an installed-plugin AddressSpaceSpec and registerAddressSpace SDK surface with parser, formatter, selection apply/mount, preview claim, startup, popstate, root replacement, and disposal. Core refuses reserved, duplicate, or overlapping prefixes and requires exactly one owner; browser navigation and metab --show share the registry. Implement provider_addresses.py encode_provider_address_atom, decode_provider_address_atom, parse_hosted_address, and format_hosted_address for /hosted/<provider-kind>/<instance-key>/<repository-key>/<resource-kind>/<resource-key>[/<inner>]. Use typed reversible unpadded base64url atoms for instance, repository opaque ID, and provider-object opaque ID; reject padding, wrong prefixes, noncanonical spellings, invalid UTF-8, dot segments, and bounds violations. Prove ports, Unicode, percent signs, slashes, empty/oversized values, and direct/index identity convergence in corpus, hosted-review-session, and cli-ui-hosted-review.
