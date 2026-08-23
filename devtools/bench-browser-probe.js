// Metabrowser — in-page half of the serving benchmark.
//
// The server-side harness (devtools/bench_serving.py) measures what curl can
// see. It cannot see what the browser does with those responses, and that is
// where two of the delivery layer's mechanisms actually pay off:
//
//   * Requests that arrive together are answered by one aggregation. Several
//     panels on one folder, and several tabs on the same folder, ask for the
//     same answer at the same time.
//   * A repeat request is answered by a validator or a retained body rather
//     than by aggregating again.
//
// Neither is observable from a request count alone — N requests still means N
// requests on the wire. What distinguishes them is how much work the *server*
// did, which every route reports in its own `Server-Timing: srv;dur=<ms>`
// header. That is the signal this probe reads: when eight simultaneous
// requests coalesce, one of them carries the cost of the aggregation and the
// rest are answered from it.
//
// Paste into the devtools console on an open folder view, or run it through
// any automation that can evaluate in the page. Returns a JSON string.
//
//   await metabrowser.bench.run()            // default: the Overview shape
//   await metabrowser.bench.run({clients: 16})
//
// Reported per query shape, because the folder Overview asks for several at
// once and a shape that never coalesces is invisible in an aggregate count.

(() => {
  if (!window.metabrowser) {
    throw new Error("Metabrowser browser probe requires window.metabrowser");
  }

  // The shapes the folder view actually requests. Measuring one the browser
  // never asks for would report a cost no reader pays.
  const SHAPES = {
    overview:
      "/api/rollup?path=&depth=0&top=0&ext_top=0&filename_top=20&remaining_top=20&ext_rank=dual",
    treemap: "/api/rollup?path=&depth=3",
    navRoot: "/api/tree?path=&depth=1",
    navSubtree: "/api/tree?path=top00&depth=2",
  };

  function serverMs(response) {
    // `Server-Timing: srv;dur=<ms>` is set by the server's request
    // middleware and measures its own work, entry to response start. It is
    // the only way from in here to tell an answer that was computed from one
    // that was handed over.
    const header = response.headers.get("server-timing");
    if (!header) {
      return null;
    }
    // One or more comma-separated metrics, each `<name>;dur=<ms>`. Only the
    // server's own `srv` metric is wanted; anything else is left alone.
    for (const metric of header.split(",")) {
      const [name, ...params] = metric.split(";");
      if (name.trim() !== "srv") {
        continue;
      }
      for (const param of params) {
        const [key, value] = param.split("=");
        if (key.trim() === "dur") {
          const parsed = parseFloat(value);
          return Number.isFinite(parsed) ? parsed : null;
        }
      }
    }
    return null;
  }

  async function timed(url, headers) {
    const t0 = performance.now();
    // `cache: "no-store"` keeps the browser's own HTTP cache from answering
    // before the request reaches the server. This probe is measuring the
    // server's coalescing and validators, not Chrome's memory cache — those
    // are different mechanisms and conflating them would credit one for the
    // other. The validator path is exercised explicitly below instead.
    const response = await fetch(url, { headers: headers || {}, cache: "no-store" });
    const body = await response.text();
    return {
      status: response.status,
      etag: response.headers.get("etag"),
      serverMs: serverMs(response),
      wallMs: performance.now() - t0,
      bytes: body.length,
      body,
    };
  }

  function stats(values) {
    const clean = values.filter((v) => typeof v === "number" && Number.isFinite(v));
    if (!clean.length) {
      return { n: 0 };
    }
    const sorted = [...clean].sort((a, b) => a - b);
    return {
      n: sorted.length,
      p50: +sorted[Math.floor(sorted.length / 2)].toFixed(1),
      max: +sorted[sorted.length - 1].toFixed(1),
      total: +sorted.reduce((a, b) => a + b, 0).toFixed(1),
    };
  }

  /**
   * What do N requests issued at once cost the server?
   *
   * Judged on server time, not request count: N requests are always N
   * requests on the wire, and the question is how much work they caused.
   *
   * Read the ratio with the index state in hand, because two different
   * mechanisms make a repeat request cheap and only one of them is
   * coalescing:
   *
   *   * While the index is *scanning*, the validator moves constantly, so
   *     nothing can be served from cache and each request would aggregate on
   *     its own. Single-flight is what collapses them, and the ratio should
   *     stay near 1x.
   *   * Once the index is *settled*, the first request retains its encoded
   *     body and every later one is handed that body instead. Each is already
   *     cheap, so there is nothing left to share and the ratio is expected to
   *     track N. That is not a failure -- the per-request cost is the number
   *     that matters here, and it should be far below the cost of an
   *     aggregation.
   *
   * So a high ratio is only a finding when per-request server time is also
   * high, which is what `costPerClientMs` is reported for.
   */
  async function consolidation(url, clients, scanning, hasValidator) {
    // A single reading first, as the thing N clients are compared against.
    const single = await timed(url);
    const results = await Promise.all(Array.from({ length: clients }, () => timed(url)));
    const bodies = new Set(results.map((r) => r.body));
    const serverTimes = results.map((r) => r.serverMs);
    const summed = stats(serverTimes);
    const ratio =
      single.serverMs && summed.total ? +(summed.total / single.serverMs).toFixed(2) : null;
    const perClient = summed.n ? +(summed.total / summed.n).toFixed(1) : null;
    // Metabrowser's stated budget: a reader should not see a spinner for work
    // under roughly this, so server time well past it is a cost worth naming
    // however it is being spent. See docs/design-system.md.
    const BUDGET_MS = 50;
    const cheapPerClient = perClient !== null && perClient <= BUDGET_MS;

    let verdict;
    if (ratio === null) {
      verdict = "no Server-Timing header; cannot attribute work";
    } else if (ratio < 2) {
      verdict = `shared one computation across ${clients} clients (${ratio}x)`;
    } else if (scanning) {
      verdict =
        `each of ${clients} clients aggregated separately (${ratio}x, ${perClient}ms each) ` +
        "— coalescing is not engaging on a moving index, which is the case it exists for";
    } else if (hasValidator && cheapPerClient) {
      verdict =
        `${ratio}x total but only ${perClient}ms per client — expected on a settled index, ` +
        "where each request is answered from the retained body rather than shared";
    } else if (hasValidator) {
      verdict =
        `${ratio}x total and ${perClient}ms per client, past the ${BUDGET_MS}ms budget ` +
        "— the retained body is not making these cheap";
    } else {
      // No validator and no shared build: every client pays in full, and the
      // cost multiplies by the number of open tabs.
      verdict =
        `no validator on this route, so all ${clients} clients paid in full ` +
        `(${perClient}ms each, ${summed.total}ms of server work)` +
        (cheapPerClient ? "" : ` — past the ${BUDGET_MS}ms budget, and it scales with tabs`);
    }

    return {
      clients,
      indexScanning: Boolean(scanning),
      singleRequestServerMs: single.serverMs,
      serverMs: summed,
      wallMs: stats(results.map((r) => r.wallMs)),
      identicalBodies: bodies.size === 1,
      distinctEtags: new Set(results.map((r) => r.etag)).size,
      serverWorkVersusOneClient: ratio,
      costPerClientMs: perClient,
      withinBudget: cheapPerClient,
      verdict,
    };
  }

  /**
   * Are validators working, and which of the three paths does a repeat take?
   *
   * A 304 with an empty body, a retained body served without a validator, and
   * a genuine rebuild are three different amounts of server work. Reporting
   * them apart is the point.
   */
  async function validators(url) {
    const first = await timed(url);
    if (!first.etag) {
      return { supported: false, reason: "no ETag on the response" };
    }
    const revalidated = await timed(url, { "If-None-Match": first.etag });
    const withoutValidator = await timed(url);
    return {
      supported: true,
      etagStable: withoutValidator.etag === first.etag,
      firstRequest: { serverMs: first.serverMs, bytes: first.bytes },
      revalidated304: {
        status: revalidated.status,
        serverMs: revalidated.serverMs,
        bytes: revalidated.bytes,
        emptyBody: revalidated.bytes === 0,
      },
      retainedBody: {
        serverMs: withoutValidator.serverMs,
        bytes: withoutValidator.bytes,
        sameBytesAsFirst: withoutValidator.bytes === first.bytes,
      },
    };
  }

  async function run(options) {
    const clients = options?.clients || 8;
    const shapes = options?.shapes || SHAPES;
    const indexStatus = await fetch(SHAPES.overview)
      .then((r) => r.json())
      .then((d) => ({ status: d.index_status, indexed: d.indexed_files }))
      .catch(() => null);

    const scanning = indexStatus ? indexStatus.status === "scanning" : false;
    const out = { indexStatus, shapes: {} };
    for (const [name, url] of Object.entries(shapes)) {
      const validatorResult = await validators(url);
      out.shapes[name] = {
        url,
        validators: validatorResult,
        consolidation: await consolidation(url, clients, scanning, validatorResult.supported),
      };
    }
    // perf.js keeps a ring buffer of every fetch the app itself made, which
    // covers the requests the page issued on its own rather than the ones
    // this probe synthesized.
    if (typeof window.metabrowser.perf?.snapshot === "function") {
      try {
        out.appFetches = window.metabrowser.perf.snapshot();
      } catch (error) {
        out.appFetches = { error: String(error) };
      }
    }
    return JSON.stringify(out, null, 2);
  }

  window.metabrowser.bench = Object.freeze({ run, SHAPES });
  return "metabrowser.bench.run() is ready";
})();
