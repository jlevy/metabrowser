// readinessIcon and readinessBadge (github/pull-readiness.js), run without a browser on the
// production module, over every verdict and tone the server can name, which the caller passes
// in from pull_readiness.py, paired every way, including pairs the server never makes: a mark
// takes its tone and its label from the readiness it is given, and its shape from the verdict
// alone. Prints what it held, and the vocabulary's verdicts, for the caller to hold to the
// server's.
const assert = require("node:assert/strict");
const path = require("node:path");
const { pathToFileURL } = require("node:url");

const { verdicts, tones, statuses } = JSON.parse(process.argv[2]);

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

(async () => {
  const {
    VERDICT_GLYPHS,
    SLOT_LABELS,
    STATUS_TONES,
    readinessBadge,
    readinessIcon,
    readinessSizers,
    requirementBadge,
    statusWord,
  } = await import(
    pathToFileURL(
      path.resolve(__dirname, "../../src/metabrowser/builtin_plugins/github/pull-readiness.js"),
    ).href
  );

  // No readiness, as a closed or merged pull request has, draws nothing at all.
  for (const none of [null, undefined]) {
    assert.equal(readinessIcon(none), null);
    assert.equal(readinessIcon(none, { named: false }), null);
    assert.equal(readinessBadge(none), null);
  }
  assert.equal(created, 0, "no readiness, no element");

  /** @type {Map<string, Set<string>>} each verdict's drawings, across every tone and form */
  const drawings = new Map(verdicts.map((verdict) => [verdict, new Set()]));
  let cases = 0;
  for (const verdict of verdicts) {
    for (const tone of tones) {
      cases += 1;
      // A label in no table, so a mark that says it took it from the readiness.
      const label = `Said ${verdict} in ${tone}`;
      const readiness = { verdict, tone, label };
      const context = `${verdict} in ${tone}`;
      for (const options of [undefined, {}, { named: true }, { named: false }]) {
        const icon = readinessIcon(readiness, options);
        assert.equal(icon.tag, "span", context);
        assert.equal(icon.className, "github-pull-readiness-icon", context);
        assert.deepEqual(icon.dataset, { verdict, tone }, context);
        // Named unless told otherwise, by the server's label; hidden, it says nothing.
        assert.deepEqual(
          said(icon),
          options?.named === false ? [null, null, "true"] : ["img", label, null],
          context,
        );
        assert.equal(icon.children.length, 1, context);
        const [shape] = icon.children;
        assert.equal(shape.tag, "svg", context);
        assert.match(shape.markup, /stroke="currentColor"/, `${context}: takes its tone's ink`);
        drawings.get(verdict).add(shape.markup);
        // Each mark is its own node, so a list of rows never moves one row's glyph to another.
        assert.notEqual(readinessIcon(readiness, options).children[0], shape, context);
      }
      const badge = readinessBadge(readiness);
      assert.equal(badge.tag, "span", context);
      assert.deepEqual(
        badge.className.split(" ").sort(),
        ["file-header-badge", "github-pull-badge", "github-pull-readiness"],
        context,
      );
      assert.deepEqual(badge.dataset, { verdict, tone }, context);
      // Its text is the server's label as given, and is its own name.
      assert.deepEqual(badge.children, [label], context);
      assert.deepEqual(said(badge), [null, null, null], context);
    }
  }
  // A verdict has one shape, whatever its tone and form, and two verdicts share a shape
  // exactly where the vocabulary gives them one glyph.
  for (const [verdict, drawn] of drawings) {
    assert.equal(drawn.size, 1, `${verdict} is drawn one way`);
  }
  const shapeOf = (verdict) => [...drawings.get(verdict)][0];
  for (const first of verdicts) {
    for (const second of verdicts) {
      assert.equal(
        shapeOf(first) === shapeOf(second),
        VERDICT_GLYPHS[first] === VERDICT_GLYPHS[second],
        `${first} and ${second}`,
      );
    }
  }
  // Each glyph is parsed once, however many rows draw it.
  const glyphs = new Set(Object.values(VERDICT_GLYPHS)).size;
  assert.equal(parses, glyphs, "each glyph is parsed once");

  // A requirement's badge says its status in the server's own word, a capital first, and
  // takes the tone the status gives a verdict; a status the server does not name has none.
  for (const status of statuses) {
    const badge = requirementBadge(status);
    assert.equal(badge.tag, "span", status);
    assert.deepEqual(
      badge.className.split(" ").sort(),
      ["file-header-badge", "github-pull-badge", "github-pull-requirement"],
      status,
    );
    assert.deepEqual(badge.dataset, { status, tone: STATUS_TONES[status] }, status);
    assert.deepEqual(badge.children, [statusWord(status)], status);
    assert.equal(statusWord(status).toLowerCase(), status.replaceAll("_", " "), status);
    assert.match(statusWord(status), /^[A-Z]/, status);
  }
  assert.equal(requirementBadge("not a status"), null, "an unnamed status has no badge");
  assert.equal(requirementBadge("constructor"), null, "nor does a name every object has");
  // The slot's sizers: one hidden badge's box for each label, in a sizer's class alone.
  const sizers = readinessSizers();
  assert.deepEqual(
    sizers.map((sizer) => sizer.textContent),
    [...SLOT_LABELS],
  );
  for (const sizer of sizers) {
    assert.equal(sizer.getAttribute("aria-hidden"), "true");
    assert.equal(sizer.className, "file-header-badge github-pull-badge github-pull-badge-sizer");
  }

  console.log(
    JSON.stringify({
      vocabulary: Object.keys(VERDICT_GLYPHS),
      slotLabels: SLOT_LABELS,
      statusTones: Object.entries(STATUS_TONES),
      requirementBadgesSayTheStatus: true,
      sizersAreHiddenLabels: true,
      cases,
      noReadinessDrawsNothing: true,
      toneAndLabelAreTheReadinesss: true,
      namedByDefaultOrHidden: true,
      oneShapePerVerdict: true,
      sharedShapesAreSharedGlyphs: true,
      eachGlyphParsedOnce: true,
    }),
  );
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
