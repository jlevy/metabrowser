// Lifecycle contracts for the binary plugin's Bytes view.
//
// Same shape as markdown_mount_behavior.js: import the renderer module, drive
// it with a fake SDK and container doubles, and assert mount, append,
// restart-on-change, disposal, and every error state without a DOM.

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const repoRoot = path.resolve(process.argv[2]);
const failures = [];

// bytes_view.js imports a sibling module, which a data-URL import cannot
// resolve. Link real files through vm modules, the same way load_plugins.js
// does, and share the host's intrinsics so values cross the boundary with
// their identities intact.
const context = vm.createContext({
  AbortController,
  Array,
  Error,
  JSON,
  Math,
  Number,
  Object,
  Promise,
  String,
  TypeError,
  Uint8Array,
  atob,
  clearTimeout,
  console,
  queueMicrotask,
  setTimeout,
});

const moduleCache = new Map();

async function moduleFor(filepath) {
  const resolved = path.resolve(filepath);
  const cached = moduleCache.get(resolved);
  if (cached) {
    return cached;
  }
  const module = new vm.SourceTextModule(fs.readFileSync(resolved, "utf-8"), {
    context,
    identifier: resolved,
  });
  moduleCache.set(resolved, module);
  await module.link((specifier, referencing) =>
    moduleFor(path.resolve(path.dirname(referencing.identifier), specifier)),
  );
  return module;
}

async function importModule(relativePath) {
  const module = await moduleFor(path.join(repoRoot, relativePath));
  await module.evaluate();
  return module.namespace;
}

function check(name, condition, detail = "failed") {
  if (!condition) {
    failures.push(`${name}: ${detail}`);
  }
}

function makeElement(selector) {
  return {
    selector,
    innerHTML: "",
    textContent: "",
    hidden: false,
    listeners: [],
    addEventListener(type, fn) {
      if (type === "click") {
        this.listeners.push(fn);
      }
    },
    insertAdjacentHTML(_position, html) {
      this.innerHTML += html;
    },
    click() {
      for (const fn of this.listeners.slice()) {
        fn();
      }
    },
  };
}

/** A container whose element identities reset each time innerHTML is written. */
function makeContainer() {
  let elements = new Map();
  let html = "";
  return {
    get innerHTML() {
      return html;
    },
    set innerHTML(value) {
      html = value;
      elements = new Map();
    },
    querySelector(selector) {
      if (!html.includes(selector.replace(".", 'class="'))) {
        // The double is permissive: any selector the renderer asks for is
        // present only if the painted markup mentions its class.
        if (!html.includes(selector.slice(1))) {
          return null;
        }
      }
      if (!elements.has(selector)) {
        elements.set(selector, makeElement(selector));
      }
      return elements.get(selector);
    },
  };
}

function base64(bytes) {
  return Buffer.from(Uint8Array.from(bytes)).toString("base64");
}

function chunkEnvelope(overrides) {
  return {
    type: "binary_chunk",
    path: "a.bin",
    offset: 0,
    bytes_read: 4,
    next_offset: 4,
    logical_size: 8,
    max_preview_bytes: 20971520,
    has_more: true,
    mtime_hash: "hash-1",
    content_base64: base64([0x41, 0x42, 0xff, 0x00]),
    ...overrides,
  };
}

function makeSdk() {
  const requests = [];
  return {
    requests,
    mb: {
      escapeHtml: (value) =>
        String(value)
          .replace(/&/g, "&amp;")
          .replace(/</g, "&lt;")
          .replace(/>/g, "&gt;")
          .replace(/"/g, "&quot;")
          .replace(/'/g, "&#39;"),
      formatSize: (bytes) => `${bytes} B`,
      fetchPluginData(plugin, route, params, options) {
        return new Promise((resolve, reject) => {
          requests.push({ plugin, route, params, options, resolve, reject });
        });
      },
    },
  };
}

function settle() {
  return new Promise((resolve) => setImmediate(resolve));
}

function contentOf(container) {
  const node = container.querySelector(".binary-bytes-content");
  return node ? node.innerHTML : "";
}

(async () => {
  const { mountBytesView, renderChunkState, decodeBase64, measureSurface } = await importModule(
    "src/metabrowser/builtin_plugins/binary/bytes_view.js",
  );

  // ── Measurement degrades rather than throwing ───────────────────
  const fallback = measureSurface(null);
  check(
    "an unmeasurable surface falls back to fixed metrics",
    fallback.charsPerLine > 0 && fallback.lineHeightPx > 0,
    JSON.stringify(fallback),
  );

  // ── Decoding ────────────────────────────────────────────────────
  const decoded = decodeBase64(base64([0, 1, 254, 255]));
  check("base64 decodes to a byte array", decoded instanceof Uint8Array, String(decoded));
  check(
    "base64 decodes every byte value exactly",
    Array.from(decoded).join(",") === "0,1,254,255",
    Array.from(decoded).join(","),
  );

  // ── First mount ─────────────────────────────────────────────────
  {
    const { mb, requests } = makeSdk();
    const container = makeContainer();
    const mounted = mountBytesView(container, { path: "a.bin" }, mb);
    check("the first mount issues one request", requests.length === 1, String(requests.length));
    check("the first request starts at offset zero", requests[0].params.offset === 0);
    check("the first request names the file", requests[0].params.path === "a.bin");
    requests[0].resolve(chunkEnvelope({}));
    const handle = await mounted;
    check(
      "the decoded chunk is painted",
      contentOf(container).includes("AB"),
      contentOf(container),
    );
    check(
      "high bytes render as hex tokens",
      contentOf(container).includes("‹FF›"),
      contentOf(container),
    );
    check(
      "control bytes render as control pictures",
      contentOf(container).includes("␀"),
      contentOf(container),
    );
    check("a handle with dispose is returned", typeof handle.dispose === "function");

    // ── Load more appends ─────────────────────────────────────────
    const before = contentOf(container);
    container.querySelector(".binary-bytes-more").click();
    check("load more issues a second request", requests.length === 2, String(requests.length));
    check(
      "load more resumes at next_offset",
      requests[1].params.offset === 4,
      String(requests[1].params.offset),
    );
    requests[1].resolve(
      chunkEnvelope({
        offset: 4,
        next_offset: 8,
        has_more: false,
        content_base64: base64([0x43, 0x44, 0x45, 0x46]),
      }),
    );
    await settle();
    const after = contentOf(container);
    check("mounted bytes are not re-rendered", after.startsWith(before), after);
    check("the appended chunk is visible", after.includes("CDEF"), after);
    // Each chunk is its own content-visibility block. Appending into one
    // shared surface is what made repeated Load more degrade quadratically:
    // every append relaid out everything already mounted.
    check(
      "each loaded chunk becomes its own block",
      (after.match(/class="binary-bytes-block"/g) || []).length === 2,
      after.slice(0, 200),
    );
    check(
      "each block declares an intrinsic size so the scrollbar stays honest",
      (after.match(/contain-intrinsic-size/g) || []).length === 2,
      after.slice(0, 200),
    );
    check(
      "the exhausted control is hidden",
      container.querySelector(".binary-bytes-more").hidden === true,
    );
    handle.dispose();
  }

  // ── File replaced between chunks ────────────────────────────────
  {
    const { mb, requests } = makeSdk();
    const container = makeContainer();
    const mounted = mountBytesView(container, { path: "a.bin" }, mb);
    requests[0].resolve(chunkEnvelope({ content_base64: base64([0x41, 0x41, 0x41, 0x41]) }));
    await mounted;
    container.querySelector(".binary-bytes-more").click();
    requests[1].resolve(
      chunkEnvelope({
        offset: 4,
        mtime_hash: "hash-2",
        has_more: false,
        content_base64: base64([0x5a, 0x5a, 0x5a, 0x5a]),
      }),
    );
    await settle();
    check("a changed file restarts at byte zero", requests.length === 3, String(requests.length));
    check("the restart requests offset zero", requests[2].params.offset === 0);
    check(
      "bytes from the previous version are discarded",
      !contentOf(container).includes("AAAA"),
      contentOf(container),
    );
  }

  // ── Loading placeholder ─────────────────────────────────────────
  {
    const { mb, requests } = makeSdk();
    const container = makeContainer();
    const mounted = mountBytesView(container, { path: "a.bin" }, mb);
    check(
      "a placeholder is painted before the first chunk arrives",
      container.innerHTML.includes("mb-delayed-loading"),
      container.innerHTML,
    );
    const raced = await Promise.race([mounted, Promise.resolve("pending")]);
    check("the mount stays pending until its request settles", raced === "pending");
    requests[0].resolve(chunkEnvelope({}));
    (await mounted).dispose();
  }

  {
    const { mb, requests } = makeSdk();
    const container = makeContainer();
    const controller = new AbortController();
    const mounted = mountBytesView(container, { path: "a.bin" }, mb, {
      signal: controller.signal,
    });
    controller.abort();
    requests[0].resolve(chunkEnvelope({ content_base64: base64([0x5a, 0x5a, 0x5a, 0x5a]) }));
    const handle = await mounted;
    check(
      "a late completion after an external abort paints nothing",
      !contentOf(container).includes("ZZZZ"),
      contentOf(container),
    );
    handle.dispose();
  }

  {
    const { mb, requests } = makeSdk();
    const container = makeContainer();
    const mounted = mountBytesView(container, { path: "a.bin" }, mb);
    requests[0].resolve(chunkEnvelope({}));
    const handle = await mounted;
    container.querySelector(".binary-bytes-more").click();
    const pendingSignal = requests[1].options.signal;
    handle.dispose();
    check("dispose aborts the in-flight request", pendingSignal.aborted === true);
    handle.dispose();
    check("dispose is idempotent", true);
    requests[1].resolve(
      chunkEnvelope({ offset: 4, content_base64: base64([0x5a, 0x5a, 0x5a, 0x5a]) }),
    );
    await settle();
    check(
      "a late completion after dispose paints nothing",
      !contentOf(container).includes("ZZZZ"),
      contentOf(container),
    );
  }

  // ── Independent mounts ──────────────────────────────────────────
  {
    const { mb, requests } = makeSdk();
    const first = makeContainer();
    const second = makeContainer();
    const firstMount = mountBytesView(first, { path: "a.bin" }, mb);
    const secondMount = mountBytesView(second, { path: "b.bin" }, mb);
    check("each mount issues its own request", requests.length === 2, String(requests.length));
    requests[1].resolve(
      chunkEnvelope({
        path: "b.bin",
        mtime_hash: "hash-b",
        next_offset: 40,
        content_base64: base64([0x42, 0x42, 0x42, 0x42]),
      }),
    );
    requests[0].resolve(
      chunkEnvelope({ mtime_hash: "hash-a", content_base64: base64([0x41, 0x41, 0x41, 0x41]) }),
    );
    const [firstHandle, secondHandle] = await Promise.all([firstMount, secondMount]);
    check("the first mount paints its own bytes", contentOf(first).includes("AAAA"));
    check("the second mount paints its own bytes", contentOf(second).includes("BBBB"));

    second.querySelector(".binary-bytes-more").click();
    check(
      "each mount keeps its own offset",
      requests[2].params.offset === 40,
      String(requests[2].params.offset),
    );
    firstHandle.dispose();
    secondHandle.dispose();
  }

  // ── Error states ────────────────────────────────────────────────
  {
    const { mb, requests } = makeSdk();
    const container = makeContainer();
    const mounted = mountBytesView(container, { path: "big.bin" }, mb);
    const oversize = new Error("fetchPluginData binary/chunk: 413");
    oversize.status = 413;
    oversize.payload = { max_preview_bytes: 1024 };
    requests[0].reject(oversize);
    await mounted;
    check(
      "the oversize state names the exact cutoff",
      container.innerHTML.includes("1024 B"),
      container.innerHTML,
    );
    check(
      "the oversize state offers no load control",
      !container.innerHTML.includes("binary-bytes-more"),
      container.innerHTML,
    );
  }

  {
    const { mb, requests } = makeSdk();
    const container = makeContainer();
    const mounted = mountBytesView(container, { path: "gone.bin" }, mb);
    const missing = new Error("fetchPluginData binary/chunk: 404");
    missing.status = 404;
    requests[0].reject(missing);
    await mounted;
    check(
      "a missing file reports its own state",
      container.innerHTML.includes("no longer available"),
      container.innerHTML,
    );
    check("failure states are announced", container.innerHTML.includes('role="alert"'));
  }

  {
    const { mb, requests } = makeSdk();
    const container = makeContainer();
    const mounted = mountBytesView(container, { path: "a.bin.gz" }, mb);
    const undecodable = new Error("fetchPluginData binary/chunk: 422");
    undecodable.status = 422;
    requests[0].reject(undecodable);
    await mounted;
    check(
      "an undecodable artifact reports decompression",
      container.innerHTML.includes("could not be decompressed"),
      container.innerHTML,
    );
  }

  {
    const { mb, requests } = makeSdk();
    const container = makeContainer();
    const mounted = mountBytesView(container, { path: "a.bin" }, mb);
    requests[0].reject(new Error("network down"));
    await mounted;
    check(
      "an unclassified failure still reports a state",
      container.innerHTML.includes("Could not load these bytes."),
      container.innerHTML,
    );
  }

  {
    const { mb, requests } = makeSdk();
    const container = makeContainer();
    const mounted = mountBytesView(container, { path: "empty.bin" }, mb);
    requests[0].resolve(
      chunkEnvelope({
        bytes_read: 0,
        next_offset: 0,
        logical_size: 0,
        has_more: false,
        content_base64: "",
      }),
    );
    await mounted;
    check(
      "an empty file reports an empty state",
      container.innerHTML.includes("This file is empty."),
      container.innerHTML,
    );
  }

  // ── Pure state rendering ────────────────────────────────────────
  {
    const { mb } = makeSdk();
    const loading = renderChunkState({ status: "loading" }, mb);
    check("the loading state defers its placeholder", loading.includes("mb-delayed-loading"));
    check("the loading state uses progressive copy", loading.includes("…"), loading);

    const dense = renderChunkState(
      {
        status: "ready",
        bytesLoaded: 4,
        logicalSize: 8,
        hasMore: true,
        accentDropped: true,
      },
      mb,
    );
    check("dropped highlighting is stated", dense.includes("Byte highlighting is off"), dense);
    check("the readout reports loaded and total", dense.includes("4 B") && dense.includes("8 B"));

    const complete = renderChunkState(
      { status: "ready", bytesLoaded: 8, logicalSize: 8, hasMore: false, accentDropped: false },
      mb,
    );
    check("a complete view states no note", !complete.includes("Byte highlighting is off"));

    // Wrapping a large run in CSS is quadratic, so the surface must not offer
    // the browser that job: lines arrive pre-broken into `white-space: pre`.
    check(
      "the surface does not ask CSS to wrap",
      !complete.includes("pre-wrap") && !complete.includes("overflow-wrap"),
      complete,
    );

    // These are bytes, not source. Without the opt-out, highlight.js runs over
    // the block after mount and rewrites the byte runs into hljs token spans.
    check(
      "the byte surface opts out of syntax highlighting",
      complete.includes("binary-bytes-content no-highlight"),
      complete,
    );
    check("the load control is a labelled button primitive", complete.includes('class="btn '));
    check("the load control declares its type", complete.includes('type="button"'));
  }

  if (failures.length) {
    console.error(`binary bytes view FAILURES:\n- ${failures.join("\n- ")}`);
    process.exit(1);
  }
  console.log("binary bytes view OK");
})();
