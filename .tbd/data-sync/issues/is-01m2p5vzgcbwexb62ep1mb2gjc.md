---
type: is
id: is-01m2p5vzgcbwexb62ep1mb2gjc
title: "GitHub Phase 3A: broker-pinned Git credential lease bridge"
kind: task
status: closed
priority: 1
version: 17
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
delegate: claude-code@spud10.local
labels:
  - release:v0.12.0
dependencies:
  - type: blocks
    target: is-01m2h7h50h2y8hhhq7x7f1zcmd
  - type: blocks
    target: is-01m2kw2bvjj5kcsczkz40cmhqx
parent_id: is-01m2h5an32kbkp6zfkhkjzq55f
hold: null
hold_until: null
created_at: 2026-09-16T22:37:16.170Z
updated_at: 2026-09-23T07:37:13.114Z
started_at: 2026-09-16T22:47:02.715Z
closed_at: 2026-09-23T07:37:13.113Z
close_reason: "Superseded 2026-09-23 by the thin-mirror plan (docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md, PR #227; epic mb-hall), per the user's decisions. Replacement: mb-nkmq (PR data via gh runner and JSON records); the token broker, askpass bridge, provider snapshot store, adapter registry, binding and rebind are retired."
resolution: null
duplicate_of: null
---
Implement the Phase 3A Git credential projection for authenticated provider-selected refs, consuming the Phase 2B GitFetchCredentialLeaseRegistry and context conversion from mb-jlon and the broker lease issuance from mb-y1ax. Keep git/process.py as the sole Git runner and project a validated lease through a packaged askpass bridge over a measured bounded inherited pipe or local IPC; replace Phase 2B's pre-Git git_credentials_unavailable refusal with this projection, never an ambient fallback. Isolate every provider-principal Git run as docs/project/architecture/arch-repository-sources-and-provider-mirrors.md#fetch-jobs-authorization-and-credentials defines. Environment: a short allowlisted environment, not a scrubbed copy of os.environ, with fixed PATH and locale, an empty Metabrowser-owned HOME and XDG_CONFIG_HOME, terminal prompting disabled, and only named proxy and certificate variables; NETRC, SSH_AUTH_SOCK, inherited GIT_CONFIG_* values, GIT_TRACE*, GIT_CURL_VERBOSE, and GIT_SSL_NO_VERIFY never pass; among Git configuration variables the runner sets only GIT_CONFIG_NOSYSTEM=1, plus named platform-required variables such as SYSTEMROOT on Windows. Configuration: system and global Git configuration disabled; fetch in a temporary repository created with an empty template holding only Metabrowser-written configuration, optionally borrowing the store's object directory as an alternate (Git then reads the store's Metabrowser-written configuration only in a local ref-listing child with no network access), never inside the shared store or a store-config-reading quarantine; empty credential-helper list, hooks disabled, and only the HTTPS protocol allowed. Prompt binding: HTTP redirects disabled, credential.useHttpPath and a fixed credential username set so Git asks exactly one password question naming the full URL, Immediately before spawning Git, core arms exactly one answer at the registering broker for that run, lease, and source URL and disarms it on Git exit, cancellation, restart, or revocation; the broker answers nothing unarmed. It compares the prompted URL after removing the fixed username and applying Git's credential URL form (percent-decoded path, no trailing slash) and registers allowlisted sources only in that form. Leases authorize an authorization-context key, not a broker session, so a deferred fetch may use a later session's lease for an equal key. Token bytes never enter plugin-visible values, Git or askpass argv or environments, files, cache records, refs, logs, or diagnostics; the separately documented broker-owned gh api child may receive only its sanitized GH_TOKEN or GH_ENTERPRISE_TOKEN variable. Test GH_TOKEN-only private-style acquisition with ambient Git auth disabled; a conflicting .netrc login, SSH agent, credential helper, SSH insteadOf rewrite, and extra authorization header in system, global, environment-injected, template, and repository-local configuration neither consulted nor written; GIT_TRACE_CURL in the parent printing no token; cross-host redirect refusal; no answer for an unarmed, disarmed, cancelled, restarted, revoked, or URL-mismatched askpass request; normalized URL matching; deferred fetch under a later equal-key session; a local HTTPS fixture with a test certificate authority passed through an allowed certificate variable; ambient principal mismatch; external gh auth switch; broker crash, revocation, and cancellation reaping Git and the bridge; fork and deleted-fork base-repository pull-ref sources; and secret absence.
