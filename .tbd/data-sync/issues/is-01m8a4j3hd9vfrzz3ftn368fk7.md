---
type: is
id: is-01m8a4j3hd9vfrzz3ftn368fk7
title: "CI: install_uv.sh fails a job when GitHub's uv release download answers 403 for longer than its 15 s retry window"
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
created_at: 2026-11-25T19:57:41.799Z
updated_at: 2026-11-25T19:57:41.799Z
---
`devtools/install_uv.sh` fetches uv's pinned release archive from
`https://github.com/astral-sh/uv/releases/download/<version>/<archive>` with curl
`--retry 5 --retry-delay 3 --retry-all-errors`. That is six tries over about 15 s, and
an error status that lasts past them fails the job at its "Install uv" step.

Seen: PR #843, run 45689553972, job 139471196453 ("unit (3.13, 1/4)"), 2026-11-25
19:53:41 to 19:53:56 UTC. All six tries got `curl: (22) The requested URL returned error:
403`, and the step exited 22 before any test ran. The 13 other jobs of the same run
installed the same pinned version, 0.11.26, from the same URL at about the same time.
So the 403 was GitHub's release download answering this one runner, not the pin or the
checksum.

curl's message does not say which host refused: github.com, or the release-assets host
it redirects to with a signed URL.

Possible fixes, to choose by measurement:

- Make the retry window long enough to outlast a short refusal, for example
  `--retry-max-time` with backoff, bounded under the step's time.
- Fall back to setup-uv's own download, which this script's header says it still does
  when the tool cache lacks uv, instead of failing the step.
- Log the final URL and the response headers on failure, so the next occurrence names
  the host and any rate-limit headers.

devtools/check_ci.py holds every setup-uv step to this script.
