// The link card in headless Chrome on a document a live `metab` server renders: Chrome's own
// pointer rests on each of its links, and its own keys move focus onto them.
//
//   CHROME_BIN=... CHROME_PROFILES=<dir> \
//     node tests/dom/link-card-chrome.mjs <the document's URL> <what its cards say, as JSON>
//
// tests/test_link_card_chrome.py serves the GitHub stand-in's checkout, writes the document,
// says what its cards say, and owns the profile directory, and stops this process's whole
// group, Chrome included, however the run ends (tests/process_group.py).
//
// For each in-app link, two rests, with the pointer on empty space between until the
// tooltip's fade has ended:
//
// 1. The time from the pointer's arrival on the link to the card's appearance, in the page's
//    own clock, within a window the two timers give it: the tooltip's appear delay
//    (TOOLTIP_APPEAR_DELAY in static/app.js) and the card's intent delay (INTENT_MS in
//    static/link-previews.js), both read from the page. The card comes on the appear delay
//    from the pointer's arrival, whatever the rest finds meanwhile: a rest that finds what
//    to say at the intent delay asks the tooltip again, which takes the newer card and keeps
//    its time, so every rest comes before a show at the intent delay could.
// 2. What the card says: what the link opens in `.tip-name`, its title once the page has read
//    it, the author's title, and "Opens here in Metabrowser" last, never the link's own words.
// 3. Where it is: centered below its link, or above it where there is no room, and nowhere
//    else when the pointer moves within the link.
// 4. That moving the pointer away puts it away.
//
// Before the catalog holds the pull request, a rest on its link, whose card has no title
// yet, and which a later rest gains, since the card keeps no answer of nothing. Then that an
// outside link's card says where it goes (OUTSIDE_LINK_CARD), that a Tab puts a card away, and that focus brought by Tab and Shift-Tab shows none; and, last, that moving the
// pointer straight from one link to the next shows the next link's card, on its link, in
// the same window, which the shell's bug H1 broke (KNOWN_BUG_H1). Throughout, no link with
// a card carries a native `title`, and the page throws nothing, logs no error, and has no
// request fail. The rules behind each run browserlessly in
// tests/dom/link-previews-session.js and tests/dom/tooltip-anchor-session.js.
//
// Each step writes `phase <name> <ms since start>` to stderr, and each rest its time.
import { launchChrome } from "./chrome-session.mjs";

const [url, said] = process.argv.slice(2);
if (!url || !said || !process.env.CHROME_BIN || !process.env.CHROME_PROFILES) {
  throw new Error("usage: CHROME_BIN CHROME_PROFILES link-card-chrome.mjs <URL> <JSON>");
}
/**
 * @type {{
 *   pull: number, pullTitle: string, pullState: string,
 *   commit: string, commitSubject: string, authorTitle: string,
 * }}
 */
const expected = JSON.parse(said);
const started = Date.now();
const phase = (name) => process.stderr.write(`phase ${name} ${Date.now() - started}\n`);
// Each wait's bound: the page's load, its links' enhancement, or the stand-in catalog's
// first fill through the fake gh, which the Pulls tab asks for as the page loads and which
// took about a second on an idle Linux container.
const STEP_MS = 15000;
// The words every in-app link's card ends with (docs/design-system.md, "Tooltips on Links").
const OPENS_HERE = "Opens here in Metabrowser";
// The list's identity (docs/design-system.md, "Tooltips on Links").
const PULLS = "Pull requests";
// Chrome's own request for the page's icon, which the app does not name
// (docs/design-system-icons.md, "Known Departures").
const BROWSERS_OWN = new Set(["/favicon.ico"]);
// The document's link to another site, whose card is one line saying where it goes, as the
// card's own renderer draws it for that address and for whether the link opens a new tab
// (`card` in static/link-previews.js, read in the page as OUTSIDE_LINK_CARD below).
const OUTSIDE_LINK = { text: "Another site", url: "https://example.com/elsewhere" };
// The shell's bug H1: a pointer that moved straight from one link with a card to another
// within the tooltip's fade left the first link's card showing. static/app.js fixed it
// (`tooltipShown`), so this is false and the step that moves so checks the second link's
// card; true makes that step record what shows and check nothing. Every other step leaves
// the pointer on empty space until the fade has ended.
const KNOWN_BUG_H1 = false;

const failures = [];
let checks = 0;
const check = (label, ok, detail = "") => {
  checks += 1;
  if (!ok) {
    const failure = `${label}${detail ? `: ${detail}` : ""}`;
    failures.push(failure);
    // As it happens, so a run that stops later still says what failed before.
    process.stderr.write(`failed ${failure}\n`);
  }
};
const fold = (text) =>
  String(text ?? "")
    .replace(/\s+/g, " ")
    .trim()
    .toLowerCase();
const pause = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

// In the page: a record of one link's rest, kept from the document's own capture listeners
// and the tooltip's class, each time in the page's clock. `reset` names the link a rest is
// on, by its words.
const PROBE = `(() => {
  const tip = document.querySelector(".custom-tooltip");
  const probe = {
    link: null, arrived: null, left: null, shown: null, hidden: null, ups: 0,
    find(text) {
      return [...document.querySelectorAll("#preview-pane a")].find((a) => a.textContent.trim() === text) ?? null;
    },
    reset(text) {
      this.link = this.find(text);
      this.arrived = this.left = this.shown = this.hidden = null;
      this.ups = 0;
      return this.link !== null;
    },
  };
  document.addEventListener("pointerover", (event) => {
    if (probe.link?.contains(event.target) && probe.arrived === null) probe.arrived = performance.now();
  }, true);
  document.addEventListener("pointerout", (event) => {
    if (probe.link?.contains(event.target) && !probe.link.contains(event.relatedTarget) && probe.left === null) {
      probe.left = performance.now();
    }
  }, true);
  let up = tip.classList.contains("visible");
  new MutationObserver(() => {
    const now = tip.classList.contains("visible");
    if (now === up) return;
    up = now;
    if (now) {
      probe.ups += 1;
      probe.shown ??= performance.now();
    } else if (probe.shown !== null) {
      probe.hidden ??= performance.now();
    }
  }).observe(tip, { attributes: true, attributeFilter: ["class"] });
  window.__linkCardProbe = probe;
  return true;
})()`;

// In the page: the rest's record, the card's lines and mark, and the boxes of the card and
// its link.
const READ = `(() => {
  const probe = window.__linkCardProbe;
  const tip = document.querySelector(".custom-tooltip");
  const box = (r) => ({ left: r.left, right: r.right, top: r.top, bottom: r.bottom, width: r.width, height: r.height });
  return {
    arrived: probe.arrived, left: probe.left, shown: probe.shown, hidden: probe.hidden, ups: probe.ups,
    up: tip.classList.contains("visible") && tip.style.display === "block",
    html: tip.innerHTML,
    lines: [...tip.children].map((line) => ({ classes: [...line.classList], text: line.textContent.replace(/\\s+/g, " ").trim() })),
    state: tip.querySelector(".link-card-mark [data-state]")?.getAttribute("data-state") ?? null,
    tip: box(tip.getBoundingClientRect()),
    link: box(probe.link.getBoundingClientRect()),
    viewport: { width: innerWidth, height: innerHeight },
    text: probe.link.textContent,
    href: probe.link.getAttribute("href"),
    focused: document.activeElement === probe.link,
  };
})()`;

// In the page: every link of the document that opens a page here, and those that carry a
// native `title`, on themselves, an ancestor, or anything inside them.
const TITLES = `(() => {
  const links = [...document.querySelectorAll("#preview-pane a[href^='/']")];
  return {
    links: links.map((a) => a.textContent.trim()),
    titled: links.filter((a) => a.closest("[title]") !== null || a.querySelector("[title], title") !== null).map((a) => a.textContent.trim()),
  };
})()`;

const chrome = await launchChrome(process.env.CHROME_BIN, {
  profiles: process.env.CHROME_PROFILES,
  width: 1280,
  height: 800,
});
try {
  phase("chrome");
  const { evaluate, send } = chrome;
  // Whatever the page threw, logged as an error, or failed to fetch, and the module's own
  // warnings when a read or a prefetch fails.
  const problems = [];
  chrome.on("Runtime.exceptionThrown", ({ exceptionDetails }) =>
    problems.push(`threw ${exceptionDetails.exception?.description ?? exceptionDetails.text}`),
  );
  chrome.on("Runtime.consoleAPICalled", ({ type, args }) => {
    const text = args.map((arg) => arg.value ?? arg.description ?? "").join(" ");
    if (type === "error" || type === "assert" || text.startsWith("metabrowser:")) {
      problems.push(`console.${type} ${text.slice(0, 400)}`);
    }
  });
  const addresses = new Map();
  const browsersOwn = (address) => BROWSERS_OWN.has(new URL(address).pathname);
  chrome.on("Network.requestWillBeSent", ({ requestId, request }) =>
    addresses.set(requestId, request.url),
  );
  chrome.on("Network.responseReceived", ({ response }) => {
    if (response.status >= 400 && !browsersOwn(response.url)) {
      problems.push(`${response.status} ${response.url}`);
    }
  });
  chrome.on("Network.loadingFailed", ({ requestId, errorText }) => {
    const address = addresses.get(requestId) ?? requestId;
    problems.push(`failed ${address}: ${errorText}`);
  });
  chrome.on("Log.entryAdded", ({ entry }) => {
    if (entry.level === "error" && !(entry.url && browsersOwn(entry.url))) {
      problems.push(`log ${entry.text} ${entry.url ?? ""}`.trim());
    }
  });
  for (const domain of ["Runtime", "Page", "Network", "Log"]) {
    await send(`${domain}.enable`);
  }
  const waitFor = async (expression, what, timeoutMs = STEP_MS) => {
    try {
      return await chrome.waitFor(expression, timeoutMs);
    } catch (error) {
      throw new Error(`${what}: ${error.message}\nproblems: ${problems.join("\n")}`);
    }
  };
  const frames = () =>
    evaluate("new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)))");
  /** Chrome's own pointer, moved to (*x*, *y*) in the viewport. */
  const pointAt = (x, y) => send("Input.dispatchMouseEvent", { type: "mouseMoved", x, y });
  /** A real key, as the keyboard sends it, to the focused element. */
  const press = async (key, { code = key, keyCode = 0, modifiers = 0 } = {}) => {
    await send("Input.dispatchKeyEvent", {
      type: "rawKeyDown",
      key,
      code,
      modifiers,
      windowsVirtualKeyCode: keyCode,
    });
    await send("Input.dispatchKeyEvent", {
      type: "keyUp",
      key,
      code,
      modifiers,
      windowsVirtualKeyCode: keyCode,
    });
    await frames();
  };
  const tab = (shift = false) =>
    press("Tab", { code: "Tab", keyCode: 9, modifiers: shift ? 8 : 0 });

  const loaded = new Promise((resolve) => chrome.on("Page.loadEventFired", resolve));
  await send("Page.navigate", { url });
  await loaded;
  phase("load");
  // The document's links, enhanced: each github.com link the page opens here has its
  // address, and the card's registry and the Commits panel, which reads a commit's subject,
  // have loaded.
  await waitFor(
    `document.querySelectorAll('#preview-pane a[href="/pull/${expected.pull}"]').length === 2 &&
      document.querySelector('#preview-pane a[href="/commit/${expected.commit}"]') !== null &&
      document.querySelector('#preview-pane a[href="/pulls"]') !== null &&
      typeof window.MetabrowserLinkPreviews?.INTENT_MS === "number" &&
      typeof window.MetabrowserGitPanel?.commitSummary === "function"`,
    "the document's links and the card",
  );
  phase("enhanced");

  const constants = await evaluate(`({
    appear: window.TOOLTIP_APPEAR_DELAY,
    fade: window.TOOLTIP_FADE_OUT,
    gap: window.TOOLTIP_ANCHOR_GAP,
    margin: window.TOOLTIP_VIEWPORT_MARGIN,
    intent: window.MetabrowserLinkPreviews.INTENT_MS,
  })`);
  const { appear: APPEAR, fade: FADE, gap: GAP, margin: MARGIN, intent: INTENT } = constants;
  process.stderr.write(
    `constants INTENT_MS ${INTENT} TOOLTIP_APPEAR_DELAY ${APPEAR} TOOLTIP_FADE_OUT ${FADE}\n`,
  );
  check(
    "the page's timers are numbers",
    [APPEAR, FADE, GAP, MARGIN, INTENT].every(Number.isFinite),
    JSON.stringify(constants),
  );
  // The windows below hold while the intent delay ends inside the appear delay, as the
  // design has it: the card is asked for again before the tooltip would have appeared.
  check(
    "the intent delay ends inside the appear delay",
    INTENT < APPEAR,
    JSON.stringify(constants),
  );
  // Where every rest's card comes up: on the appear delay from the pointer's arrival,
  // whatever its provider does meanwhile, and sooner than a show at the intent delay could
  // bring one. A provider that answers at once (a file's, a folder's, the list's) answers at
  // the intent delay, inside the appear delay, and the tooltip takes the newer card and keeps
  // its time; one that reads the server answers then or later, when the card comes with what
  // the page knew; and where the page knows what the card says, nothing is read.
  const WINDOW = [APPEAR, INTENT + APPEAR];
  // By then any card a rest or a focus would bring is up, even one first asked for at the
  // intent delay, with an appear delay to spare: what a step that shows none waits.
  const CARD_BY_MS = INTENT + 2 * APPEAR;
  // How long a step waits for a card, or for one to go, past when it should have: long
  // enough that a late one is reported with its time rather than as none.
  const LATE_MS = 2 * CARD_BY_MS;

  await evaluate(PROBE);
  // Where the pointer waits between rests: the pane's empty margin, on no link and no tip.
  const park = await evaluate(`(() => {
    const pane = document.getElementById("preview-pane").getBoundingClientRect();
    const x = Math.round(pane.right - 60);
    const y = Math.round(pane.top + pane.height / 2);
    const there = document.elementFromPoint(x, y);
    return { x, y, clear: there !== null && there.closest("a, [data-tip-text]") === null };
  })()`);
  check("the pointer waits on no link and no tip", park.clear, JSON.stringify(park));
  const away = async () => {
    await pointAt(park.x, park.y);
    await waitFor(
      `document.querySelector(".custom-tooltip").style.display !== "block"`,
      "the card is away",
    );
  };

  const titles = await evaluate(TITLES);
  check(
    "no link with a card carries a native title",
    titles.titled.length === 0,
    JSON.stringify(titles),
  );

  /** The point *at* of the way across *text*'s link, on its first line. */
  const across = (text, at) =>
    evaluate(`(() => {
      const link = window.__linkCardProbe.find(${JSON.stringify(text)});
      const line = link?.getClientRects()[0];
      return line ? { x: line.left + line.width * ${at}, y: line.top + line.height / 2 } : null;
    })()`);
  /** The pointer rests on *text*'s link: its card as it first comes up, or with none. */
  const rest = async (text) => {
    await away();
    await evaluate(`window.__linkCardProbe.reset(${JSON.stringify(text)})`);
    const point = await across(text, 0.5);
    if (point === null) {
      return null;
    }
    await pointAt(point.x, point.y);
    await chrome.waitFor(`window.__linkCardProbe.shown !== null`, LATE_MS).catch(() => {});
    return evaluate(READ);
  };

  // A rest on the pull request before its catalog is known to hold it, as soon as the page
  // has its links: a card with no title, unless the catalog filled first. The card keeps no
  // answer, a provider keeps none of a catalog not yet whole, and so the rests below, once
  // the catalog holds the pull request, say its title (review H4).
  const early = await rest(`Pull request ${expected.pull}`);
  process.stderr.write(
    `a rest before the catalog was known to hold #${expected.pull}: ` +
      `${early?.lines.map((line) => line.text).join(" | ") ?? "no card"}\n`,
  );
  await away();
  // The catalog holds the pull request, as it does once the page's first refresh is in.
  await waitFor(
    `(async () => {
      await new Promise((resolve) => setTimeout(resolve, 100));
      const answer = await (await fetch("/api/plugin/github/pulls?q=${expected.pull}")).json();
      return (answer.rows ?? []).some((row) => row.number === ${expected.pull} && row.title);
    })()`,
    "the catalog holds the pull request",
  );
  phase("ready");

  /** The card is where its link is: centered on it, below, or above without room below. */
  const placed = (label, card) => {
    const { tip, link, viewport } = card;
    const room = link.bottom + GAP + tip.height <= viewport.height - MARGIN;
    const vertical = room
      ? Math.abs(tip.top - (link.bottom + GAP)) <= 1
      : Math.abs(tip.bottom - (link.top - GAP)) <= 1;
    const centered = Math.abs((tip.left + tip.right) / 2 - (link.left + link.right) / 2) <= 1;
    const clamped =
      Math.abs(tip.left - MARGIN) <= 1 || Math.abs(tip.right - (viewport.width - MARGIN)) <= 1;
    check(
      `${label}: the card is ${room ? "below" : "above"} its link, centered on it`,
      vertical && (centered || clamped),
      JSON.stringify({ tip, link, viewport }),
    );
    return room ? "below" : "above";
  };

  /** What every card says: its identity first, where it opens last, never its link's words. */
  const says = (label, card, link) => {
    const lines = card.lines;
    const first = lines[0];
    const last = lines[lines.length - 1];
    const detail = JSON.stringify(lines);
    check(
      `${label}: its first line is the card's name`,
      first?.classes.includes("tip-name"),
      detail,
    );
    check(
      `${label}: it names what the link opens`,
      link.identity(first?.text ?? "", card),
      `${card.href} ${detail}`,
    );
    check(
      `${label}: its last line says it opens here`,
      last?.classes.includes("tip-detail") && last.text === OPENS_HERE,
      detail,
    );
    check(
      `${label}: no line says the link's own words`,
      lines.every((line) => fold(line.text) !== fold(card.text)),
      `${JSON.stringify(card.text)} ${detail}`,
    );
  };

  // A file's or folder's card names the path its link's address opens.
  const VIEW = "/view/";
  const viewPath = (name, card) =>
    card.href.startsWith(VIEW) && name === decodeURIComponent(card.href.slice(VIEW.length));
  const shortOf = (name) => {
    const match = /^Commit ([0-9a-f]+)$/.exec(name);
    return match !== null && match[1].length >= 7 && expected.commit.startsWith(match[1]);
  };
  // The document's in-app links, by their words, in its order: what each card names, the
  // lines its data gives by the second rest, and the window of its first rest.
  const links = [
    {
      text: "The guide",
      identity: viewPath,
      // The author's own words, quoted as theirs, after the path the app names.
      lines: [`“${expected.authorTitle}”`],
      first: "at once",
    },
    {
      text: "The source folder",
      identity: (name, card) => name.endsWith("/") && viewPath(name, card),
      lines: [],
      first: "at once",
    },
    {
      text: `Pull request ${expected.pull}`,
      identity: (name) => name === `Pull request #${expected.pull}`,
      lines: [expected.pullTitle],
      state: expected.pullState,
      first: "read",
    },
    {
      // Its words are the title the card would say, so the card leaves the title out.
      text: expected.pullTitle,
      identity: (name) => name === `Pull request #${expected.pull}`,
      lines: [],
      state: expected.pullState,
      first: "known",
    },
    {
      text: "The head commit",
      identity: shortOf,
      lines: [expected.commitSubject],
      first: "read",
    },
    {
      text: "The pull requests",
      identity: (name) => name === PULLS,
      lines: [],
      first: "at once",
    },
    {
      text: "the guide again",
      identity: viewPath,
      lines: [],
      first: "known",
      foot: true,
    },
  ];
  // The link beside the last, which the pointer reaches only at the end, straight from it,
  // so that its card is not yet known then (KNOWN_BUG_H1).
  const straightTo = "the readme";
  check(
    "every link of the document that opens a page here is rested on",
    JSON.stringify([...titles.links].sort()) ===
      JSON.stringify([...links.map((link) => link.text), straightTo].sort()),
    JSON.stringify(titles.links),
  );
  const placements = new Set();
  for (const link of links) {
    if (link.foot) {
      // At the pane's foot, where the card has no room below its link.
      await away();
      await evaluate(
        `window.__linkCardProbe.find(${JSON.stringify(link.text)})?.scrollIntoView({ block: "end" })`,
      );
      await frames();
    }
    const cards = [];
    for (const [round, kind] of [
      [1, link.first],
      [2, "known"],
    ]) {
      const label = `${JSON.stringify(link.text)}, rest ${round}`;
      const card = await rest(link.text);
      if (card === null || card.shown === null) {
        check(`${label}: its card comes up`, false, JSON.stringify(card));
        break;
      }
      const delay = card.shown - card.arrived;
      const [low, high] = WINDOW;
      const where = placed(label, card);
      placements.add(where);
      process.stderr.write(
        `rest ${label}: up ${Math.round(delay)} ms after the pointer arrived, ` +
          `window [${low}, ${high}) for a card ${kind === "read" ? "that reads" : kind}; ` +
          `${where}: ${card.lines.map((line) => line.text).join(" | ")}\n`,
      );
      check(`${label}: the pointer arrived on the link`, card.arrived !== null);
      check(
        `${label}: up in [${low}, ${high}) ms`,
        delay >= low && delay < high,
        `${Math.round(delay)} ms`,
      );
      says(label, card, link);
      if (round === 1) {
        // The pointer moves within the link: the card stays as and where it is.
        for (const at of [0.1, 0.9]) {
          const point = await across(link.text, at);
          await pointAt(point.x, point.y);
        }
        await pause(APPEAR);
        await frames();
        const still = await evaluate(READ);
        check(
          `${label}: the card holds still while the pointer moves within the link`,
          still.up &&
            still.ups === 1 &&
            JSON.stringify(still.tip) === JSON.stringify(card.tip) &&
            still.html === card.html,
          JSON.stringify({ before: card.tip, after: still.tip, ups: still.ups }),
        );
      }
      cards.push(card);
      // The pointer leaves: the card goes as it leaves, not on a timer.
      await pointAt(park.x, park.y);
      await chrome.waitFor(`window.__linkCardProbe.hidden !== null`, LATE_MS).catch(() => {});
      const gone = await evaluate(READ);
      check(
        `${label}: moving away puts the card away`,
        gone.left !== null && gone.hidden !== null && gone.hidden - gone.left < FADE,
        JSON.stringify({ left: gone.left, hidden: gone.hidden }),
      );
      await away();
    }
    const last = cards[cards.length - 1];
    if (last !== undefined) {
      const label = `${JSON.stringify(link.text)}, by its last rest`;
      for (const line of link.lines) {
        check(
          `${label}: it says ${JSON.stringify(line)}`,
          last.lines.some((said) => said.text === line),
          JSON.stringify(last.lines),
        );
      }
      if (link.state !== undefined) {
        check(`${label}: its mark is its ${link.state} state's`, last.state === link.state);
      }
      if (link.foot) {
        check(`${label}: its card had no room below`, placed(label, last) === "above");
      }
    }
    phase(`rests on ${JSON.stringify(link.text)}`);
  }
  check(
    "cards are placed both below and above their links",
    placements.has("below") && placements.has("above"),
    JSON.stringify([...placements]),
  );

  // An outside link, back in view: the pointer rests as long as any card would take, and
  // its card is OUTSIDE_LINK_CARD, the renderer's own lines for its address and its tab.
  await away();
  await evaluate(`(() => {
    window.__linkCardProbe.reset(${JSON.stringify(OUTSIDE_LINK.text)});
    window.__linkCardProbe.link.scrollIntoView({ block: "center" });
  })()`);
  await frames();
  const OUTSIDE_LINK_CARD = await evaluate(`(() => {
    const previews = window.MetabrowserLinkPreviews;
    const link = window.__linkCardProbe.link;
    const html = previews.card(
      previews.subject({ kind: "external", url: ${JSON.stringify(OUTSIDE_LINK.url)} }),
      null,
      { linkText: link.textContent, newTab: link.getAttribute("target") === "_blank" },
    );
    const box = document.createElement("div");
    box.innerHTML = html;
    return [...box.children].map((line) => line.textContent.replace(/\\s+/g, " ").trim());
  })()`);
  check(
    "the renderer's card for the outside link is one line naming its host",
    OUTSIDE_LINK_CARD.length === 1 && OUTSIDE_LINK_CARD[0].startsWith("Opens example.com"),
    JSON.stringify(OUTSIDE_LINK_CARD),
  );
  const outside = await across(OUTSIDE_LINK.text, 0.5);
  if (outside !== null) {
    await pointAt(outside.x, outside.y);
    await pause(CARD_BY_MS);
    await frames();
  }
  const outsideRest = outside === null ? null : await evaluate(READ);
  const outsideSays = outsideRest?.up ? outsideRest.lines.map((line) => line.text) : [];
  check(
    `an outside link's card says ${JSON.stringify(OUTSIDE_LINK_CARD)}`,
    outsideRest !== null &&
      outsideRest.arrived !== null &&
      outsideRest.ups === 1 &&
      JSON.stringify(outsideSays) === JSON.stringify(OUTSIDE_LINK_CARD),
    JSON.stringify({ arrived: outsideRest?.arrived, ups: outsideRest?.ups, says: outsideSays }),
  );
  phase("an outside link");

  // Focus. A Tab while a card is up puts it away, and none comes back; then focus brought
  // onto each link by Tab, and Shift-Tab, shows none, with the pointer away.
  const [firstLink, secondLink] = links;
  await away();
  await evaluate(`window.__linkCardProbe.find(${JSON.stringify(secondLink.text)}).focus()`);
  const upBefore = await rest("The pull requests");
  check("a card is up before the Tab", upBefore?.up === true);
  await evaluate(`window.__linkCardProbe.reset(${JSON.stringify(firstLink.text)})`);
  await tab(true);
  await pause(CARD_BY_MS);
  await frames();
  const afterTab = await evaluate(READ);
  check(
    "Shift-Tab, with a card up, moves focus and puts the card away",
    afterTab.focused && !afterTab.up && afterTab.ups === 0,
    JSON.stringify({ focused: afterTab.focused, up: afterTab.up, ups: afterTab.ups }),
  );
  await away();
  // In the document's order from the first link, with Tab: the rest of the list, the
  // outside link, and the two links at the foot.
  const order = [
    ...links.slice(1, -1).map((link) => link.text),
    "Another site",
    links.at(-1).text,
    straightTo,
  ];
  for (const text of order) {
    await evaluate(`window.__linkCardProbe.reset(${JSON.stringify(text)})`);
    await tab();
    await pause(CARD_BY_MS);
    await frames();
    const focused = await evaluate(READ);
    check(
      `Tab onto ${JSON.stringify(text)}: focus is on it and it shows no card`,
      focused.focused && focused.ups === 0 && !focused.up,
      JSON.stringify({ focused: focused.focused, ups: focused.ups }),
    );
  }
  phase("focus");

  // H1: straight from one link's card onto the next link, within the fade. The pointer rests
  // on the foot's file link until its card is up, then moves in one step onto the README
  // beside it, whose card the page does not know yet, and what shows is read once any card
  // would be up: the README's card, on its link, up in the window every rest's comes in.
  // Last, so that what it leaves cannot touch another step.
  const straightFrom = links.at(-1).text;
  await away();
  await evaluate(
    `window.__linkCardProbe.find(${JSON.stringify(straightFrom)}).scrollIntoView({ block: "center" })`,
  );
  await frames();
  const before = await rest(straightFrom);
  check(`H1: ${JSON.stringify(straightFrom)}'s card is up before the move`, before?.up === true);
  await evaluate(`window.__linkCardProbe.reset(${JSON.stringify(straightTo)})`);
  const onto = await across(straightTo, 0.5);
  if (before !== null && onto !== null) {
    await pointAt(onto.x, onto.y);
    await pause(CARD_BY_MS);
    await frames();
    const after = await evaluate(READ);
    /** Whether *tip* is placed on *link*, below or above it, centered. */
    const on = (tip, link) =>
      Math.abs((tip.left + tip.right) / 2 - (link.left + link.right) / 2) <= 1 &&
      (Math.abs(tip.top - (link.bottom + GAP)) <= 1 ||
        Math.abs(tip.bottom - (link.top - GAP)) <= 1);
    let placedOn = "neither link";
    if (on(after.tip, after.link)) {
      placedOn = JSON.stringify(straightTo);
    } else if (on(after.tip, before.link)) {
      placedOn = JSON.stringify(straightFrom);
    }
    const shownAt =
      after.shown === null ? "never" : `${Math.round(after.shown - after.arrived)} ms`;
    process.stderr.write(
      `H1 (static/app.js): straight from ${JSON.stringify(straightFrom)} to ` +
        `${JSON.stringify(straightTo)}: ${CARD_BY_MS} ms after the move ` +
        `${after.up ? "a card is up" : "no card is up"}, placed on ${placedOn}, saying ` +
        `${after.lines.map((line) => line.text).join(" | ") || "nothing"}; it came up ` +
        `${shownAt} after the pointer arrived, window [${WINDOW[0]}, ${WINDOW[1]}); ` +
        `${KNOWN_BUG_H1 ? "recorded, not checked" : "checked"}\n`,
    );
    if (!KNOWN_BUG_H1) {
      const label = `straight from ${JSON.stringify(straightFrom)} to ${JSON.stringify(straightTo)}`;
      check(
        `${label}: the README's card is up, on its link`,
        after.up &&
          viewPath(after.lines[0]?.text ?? "", after) &&
          placedOn === JSON.stringify(straightTo),
        JSON.stringify(after.lines),
      );
      const delay = after.shown === null ? Number.NaN : after.shown - after.arrived;
      check(
        `${label}: up in [${WINDOW[0]}, ${WINDOW[1]}) ms`,
        after.arrived !== null && delay >= WINDOW[0] && delay < WINDOW[1],
        shownAt,
      );
    }
    await pointAt(park.x, park.y);
    const left = await chrome
      .waitFor(`document.querySelector(".custom-tooltip").style.display !== "block"`, LATE_MS)
      .catch(() => false);
    check("after the straight move, moving away puts the card away", left === true);
  }
  phase("straight from one link to the next");

  const titlesAfter = await evaluate(TITLES);
  check(
    "after every rest, no link with a card carries a native title",
    titlesAfter.titled.length === 0,
    JSON.stringify(titlesAfter),
  );
  check(
    "no page error, console error, or failed request",
    problems.length === 0,
    problems.join("\n"),
  );
} finally {
  await chrome.close();
}
if (failures.length > 0) {
  process.stderr.write(`${failures.join("\n")}\n`);
  process.exit(1);
}
process.stdout.write(`link card in Chrome: ${checks} checks passed\n`);
