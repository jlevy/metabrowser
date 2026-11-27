// A pull request's Conversation timeline, laid out and painted by a real engine: the
// production page module and its stylesheets, mounted on a recorded record in headless
// Chrome, with a timeline projection that puts commits among its comments and reviews.
//
//   CHROME_BIN=/path/to/chrome CHROME_PROFILES=/dir/the/caller/removes \
//     KPRESS_STATIC=/dir/with/kpress/css/and/fonts KPRESS_SHEETS='["css/…", …]' \
//     node tests/dom/github-pull-timeline-chrome.mjs [--shots DIR]
//
// tests/test_github_pull_timeline_chrome.py copies KPress's tokens, faces, and document
// stylesheets out of the installed package, owns the profile, and runs this in a process
// group of its own. `--shots DIR` also writes a screenshot of each layout, for review.
//
// The record is pull request 7 of tests/fixtures/github-pull-page-responses.json, with its
// recorded Markdown answers. The projection is this session's: two commits in a run after
// the description, a review with no text, the comment, a commit, and the approving review.
// It is laid out both ways the page places commits (github-pull-timeline-session.js holds
// which): answered after the conversation painted, its commits go after everything, past
// the review comments; held at a repaint, they go among the cards in provider order.
//
// What it holds (docs/design-system.md, "The Pull Request Page", "Conversation Timeline"):
// - a commit row is set in the type of a card head: the same size and line, its verb and
//   age as a comment's, and its hash at the same size, as a short commit ID is everywhere;
// - every heading reads alike (mb-novh): the author, a plain verb, and the age, and a boxed
//   chip after the age only for a review state the verb does not say;
// - one rhythm (mb-w7rt): every two consecutive events are the timeline's one token apart,
//   a card by its border and a commit by the glyphs of its text nodes, card to card, card to
//   commit, commit to card, and commit to commit alike, and roomier than the 12 px cards
//   had, and anything else below an event, Review comments, keeps the page's gap and its
//   own margin;
// - every card head's avatar, or its box with the person glyph for an author without one,
//   is on the line, and every head's name starts where the commits' subjects do;
// - one line joins every two adjacent events, at one x, from a card's edge or a commit's
//   node to the next, and is drawn nowhere else: not above the first event, past the last,
//   or across anything that is not an event. Each commit has a node on the line, at its
//   first line. The line is read from the boxes Chrome laid out and from the pixels it
//   painted, so a card that clips it or a box that covers it fails here.
// The order of events is the browserless session's, and is not changed here.
import fs from "node:fs";
import http from "node:http";
import { createRequire } from "node:module";
import path from "node:path";
import zlib from "node:zlib";
import { launchChrome } from "./chrome-session.mjs";

// The SDK's age builder over the ages a fake plays (sdk-ref-fixture.js), its source
// interpolated into a page script, so a page draws the labels the session chose.
const { agesFrom } = createRequire(import.meta.url)("./sdk-ref-fixture.js");

const root = path.resolve(import.meta.dirname, "../..");
const STATIC = path.join(root, "src/metabrowser/static");
const GITHUB = path.join(root, "src/metabrowser/builtin_plugins/github");
const FIXTURES = path.join(root, "tests/fixtures/github-pull-page-responses.json");
const KPRESS = path.resolve(/** @type {string} */ (process.env.KPRESS_STATIC));
const SHEETS = /** @type {string[]} */ (JSON.parse(process.env.KPRESS_SHEETS ?? "[]"));
const SHOTS = (() => {
  const at = process.argv.indexOf("--shots");
  return at === -1 ? null : path.resolve(process.argv[at + 1]);
})();
const failures = [];
let checks = 0;
const check = (label, ok, detail = "") => {
  checks += 1;
  if (!ok) {
    failures.push(`${label}${detail ? `: ${detail}` : ""}`);
  }
};
const round = (value) => Math.round(value * 100) / 100;

// The scripts the SDK's helpers need, in the order tests/dom/sdk-sandbox.js loads them.
const SDK = [
  "request-error.js",
  "formatters.js",
  "inventory-scope.js",
  "resource-context.js",
  "view-state.js",
  "navigation.js",
  "plugin-sdk.js",
  "plugin-sdk-views.js",
];
const PAGE = `<!doctype html><html><head><meta charset="utf-8"><title>pull timeline</title>
<link rel="stylesheet" href="/kpress/css/style-tokens.css">
<link rel="stylesheet" href="/static/styles.css">
<link rel="stylesheet" href="/github/styles.css">
${SHEETS.map((sheet) => `<link rel="stylesheet" href="/kpress/${sheet}">`).join("\n")}
<script>
  window.METABROWSER_SETTINGS = { SYNTAX_HIGHLIGHT_MAX_BYTES: 524288, SYNTAX_LANGUAGE_BY_BASENAME: {}, SYNTAX_LANGUAGE_BY_EXTENSION: {} };
  window.MetabrowserIcons = { copy: '<svg data-icon="copy"></svg>' };
</script>
<script src="/static/inert-html.js"></script>
${SDK.map((name) => `<script src="/static/${name}"></script>`).join("\n")}
</head><body><div id="preview-pane" class="preview-pane"></div></body></html>`;

const TYPES = {
  ".css": "text/css",
  ".js": "text/javascript",
  ".json": "application/json",
  ".woff2": "font/woff2",
};
function serve() {
  const server = http.createServer((request, response) => {
    const url = new URL(request.url ?? "/", "http://localhost");
    let file = null;
    if (url.pathname === "/" || url.pathname.startsWith("/pull/")) {
      response.writeHead(200, { "content-type": "text/html" });
      response.end(PAGE);
      return;
    }
    if (url.pathname === "/fixtures.json") {
      file = FIXTURES;
    } else if (url.pathname.startsWith("/static/")) {
      file = path.join(STATIC, url.pathname.slice(8));
    } else if (url.pathname.startsWith("/github/")) {
      file = path.join(GITHUB, url.pathname.slice(8));
    } else if (url.pathname.startsWith("/kpress/")) {
      file = path.join(KPRESS, url.pathname.slice(8));
    }
    const within = [root, KPRESS].some((dir) => file?.startsWith(dir + path.sep));
    if (!file || !within || !fs.existsSync(file)) {
      response.writeHead(404);
      response.end();
      return;
    }
    response.writeHead(200, { "content-type": TYPES[path.extname(file)] ?? "text/plain" });
    fs.createReadStream(file).pipe(response);
  });
  return new Promise((resolve) => server.listen(0, "127.0.0.1", () => resolve(server)));
}

// In the page: mount pull request 7 on its Conversation, answer its requests, place the
// commits the way `arrangement` names, and read every event's boxes, type, and pseudo-
// elements, in page coordinates.
const MEASURE = `async (arrangement, width, theme) => {
  const recorded = window.__recorded ??= await (await fetch("/fixtures.json")).json();
  const page = window.__page ??= await import("/github/pull-page.js");
  const mb = window.metabrowser;
  document.documentElement.setAttribute("data-theme", theme);
  const envelope = structuredClone(recorded.current.body);
  envelope.comparison_route = null;
  envelope.record.comparison = null;
  envelope.record.unavailable.comparison = "no_store";
  const record = envelope.record;
  const [quiet, approved] = record.reviews;
  const commit = (oid, subject, at) => ({ kind: "commit", oid, subject, committed_at: at });
  const events = [
    commit("3c4a8f1b2d6e09a7c5b3f1e8d2a6c4b0e9f7a5d3", "Teach the counter a second step", "2026-09-16T11:02:00Z"),
    commit(quiet.commit_id, "Count to two in the app", "2026-09-16T11:40:00Z"),
    { kind: "review", id: String(quiet.id) },
    { kind: "comment", id: String(record.issue_comments[0].id) },
    commit(record.pull.head.sha, "Address the review", "2026-09-16T17:35:00Z"),
    { kind: "review", id: String(approved.id) },
  ];
  const markdown = new Map(
    Object.entries(recorded)
      .filter(([key, entry]) => key.startsWith("markdown ") && entry.body?.part)
      .map(([, entry]) => [entry.body.part, entry.body]),
  );
  const json = (body) =>
    new Response(JSON.stringify(body), { status: 200, headers: { "content-type": "application/json" } });
  let timelineAsked = 0;
  window.fetch = async (route) => {
    const url = new URL(String(route), "http://localhost");
    if (url.pathname === "/api/plugin/github/pull-timeline") {
      timelineAsked += 1;
      return json({ record_revision: envelope.record_revision, state: "complete", events });
    }
    if (url.pathname === "/api/plugin/github/pull") {
      return json(envelope);
    }
    if (url.pathname === "/api/plugin/github/pull-markdown") {
      const answer = markdown.get(url.searchParams.get("part"));
      if (answer) {
        return json({ ...answer, record_revision: envelope.record_revision, assets: {} });
      }
    }
    return new Response(null, { status: 304 });
  };
  history.replaceState(null, "", "/pull/7");
  const pane = document.getElementById("preview-pane");
  pane.style.width = width + "px";
  const container = document.createElement("div");
  pane.replaceChildren(container);
  const handle = page.mountPullPage(
    container,
    { number: 7, tab: "", reader: { initial: { etag: null, body: envelope }, fetchAfterMs: 0 } },
    {
      perf: { measure: (_label, work) => work(), measureAsync: (_label, work) => work() },
      ensureAsset: async () => {},
      loadKpressAssets: async () => {},
      whenIdle: mb.whenIdle,
      ensureKindAssets: async () => {},
      decorateExternalLink: mb.decorateExternalLink,
      // The link card's SDK methods, which the page calls as it draws, replaces, and puts
      // away its texts (static/plugin-sdk-views.js).
      previewLink: mb.previewLink,
      forgetPreview: mb.forgetPreview,
      disposePreviews: mb.disposePreviews,
      refChip: mb.refChip,
      refChipHtml: mb.refChipHtml,
      mergeRefs: mb.mergeRefs,
      mountRefMenus: mb.mountRefMenus,
      actorIdentity: mb.actorIdentity,
      titleNodes: mb.titleNodes,
      shortCommit: mb.shortCommit,
      countPartsNodes: mb.countPartsNodes,
      formatInteger: mb.formatInteger,
      ...(${agesFrom})(document, () => ({ label: "2mo ago", className: "age-old" })),
      formatTimestamp: (seconds) => new Date(seconds * 1000).toISOString(),
      navigation: { href: () => "/view/" },
      sourceKind: () => "filesystem",
      icons: { toggle: "" },
    },
  );
  await handle.ready;
  handle.activate();
  const frames = () => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  // The commits took 34 to 40 ms to arrive on a Mac (\`waited\` in each record); the bound
  // is the shared waitFor's 20 s (chrome-session.mjs), since this session's 48 s bound is
  // set for a loaded CI runner, on which an inner bound must not fire first.
  const began = performance.now();
  const until = async (test, what) => {
    const deadline = performance.now() + 20000;
    while (performance.now() < deadline) {
      if (test()) return;
      await new Promise((resolve) => setTimeout(resolve, 10));
    }
    throw new Error("timed out waiting for " + what);
  };
  const body = () => container.querySelector(".github-pull-body");
  const commits = () => body()?.querySelectorAll(":scope > .github-pull-commit").length ?? 0;
  await until(() => commits() === 3, "the commits");
  if (arrangement === "held") {
    // A repaint with the projection held: the Conversation's return from another tab.
    history.replaceState(null, "", "/pull/7/checks");
    handle.land({ tab: "checks" });
    history.replaceState(null, "", "/pull/7");
    handle.land({ tab: "" });
    await until(
      () => body()?.children[1]?.classList.contains("github-pull-commit") && commits() === 3,
      "the commits among the cards",
    );
  }
  const waited = Math.round(performance.now() - began);
  // The recorded authors have no avatar URL, so each head draws the avatar's box with the
  // person glyph in it. Most authors have one, so every head but the description's gets the
  // image authorLabel draws in that box, without a request; the description keeps its glyph.
  const heads = [...body().querySelectorAll(":scope > .github-pull-card > .github-pull-card-head")];
  for (const head of heads.slice(1)) {
    const slot = head.querySelector(".github-pull-identity > .actor-avatar");
    if (slot) {
      const image = document.createElement("img");
      image.className = "actor-avatar-image";
      image.alt = "";
      image.width = 18;
      image.height = 18;
      image.src = "data:image/svg+xml," + encodeURIComponent(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 18 18"><circle cx="9" cy="9" r="9" fill="#8a8f98"/></svg>',
      );
      slot.replaceChildren(image);
    }
  }
  await Promise.allSettled([...container.querySelectorAll(".actor-avatar-image")].map((image) => image.decode()));
  await document.fonts.ready;
  await frames();
  const round = (value) => Math.round(value * 100) / 100;
  const box = (node) => {
    const r = node.getBoundingClientRect();
    return {
      top: round(r.top + scrollY),
      bottom: round(r.bottom + scrollY),
      left: round(r.left + scrollX),
      right: round(r.right + scrollX),
    };
  };
  // An element's first line of glyphs, as a range reads it.
  const firstLine = (element) => {
    const range = document.createRange();
    range.selectNodeContents(element);
    const r = [...range.getClientRects()].find((x) => x.width > 0);
    return r
      ? { top: round(r.top + scrollY), bottom: round(r.bottom + scrollY), left: round(r.left + scrollX) }
      : null;
  };
  // Where an element's glyphs start and end, however it wraps: the union of its text nodes'
  // own boxes. A range over the element would also give each flex item's border box, and a
  // commit row's items fill its line, so it would read the row's box and not its text.
  const glyphs = (element) => {
    const rects = [];
    const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT);
    for (let node = walker.nextNode(); node !== null; node = walker.nextNode()) {
      const range = document.createRange();
      range.selectNodeContents(node);
      for (const r of range.getClientRects()) {
        if (r.width > 0) rects.push({ top: r.top, bottom: r.bottom });
      }
    }
    if (rects.length === 0) return null;
    return {
      top: round(Math.min(...rects.map((r) => r.top)) + scrollY),
      bottom: round(Math.max(...rects.map((r) => r.bottom)) + scrollY),
    };
  };
  const type = (node) => {
    if (!node) return null;
    const s = getComputedStyle(node);
    return { size: s.fontSize, line: s.lineHeight, weight: s.fontWeight, color: s.color, family: s.fontFamily, adjust: s.fontSizeAdjust };
  };
  // An absolutely positioned pseudo-element, in page coordinates: Chrome resolves its
  // offsets and size to the used values, from its element's padding box.
  const pseudo = (node, which) => {
    const s = getComputedStyle(node, which);
    if (s.content === "none" || s.content === "normal" || s.display === "none" || s.position !== "absolute") {
      return null;
    }
    const own = getComputedStyle(node);
    const r = node.getBoundingClientRect();
    return {
      left: round(r.left + scrollX + parseFloat(own.borderLeftWidth) + parseFloat(s.left)),
      top: round(r.top + scrollY + parseFloat(own.borderTopWidth) + parseFloat(s.top)),
      width: round(parseFloat(s.width)),
      height: round(parseFloat(s.height)),
      radius: s.borderTopLeftRadius,
      color: s.backgroundColor,
    };
  };
  const probe = document.createElement("span");
  container.append(probe);
  // The commit-ID face, as a short commit ID is set wherever it appears
  // (docs/design-system.md, "Short Commit IDs"): the one gray, and the monospace face with
  // the sans's x-height.
  probe.style.color = "var(--muted)";
  probe.style.fontFamily = "var(--font-mono)";
  probe.style.fontSizeAdjust = "var(--font-sans-ex-height)";
  const idFace = {
    color: getComputedStyle(probe).color,
    family: getComputedStyle(probe).fontFamily,
    adjust: getComputedStyle(probe).fontSizeAdjust,
  };
  probe.remove();
  const items = [...body().children].map((node) => {
    const kind = node.classList.contains("github-pull-commit")
      ? "commit"
      : node.classList.contains("github-pull-card")
        ? "card"
        : "other";
    const item = {
      kind,
      label: (node.textContent || "").trim().replace(/\\s+/g, " ").slice(0, 32),
      box: box(node),
      before: pseudo(node, "::before"),
      after: pseudo(node, "::after"),
    };
    if (kind === "commit") {
      const subject = node.querySelector(".github-pull-commit-subject");
      const when = [...node.children].find((child) => /^committed /.test(child.textContent || ""));
      item.text = firstLine(subject);
      item.glyphs = glyphs(node);
      item.type = {
        row: type(node),
        subject: type(subject),
        when: type(when),
        age: type(node.querySelector(".github-pull-age")),
        sha: type(node.querySelector(".git-commit-sha")),
      };
      item.shaText = node.querySelector(".git-commit-sha")?.textContent ?? null;
    } else if (kind === "card") {
      const head = node.querySelector(":scope > .github-pull-card-head");
      const author = head?.querySelector(".github-pull-author");
      const avatar = head?.querySelector(".github-pull-identity > .actor-avatar");
      item.text = author ? firstLine(author) : null;
      item.avatar = avatar ? box(avatar) : null;
      item.slot = avatar ? avatar.querySelector("img") === null : false;
      item.type = { head: type(head), age: type(head?.querySelector(".github-pull-age")) };
      // The heading as read: its words, the verb said in the head's own text, and its chips.
      item.heading = head ? head.textContent.replace(/\\s+/g, " ").trim() : null;
      item.verb = head
        ? [...head.childNodes]
            .filter((node) => node.nodeType === Node.TEXT_NODE)
            .map((node) => node.textContent.trim())
            .filter(Boolean)
        : [];
      item.chips = head
        ? [...head.querySelectorAll(".github-pull-badge")].map((chip) => ({
            text: chip.textContent,
            last: chip === head.lastElementChild && chip.previousElementSibling?.classList.contains("github-pull-age"),
            boxed: getComputedStyle(chip).borderTopStyle !== "none",
          }))
        : [];
    } else {
      item.margin = parseFloat(getComputedStyle(node).marginBlockStart);
    }
    return item;
  });
  const gap = parseFloat(getComputedStyle(body()).rowGap);
  const rhythm = parseFloat(getComputedStyle(body()).getPropertyValue("--github-pull-rhythm"));
  // Review comments: its heading over its first card, and each card over the next.
  const threads = (() => {
    const section = container.querySelector(".github-pull-threads");
    const heading = section?.querySelector(":scope > h2");
    const cards = section ? [...section.querySelectorAll(":scope > .github-pull-card")] : [];
    if (!heading || cards.length < 2) return null;
    const r = (node) => node.getBoundingClientRect();
    // Its tally, beside the name after the separator, on the heading's one line
    // (docs/design-system.md, "Heading Tallies").
    const tally = heading.querySelector(":scope > .heading-tally");
    const name = document.createRange();
    name.setStart(heading.firstChild, 0);
    name.setEnd(heading.firstChild, heading.firstChild.length);
    return {
      sectionGap: parseFloat(getComputedStyle(section).getPropertyValue("--github-pull-gap")),
      headingToCard: round(r(cards[0]).top - r(heading).bottom),
      between: cards.slice(1).map((card, at) => round(r(card).top - r(cards[at]).bottom)),
      heading: heading.textContent,
      tally: tally === null ? null : {
        fromName: round(r(tally).left - name.getBoundingClientRect().right),
        sameLine: Math.abs(r(tally).bottom - name.getBoundingClientRect().bottom) < 1,
        weight: getComputedStyle(tally).fontWeight,
        figureWeight: getComputedStyle(tally.querySelector(".heading-tally-figure")).fontWeight,
        dotHidden: tally.querySelector(".heading-tally-dot")?.getAttribute("aria-hidden") === "true",
        muted: (() => {
          const probe = document.createElement("span");
          probe.style.color = "var(--muted)";
          heading.append(probe);
          const muted = getComputedStyle(probe).color;
          probe.remove();
          return getComputedStyle(tally).color === muted;
        })(),
      },
    };
  })();
  window.__dispose = () => handle.dispose();
  return {
    width,
    theme,
    arrangement,
    timelineAsked,
    waited,
    gap,
    rhythm,
    threads,
    idFace,
    shortCommit: mb.shortCommit("0123456789abcdef0123456789abcdef01234567"),
    items,
    // To the conversation's end: the page past it is the window's.
    height: Math.ceil(body().getBoundingClientRect().bottom + scrollY),
  };
}`;

/** A PNG Chrome wrote: 8-bit RGB or RGBA, not interlaced. */
function decodePng(buffer) {
  let at = 8;
  let width = 0;
  let height = 0;
  let channels = 0;
  const data = [];
  while (at < buffer.length) {
    const length = buffer.readUInt32BE(at);
    const kind = buffer.toString("ascii", at + 4, at + 8);
    const chunk = buffer.subarray(at + 8, at + 8 + length);
    if (kind === "IHDR") {
      width = chunk.readUInt32BE(0);
      height = chunk.readUInt32BE(4);
      channels = { 2: 3, 6: 4 }[chunk[9]] ?? 0;
      if (chunk[8] !== 8 || channels === 0 || chunk[12] !== 0) {
        throw new Error("a PNG this reader does not read");
      }
    } else if (kind === "IDAT") {
      data.push(chunk);
    } else if (kind === "IEND") {
      break;
    }
    at += 12 + length;
  }
  const raw = zlib.inflateSync(Buffer.concat(data));
  const stride = width * channels;
  const pixels = Buffer.alloc(height * stride);
  for (let y = 0; y < height; y += 1) {
    const filter = raw[y * (stride + 1)];
    for (let x = 0; x < stride; x += 1) {
      const a = x >= channels ? pixels[y * stride + x - channels] : 0;
      const b = y > 0 ? pixels[(y - 1) * stride + x] : 0;
      const c = x >= channels && y > 0 ? pixels[(y - 1) * stride + x - channels] : 0;
      let value = raw[y * (stride + 1) + 1 + x];
      if (filter === 1) {
        value += a;
      } else if (filter === 2) {
        value += b;
      } else if (filter === 3) {
        value += (a + b) >> 1;
      } else if (filter === 4) {
        const p = a + b - c;
        const pa = Math.abs(p - a);
        const pb = Math.abs(p - b);
        const pc = Math.abs(p - c);
        value += pa <= pb && pa <= pc ? a : pb <= pc ? b : c;
      }
      pixels[y * stride + x] = value & 255;
    }
  }
  return {
    pixel(x, y) {
      const start = Math.floor(y) * stride + Math.floor(x) * channels;
      return [pixels[start], pixels[start + 1], pixels[start + 2]];
    },
  };
}
const distance = (one, two) =>
  one.reduce((sum, value, index) => sum + Math.abs(value - two[index]), 0);

const centerX = (part) => part.left + part.width / 2;
const centerY = (part) => part.top + part.height / 2;
const isEvent = (item) => item !== undefined && item.kind !== "other";
// Where the line meets an event: a card at its edge, a commit at its node.
const attach = (item, side) =>
  item.kind === "commit" && item.after ? centerY(item.after) : item.box[side];
// The line's segments: each event's ::before.
const segments = (items) =>
  items
    .filter((item) => isEvent(item) && item.before && item.before.height > 0)
    .map((item) => ({
      x: centerX(item.before),
      width: item.before.width,
      top: item.before.top,
      bottom: item.before.top + item.before.height,
    }));
// Whether the segments at x cover [from, to], to half a pixel.
const covered = (parts, x, from, to) => {
  let reached = from;
  for (const part of [...parts].sort((one, two) => one.top - two.top)) {
    if (Math.abs(part.x - x) <= 0.5 && part.top <= reached + 0.5 && part.bottom > reached) {
      reached = part.bottom;
    }
  }
  return reached >= to - 0.5;
};
// How much of [from, to] the segments at x draw.
const drawnWithin = (parts, x, from, to) =>
  parts
    .filter((part) => Math.abs(part.x - x) <= 0.5)
    .reduce(
      (sum, part) => sum + Math.max(0, Math.min(part.bottom, to) - Math.max(part.top, from)),
      0,
    );

function hold(measured, image) {
  const { items } = measured;
  const where = `${measured.arrangement} at ${measured.width} px, ${measured.theme}`;
  const commits = items.filter((item) => item.kind === "commit");
  const cards = items.filter((item) => item.kind === "card");
  // The card head every commit is compared with: the first comment's or review's.
  const head = cards.find((card, index) => index > 0 && card.text && card.avatar) ?? cards[0];
  check(
    `${where}: three commits and four cards`,
    commits.length === 3 && cards.length === 4,
    `${commits.length} and ${cards.length}`,
  );

  // Type: a commit row is set as a card head is.
  for (const row of commits) {
    const label = `${where}: commit "${row.label}"`;
    check(
      `${label} is set at the card head's size`,
      row.type.subject.size === head.type.head.size,
      `${row.type.subject.size} against ${head.type.head.size}`,
    );
    check(
      `${label} has the card head's line`,
      row.type.row.line === head.type.head.line,
      `${row.type.row.line} against ${head.type.head.line}`,
    );
    check(
      `${label} says when as a card head does`,
      row.type.when?.size === head.type.head.size && row.type.when?.color === head.type.head.color,
      `${row.type.when?.size} ${row.type.when?.color} against ${head.type.head.size} ${head.type.head.color}`,
    );
    check(
      `${label} has a card head's age`,
      row.type.age?.size === head.type.age?.size,
      `${row.type.age?.size} against ${head.type.age?.size}`,
    );
    check(
      `${label} sets its hash at its text's size, with the sans's x-height`,
      row.type.sha?.size === row.type.subject.size &&
        row.type.sha?.adjust === measured.idFace.adjust &&
        measured.idFace.adjust !== "none",
      `${row.type.sha?.size} ${row.type.sha?.adjust} against ${row.type.subject.size} ${measured.idFace.adjust}`,
    );
    // A short commit ID, as every line names one: its length, the one gray, and the
    // commit-ID face, though it links to the commit on GitHub.
    check(
      `${label} names its commit by a short commit ID`,
      row.shaText?.length === measured.shortCommit.length,
      `${JSON.stringify(row.shaText)} against ${measured.shortCommit.length} characters`,
    );
    check(
      `${label} sets its commit ID in the commit-ID face and gray`,
      row.type.sha?.color === measured.idFace.color &&
        row.type.sha?.family === measured.idFace.family,
      `${row.type.sha?.color} ${row.type.sha?.family} against ${measured.idFace.color} ${measured.idFace.family}`,
    );
  }

  // Every event's heading reads alike (mb-novh): the author, a plain verb in the head's own
  // text, and the age, and a boxed chip after the age only for a review's state the verb
  // does not say. The recorded reviews are a plain one, which has none, and an approval.
  for (const card of cards) {
    const label = `${where}: card "${card.label}"`;
    const verb = card.verb[0];
    check(
      `${label}'s heading is the author, a plain verb, and the age`,
      ["opened", "commented", "reviewed"].includes(verb) &&
        card.heading.startsWith(`${card.heading.split(" ")[0]} ${verb} `),
      JSON.stringify({ heading: card.heading, verb: card.verb }),
    );
    check(
      `${label} boxes only a state its verb does not say, after its age`,
      card.chips.every(
        (chip) =>
          chip.boxed &&
          chip.last &&
          ["Approved", "Changes requested", "Dismissed"].includes(chip.text),
      ),
      JSON.stringify(card.chips),
    );
  }
  const reviews = cards.filter((card) => card.verb[0] === "reviewed");
  check(
    `${where}: a plain review has no chip, and an approval one, "Approved"`,
    reviews.length === 2 &&
      reviews.some((card) => card.chips.length === 0) &&
      reviews.some((card) => card.chips.length === 1 && card.chips[0].text === "Approved"),
    JSON.stringify(reviews.map((card) => [card.heading, card.chips])),
  );
  // One rhythm (mb-w7rt): the visible space between any two consecutive events, card or
  // commit, is the timeline's one token, roomier than the 12 px cards had. Visible is a card's
  // border, and a commit row's glyphs, read from its text nodes, whose row is its line: so
  // every box is the token apart, and a commit's glyphs are the token from a card's border
  // and from the next commit's. In Chrome 152 every box gap measured the token exactly, and
  // the glyphs 20 to 21 px: the face's glyphs fill 20 of the line's 21 px, and a face whose
  // glyphs sit higher or lower in their line may differ by its half-leading, a pixel at most.
  // A line taller than its glyphs, as `line-height: 2` on the rows and heads, fails here.
  // A row that a narrow pane wraps can end on a line that holds only its hash, a short
  // commit ID whose line box is its glyphs' (`.git-commit-sha`), so it shows the rhythm
  // below it as any row does. When the hash was a step below the row's text with the row's
  // line ratio, 13 px SF Mono's 15 px of glyphs left 2.5 px of their 19.5 px line under
  // them, and 22.5 px showed below such a row at 420 px; and when it took the row's size,
  // its line's half-leading grew a one-line row to 22 px (mb-qq4e).
  const rhythm = measured.rhythm;
  check(`${where}: the rhythm is one token, roomier than 12 px`, rhythm > 12, String(rhythm));
  const top = (item) => (item.kind === "commit" ? item.glyphs.top : item.box.top);
  const end = (item) => (item.kind === "commit" ? item.glyphs.bottom : item.box.bottom);
  const spaces = [];
  for (const [index, item] of items.entries()) {
    const next = items[index + 1];
    if (!isEvent(next)) {
      continue;
    }
    const pair = `${item.kind} to ${next.kind}`;
    const between = next.box.top - item.box.bottom;
    check(
      `${where}: ${pair}, "${item.label}" to "${next.label}", are the rhythm apart`,
      Math.abs(between - rhythm) < 0.5,
      `${round(between)} against ${rhythm} px`,
    );
    const space = top(next) - end(item);
    spaces.push([pair, round(space)]);
    check(
      `${where}: ${pair}, "${item.label}" to "${next.label}", show the rhythm between them`,
      space >= rhythm - 1 && space <= rhythm + 1,
      `${round(space)} against ${rhythm} px`,
    );
  }
  // Anything else keeps the page's gap above it, and its own margin: the rhythm is the
  // events' alone, as it is the Conversation's and not the Files or Checks tab's. Review
  // comments stands 28 px below a card, as before the rhythm; with the rhythm as the body's
  // gap it stood 36 px below, in Chrome 152.
  for (const [index, item] of items.entries()) {
    const next = items[index + 1];
    if (!isEvent(item) || next === undefined || isEvent(next)) {
      continue;
    }
    const between = next.box.top - item.box.bottom;
    check(
      `${where}: "${next.label}" keeps the page's gap and its own margin below "${item.label}"`,
      measured.gap < rhythm && Math.abs(between - (measured.gap + next.margin)) < 0.5,
      `${round(between)} against ${measured.gap} and ${next.margin} px`,
    );
  }
  const shown = spaces.map(([, space]) => space);
  check(
    `${where}: every pair shows the same space, to the face's pixel`,
    shown.length > 0 && Math.max(...shown) - Math.min(...shown) <= 1,
    JSON.stringify(spaces),
  );
  // Under Review comments the rhythm is between its cards only: its heading sits over the
  // first at the sections' own gap, as every section's heading does over its content. With
  // the rhythm as the section's gap it stood 20 px over its first card (mb-xlla).
  const threads = measured.threads;
  check(
    `${where}: Review comments' heading is the sections' gap over its first card, and its cards the rhythm apart`,
    threads !== null &&
      threads.sectionGap < rhythm &&
      Math.abs(threads.headingToCard - threads.sectionGap) < 0.5 &&
      threads.between.length > 0 &&
      threads.between.every((space) => Math.abs(space - rhythm) < 0.5),
    JSON.stringify(threads),
  );
  // Its heading's tally sits beside the name after the separator, on its line, regular and
  // muted with a bold numeral, the dot hidden from assistive technology.
  check(
    `${where}: Review comments' tally is beside its name`,
    threads !== null &&
      threads.heading === `Review comments · ${threads.between.length + 1}` &&
      threads.tally !== null &&
      Math.abs(threads.tally.fromName) < 0.5 &&
      threads.tally.sameLine &&
      threads.tally.weight === "400" &&
      threads.tally.figureWeight === "700" &&
      threads.tally.dotHidden &&
      threads.tally.muted,
    JSON.stringify(threads),
  );
  for (const row of commits) {
    const label = `${where}: commit "${row.label}"`;
    check(
      `${label} starts where a name after its avatar does`,
      Math.abs(row.text.left - head.text.left) < 0.5,
      `${row.text.left} against ${head.text.left}`,
    );
  }

  // The line: at one x, the avatars' center, with a node on it at each commit's first line.
  const parts = segments(items);
  const rail = head.avatar ? (head.avatar.left + head.avatar.right) / 2 : Number.NaN;
  const lineWidth = parts[0]?.width ?? Number.NaN;
  check(
    `${where}: the line runs down the avatars' center`,
    parts.length > 0 && parts.every((part) => Math.abs(part.x - rail) <= 0.5),
    `${JSON.stringify(parts.map((part) => part.x))} against ${rail}`,
  );
  // Every card head, the description's among them with the person glyph in the avatar's box,
  // has its avatar or its box on the line and its name where the commits' subjects start.
  check(
    `${where}: the head with no avatar keeps the avatar's box, the glyph in it`,
    cards.filter((card) => card.slot).length === 1 && cards[0].slot,
    JSON.stringify(cards.map((card) => card.slot)),
  );
  for (const card of cards) {
    const label = `${where}: card "${card.label}"`;
    const center = card.avatar ? (card.avatar.left + card.avatar.right) / 2 : Number.NaN;
    check(
      `${label} has its ${card.slot ? "avatar's box" : "avatar"} on the line`,
      Math.abs(center - rail) <= 0.5,
      `${center} against ${rail}`,
    );
    check(
      `${label}'s name starts where the commits' subjects do`,
      card.text !== null && commits.every((row) => Math.abs(row.text.left - card.text.left) < 0.5),
      `${card.text?.left} against ${commits.map((row) => row.text.left)}`,
    );
  }
  for (const row of commits) {
    const node = row.after;
    const label = `${where}: commit "${row.label}"`;
    check(
      `${label} has a round node on the line`,
      node !== null && node.radius === "50%" && Math.abs(centerX(node) - rail) <= 0.5,
      JSON.stringify(node),
    );
    if (node !== null) {
      const middle = (row.text.top + row.text.bottom) / 2;
      check(
        `${label}'s node is at its first line`,
        Math.abs(centerY(node) - middle) <= 0.75,
        `${centerY(node)} against ${middle}`,
      );
      check(
        `${label}'s node is wider than the line`,
        node.width >= 3 * lineWidth,
        `${node.width} px`,
      );
    }
  }
  // Joined: every two adjacent events. Not joined: across anything else, above the first
  // event, or past the last.
  for (const [index, item] of items.entries()) {
    const next = items[index + 1];
    if (!isEvent(item) || !isEvent(next)) {
      continue;
    }
    const from = attach(item, "bottom");
    const to = attach(next, "top");
    check(
      `${where}: the line joins "${item.label}" to "${next.label}"`,
      covered(parts, rail, from, to),
      `${from} to ${to}`,
    );
  }
  for (const [index, item] of items.entries()) {
    if (!isEvent(item)) {
      continue;
    }
    const previous = items[index - 1];
    const next = items[index + 1];
    if (!isEvent(previous)) {
      const from = previous ? previous.box.top : 0;
      check(
        `${where}: no line above "${item.label}"`,
        drawnWithin(parts, rail, from, attach(item, "top")) < 0.5,
      );
    }
    if (!isEvent(next)) {
      const to = next ? next.box.bottom : measured.height;
      check(
        `${where}: no line past "${item.label}"`,
        drawnWithin(parts, rail, attach(item, "bottom"), to) < 0.5,
      );
    }
  }

  // Paint: in each gap between joined events the line's pixel differs from the page's
  // beside it, and is the same pixel in every gap; a node differs from both.
  const x = Number.isFinite(rail) ? Math.floor(rail) : 0;
  const inks = [];
  for (const [index, item] of items.entries()) {
    const next = items[index + 1];
    if (!isEvent(item) || !isEvent(next)) {
      continue;
    }
    const y = (item.box.bottom + next.box.top) / 2;
    const ink = image.pixel(x, y);
    const page = image.pixel(x + 9, y);
    inks.push(ink);
    check(
      `${where}: the line is painted between "${item.label}" and "${next.label}"`,
      distance(ink, page) >= 12,
      `${ink} against ${page}`,
    );
  }
  check(
    `${where}: the line is one ink`,
    inks.every((ink) => distance(ink, inks[0]) <= 3),
    JSON.stringify(inks),
  );
  for (const row of commits) {
    if (row.after === null) {
      continue;
    }
    const node = image.pixel(x, centerY(row.after));
    const page = image.pixel(x + 9, row.box.top + 1);
    check(
      `${where}: commit "${row.label}"'s node is painted`,
      distance(node, page) >= 12 && distance(node, inks[0] ?? page) >= 12,
      `${node} against ${page} and ${inks[0]}`,
    );
  }
}

// Each arrangement in a wide pane, the held one in a narrow one too, and both themes.
const LAYOUTS = [
  ["late", 980, "light"],
  ["held", 980, "light"],
  ["held", 420, "light"],
  ["late", 980, "dark"],
  ["held", 980, "dark"],
];

/**
 * A commit's ID under the pointer: a link, so it underlines, and still the commit-ID gray
 * (docs/design-system.md, "Short Commit IDs"). The pointer moves away after, before the
 * next layout's screenshot.
 *
 * @param {Awaited<ReturnType<typeof launchChrome>>} chrome
 * @param {{arrangement: string, width: number, theme: string, idFace: {color: string}}} measured
 */
async function holdHover(chrome, measured) {
  const where = `${measured.arrangement} at ${measured.width} px, ${measured.theme}`;
  const at = await chrome.evaluate(`(() => {
    const id = document.querySelector(".github-pull-commit .git-commit-sha");
    id.scrollIntoView({ block: "center" });
    const r = id.getBoundingClientRect();
    return { x: r.left + r.width / 2, y: r.top + r.height / 2 };
  })()`);
  await chrome.send("Input.dispatchMouseEvent", { type: "mouseMoved", x: at.x, y: at.y });
  const hovered = await chrome.evaluate(`(() => {
    const id = document.querySelector(".github-pull-commit .git-commit-sha");
    const s = getComputedStyle(id);
    return { hover: id.matches(":hover"), color: s.color, line: s.textDecorationLine };
  })()`);
  await chrome.send("Input.dispatchMouseEvent", { type: "mouseMoved", x: 0, y: 0 });
  await chrome.evaluate("window.scrollTo(0, 0)");
  check(
    `${where}: a commit ID under the pointer underlines and stays the commit-ID gray`,
    hovered.hover && hovered.line === "underline" && hovered.color === measured.idFace.color,
    JSON.stringify(hovered),
  );
}

const server = await serve();
const { port } = /** @type {import("node:net").AddressInfo} */ (server.address());
/** @type {Awaited<ReturnType<typeof launchChrome>> | null} */
let chrome = null;
try {
  chrome = await launchChrome(/** @type {string} */ (process.env.CHROME_BIN), {
    profiles: /** @type {string} */ (process.env.CHROME_PROFILES),
    width: 1100,
    height: 1600,
  });
  await chrome.send("Page.enable");
  await chrome.send("Page.navigate", { url: `http://127.0.0.1:${port}/pull/7` });
  await chrome.waitFor(
    "document.readyState === 'complete' && !!window.metabrowser && !!window.MetabrowserInertHtml",
  );
  for (const [arrangement, width, theme] of LAYOUTS) {
    const measured = await chrome.evaluate(
      `(${MEASURE})(${JSON.stringify(arrangement)}, ${width}, ${JSON.stringify(theme)})`,
    );
    process.stderr.write(`${JSON.stringify(measured)}\n`);
    const shot = await chrome.send("Page.captureScreenshot", {
      format: "png",
      captureBeyondViewport: true,
      clip: { x: 0, y: 0, width, height: measured.height, scale: 1 },
    });
    const png = Buffer.from(shot.data, "base64");
    if (SHOTS !== null) {
      fs.mkdirSync(SHOTS, { recursive: true });
      fs.writeFileSync(path.join(SHOTS, `${arrangement}-${width}-${theme}.png`), png);
    }
    hold(measured, decodePng(png));
    await holdHover(chrome, measured);
    await chrome.evaluate("window.__dispose()");
  }
} finally {
  await chrome?.close();
  server.close();
}
if (failures.length > 0) {
  process.stderr.write(`${failures.join("\n")}\n`);
  process.exit(1);
}
process.stdout.write(`pull timeline in Chrome: ${checks} checks passed\n`);
