# Post-Load Performance Survey

**Date:** 2026-11-26

**Status:** Diagnostic baseline.
The campaign’s acceptance series is pending.

## What the Tools Cover

| Question | Instrument | Evidence |
| --- | --- | --- |
| When can a reader begin? | The startup profile and the first-visit recorder’s startup facts | Process launch to HTTP and inventory readiness, first useful document, preparation boundary, and work still in flight |
| What costs time in the real server? | The headless navigation benchmark with golden-backed API cases | First and repeated HTTP reads, response equality, gzip transfer, ETag revalidation, and server phases |
| What does the reader see after startup preparation? | The transition recorder in Chrome and the WKWebView probe | Exact subject painted at input, blank and placeholder frames, movement, continuity, and convergence |
| What work did the external tools do? | The event log and the bounded live GitHub fetch probe | Git and `gh` process intervals, concurrency, transport status, bytes, validators, and rate observations |

The existing standard transition series rehearses its destinations before measuring.
Keep it for warm-server comparisons.
The first-visit scenario instead keeps ordinary product preparation and records it
separately from the first click.
Browser shell rendering is a separate measurement from the headless HTTP loop.
The HTTP pilot uses a new connection per sample, so its transfer and request elapsed
times describe that transport regime.

## Diagnostic Runs

The corpus was a standalone clone of Metabrowser at `7a02fed4b131`. The product base was
`b38b2ca33c7a`, with the browser harness at revision 6 and Chrome 152. Machine load was
far above the quiet-window acceptance threshold during these runs.
The numbers locate slow paths and show what the tools captured.

### Real HTTP Reads

One headless run checked the response fields and hashes through the actual server.
The repeat columns summarize three requests per case.
The first column is one observation.
All times are milliseconds.

| Route | First read | Repeated median | Repeated maximum |
| --- | ---: | ---: | ---: |
| Git history, first 250 commits | 479 | 21 | 24 |
| Commit comparison | 212 | 76 | 81 |
| Commit detail | 80 | 42 | 71 |
| Large Markdown source | 31 | 44 | 53 |

The first Git history request spent 475 ms in the server.
History and the file each returned 304 with an empty body when revalidated.
Large Markdown source retrieval was much faster than useful paint in the separate Chrome
run. A slow request body transfer alone cannot account for that observation.
The per-request server log recorded roughly four seconds in the KPress render stage on
the large document.

The next headless pilot issued history and comparison reads during a recorded startup
preparation phase. Preparation took 1.02 s in that run.
The first later history and comparison reads took 17 ms and 84 ms, respectively, and
returned the same checked content as their prepared responses.
This shows work available to move out of the click path.
This run did not measure the effect of automatic preparation on startup or foreground
contention.

A separate headless pilot copied the prepared cache from Chrome and verified the PR
record and rendered description for #888 through HTTP. The first record read took 436
ms, and the first description read took 2.08 s. Repeated medians were 32 ms and 20 ms,
respectively. This gives the campaign a server-only loop for a PR page’s first useful
content, including server-side Markdown rendering.

### First Visits in Chrome

The broad wiring pass completed the Files, keyboard, views, Commits, tree, and palette
journeys.
The Pulls return sometimes failed to converge and its pinned historical PR #353
did not appear in the list.
The new subject override exercised the full PR sequence with #888, #882, #887, and #880.
The recorder refused that run because the first Pulls view changed between readiness and
convergence, and the editable build’s reported identity changed during the run.
The per-transition observations below are triage evidence from that refused run.

| Transition | Useful content | Visible before ready |
| --- | ---: | --- |
| First selected PR | 18.9 s | Blank and placeholder frames |
| First Changes tab | 5.2 s | Placeholder frames |
| First Checks tab | 39 ms | Continuous content |
| Conversation revisit | 47 ms | Continuous content |
| Changes revisit | 357 ms | A short placeholder |
| Return to an earlier PR | 78 ms | Continuous content |

Server logs let the first selected PR be placed on the same clock as the provider.
Twenty completed `gh` subprocess spans overlapped its wait, with up to five of those
spans concurrent. A Git fetch lasting about 32 seconds also overlapped the wait.
Overlap helps select the next experiments.
It does not prove that every process in that window blocked the paint.

The broad Files pass also recorded five blank frames when opening an image.
The renderer mounted the image while decoding was still pending.
The image change hands its decode promise to the existing view compositor, so the
current preview can stay visible until the image is ready.
A diagnostic rerun counted one blank frame.
Its editable version label was inconsistent, so these samples do not establish a gate.

### Live GitHub Reads

Three pairs compared the same two merged PRs in series and at concurrency two.
Serial pair elapsed time was 1.93–2.29 s. Concurrent pair elapsed time was 1.03–1.59 s.
The local `gh --version` invocations took 76–205 ms.
The two-request test establishes a point to retest under representative provider
traffic.

All three conditional reads returned HTTP 304, no body, and CLI exit status 1. The
account’s `core` used counter stayed flat twice and rose by one once.
The counter is shared with other clients.
Each minimal GraphQL batch reported one `graphql` point.
Its projection and response size differed from the REST pair, so those timings price
different work. No rate refusal occurred.
Keep the existing deterministic refusal tests for retry and reset behavior.

## Experiments to Run Next

1. Move the measured Git history preparation into the startup phase.
   Measure HTTP readiness, first browsing request, and competing foreground work.
   Run the headless prepare option to price a warm entry, then test one actual startup
   implementation.
2. Split PR time into catalog readiness, record preparation, Git acquisition, and
   comparison hydration.
   Verify the exact first Conversation and Changes content, and test demand-first
   ordering before increasing speculative concurrency.
3. Measure KPress server rendering separately from browser document insertion and
   layout. Use the large Markdown file as a guard for cost moved between the two.
4. Recheck visible continuity and steady navigation in Chrome and WKWebView after the
   accepted changes are composed.
   Keep browser, API, and native startup results separate.

The [plan](../specs/active/plan-2026-11-26-post-load-performance.md) defines acceptance.
The [runbook](../../../explorations/performance-loop/README.md) gives the commands.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
