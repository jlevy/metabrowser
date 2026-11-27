// Browserless session for the link card across its boundaries: the exact shell tooltip, the
// exact SDK that registers a link and loads the card, the exact registry, the exact
// providers, and the exact resolver, on one page.
//
// tests/dom/link-previews-session.js holds the card's rules on the module alone, and
// tests/dom/link-preview-providers-session.js the providers' on a stand-in registry. Every
// boundary there is a stand-in, which is how a card that came back after focus moved, an
// answer of nothing kept for the page's life, and an image's tooltip fighting its link's
// card each passed. Here one realm, as one page is, runs them together
// (tests/dom/link-card-page.js says what runs and what is a stand-in): app.js's tooltip and
// its delegated listeners, static/repository-links.js's `enhance` over a pull request's text
// in a KPress host, which registers each link through static/plugin-sdk-views.js, and the
// `link-previews` bundle it loads at the first rest, here at once, whose providers' reads
// replay the server's own answers 40 ms later on this file's clock.
// tests/dom/link-preview-loader-session.js holds what that first rest's load does.
//
// It prints, for each step, what the reader would see; tests/test_link_card_integration_session.py
// holds its invariants, and this file exits 1 on a failed one, naming each session that
// failed. Name sessions on the command line to run only those.

const { FakeElement, assert, createPage, recorded } = require("./link-card-page.js");

const CANONICAL = "https://github.com/octo/demo";
const BADGE = "https://img.example/badge.svg";

// ── The sessions ───────────────────────────────────────────────────

const TITLES = Object.fromEntries(
  Object.entries(recorded)
    .filter(([name]) => name.startsWith("pulls?q="))
    .flatMap(([, answer]) => answer.body.rows.map((row) => [row.number, row.title])),
);
const pullLink = (number) => [`#${number}`, `${CANONICAL}/pull/${number}`];

/** A rest on a link to a pull request: its card, with the title its catalog row gives. */
async function rest() {
  const page = createPage();
  const { anchors } = page.text(pullLink(12));
  await page.point(0, anchors["#12"]);
  await page.look(299);
  const seen = await page.look(320);
  assert(
    seen?.includes(TITLES[12]) && page.log.at(-1).on === "#12",
    `a rest did not show the card with its title on time: ${seen}`,
  );
  await page.point(700, page.body);
  await page.look(900);
  assert(page.log.at(-1).sees === null, "the card stayed after the pointer left");
  return page.log;
}

/** Straight from one link's card onto the next: the next link's card, on the next link. */
async function handover() {
  const page = createPage();
  const { anchors } = page.text(pullLink(12), pullLink(13));
  await page.point(0, anchors["#12"]);
  await page.look(700);
  await page.point(720, anchors["#13"]);
  const seen = await page.look(1100);
  assert(
    seen?.includes(TITLES[13]) && page.log.at(-1).on === "#13",
    `straight from #12 onto #13, the card shown was not #13's: ${seen}`,
  );
  return page.log;
}

/** Focus moves onto the link while its read is out: the card does not come back. */
async function focusDuringRead() {
  const page = createPage();
  const { anchors } = page.text(pullLink(14));
  await page.point(0, anchors["#14"]);
  await page.focus(260, anchors["#14"]);
  await page.look(280);
  await page.look(700);
  const after = page.log.slice(page.log.findIndex((entry) => entry.focus));
  assert(
    page.log.some((entry) => entry.read?.startsWith("github/pulls?q=14")),
    "the rest asked for nothing before focus moved",
  );
  assert(!after.some((entry) => entry.sees), "a card came back after focus moved");
  return page.log;
}

/** A read that fails is read again at the next rest, which then says the title. */
async function retry() {
  const page = createPage();
  const { anchors } = page.text(pullLink(15));
  page.fail("pulls?q=15");
  await page.point(0, anchors["#15"]);
  const first = await page.look(700);
  await page.point(800, page.body);
  await page.point(1000, anchors["#15"]);
  const second = await page.look(1700);
  assert(first !== null && !first.includes(TITLES[15]), `a failed read gave a title: ${first}`);
  assert(second?.includes(TITLES[15]), `the next rest did not read again: ${second}`);
  return page.log;
}

/** A file the served tree gains after a rest that found it missing is not missing after. */
async function staleFile() {
  const page = createPage();
  const { anchors } = page.text(["the old guide", `${CANONICAL}/blob/main/docs/old-guide.md`]);
  await page.point(0, anchors["the old guide"]);
  const before = await page.look(700);
  await page.point(800, page.body);
  page.serve(["README.md", "docs/guide.md", "docs/old-guide.md"]);
  await page.point(1000, anchors["the old guide"]);
  const after = await page.look(1700);
  assert(before?.endsWith("Not in the served files"), `the missing file was not said: ${before}`);
  // A link to the served branch's file, which opens in the served working tree.
  assert(
    after?.endsWith(page.opens()["working-tree"]) && !after.includes("Not in the served files"),
    `a file the tree gained was still called missing: ${after}`,
  );
  return page.log;
}

/**
 * An image the page did not load inside a link with a card: the pointer rests on the link's
 * words, crosses onto the image's chip and back, and the card, which says the image's
 * address, is the one tooltip the whole time. The chip's own tooltip is the shell's
 * (`tipTextAnchor` in app.js, which shows a chip's in rendered text).
 */
async function imageInLink() {
  const page = createPage();
  const chip = new FakeElement("span", "the badge's chip", {
    class: "mb-image-fallback",
    "data-tip-text": BADGE,
  });
  chip.append("build passing");
  const words = new FakeElement("span", "the link's words");
  words.append("the build ");
  const { anchors } = page.text(["#12", `${CANONICAL}/pull/12`, [words, chip]]);
  const link = anchors["#12"];
  await page.point(0, words);
  const seen = [await page.look(400)];
  await page.point(450, chip);
  seen.push(await page.look(800));
  await page.point(850, words);
  seen.push(await page.look(1200));
  assert(
    seen.every((card) => card?.includes(`Image from ${BADGE}`) && card.includes(TITLES[12])),
    `the card was not the one tooltip over the link and its image: ${JSON.stringify(seen)}`,
  );
  assert(
    page.log.filter((entry) => entry.sees).every((entry) => entry.on === link.name),
    "a tooltip was placed on something other than the link",
  );
  assert(chip.getAttribute("data-tip-text") === null, "the chip kept a tooltip of its own");
  return page.log;
}

/** A link to another site: one line saying where it goes, in a new tab as the text opens it. */
async function outside() {
  const page = createPage();
  const { anchors } = page.text(["elsewhere", "https://example.com/elsewhere"]);
  await page.point(0, anchors.elsewhere);
  const seen = await page.look(320);
  assert(seen === "Opens example.com in a new tab", `an outside link's card said ${seen}`);
  assert(!page.log.some((entry) => entry.read), "a rest on an outside link read something");
  return page.log;
}

const SESSIONS = {
  rest,
  handover,
  "focus during the read": focusDuringRead,
  "a failed read, then the next rest": retry,
  "a file the tree gains": staleFile,
  "an image inside a link": imageInLink,
  "a link to another site": outside,
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
