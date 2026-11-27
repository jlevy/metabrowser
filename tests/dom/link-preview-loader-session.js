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
// is a GitHub checkout's, whose pull request's text the resolver reads.
//
// It prints, for each session, what the reader would see and what the page asked for:
// each registration and whether the SDK answered that the link has a card (`registered`,
// `card`), the pointer (`pointer`), a press (`press`), the bundle asked for (`load`) and
// run (`loaded`), each read (`read`), each warning (`warned`), and what the tooltip shows
// (`sees`) and on what (`on`). tests/test_link_preview_loader_session.py holds its
// invariants, and this file exits 1 on a failed one, naming each session that failed.
// Name sessions on the command line to run only those.

const { assert, createPage } = require("./link-card-page.js");

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
    anchors[GUIDE.name].getAttribute("title") === GUIDE.title &&
      anchors[ELSEWHERE.name].getAttribute("title") === ELSEWHERE.title,
    "a link whose card did not load lost its author's title",
  );
  assert(
    page.log.find((entry) => entry.registered === DOCS.name)?.card === false,
    "a link registered after a failed load was said to have a card",
  );
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

const SESSIONS = {
  "registered before the bundle": registeredBeforeTheBundle,
  "the first rest loads it": theFirstRestLoadsIt,
  "the first rest keeps its time": theFirstRestKeepsItsTime,
  "left during the load": leftDuringTheLoad,
  "pressed during the load": pressedDuringTheLoad,
  "forgotten and disposed before the load": forgottenAndDisposedBeforeTheLoad,
  "a failed load": aFailedLoad,
  "a touch": aTouch,
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
