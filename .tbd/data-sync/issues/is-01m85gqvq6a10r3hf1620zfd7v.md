---
type: is
id: is-01m85gqvq6a10r3hf1620zfd7v
title: Guided PR Chrome test probes the stand-in's /view/ without first waiting for its banner, so the 15 s first-answer budget covers the whole cold start (15-19 s at load ~440)
kind: bug
status: open
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m2gb3gpn7vcsw0as4xa243tg
created_at: 2026-11-24T00:54:21.157Z
updated_at: 2026-11-25T02:31:15.026Z
---
On claude/guided-pr-ready (59d456621, bead mb-q30d), tests/test_github_guided_pr_chrome.py starts the stand-in server (tests/github_pull_fixture.py --serve 7) and calls _wait_until_serving (tests/test_nav_metadata_chrome.py:109, bounded by _SERVING_BUDGET_S = 15 s) at once. Every other caller on main first calls _read_port, which waits up to _BANNER_BUDGET_S = 30 s for the 'Serving ... at' banner, so its 15 s covers only the time from banner to first answer. Here it covers the interpreter's whole cold start. Measured 2026-11-23 against the same stand-in (attic probes serve_probe.py and traced_serve.py): at load ~436 the socket refused connections for 15.4 s (227 attempts), the server spending that time importing modules (faulthandler dumps every 0.5 s showed importlib frames, about 2.2 s of CPU), then six 0.2 s attempts timed out while the lifespan ran, and a patient request answered 2.0 s later: first answer at about 18.7 s. At load ~471 a patient probe got its first 200 at 10.9 s, the request taking 1.86 s. The failed run's server log held only the clone line because the banner had not yet been printed. It was not the clone, not a lock and not a blocked event loop. Fix (for the branch's owner): wait for the stand-in's own banner, which names /pull/7 rather than /view/ so _SERVING_LINE does not match, with a pattern such as r'^Serving .* at http://127\.0\.0\.1:(\d+)/pull/7', bounded by _BANNER_BUDGET_S, then call _wait_until_serving, and add _BANNER_BUDGET_S to LIFECYCLE_S. Real metab serve starts its open-browser probe only after printing the banner (src/metabrowser/cli/serve.py around line 484), so it does not share this test's mistake. Inferred, not measured: that probe's 0.2 s per-attempt timeout (src/metabrowser/cli/http_readiness.py:44) is below the 1.9-2.0 s a cold first answer took at load 440-470, so under such load metab may print 'did not serve HTTP OK ... not opening browser automatically' rather than open the browser; warm answers took 0.10-0.17 s.
