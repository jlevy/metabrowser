// Browserless session for how a link gets its card before the card's code has loaded: the
// SDK's registration (`metabrowser.previewLink`, `forgetPreview`, `disposePreviews` in
// static/plugin-sdk-views.js), which keeps every link a surface registers, loads the
// `link-previews` bundle at the page's first rest on one, and hands the bundle's registry
// those links and that rest.
//
// Each session is one page (tests/dom/link-card-page.js): app.js's own tooltip and its
// delegated listeners, the SDK's view helpers run whole, and the exact bundle, run when the
// SDK asks for it, after the time the session gives the load, or refused. Most pages are a
// plain folder's, with no GitHub identity, whose Markdown document links a file, a folder,
// another site, and a mail address, registered as the Markdown enhancer registers them; one
// is a GitHub checkout's, whose pull request's text the resolver reads. Others link other
// sites by addresses the browser reads against the page's own, register links while the
// bundle loads and after, and let a document go without disposing it, which the collector
// then takes (`collected`).
//
// It prints, for each session, what the reader would see and what the page asked for:
// each registration and whether the SDK answered that the link has a card (`registered`,
// `card`), the pointer (`pointer`), a press (`press`), the bundle asked for (`load`) and
// run (`loaded`), each read (`read`), each warning (`warned`), what the tooltip shows
// (`sees`) and on what (`on`), each link's title (`titles`), and how many pointer listeners
// a document has (`listeners`). tests/test_link_preview_loader_session.py holds its
// invariants, and this file exits 1 on a failed one, naming each session that failed.
// Name sessions on the command line to run only those.

const fs = require("node:fs");
const path = require("node:path");
const v8 = require("node:v8");
const vm = require("node:vm");
const {
  FakeElement,
  PAGE_ADDRESS,
  assert,
  createPage,
  markdownLink,
} = require("./link-card-page.js");

// The collector, so a session can show what the SDK lets go of.
v8.setFlagsFromString("--expose-gc");
const collectGarbage = vm.runInNewContext("gc");

/** The longest outside address the SDK reads, as static/plugin-sdk-views.js bounds it. */
const OUTSIDE_BOUND = (() => {
  const views = fs.readFileSync(
    path.join(__dirname, "../../src/metabrowser/static/plugin-sdk-views.js"),
    "utf8",
  );
  const found = views.match(/\n {2}const MAX_OUTSIDE_URL_LENGTH = (\d+) \* (\d+);\n/);
  assert(found, "static/plugin-sdk-views.js bounds no outside address");
  return Number(found[1]) * Number(found[2]);
})();

const GUIDE = Object.freeze({
  name: "the guide",
  href: "/view/docs/guide.md",
  title: "How to start",
  target: Object.freeze({
    kind: "view",
    target: { path: "docs/guide.md" },
    localization: "revision",
  }),
});
const DOCS = Object.freeze({
  name: "the docs folder",
  href: "/view/docs/",
  target: Object.freeze({ kind: "view", target: { path: "docs/" }, localization: "revision" }),
});
const ELSEWHERE = Object.freeze({
  name: "elsewhere",
  href: "https://example.com/elsewhere",
  title: "A page elsewhere",
  target: Object.freeze({ kind: "external", url: "https://example.com/elsewhere" }),
});
const MAIL = Object.freeze({
  name: "write to us",
  href: "mailto:team@example.com",
  title: "The team's address",
  target: Object.freeze({ kind: "external", url: "mailto:team@example.com" }),
});
const LOAD_MS = 30;

/**
 * Links whose authors titled them, each as a Markdown document writes one, and a link
 * nothing else names among them: what assistive technology reads of each (`reading`) is
 * what Chrome read of the same markup.
 */
const TO_GUIDE = Object.freeze({ href: GUIDE.href, target: GUIDE.target });
const TITLED = Object.freeze([
  // Words of its own, and a title read as its description.
  Object.freeze({ ...TO_GUIDE, name: "Setup", title: "How to set it up" }),
  // `[![](badge.svg)](https://ci.example.com/build "CI status")`: an image with an empty
  // `alt`, which says nothing, so the link's title is its name.
  Object.freeze({
    name: "the CI badge",
    href: "https://ci.example.com/build",
    title: "CI status",
    image: { alt: "" },
    target: Object.freeze({ kind: "external", url: "https://ci.example.com/build" }),
  }),
  // An image with no `alt`, whose own title names it and so the link.
  Object.freeze({
    href: DOCS.href,
    target: DOCS.target,
    name: "the docs diagram",
    image: { title: "The docs, drawn" },
  }),
  // The image names its part of the link, and the link has a description of its own.
  Object.freeze({
    ...TO_GUIDE,
    name: "setup with build status",
    textBeforeImage: "Setup ",
    title: "Open the setup guide",
    image: { title: "Build status" },
  }),
  // `[![](badge.svg "Build status")](docs/guide.md)`: a title on an image with an empty
  // `alt` names nothing, so nothing named the link; its card says that title, and now so
  // does its name.
  Object.freeze({
    ...TO_GUIDE,
    name: "the build badge",
    image: { alt: "", title: "Build status" },
  }),
  // Its author's own `aria-label` and `aria-description`, which stay as they are.
  Object.freeze({
    ...TO_GUIDE,
    name: "the labelled link",
    label: "The guide",
    title: "Start here",
  }),
  Object.freeze({ ...TO_GUIDE, name: "the described link", title: "A guide", description: "Ours" }),
  // A title that says its words again, which is read once.
  Object.freeze({
    href: ELSEWHERE.href,
    target: ELSEWHERE.target,
    name: "Elsewhere",
    title: "Elsewhere",
  }),
]);

/**
 * What assistive technology reads of *anchor*, a link: its name and its description, by
 * the rules Chrome's accessibility tree (`Accessibility.getPartialAXTree`) followed for each
 * markup above and for its `aria-label` and `aria-description` in place of its titles. Its
 * name is its `aria-label`, else what it holds (its text and the names of its images),
 * else its own `title`. An image's name comes from its `aria-label`, `alt` or `title`, in
 * that order. A link's description is its `aria-description`, else its `title` where
 * that is not its name.
 */
function reading(anchor) {
  const words = (value) =>
    String(value ?? "")
      .replace(/\s+/g, " ")
      .trim();
  const held = (node) =>
    node.childNodes
      .map((child) => {
        if (child.nodeType === 3) {
          return child.nodeValue;
        }
        if (child.tagName === "IMG") {
          return (
            child.getAttribute("aria-label") ??
            child.getAttribute("alt") ??
            child.getAttribute("title") ??
            ""
          );
        }
        return held(child);
      })
      .join(" ");
  const title = words(anchor.getAttribute("title"));
  const name = words(anchor.getAttribute("aria-label")) || words(held(anchor)) || title;
  const description =
    words(anchor.getAttribute("aria-description")) || (title === name ? "" : title);
  return { name, description };
}

/** Every attribute of *anchor* and of each element it holds, in order: what its author wrote. */
function attributesOf(anchor) {
  const elements = [anchor, ...anchor.querySelectorAll("*")];
  return JSON.stringify(elements.map((element) => [...element.attributes].sort()));
}

/** A plain folder's page, with no GitHub identity, whose bundle loads *loadMs* after asked. */
function folderPage(cards = { loadMs: LOAD_MS }) {
  return createPage({ repository: null, cards });
}

/** The tooltip's lines over *log*, after the first entry *from*. */
function seen(log, from = 0) {
  return log.slice(from).filter((entry) => entry.sees);
}

/**
 * Links registered on a page that has no GitHub identity, and no pointer anywhere: each link
 * the card is about is registered, a mail link is not and keeps its title, and nothing is
 * loaded however long the page waits.
 */
async function registeredBeforeTheBundle() {
  const page = folderPage();
  const { anchors } = page.markdown("the README", GUIDE, DOCS, ELSEWHERE, MAIL);
  await page.look(5000);
  assert(!page.log.some((entry) => entry.load), "a page with no rest loaded the card");
  assert(!page.loaded(), "the card's registry ran with no rest");
  assert(
    anchors[MAIL.name].getAttribute("title") === MAIL.title,
    "a mail link lost the title it has no card to say",
  );
  assert(
    anchors[GUIDE.name].getAttribute("title") === null,
    "a link with a card kept its native title",
  );
  return page.log;
}

/**
 * The first rest on a plain folder's page: it loads the bundle, and the card of the link the
 * pointer rests on comes up on it for that rest, the tooltip's own delay after the load. Then
 * the outside link's card, the module's own from then on.
 */
async function theFirstRestLoadsIt() {
  const page = folderPage();
  const { anchors } = page.markdown("the README", GUIDE, DOCS, ELSEWHERE, MAIL);
  await page.point(1000, anchors[GUIDE.name]);
  await page.look(1000 + LOAD_MS + page.appearDelay - 1);
  const guide = await page.look(1000 + LOAD_MS + page.appearDelay + 20);
  assert(
    guide?.startsWith("docs/guide.md") && guide.includes("How to start"),
    `the first rest showed no card for its link: ${guide}`,
  );
  assert(page.log.at(-1).on === GUIDE.name, "the first rest's card is not on its link");
  await page.point(1600, page.body);
  await page.point(1800, anchors[ELSEWHERE.name]);
  const elsewhere = await page.look(2200);
  assert(
    elsewhere?.startsWith("Opens example.com") && elsewhere.includes("A page elsewhere"),
    `the outside link's card said ${elsewhere}`,
  );
  await page.point(2400, page.body);
  await page.point(2600, anchors[DOCS.name]);
  const docs = await page.look(3000);
  assert(docs?.startsWith("docs/"), `the folder's card said ${docs}`);
  await page.point(3200, anchors[MAIL.name]);
  await page.look(3600);
  assert(page.log.at(-1).sees === null, "a mail link showed a card");
  assert(page.log.filter((entry) => entry.load).length === 1, "the card was loaded twice");
  return page.log;
}

/**
 * The first rest on a GitHub checkout's page, on a pull request's link the resolver read,
 * while the bundle takes 100 ms: the title is read when a rest that began on a loaded page
 * would read it, the intent delay after the pointer arrived, and is in the card when it
 * comes up.
 */
async function theFirstRestKeepsItsTime() {
  const page = createPage({ cards: { loadMs: 100 } });
  const { anchors } = page.text(["#12", "https://github.com/octo/demo/pull/12"]);
  await page.point(0, anchors["#12"]);
  await page.look(100 + page.appearDelay - 1);
  const card = await page.look(100 + page.appearDelay + 20);
  const read = page.log.find((entry) => entry.read?.startsWith("github/pulls?q=12"));
  assert(read?.at === 250, `the first rest read its title at ${read?.at}, not at 250`);
  assert(card?.includes("feat(links)"), `the first rest's card had no title: ${card}`);
  return page.log;
}

/** The pointer leaves the link while the bundle loads: no card, and the next rest has one. */
async function leftDuringTheLoad() {
  const page = folderPage();
  const { anchors } = page.markdown("the README", GUIDE);
  await page.point(0, anchors[GUIDE.name]);
  await page.point(10, page.body);
  await page.look(800);
  assert(seen(page.log).length === 0, "a rest the pointer left showed its card");
  const before = page.log.length;
  await page.point(1000, anchors[GUIDE.name]);
  const card = await page.look(1400);
  assert(card?.startsWith("docs/guide.md"), `the next rest showed no card: ${card}`);
  assert(!page.log.slice(before).some((entry) => entry.load), "the next rest loaded it again");
  return page.log;
}

/**
 * The reader presses on the link while the bundle loads: that rest shows no card, moving
 * within the link changes nothing, and leaving and coming back is a rest with a card.
 */
async function pressedDuringTheLoad() {
  const page = folderPage();
  const { anchors } = page.markdown("the README", GUIDE);
  await page.point(0, anchors[GUIDE.name]);
  await page.press(10);
  await page.look(800);
  assert(seen(page.log).length === 0, "a rest the reader pressed showed its card");
  await page.point(1000, page.body);
  await page.point(1200, anchors[GUIDE.name]);
  const card = await page.look(1600);
  assert(card?.startsWith("docs/guide.md"), `the rest after the press showed no card: ${card}`);
  return page.log;
}

/**
 * A link forgotten and a document disposed before the bundle loads: a rest on the disposed
 * document's link loads nothing, the forgotten link has no card once it has loaded, and the
 * others keep theirs.
 */
async function forgottenAndDisposedBeforeTheLoad() {
  const page = folderPage();
  const first = page.markdown("the README", GUIDE, ELSEWHERE);
  const second = page.markdown("the changelog", DOCS);
  page.sdk.forgetPreview(first.anchors[ELSEWHERE.name]);
  page.sdk.disposePreviews(second.prose);
  page.log.push({ at: page.clock.now, forgot: ELSEWHERE.name, disposed: "the changelog" });
  await page.point(0, second.anchors[DOCS.name]);
  await page.look(800);
  assert(!page.log.some((entry) => entry.load), "a rest on a disposed document's link loaded it");
  await page.point(1000, first.anchors[GUIDE.name]);
  const guide = await page.look(1400);
  assert(guide?.startsWith("docs/guide.md"), `a registered link had no card: ${guide}`);
  await page.point(1600, first.anchors[ELSEWHERE.name]);
  await page.look(2000);
  assert(page.log.at(-1).sees === null, "a forgotten link showed a card");
  await page.point(2200, second.anchors[DOCS.name]);
  await page.look(2600);
  assert(page.log.at(-1).sees === null, "a disposed document's link showed a card");
  assert(
    attributesOf(first.anchors[ELSEWHERE.name]) === attributesOf(markdownLink(ELSEWHERE)),
    "a link forgotten before the load is not as its author wrote it",
  );
  return page.log;
}

/**
 * A bundle that does not load: no card, one warning, each link's author's title back on it,
 * and no later rest or registration asks again or gives a card.
 */
async function aFailedLoad() {
  const page = folderPage({ loadMs: LOAD_MS, fails: true });
  const { anchors } = page.markdown("the README", GUIDE, ELSEWHERE);
  await page.point(0, anchors[GUIDE.name]);
  await page.look(800);
  await page.point(1000, page.body);
  await page.point(1200, anchors[ELSEWHERE.name]);
  await page.look(1600);
  const later = page.markdown("the changelog", DOCS);
  await page.point(1800, later.anchors[DOCS.name]);
  await page.look(2200);
  assert(seen(page.log).length === 0, "a page whose card did not load showed one");
  assert(page.log.filter((entry) => entry.load).length === 1, "a failed load was asked again");
  assert(page.log.filter((entry) => entry.warned).length === 1, "a failed load did not warn once");
  assert(
    [GUIDE, ELSEWHERE].every(
      (link) => attributesOf(anchors[link.name]) === attributesOf(markdownLink(link)),
    ),
    "a link whose card did not load is not as its author wrote it, its title back",
  );
  assert(
    page.log.find((entry) => entry.registered === DOCS.name)?.card === false,
    "a link registered after a failed load was said to have a card",
  );
  return page.log;
}

/**
 * The titles a link's card takes in place of its native tooltip still say what they said
 * to assistive technology: each link reads as it did as written, before the card's code
 * loads and after, registered again, as a later pass registers one; a link nothing named is
 * named by the title its card says. A link forgotten, and then each of its document's when
 * it is disposed, is back as its author wrote it, its author's own attributes among them.
 */
async function authorTitlesForAssistiveTechnology() {
  const page = folderPage();
  const links = [...TITLED, MAIL];
  const read = (stage, anchors, only = links) => {
    for (const link of only) {
      const anchor = anchors[link.name];
      page.log.push({
        at: page.clock.now,
        reads: link.name,
        stage,
        ...reading(anchor),
        ...(stage === "forgotten" || stage === "disposed"
          ? { asWritten: attributesOf(anchor) === attributesOf(markdownLink(link)) }
          : {}),
      });
    }
  };
  const written = Object.fromEntries(links.map((link) => [link.name, markdownLink(link)]));
  read("as written", written);
  const { prose, anchors } = page.markdown("the README", ...links);
  read("registered", anchors);
  const mixedLink = anchors["setup with build status"];
  assert(
    !mixedLink.hasAttribute("title") && mixedLink.querySelectorAll("[title]").length === 0,
    "a link with a card kept a second, native tooltip",
  );
  await page.point(1000, anchors.Setup);
  const card = await page.look(1600);
  assert(card?.includes("How to set it up"), `the card did not say the title: ${card}`);
  for (const link of links) {
    page.register(prose, anchors[link.name], link, link.title ?? link.image?.title ?? null);
  }
  read("registered again", anchors);
  for (const stage of ["registered", "registered again"]) {
    for (const link of links) {
      const before = reading(written[link.name]);
      const after = page.log.find((entry) => entry.reads === link.name && entry.stage === stage);
      const named = before.name || (link.title ?? link.image?.title ?? "");
      assert(
        after.name === named && after.description === before.description,
        `${stage}, ${link.name} read ${JSON.stringify(after)}, not ${JSON.stringify(before)}`,
      );
    }
  }
  page.sdk.forgetPreview(anchors.Setup);
  read("forgotten", anchors, links.slice(0, 1));
  page.sdk.disposePreviews(prose);
  read("disposed", anchors);
  const changed = page.log.filter((entry) => entry.asWritten === false).map((entry) => entry.reads);
  assert(changed.length === 0, `not as written once its card ended: ${changed.join(", ")}`);
  return page.log;
}

/** A touch is a tap that opens the link: it loads nothing, and a pointer's rest after does. */
async function aTouch() {
  const page = folderPage();
  const { anchors } = page.markdown("the README", GUIDE);
  await page.point(0, anchors[GUIDE.name], "touch");
  await page.look(800);
  assert(!page.log.some((entry) => entry.load), "a touch loaded the card");
  assert(seen(page.log).length === 0, "a touch showed a card");
  await page.point(1000, page.body, "touch");
  await page.point(1200, anchors[GUIDE.name]);
  const card = await page.look(1600);
  assert(
    card?.startsWith("docs/guide.md"),
    `the pointer's rest after a touch had no card: ${card}`,
  );
  return page.log;
}

/** A Markdown link to another site, its address as its author wrote it, with a title. */
function outside(name, url) {
  return { name, href: url, title: `About ${name}`, target: { kind: "external", url } };
}

/** Each link's title now, by its name. */
function titles(anchors) {
  return Object.fromEntries(
    Object.entries(anchors).map(([name, anchor]) => [name, anchor.getAttribute("title")]),
  );
}

/**
 * Outside links, read where the browser follows them, against the page's address: whether
 * the SDK says each has a card before the bundle loads is what the card says once it has,
 * so the hand-over gives no link back its title, and each answers the same registered
 * again. On this `http` page `http:example.com` is a file beside the page and the page's
 * own origin is no other site, so neither has a card; an address longer than the SDK reads
 * has none, and one at that length has its card.
 */
async function outsideAddresses() {
  const page = folderPage();
  const longest = "https://example.com/?q=";
  const links = [
    outside("elsewhere", ELSEWHERE.href),
    outside("a scheme-relative address", "//example.com/docs"),
    outside("another scheme and no slashes", "https:example.com"),
    outside("the page's scheme and no host", "http:example.com"),
    outside("the page's own origin", `${new URL(PAGE_ADDRESS).origin}/view/docs/guide.md`),
    outside("an address at the bound", longest.padEnd(OUTSIDE_BOUND, "q")),
    outside("an address past the bound", longest.padEnd(OUTSIDE_BOUND + 1, "q")),
  ];
  const { prose, anchors } = page.markdown("the README", ...links);
  const registered = titles(anchors);
  await page.point(0, anchors.elsewhere);
  await page.look(LOAD_MS + page.appearDelay + 20);
  const handed = titles(anchors);
  page.log.push({ at: page.clock.now, titles: handed });
  assert(
    JSON.stringify(handed) === JSON.stringify(registered),
    "the hand-over gave a link back its title: the SDK's answer was not the card's",
  );
  for (const link of links) {
    const card = page.sdk.previewLink(prose, anchors[link.name], link.target, {
      authorTitle: link.title,
    });
    page.log.push({ at: page.clock.now, registered: link.name, card });
    assert(
      card === (registered[link.name] === null),
      `${link.name} was said to have a card before the load and not after, or the reverse`,
    );
  }
  for (const [at, name] of [
    [1000, "a scheme-relative address"],
    [2000, "another scheme and no slashes"],
  ]) {
    await page.point(at, page.body);
    await page.point(at + 200, anchors[name]);
    const card = await page.look(at + 600);
    assert(card?.startsWith("Opens example.com"), `${name}'s card said ${card}`);
  }
  return page.log;
}

/** A document registered and then let go of by its surface, without `disposePreviews`. */
function registerAndLetGo(page) {
  const { host, prose } = page.markdown("the lost document", GUIDE, ELSEWHERE);
  host.remove();
  return new WeakRef(prose);
}

/**
 * A document its surface replaced without disposing it, before the bundle loads, as on a
 * page read only by touch or the keyboard, where it never does: the SDK keeps nothing of it,
 * so the collector takes it, and a later document's first rest still loads the card.
 */
async function aDocumentNoSurfaceDisposed() {
  const page = folderPage();
  const lost = registerAndLetGo(page);
  // A new task, past the one that made the reference, which keeps its document until then.
  await new Promise((resolve) => setTimeout(resolve, 0));
  collectGarbage();
  const collected = lost.deref() === undefined;
  page.log.push({ at: page.clock.now, collected });
  assert(collected, "the SDK kept a document its surface let go of, for its links");
  const kept = page.markdown("the changelog", DOCS);
  await page.point(1000, kept.anchors[DOCS.name]);
  const card = await page.look(1000 + LOAD_MS + page.appearDelay + 20);
  assert(card?.startsWith("docs/"), `the next document's first rest showed ${card}`);
  return page.log;
}

/**
 * Links registered while the bundle loads, in a document of their own, and after it has
 * loaded, in the first: the hand-over takes the first, and each has its card. The first
 * document has one delegated pair of pointer listeners throughout, the SDK's until the
 * hand-over and the registry's after, however many links it registers.
 */
async function registeredDuringAndAfterTheLoad() {
  const page = folderPage({ loadMs: 50 });
  const first = page.markdown("the README", GUIDE);
  const listeners = () =>
    first.prose.listeners.filter(({ type }) => type === "pointerover" || type === "pointerout")
      .length;
  page.log.push({ at: page.clock.now, listeners: listeners() });
  await page.point(0, first.anchors[GUIDE.name]);
  await page.clock.to(20);
  const during = page.markdown("the changelog", DOCS);
  await page.look(400);
  page.log.push({ at: page.clock.now, listeners: listeners() });
  const later = new FakeElement("a", ELSEWHERE.name, { href: ELSEWHERE.href });
  later.append(ELSEWHERE.name);
  first.prose.append(later);
  const card = page.sdk.previewLink(first.prose, later, ELSEWHERE.target, {});
  page.log.push({ at: page.clock.now, registered: ELSEWHERE.name, card });
  page.log.push({ at: page.clock.now, listeners: listeners() });
  await page.point(600, page.body);
  await page.point(800, during.anchors[DOCS.name]);
  const docs = await page.look(1200);
  assert(docs?.startsWith("docs/"), `a link registered during the load showed ${docs}`);
  await page.point(1400, later);
  const elsewhere = await page.look(1800);
  assert(
    elsewhere?.startsWith("Opens example.com"),
    `a link registered after the load showed ${elsewhere}`,
  );
  const counts = page.log.filter((entry) => "listeners" in entry).map((entry) => entry.listeners);
  assert(
    counts.every((count) => count === counts[0]),
    `the document's listeners went ${counts.join(", ")}`,
  );
  return page.log;
}

const SESSIONS = {
  "registered before the bundle": registeredBeforeTheBundle,
  "the first rest loads it": theFirstRestLoadsIt,
  "the first rest keeps its time": theFirstRestKeepsItsTime,
  "left during the load": leftDuringTheLoad,
  "pressed during the load": pressedDuringTheLoad,
  "forgotten and disposed before the load": forgottenAndDisposedBeforeTheLoad,
  "a failed load": aFailedLoad,
  "a touch": aTouch,
  "outside addresses": outsideAddresses,
  "a document no surface disposed": aDocumentNoSurfaceDisposed,
  "registered during and after the load": registeredDuringAndAfterTheLoad,
  "an author's title, for assistive technology": authorTitlesForAssistiveTechnology,
};

/** Every session, or those named on the command line, each one's failure said as it ends. */
async function main() {
  const named = process.argv.slice(2);
  const transcript = {};
  const failed = [];
  for (const [name, session] of Object.entries(SESSIONS)) {
    if (named.length > 0 && !named.includes(name)) {
      continue;
    }
    try {
      transcript[name] = await session();
    } catch (error) {
      failed.push(`${name}: ${error.message}`);
    }
  }
  if (failed.length > 0) {
    throw new Error(`failed:\n${failed.join("\n")}`);
  }
  process.stdout.write(`${JSON.stringify(transcript, null, 1)}\n`);
}

main().catch((error) => {
  console.error(error.message);
  process.exit(1);
});
