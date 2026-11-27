// The status vocabulary (github/pull-readiness.js), run without a browser on the production
// module, over every verdict, tone, requirement, and check bucket the server can name, which
// the caller passes in from pull_readiness.py and pull_status.py, paired every way, including
// pairs the server never makes. It holds the vocabulary's invariants:
//
// - a mark takes its tone and its label from what it is given, and its shape from its meaning;
// - a chip's glyph is the same drawing as the compact glyph of its meaning, the verdict's for
//   the header's chip, the verdict a requirement heads for its row, and the checks
//   requirement's for a check that passed, failed, or is pending;
// - no glyph is drawn for two meanings, and no meaning in two glyphs.
//
// Prints what it held, and the module's copies of the server's vocabulary, for the caller to
// hold to the server's.
const assert = require("node:assert/strict");
const path = require("node:path");
const { pathToFileURL } = require("node:url");

const { verdicts, tones, statuses, headlines, kinds, buckets } = JSON.parse(process.argv[2]);

let created = 0;
let parses = 0;

class Element {
  constructor(tag, markup = null) {
    this.tag = tag;
    this.markup = markup;
    this.attributes = new Map();
    this.children = [];
    this.dataset = {};
    this.className = "";
  }
  getAttribute(name) {
    return this.attributes.get(name) ?? null;
  }
  setAttribute(name, value) {
    this.attributes.set(name, String(value));
  }
  append(...nodes) {
    this.children.push(...nodes);
  }
  get textContent() {
    return this.children
      .map((child) => (typeof child === "string" ? child : child.textContent))
      .join("");
  }
  set textContent(value) {
    this.children = value === "" ? [] : [String(value)];
  }
}

globalThis.document = {
  createElement: (tag) => {
    created += 1;
    return new Element(tag);
  },
  importNode: (node) => new Element(node.tag, node.markup),
};
globalThis.DOMParser = class {
  parseFromString(markup) {
    parses += 1;
    const opened = /^<(\w+)/.exec(markup);
    return { body: { firstElementChild: opened === null ? null : new Element(opened[1], markup) } };
  }
};

const ACCESSIBLE = ["role", "aria-label", "aria-hidden"];
const said = (element) => ACCESSIBLE.map((name) => element.getAttribute(name));
const classes = (element) => element.className.split(" ").sort();

/** A chip's glyph's drawing and its label, holding the chip's shape on the way. */
function chipParts(badge, context) {
  assert.equal(badge.tag, "span", context);
  assert.deepEqual(said(badge), [null, null, null], `${context}: named by its text`);
  assert.equal(badge.children.length, 2, `${context}: a glyph, then the label`);
  const [box, label] = badge.children;
  assert.equal(box.className, "github-pull-badge-glyph", context);
  assert.equal(box.getAttribute("aria-hidden"), "true", `${context}: the glyph is not read`);
  assert.equal(box.children.length, 1, context);
  const [svg] = box.children;
  assert.equal(svg.tag, "svg", context);
  assert.match(svg.markup, /stroke="currentColor"/, `${context}: takes its tone's ink`);
  assert.equal(typeof label, "string", context);
  return { drawing: svg.markup, label };
}

(async () => {
  const R = await import(
    pathToFileURL(
      path.resolve(__dirname, "../../src/metabrowser/builtin_plugins/github/pull-readiness.js"),
    ).href
  );

  // No readiness, as a closed or merged pull request has, draws nothing at all.
  for (const none of [null, undefined]) {
    assert.equal(R.readinessIcon(none), null);
    assert.equal(R.readinessIcon(none, { named: false }), null);
    assert.equal(R.readinessBadge(none), null);
  }
  assert.equal(created, 0, "no readiness, no element");

  /** Each meaning's drawing, as every form draws it. @type {Map<string, Set<string>>} */
  const drawings = new Map();
  const drew = (meaning, drawing) => {
    drawings.set(meaning, (drawings.get(meaning) ?? new Set()).add(drawing));
  };
  // The verdicts that mean one thing: nothing blocks the pull request, ready to merge or, as a
  // draft, ready for review. Every other verdict is a meaning of its own.
  const meaningOf = (verdict) => (verdict === "ready_for_review" ? "ready" : verdict);

  let cases = 0;
  for (const verdict of verdicts) {
    for (const tone of tones) {
      cases += 1;
      // A label in no table, so a mark that says it took it from the readiness.
      const label = `Said ${verdict} in ${tone}`;
      const readiness = { verdict, tone, label };
      const context = `${verdict} in ${tone}`;
      /** @type {Set<string>} */
      const compact = new Set();
      for (const options of [undefined, {}, { named: true }, { named: false }]) {
        const icon = R.readinessIcon(readiness, options);
        assert.equal(icon.tag, "span", context);
        assert.deepEqual(
          classes(icon),
          ["github-pull-readiness-icon", "github-pull-tone"],
          context,
        );
        assert.deepEqual(icon.dataset, { tone, verdict }, context);
        // Named unless told otherwise, by the server's label; hidden, it says nothing.
        assert.deepEqual(
          said(icon),
          options?.named === false ? [null, null, "true"] : ["img", label, null],
          context,
        );
        assert.equal(icon.children.length, 1, context);
        const [svg] = icon.children;
        assert.equal(svg.tag, "svg", context);
        compact.add(svg.markup);
        // Each mark is its own node, so a list of rows never moves one row's glyph to another.
        assert.notEqual(R.readinessIcon(readiness, options).children[0], svg, context);
      }
      assert.equal(compact.size, 1, `${context}: one compact glyph`);
      const badge = R.readinessBadge(readiness);
      assert.deepEqual(
        classes(badge),
        ["file-header-badge", "github-pull-badge", "github-pull-readiness", "github-pull-tone"],
        context,
      );
      assert.deepEqual(badge.dataset, { tone, verdict }, context);
      const chip = chipParts(badge, context);
      assert.equal(chip.label, label, `${context}: the chip says the server's label`);
      assert.equal(
        chip.drawing,
        [...compact][0],
        `${context}: the chip's glyph is its compact one`,
      );
      drew(meaningOf(verdict), chip.drawing);
    }
  }
  const verdictDrawing = (verdict) => [...drawings.get(meaningOf(verdict))][0];

  // A requirement's chip draws the glyph of the verdict it heads at that status, `checking`'s
  // when GitHub has not answered, and its met glyph when it is met; it says its status's word
  // and takes the tone it was given. A pair the server never sends draws no chip.
  const heads = new Map(headlines.map(([kind, status, verdict]) => [`${kind} ${status}`, verdict]));
  let requirementChips = 0;
  for (const kind of kinds) {
    for (const status of statuses) {
      for (const tone of tones) {
        const context = `${kind} ${status} in ${tone}`;
        const badge = R.requirementBadge({ kind, status, tone });
        const verdict =
          status === "unknown" ? "checking" : (heads.get(`${kind} ${status}`) ?? null);
        if (status !== "met" && verdict === null) {
          assert.equal(badge, null, `${context}: the server sends no such row`);
          continue;
        }
        if (status === "met" && !Object.hasOwn(R.MET_GLYPHS, kind)) {
          assert.equal(badge, null, `${context}: the server never says it is met`);
          continue;
        }
        requirementChips += 1;
        assert.deepEqual(
          classes(badge),
          ["file-header-badge", "github-pull-badge", "github-pull-requirement", "github-pull-tone"],
          context,
        );
        assert.deepEqual(badge.dataset, { tone, kind, status }, context);
        const chip = chipParts(badge, context);
        assert.equal(chip.label, R.statusWord(status), context);
        assert.equal(R.statusWord(status).toLowerCase(), status.replaceAll("_", " "), context);
        assert.match(R.statusWord(status), /^[A-Z]/, context);
        if (status === "met") {
          drew(`met ${kind}`, chip.drawing);
        } else {
          assert.equal(
            chip.drawing,
            verdictDrawing(verdict),
            `${context} draws ${verdict}'s glyph`,
          );
        }
      }
    }
  }
  for (const given of [
    { kind: "conflicts", status: "unmet", tone: "a tone no table names" },
    { kind: "conflicts", status: "not a status", tone: "danger" },
    { kind: "constructor", status: "unmet", tone: "danger" },
    { kind: "conflicts", status: "constructor", tone: "danger" },
  ]) {
    assert.equal(R.requirementBadge(given), null, JSON.stringify(given));
  }

  // A check's chip: its bucket's glyph and tone, and its own words, a capital first. A check
  // that passed, failed, or is pending is the checks requirement met, unmet, or waiting.
  const CHECKS_AT = { pass: "met", fail: "unmet", pending: "waiting" };
  const checkTones = {};
  for (const bucket of buckets) {
    const context = `a check in ${bucket}`;
    const badge = R.checkBadge({ bucket, label: "in progress" });
    assert.deepEqual(
      classes(badge),
      ["file-header-badge", "github-pull-badge", "github-pull-check", "github-pull-tone"],
      context,
    );
    assert.equal(badge.dataset.bucket, bucket, context);
    checkTones[bucket] = badge.dataset.tone;
    const chip = chipParts(badge, context);
    assert.equal(chip.label, "In progress", context);
    if (Object.hasOwn(CHECKS_AT, bucket)) {
      const as = R.requirementBadge({ kind: "checks", status: CHECKS_AT[bucket], tone: "success" });
      assert.equal(chip.drawing, chipParts(as, context).drawing, `${context} is the checks' mark`);
    } else {
      drew(`check ${bucket}`, chip.drawing);
    }
  }
  const unknown = R.checkBadge({ bucket: "a bucket no build sorts into", label: "odd" });
  assert.equal(unknown.dataset.tone, "neutral", "an unknown bucket is neutral");
  assert.deepEqual(unknown.children, ["Odd"], "and draws its words alone");

  // One code for each meaning, and no code for two.
  for (const [meaning, drawn] of drawings) {
    assert.equal(drawn.size, 1, `${meaning} is drawn one way in every form`);
  }
  const byDrawing = new Map();
  for (const [meaning, drawn] of drawings) {
    const drawing = [...drawn][0];
    assert.equal(
      byDrawing.get(drawing),
      undefined,
      `${meaning} and ${byDrawing.get(drawing)} share a glyph`,
    );
    byDrawing.set(drawing, meaning);
  }
  // Each glyph is parsed once, however many marks draw it.
  assert.equal(parses, byDrawing.size, "each glyph is parsed once");

  // The slot's sizers: one hidden chip's box for each label, its glyph's box before it.
  const sizers = R.readinessSizers();
  assert.deepEqual(
    sizers.map((sizer) => sizer.textContent),
    [...R.SLOT_LABELS],
  );
  for (const sizer of sizers) {
    assert.equal(sizer.getAttribute("aria-hidden"), "true");
    assert.equal(sizer.className, "file-header-badge github-pull-badge github-pull-badge-sizer");
    assert.equal(sizer.children[0].className, "github-pull-badge-glyph", "a glyph's room first");
    assert.equal(sizer.children[0].children.length, 0, "and empty");
  }

  console.log(
    JSON.stringify({
      vocabulary: Object.keys(R.VERDICT_GLYPHS),
      slotLabels: R.SLOT_LABELS,
      statusOrder: R.STATUS_ORDER,
      tones: R.TONES,
      requirementVerdicts: Object.entries(R.REQUIREMENT_VERDICTS).flatMap(([kind, at]) =>
        Object.entries(at).map(([status, verdict]) => [kind, status, verdict]),
      ),
      checkTones,
      cases,
      requirementChips,
      meanings: drawings.size,
      noReadinessDrawsNothing: true,
      toneAndLabelAreTheGivens: true,
      namedByDefaultOrHidden: true,
      chipGlyphIsTheCompactGlyph: true,
      oneGlyphPerMeaning: true,
      eachGlyphParsedOnce: true,
      sizersAreHiddenChips: true,
    }),
  );
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
