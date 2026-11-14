// Injected at document start, by WebKitDriver's measure mode in the app's WKWebView and by
// chrome.mjs in Chrome. Records every fetch the page makes, how many root-summary
// requests it has in flight, and what the Commits tab shows from the moment it is opened,
// CLICK_AT_MS after navigation start, until its first rows appear. run.sh prepends the
// two settings; FRAMES adds same-origin pages, standing in for other tabs on the server.
(() => {
  if (window !== window.top) {
    return;
  }
  const FRAMES = Number(globalThis.__stormFrames || 0);
  const CLICK_AT_MS = Number(globalThis.__stormClickAtMs || 20000);
  const TIMEOUT_MS = Number(globalThis.__stormTimeoutMs || 90000);
  const t0 = performance.timeOrigin;
  const now = () => Math.round(performance.now());
  const requests = [];
  let treeInFlight = 0;
  let treeMaxInFlight = 0;
  let depth0InFlight = 0;
  let depth0MaxInFlight = 0;
  const samples = [];
  const origFetch = window.fetch.bind(window);
  window.fetch = async function stormFetch(input, init) {
    const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
    const path = url.replace(location.origin, "");
    const rec = { path, start: now() };
    requests.push(rec);
    const isTree = path.startsWith("/api/tree");
    const isDepth0 = path === "/api/tree?depth=0";
    if (isTree) {
      treeInFlight += 1;
      treeMaxInFlight = Math.max(treeMaxInFlight, treeInFlight);
      rec.treeInFlight = treeInFlight;
    }
    if (isDepth0) {
      depth0InFlight += 1;
      depth0MaxInFlight = Math.max(depth0MaxInFlight, depth0InFlight);
    }
    try {
      const resp = await origFetch(input, init);
      rec.end = now();
      rec.status = resp.status;
      const timing = resp.headers.get("server-timing") || "";
      const match = /srv;dur=([0-9.]+)/.exec(timing);
      if (match) {
        rec.srv = Math.round(Number(match[1]));
      }
      return resp;
    } catch (error) {
      rec.end = now();
      rec.error = String(error);
      throw error;
    } finally {
      if (isTree) {
        treeInFlight -= 1;
      }
      if (isDepth0) {
        depth0InFlight -= 1;
      }
    }
  };
  const sampler = setInterval(() => {
    samples.push([now(), treeInFlight, depth0InFlight]);
  }, 250);

  // The status read shares the connection pool a starved trial is measuring, so it is
  // bounded, never awaited before the click, and the whole probe has a deadline after
  // which it reports what it has.
  const STATUS_TIMEOUT_MS = 3000;
  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

  async function scanStatus() {
    const sentAt = now();
    const controller = new AbortController();
    const answer = origFetch("/api/index/progress", {
      cache: "no-store",
      signal: controller.signal,
    })
      .then((resp) => resp.json())
      .then(
        (body) => ({ sentAt, at: now(), status: body.status, files: body.indexed_files }),
        (error) => ({ sentAt, at: now(), error: String(error) }),
      );
    const unanswered = sleep(STATUS_TIMEOUT_MS).then(() => {
      controller.abort();
      return { sentAt, at: now(), error: `no answer in ${STATUS_TIMEOUT_MS} ms` };
    });
    return Promise.race([answer, unanswered]);
  }

  const panelText = () =>
    (document.querySelector('[data-tab-content="git"] .git-history-skeleton')
      ? "[skeleton] "
      : "") +
    (document.querySelector('[data-tab-content="git"]')?.textContent || "")
      .replace(/\s+/g, " ")
      .trim()
      .slice(0, 160);

  /** @param {Record<string, unknown>} record */
  async function run(record) {
    // Extra same-origin pages, standing in for other tabs on the same server.
    for (let index = 0; index < FRAMES; index++) {
      const frame = document.createElement("iframe");
      frame.src = "/view/";
      frame.style.cssText = `position:fixed;left:${index * 20}px;bottom:0;width:400px;height:300px;opacity:0.05;pointer-events:none;z-index:9999`;
      document.body.appendChild(frame);
    }
    // The tab registers after /api/git/repo answers.
    while (now() < CLICK_AT_MS) {
      if (
        record.tabRegisteredAt === undefined &&
        document.querySelector('.tab-btn[data-tab="git"]')
      ) {
        record.tabRegisteredAt = now();
      }
      await sleep(100);
    }
    // Sent beside the click, not before it.
    const atClick = scanStatus().then((status) => {
      record.scanAtClick = status;
    });
    const deadline = CLICK_AT_MS + TIMEOUT_MS;
    let button = null;
    while (now() < deadline) {
      button = document.querySelector('.tab-btn[data-tab="git"]');
      if (button) {
        break;
      }
      await sleep(100);
    }
    if (record.tabRegisteredAt === undefined && button) {
      record.tabRegisteredAt = now();
    }
    if (!button) {
      record.clicked = false;
      record.outcome = "commits tab never registered";
    } else {
      record.clickAt = now();
      button.click();
      record.clicked = true;
      const snapshots = [];
      record.snapshots = snapshots;
      let last = null;
      while (now() < deadline) {
        const text = panelText();
        if (text !== last) {
          snapshots.push([now(), text]);
          last = text;
        }
        const rows = document.querySelectorAll('[data-tab-content="git"] .git-graph-row').length;
        if (rows > 0) {
          record.firstRowsAt = now();
          record.rows = rows;
          break;
        }
        await sleep(50);
      }
      record.outcome = record.firstRowsAt ? "rows" : "timeout";
      if (record.firstRowsAt) {
        record.commitsTimeToLoadMs = record.firstRowsAt - record.clickAt;
      }
    }
    await atClick;
    record.scanAtEnd = await scanStatus();
    // Let in-flight tree requests settle a moment so their timings land.
    await sleep(500);
  }

  /** @param {Record<string, unknown>} record */
  function finish(record) {
    clearInterval(sampler);
    record.treeMaxInFlight = treeMaxInFlight;
    record.depth0MaxInFlight = depth0MaxInFlight;
    record.requests = requests;
    record.samples = samples;
    record.resources = performance
      .getEntriesByType("resource")
      .filter((entry) => !entry.name.includes("/api/"))
      .map((entry) => [
        entry.name.replace(location.origin, ""),
        Math.round(entry.startTime),
        Math.round(entry.responseEnd),
      ]);
    record.timeOrigin = t0;
    return record;
  }

  /** @type {(record: Record<string, unknown>) => void} */
  let resolveDone = () => {};
  globalThis.__webkitGate = { done: new Promise((resolve) => (resolveDone = resolve)) };
  const start = () => {
    /** @type {Record<string, unknown>} */
    const record = { clickAtTarget: CLICK_AT_MS, frames: FRAMES };
    // Past this the probe reports whatever it has, whatever is still waiting.
    const overall = CLICK_AT_MS + TIMEOUT_MS + 2 * STATUS_TIMEOUT_MS + 1000;
    const deadline = sleep(Math.max(0, overall - now())).then(() => {
      record.outcome ??= "probe deadline";
      record.probeDeadlineAt = now();
    });
    Promise.race([run(record), deadline]).then(
      () => resolveDone(finish(record)),
      (error) => {
        record.error = String(error);
        resolveDone(finish(record));
      },
    );
  };
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start, { once: true });
  } else {
    start();
  }
})();
