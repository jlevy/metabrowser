// Deterministic memo-cost contract for wiki-link resolution.
//
// Resolving the links of one document repeats a memo probe per target, and the
// memo key is a string. V8 content-hashes a string only up to 16,383 code
// units and derives the hash from the length alone above that, so keys past
// that bound collide by construction and every probe decays into a
// full-length comparison against every key already stored. The cost is
// quadratic in the links of a document and linear in the length of its path,
// which no wall clock has to observe: counting the code units the resolver
// hands to a memo states it directly.
//
// The session counts those code units and the catalog reads that back them, so
// a bound holds on any machine (see docs/large-content-rendering.md).

const assert = require("node:assert");

const MEMO_KEY_BOUND = 16_383;
// One authored target, carried across the memo probes of a single resolution.
// The number this bound exists to keep out of a key is the source path, which
// this session makes 20,409 code units long.
const MEMO_KEY_CODE_UNITS_PER_TARGET = 128;
const TARGETS = 512;
const SEGMENT = "provider-segment/";

const failures = [];

function check(label, condition, detail = "") {
  if (!condition) {
    failures.push(`${label}${detail ? `: ${detail}` : ""}`);
  }
}

/**
 * Count the string-key code units this realm's `Map` probes carry. Production
 * modules share these intrinsics, so the count is the resolver's own.
 */
function installMapKeyWorkMeter() {
  const prototype = Map.prototype;
  const original = {
    delete: prototype.delete,
    get: prototype.get,
    has: prototype.has,
    set: prototype.set,
  };
  let keyCodeUnits = 0;
  let maxKeyLength = 0;
  let probes = 0;
  let counting = false;

  const charge = (key) => {
    if (!counting || typeof key !== "string") {
      return;
    }
    probes += 1;
    keyCodeUnits += key.length;
    maxKeyLength = Math.max(maxKeyLength, key.length);
  };

  for (const name of ["delete", "get", "has", "set"]) {
    prototype[name] = function meteredMapMethod(key, ...rest) {
      charge(key);
      return original[name].call(this, key, ...rest);
    };
  }

  return {
    read: () => ({ keyCodeUnits, maxKeyLength, probes }),
    restore() {
      for (const name of ["delete", "get", "has", "set"]) {
        prototype[name] = original[name];
      }
    },
    reset() {
      keyCodeUnits = 0;
      maxKeyLength = 0;
      probes = 0;
    },
    start() {
      counting = true;
    },
    stop() {
      counting = false;
    },
  };
}

/** @param {number} segments */
function sourcePathOf(segments) {
  return `${SEGMENT.repeat(segments)}readme.md`;
}

(async () => {
  const module = await import(
    `file://${require("node:path").join(__dirname, "../../src/metabrowser/builtin_plugins/markdown/wiki-resolver.js")}`
  );
  const meter = installMapKeyWorkMeter();

  let catalogReads = 0;
  const catalogFile = (basename, path) => ({
    basename,
    get path() {
      catalogReads += 1;
      return path;
    },
  });
  const snapshot = () => ({
    complete: true,
    files: [catalogFile("published.md", "docs/published.md")],
  });

  /**
   * Resolve one document's worth of distinct targets, the way the
   * reconciliation coordinator does: one snapshot-scoped context and one
   * trusted source context shared by every target of the document.
   *
   * @param {number} segments
   */
  function resolveDocument(segments) {
    const sourcePath = sourcePathOf(segments);
    const context = module.createWikiResolutionContext(snapshot());
    const sourceContext = module.createTrustedWikiSourcePathContext(sourcePath);
    while (!sourceContext.step(500_000).done) {
      // The coordinator prepares the source once before the first target.
    }
    meter.reset();
    catalogReads = 0;
    meter.start();
    const resolutions = [];
    for (let index = 0; index < TARGETS; index += 1) {
      const application = context.beginTrusted(
        {
          action: "navigate",
          authoredTarget: `Missing-${index}`,
          sourcePath,
          syntax: "wiki",
        },
        sourceContext,
      );
      while (true) {
        const step = application.step(500_000);
        if (step.done && step.result) {
          resolutions.push(step.result);
          break;
        }
      }
    }
    meter.stop();
    const work = meter.read();
    const reads = catalogReads;
    context.dispose();
    return { reads, resolutions, sourcePath, work };
  }

  try {
    const long = resolveDocument(1200);
    const longer = resolveDocument(2400);

    check(
      "every memo key stays inside the content-hash bound",
      long.work.maxKeyLength <= MEMO_KEY_BOUND && longer.work.maxKeyLength <= MEMO_KEY_BOUND,
      `${long.work.maxKeyLength} code units from a ${long.sourcePath.length}-code-unit source`,
    );
    check(
      "doubling the source path does not change what a memo probe carries",
      long.work.keyCodeUnits === longer.work.keyCodeUnits,
      `${long.work.keyCodeUnits} against ${longer.work.keyCodeUnits} code units`,
    );
    check(
      "memo key cost stays constant per target",
      long.work.keyCodeUnits <= TARGETS * MEMO_KEY_CODE_UNITS_PER_TARGET,
      `${long.work.keyCodeUnits} code units for ${TARGETS} targets`,
    );
    check(
      "resolution still reports every target missing",
      long.resolutions.length === TARGETS &&
        long.resolutions.every((resolution) => resolution.status === "missing"),
      String(long.resolutions.filter((resolution) => resolution.status !== "missing").length),
    );
    check(
      "resolution still reads the catalog for every target",
      long.reads >= TARGETS,
      String(long.reads),
    );

    // A memo that never hits would also keep keys short. Resolving one target
    // twice must not read the catalog again.
    const sourcePath = sourcePathOf(1200);
    const context = module.createWikiResolutionContext(snapshot());
    const sourceContext = module.createTrustedWikiSourcePathContext(sourcePath);
    while (!sourceContext.step(500_000).done) {
      // Prepared once, as above.
    }
    const resolveOnce = () => {
      const application = context.beginTrusted(
        { action: "navigate", authoredTarget: "Repeat", sourcePath, syntax: "wiki" },
        sourceContext,
      );
      while (true) {
        const step = application.step(500_000);
        if (step.done && step.result) {
          return step.result;
        }
      }
    };
    resolveOnce();
    catalogReads = 0;
    const repeated = resolveOnce();
    check("a repeated target is answered from the memo", catalogReads === 0, String(catalogReads));
    check("a repeated target still resolves", repeated.status === "missing", repeated.status);
    context.dispose();

    assert.ok(long.work.probes > 0, "the meter observed no memo probe");
    console.log(
      JSON.stringify(
        {
          longSourceCodeUnits: long.sourcePath.length,
          memoKeyCodeUnits: long.work.keyCodeUnits,
          memoKeyMaxLength: long.work.maxKeyLength,
          longerSourceCodeUnits: longer.sourcePath.length,
          targets: TARGETS,
        },
        null,
        2,
      ),
    );
  } finally {
    meter.restore();
  }

  if (failures.length) {
    console.error(failures.join("\n"));
    process.exit(1);
  }
  console.log("wiki resolver memo work OK");
})();
