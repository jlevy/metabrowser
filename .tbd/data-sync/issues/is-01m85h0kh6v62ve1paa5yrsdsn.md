---
type: is
id: is-01m85h0kh6v62ve1paa5yrsdsn
title: "CI: setup-uv aborts a job when its manifest fetch from raw.githubusercontent.com exceeds a fixed 5 s"
kind: bug
status: in_progress
priority: 1
version: 3
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/778
    at: 2026-11-24T01:12:09.243Z
delegate: claude-code@spud10.local
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-24T00:59:07.685Z
updated_at: 2026-11-24T01:12:20.765Z
started_at: 2026-11-24T01:12:20.764Z
---
setup-uv v8.2.0 (fac544c) fetches https://raw.githubusercontent.com/astral-sh/versions/main/v1/uv.ndjson even with version and checksum pinned (getArtifact resolves the download URL from the manifest). src/utils/fetch.ts wraps every fetch in AbortSignal.timeout(5_000) with no retry, so a single slow response fails Install uv and the job. Seen: PR #766 run 45299956083 job 138130034436 (chrome 3.13 4/4), 2026-11-24T00:50:19Z fetch, 00:50:24.88Z '##[error]The operation was aborted due to timeout'. Fix in ci.yml (and other workflows using setup-uv): make the install not depend on one 5 s fetch, e.g. a retried second setup-uv step gated on the first's failure, or installing the pinned, checksummed uv release with curl --retry. Measure which, and record why beside the step.
