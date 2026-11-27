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

const {
  FakeElement,
  SERVED_FILES,
  assert,
  catalogLists,
  createPage,
  recorded,
} = require("./link-card-page.js");

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

/** A served file's link, as the Markdown enhancer registers a document's link to it. */
const fileLink = (name, file) => ({
  name,
  href: `/view/${file}`,
  target: { kind: "view", target: { path: file }, localization: "revision" },
});

/**
 * A plain folder's document links each of its files, and a rest on each shows its card: one
 * the page's Quick File catalog leaves out, as it leaves out a hidden, a gitignored, and a
 * symlinked file, opens all the same, so its card says what a listed file's says.
 */
async function unlistedFiles() {
  const page = createPage({ repository: null });
  const links = SERVED_FILES.map((file) =>
    fileLink(catalogLists(file) ? `listed ${file.path}` : `unlisted ${file.path}`, file.path),
  );
  const { anchors } = page.markdown("the README", ...links);
  const cards = {};
  let time = 0;
  for (const link of links) {
    await page.point(time, anchors[link.name]);
    cards[link.name] = await page.look(time + 700);
    await page.point(time + 800, page.body);
    time += 1000;
  }
  const [listed] = links.filter((link) => link.name.startsWith("listed "));
  const where = cards[listed.name]?.split(" | ").slice(1).join(" | ");
  assert(where, `a listed file's card said nothing of where it opens: ${cards[listed.name]}`);
  for (const link of links) {
    assert(
      cards[link.name] === `${link.target.target.path} | ${where}`,
      `${link.name}'s card is not a listed file's: ${cards[link.name]}`,
    );
  }
  return page.log;
}

/** A folder the tree totals after a rest on its link: the next rest says its totals. */
async function folderTotaled() {
  const page = createPage({ repository: null });
  const docs = {
    name: "the docs",
    href: "/view/docs/",
    target: { kind: "view", target: { path: "docs/" }, localization: "revision" },
  };
  const { anchors } = page.markdown("the README", docs);
  await page.point(0, anchors[docs.name]);
  const before = await page.look(700);
  await page.point(800, page.body);
  page.total("docs", { files: 1, bytes: 48 });
  await page.point(1000, anchors[docs.name]);
  const after = await page.look(1700);
  const gained = (after ?? "").split(" | ").filter((line) => !before?.split(" | ").includes(line));
  assert(
    before !== null && gained.length === 1 && after?.startsWith("docs/ | "),
    `the next rest did not say the totals the tree gained: ${before} then ${after}`,
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
  "files the catalog leaves out": unlistedFiles,
  "a folder the tree totals": folderTotaled,
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
