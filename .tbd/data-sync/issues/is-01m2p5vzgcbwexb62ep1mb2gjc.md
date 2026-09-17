---
type: is
id: is-01m2p5vzgcbwexb62ep1mb2gjc
title: "GitHub Phase 3A: broker-pinned Git credential lease bridge"
kind: task
status: open
priority: 1
version: 12
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
delegate: claude-code@spud10.local
labels:
  - release:v0.11.0
dependencies:
  - type: blocks
    target: is-01m2h7h50h2y8hhhq7x7f1zcmd
  - type: blocks
    target: is-01m2kw2bvjj5kcsczkz40cmhqx
parent_id: is-01m2h5an32kbkp6zfkhkjzq55f
hold: null
hold_until: null
created_at: 2026-09-16T22:37:16.170Z
updated_at: 2026-09-17T01:36:50.541Z
started_at: 2026-09-16T22:47:02.715Z
---
Implement the Phase 3A Git credential projection for authenticated provider-selected refs, consuming the Phase 2B GitFetchCredentialLeaseRegistry and context conversion from mb-jlon and the broker lease issuance from mb-y1ax. Keep git/process.py as the sole Git runner and project a validated lease through a packaged askpass bridge over a measured bounded inherited pipe or local IPC; replace Phase 2B's pre-Git git_credentials_unavailable refusal with this projection, never an ambient fallback. Isolate every provider-principal Git run as docs/project/architecture/arch-repository-sources-and-provider-mirrors.md#fetch-jobs-authorization-and-credentials defines. Environment: a short allowlisted environment, not a scrubbed copy of os.environ, with fixed PATH and locale, an empty Metabrowser-owned HOME and XDG_CONFIG_HOME, terminal prompting disabled, and only named proxy and certificate variables; NETRC, SSH_AUTH_SOCK, GIT_CONFIG_*, GIT_TRACE*, GIT_CURL_VERBOSE, and GIT_SSL_NO_VERIFY never pass. Configuration: system and global Git configuration disabled; fetch in a temporary repository created with an empty template holding only Metabrowser-written configuration, optionally borrowing the store's object directory as an alternate, never inside the shared store or a store-config-reading quarantine; empty credential-helper list, hooks disabled, and only the HTTPS protocol allowed. Prompt binding: HTTP redirects disabled, credential.useHttpPath and a fixed credential username set so Git asks exactly one password question naming the full URL, and the broker answers only when that URL exactly equals an allowlisted source of the live registered lease. Token bytes never enter plugin-visible values, Git or askpass argv or environments, files, cache records, refs, logs, or diagnostics; the separately documented broker-owned gh api child may receive only its sanitized GH_TOKEN or GH_ENTERPRISE_TOKEN variable. Test GH_TOKEN-only private-style acquisition with ambient Git auth disabled; a conflicting .netrc login, SSH agent, credential helper, SSH insteadOf rewrite, and extra authorization header in system, global, environment-injected, template, and repository-local configuration neither consulted nor written; GIT_TRACE_CURL in the parent printing no token; cross-host redirect refusal; askpass refusal for a non-matching URL; ambient principal mismatch; external gh auth switch; broker crash, revocation, and cancellation reaping Git and the bridge; fork and deleted-fork base-repository pull-ref sources; and secret absence.
