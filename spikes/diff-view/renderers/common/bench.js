// Shared page-side benchmark harness for the renderer spikes.
// Collects render wall time, long tasks, and DOM node counts per scenario.

const longTasks = [];
try {
  const obs = new PerformanceObserver((list) => {
    for (const entry of list.getEntries()) {
      longTasks.push(entry.duration);
    }
  });
  obs.observe({ type: "longtask", buffered: true });
} catch {
  // longtask unsupported: results simply omit it
}

window.__RESULTS = [];
window.__benchDone = false;

/**
 * @param {string} name
 * @param {() => void | Promise<void>} fn
 */
export async function bench(name, fn) {
  await new Promise((r) => requestAnimationFrame(() => r(undefined)));
  const before = longTasks.length;
  const t0 = performance.now();
  await fn();
  void document.body.offsetHeight; // force layout
  await new Promise((r) => requestAnimationFrame(() => setTimeout(r, 0)));
  const t1 = performance.now();
  const tasks = longTasks.slice(before);
  window.__RESULTS.push({
    name,
    renderMs: Number((t1 - t0).toFixed(1)),
    longTaskMs: Number(tasks.reduce((a, b) => a + b, 0).toFixed(1)),
    longTasks: tasks.length,
    domNodes: document.getElementsByTagName("*").length,
  });
}

export function done() {
  window.__benchDone = true;
}

/** @param {string} url */
export async function fetchJson(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${url}: ${res.status}`);
  return res.json();
}

/** @param {string} url */
export async function fetchText(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${url}: ${res.status}`);
  return res.text();
}

/** @param {unknown} err */
export function fail(err) {
  window.__RESULTS.push({ name: "ERROR", error: String(err) });
  window.__benchDone = true;
}

/**
 * Resolve with elapsed ms once no new long tasks have been observed for
 * `quietMs`, capped at `capMs`. Coarse settle signal for shadow-DOM renderers.
 *
 * @param {number} quietMs
 * @param {number} capMs
 * @returns {Promise<number>}
 */
export function quietLongTasks(quietMs, capMs) {
  return new Promise((resolve) => {
    const t0 = performance.now();
    let lastCount = longTasks.length;
    let lastChange = t0;
    const iv = setInterval(() => {
      const now = performance.now();
      if (longTasks.length !== lastCount) {
        lastCount = longTasks.length;
        lastChange = now;
      }
      if (now - lastChange >= quietMs || now - t0 > capMs) {
        clearInterval(iv);
        resolve(Number((lastChange - t0).toFixed(1)));
      }
    }, 100);
  });
}

/**
 * Count DOM nodes including open shadow roots.
 *
 * @param {ParentNode} root
 * @returns {number}
 */
export function countNodes(root) {
  let count = 0;
  for (const el of root.querySelectorAll("*")) {
    count += 1;
    if (el.shadowRoot) count += countNodes(el.shadowRoot);
  }
  return count;
}

/**
 * Resolve with elapsed ms once `root` has had no DOM mutations for `quietMs`,
 * capped at `capMs`. Used to time async enrichment (e.g. highlighting) settling.
 *
 * @param {Node} root
 * @param {number} quietMs
 * @param {number} capMs
 * @returns {Promise<number>}
 */
export function quiet(root, quietMs, capMs) {
  return new Promise((resolve) => {
    const t0 = performance.now();
    let last = t0;
    const mo = new MutationObserver(() => {
      last = performance.now();
    });
    mo.observe(root, { subtree: true, childList: true, attributes: true, characterData: true });
    const iv = setInterval(() => {
      const now = performance.now();
      if (now - last >= quietMs || now - t0 > capMs) {
        clearInterval(iv);
        mo.disconnect();
        resolve(Number((last - t0).toFixed(1)));
      }
    }, 100);
  });
}
