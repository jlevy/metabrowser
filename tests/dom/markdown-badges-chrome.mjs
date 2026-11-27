// A README's badge row drawn in headless Chrome against a live `metab`, as github.com draws
// it: badges on one line, each going where its author sent it, and no mark after a link
// that holds only an image. Trusted, `--untrusted`, and `--untrusted` after the reader
// ticks "Block remote images" in the Metabrowser menu.
//
// Usage: node markdown-badges-chrome.mjs METAB ROOT PORT STATE_DIR, with CHROME_BIN set,
// and CHROME_PROFILES naming where Chrome's profile goes (tests/dom/chrome-session.mjs).
// tests/test_markdown_badges_chrome.py copies tests/fixtures/badges to ROOT: a README of
// five badges, which this session answers from Chrome's own network layer (the DevTools
// `Fetch` domain), so no request leaves the machine and each one is counted: four over
// https, three of them in links, and one over http.
//
// Under each profile it checks, in the document as the reader sees it:
//
// - the badges lie on one line, left to right, none over another, each as high as the
//   others (a link wrapping under its siblings, as the GitHub mark did, is a failure);
// - each badge is in a link to its author's destination, and no link is empty or holds
//   a second one, whatever draws it: an image, or the fallback chip;
// - no mark follows a link that holds only an image, the GitHub link included, and the
//   link with words of its own is marked as before;
// - trusted: every image loads. Untrusted: the https images load, with no `Referer`
//   sent, under a policy that admits https images, and the http one is the fallback
//   chip in its link, with the address it stands for in its tooltip;
// - the page's response says `Referrer-Policy: no-referrer`, and an image a Mermaid
//   diagram in the README names, which the allowlist never wrote, is asked for with no
//   Referer (the README's last block is a diagram whose image shape names one);
// - the box is drawn disabled and the menu's opening, which loads its wiring, enables it;
// - blocked: the box is ticked, no request leaves the page, no image is drawn, every badge
//   is its chip in the same link, the unlinked ones in a link to their image, and the
//   policy is the narrow one, which the browser enforces: a console probe of an image
//   from the web is refused, and hovering a chip shows its image's address in the app's
//   one tooltip, its link's card ("Image from" the address); unticked again, the images,
//   the diagram's too, are back.
//
// Each step writes `phase <name> <ms since start>` to stderr. It prints
// `markdown badges in Chrome: <n> checks passed`, or the failures and exits 1.
import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { launchChrome } from "./chrome-session.mjs";

const [metab, root, port, state] = process.argv.slice(2);
if (!metab || !root || !port || !state || !process.env.CHROME_BIN) {
  throw new Error(
    "usage: CHROME_BIN CHROME_PROFILES markdown-badges-chrome.mjs METAB ROOT PORT STATE",
  );
}
// Where a run keeps the pages it drew, for a person to look at: unset in the suite.
const shots = process.env.BADGES_SCREENSHOTS ?? "";
const base = `http://127.0.0.1:${port}`;
const started = Date.now();
const phase = (name) => process.stderr.write(`phase ${name} ${Date.now() - started}\n`);

const failures = [];
let checks = 0;
const check = (label, ok, detail = "") => {
  checks += 1;
  if (!ok) {
    const failure = `${label}${detail === "" ? "" : `: ${JSON.stringify(detail)}`}`;
    failures.push(failure);
    process.stderr.write(`failed ${failure}\n`);
  }
};
// Layout rounds to a fraction of a pixel.
const near = (a, b, within = 1.5) => Math.abs(a - b) <= within;

/** Start a server with *flags*, and resolve to its stop once it says where it serves. */
async function serve(flags) {
  const server = spawn(
    metab,
    [
      root,
      "--no-open",
      "--port",
      port,
      "--cache-dir",
      path.join(state, "cache"),
      "--config-dir",
      path.join(state, "config"),
      ...flags,
    ],
    {
      stdio: ["ignore", "pipe", "pipe"],
      env: { ...process.env, METABROWSER_LOG_LEVEL: "WARNING" },
    },
  );
  const exited = new Promise((resolve) => server.once("exit", resolve));
  let output = "";
  await new Promise((resolve, reject) => {
    const bound = setTimeout(() => reject(new Error(`no server: ${output}`)), 30000);
    const read = (chunk) => {
      output += chunk;
      if (output.includes("Serving ") && output.includes(base)) {
        clearTimeout(bound);
        resolve();
      }
    };
    server.stdout.on("data", read);
    server.stderr.on("data", read);
    server.once("exit", () => reject(new Error(`server exited: ${output}`)));
  });
  return async () => {
    server.kill();
    await exited;
  };
}

// A badge, 90 by 20: what every image address answers.
const BADGE = Buffer.from(
  '<svg xmlns="http://www.w3.org/2000/svg" width="90" height="20">' +
    '<rect width="90" height="20" rx="3" fill="#555"/></svg>',
).toString("base64");

const DESTINATIONS = [
  "https://x.com/ojoshe",
  "https://github.com/octo/demo/actions/workflows/ci.yml",
  "https://www.npmjs.com/package/demo",
];
const IMAGES = [
  "https://badges.test/follow.svg",
  "https://badges.test/ci.svg",
  "https://badges.test/npm.svg",
  "https://badges.test/standalone.svg",
  "http://badges.test/insecure.svg",
];

// The view the reader sees, once the shell has moved it from its hidden stage into the pane.
const VIEW = `(() => {
  const pane = document.querySelector(".preview-pane");
  if (!pane || pane.querySelector(":scope > .preview-file-stage")) {
    return null;
  }
  return pane.querySelector(':scope > [data-active-view="true"]');
})()`;
const BADGE_ROW = `${VIEW}?.querySelector(".kpress-prose p")`;
// What stands for a badge: an image, or the chip an image the page does not load becomes.
const STANDS = "img, .mb-image-fallback";
const badgesSettled = `(() => {
  const row = ${BADGE_ROW};
  const badges = row ? [...row.querySelectorAll("${STANDS}")] : [];
  return badges.length === 5 && badges.every((badge) => badge.tagName !== "IMG" || badge.complete);
})()`;
// The README's Mermaid diagram, whose image shape names an image the allowlist never sees,
// settled: drawn, or showing its error.
const diagramSettled = `(() => {
  const figures = [...(${VIEW}?.querySelectorAll('[data-kpress-diagram="mermaid"]') ?? [])];
  return figures.length === 1 && ["rendered", "error"].includes(figures[0].dataset.kpressDiagramStatus);
})()`;
const settled = `(${badgesSettled}) && (${diagramSettled})`;
// The image the diagram names, which is asked for apart from the badges.
const DIAGRAM_IMAGE = "https://badges.test/mermaid.svg";

// Every badge of the row, left to right, as a box and as what it is and where it goes; the
// links of the row; and what follows each link.
const MEASURE = `(() => {
  const row = ${BADGE_ROW};
  const box = (element) => {
    const rect = element.getBoundingClientRect();
    return { left: rect.left, right: rect.right, top: rect.top, bottom: rect.bottom,
      width: rect.width, height: rect.height };
  };
  const badges = [...row.querySelectorAll("${STANDS}")].map((badge) => {
    const link = badge.closest("a");
    return {
      kind: badge.tagName === "IMG" ? "image" : "chip",
      text: badge.tagName === "IMG" ? badge.alt : badge.textContent,
      src: badge.tagName === "IMG" ? badge.getAttribute("src") : null,
      loaded: badge.tagName === "IMG" ? badge.naturalWidth : null,
      referrerPolicy: badge.tagName === "IMG" ? badge.getAttribute("referrerpolicy") : null,
      tip: badge.getAttribute("data-tip-text"),
      href: link?.getAttribute("href") ?? null,
      box: box(badge),
    };
  });
  const links = [...row.querySelectorAll("a")].map((link) => ({
    href: link.getAttribute("href"),
    holds: [...link.children].map((child) => child.tagName.toLowerCase()),
    text: link.textContent.trim(),
    nested: link.querySelector("a") !== null,
    marks: [...link.querySelectorAll(".external-link-icon")].length,
  }));
  const after = [...document.querySelectorAll(".kpress-prose p")].find((p) => p.textContent.startsWith("A line of text"));
  return {
    badges,
    links,
    images: row.querySelectorAll("img").length,
    marks: row.querySelectorAll(".external-link-icon").length,
    row: box(row),
    afterLinks: [...after.querySelectorAll("a")].map((link) => ({
      href: link.getAttribute("href"),
      marks: link.querySelectorAll(".external-link-icon").length,
    })),
  };
})()`;

const frames = () =>
  "new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve(true))))";

/** The badges lie on one line: left to right, none over another, as high as each other. */
function checkOneLine(profile, badges) {
  const top = badges[0].box.top;
  check(
    `${profile} the badges lie on one line`,
    badges.every((badge) => near(badge.box.top, top, 2) && near(badge.box.height, 20, 2)),
    badges.map((badge) => badge.box),
  );
  check(
    `${profile} the badges are in order and none is over another`,
    badges.every((badge, at) => at === 0 || badge.box.left >= badges[at - 1].box.right - 1),
    badges.map((badge) => badge.box),
  );
}

/** Each badge is in a link to its author's destination; no link is empty or holds a link. */
function checkLinks(profile, { badges, links, marks, afterLinks }) {
  check(
    `${profile} each linked badge goes where its author sent it`,
    DESTINATIONS.every((destination, at) => badges[at].href === destination),
    badges.map((badge) => badge.href),
  );
  check(
    `${profile} the badges that are not in a link are not drawn linking elsewhere`,
    badges[3].kind === "image" ? badges[3].href === null : badges[3].href === IMAGES[3],
    badges[3],
  );
  check(
    `${profile} no link is empty or holds another link`,
    links.every((link) => !link.nested && (link.holds.length > 0 || link.text !== "")),
    links,
  );
  check(
    `${profile} a link with words of its own is marked as before: the GitHub one, and not another`,
    afterLinks.length === 2 && afterLinks[0].marks === 0 && afterLinks[1].marks === 1,
    afterLinks,
  );
  check(
    `${profile} a link that holds only an image has no mark after it`,
    links
      .filter((link) => link.holds.length > 0 && link.text === "")
      .every((link) => link.marks === 0) && marks === 0,
    links,
  );
}

async function screenshot(page, name) {
  if (shots === "") {
    return;
  }
  const { data } = await page.send("Page.captureScreenshot", { format: "png" });
  fs.mkdirSync(shots, { recursive: true });
  fs.writeFileSync(path.join(shots, `${name}.png`), Buffer.from(data, "base64"));
}

const page = await launchChrome(process.env.CHROME_BIN, {
  profiles: process.env.CHROME_PROFILES,
  height: 700,
});
/** @type {Array<{url: string, referer: string | null}>} */
const requests = [];
try {
  await page.send("Page.enable");
  await page.send("Network.enable");
  await page.send("Network.setCacheDisabled", { cacheDisabled: true });
  // Answer every badge from here, and count it: what leaves the page is what is asked for.
  await page.send("Fetch.enable", {
    patterns: [{ urlPattern: "https://badges.test/*" }, { urlPattern: "http://badges.test/*" }],
  });
  page.on("Fetch.requestPaused", (event) => {
    const headers = Object.fromEntries(
      Object.entries(event.request.headers).map(([name, value]) => [name.toLowerCase(), value]),
    );
    requests.push({ url: event.request.url, referer: headers.referer ?? null });
    void page.send("Fetch.fulfillRequest", {
      requestId: event.requestId,
      responseCode: 200,
      responseHeaders: [{ name: "Content-Type", value: "image/svg+xml" }],
      body: BADGE,
    });
  });
  /** The shell's response headers for a request that carries *cookie*. @param {string} cookie */
  const headers = async (cookie) => {
    const answer = await fetch(`${base}/view/`, { headers: cookie ? { cookie } : {} });
    return answer.headers;
  };
  /** @param {string} cookie */
  const policy = async (cookie) => (await headers(cookie)).get("content-security-policy") ?? "";

  /** Wait for *expression* across a page that loads again, where a call can land between two. */
  const settle = async (expression, timeoutMs = 30000) => {
    const deadline = Date.now() + timeoutMs;
    for (;;) {
      try {
        if (await page.evaluate(expression)) {
          return;
        }
      } catch {
        // Chrome had no page to answer in: the navigation's, which the next try finds.
      }
      if (Date.now() > deadline) {
        throw new Error(`timed out waiting for ${expression}`);
      }
      await new Promise((resolve) => setTimeout(resolve, 50));
    }
  };

  /** Open the Metabrowser menu, and wait for the box's wiring, which its opening loads. */
  const openMenu = async () => {
    await page.evaluate(`document.getElementById("settings-btn").click()`);
    await settle(
      `window.MetabrowserRemoteImages !== undefined && document.getElementById("settings-control").getAttribute("aria-expanded") === "true"`,
    );
  };

  /**
   * Click the control *id*, which loads the page again: the old document is marked, so a
   * wait for the new one cannot be answered by the old.
   * @param {string} id
   */
  const click = async (id) => {
    await page.evaluate(`(() => {
      window.__beforeReload = true;
      document.getElementById("${id}").click();
      return true;
    })()`);
  };

  const open = async () => {
    requests.length = 0;
    await page.send("Page.navigate", { url: `${base}/view/README.md` });
    await page.waitFor(settled, 30000);
    await page.evaluate("document.fonts.ready.then(() => true)");
    await page.evaluate(frames());
    return page.evaluate(MEASURE);
  };

  // ── A trusted folder ────────────────────────────────────────────────────────────────
  let stop = await serve([]);
  phase("trusted server");
  try {
    const trusted = await open();
    check(
      "trusted every badge is an image that loaded",
      trusted.badges.length === 5 &&
        trusted.badges.every((badge) => badge.kind === "image" && badge.loaded === 90),
      trusted.badges,
    );
    checkOneLine("trusted", trusted.badges);
    checkLinks("trusted", trusted);
    await screenshot(page, "trusted");
  } finally {
    await stop();
  }
  phase("trusted");

  // ── An untrusted source, which shows the images of the web over https ─────────────
  stop = await serve(["--untrusted"]);
  phase("untrusted server");
  try {
    const open_ = await open();
    check(
      "untrusted the https images load, with the policy that sends no referrer",
      open_.badges
        .slice(0, 4)
        .every(
          (badge) =>
            badge.kind === "image" && badge.loaded === 90 && badge.referrerPolicy === "no-referrer",
        ),
      open_.badges,
    );
    check(
      "untrusted the http badge is the fallback chip, in its link to the image",
      open_.badges[4].kind === "chip" &&
        open_.badges[4].text === "Insecure" &&
        open_.badges[4].tip === IMAGES[4] &&
        open_.badges[4].href === IMAGES[4],
      open_.badges[4],
    );
    check(
      "untrusted the page asked for the four https images and sent no referrer",
      requests.filter((request) => request.url !== DIAGRAM_IMAGE).length === 4 &&
        IMAGES.slice(0, 4).every((url) => requests.some((request) => request.url === url)) &&
        requests.every((request) => request.referer === null),
      requests,
    );
    // The page's own policy sends no referrer, which is what covers an image the allowlist
    // never wrote: this one is named by a Mermaid image shape and laid out in the page.
    check(
      "untrusted the Mermaid diagram's image is asked for, with no referrer",
      requests.filter((request) => request.url === DIAGRAM_IMAGE).length >= 1 &&
        requests
          .filter((request) => request.url === DIAGRAM_IMAGE)
          .every((request) => request.referer === null),
      requests,
    );
    check(
      "untrusted the response says so: Referrer-Policy no-referrer",
      (await headers("")).get("referrer-policy") === "no-referrer",
    );
    check(
      "untrusted the policy admits https images",
      (await policy("")).includes("img-src 'self' data: https:;"),
      await policy(""),
    );
    checkOneLine("untrusted", open_.badges);
    checkLinks("untrusted", open_);
    check(
      "untrusted the box is not ticked",
      (await page.evaluate("document.getElementById('block-remote-images-input')?.checked")) ===
        false,
    );
    await screenshot(page, "untrusted");

    // The reader opens the menu, which wires its box, and ticks it: the cookie is written
    // and the page loads again, under the narrow policy, with no request for an image of
    // the web.
    requests.length = 0;
    check(
      "untrusted the box is disabled until the menu wires it",
      (await page.evaluate("document.getElementById('block-remote-images-input').disabled")) ===
        true,
    );
    await openMenu();
    check(
      "untrusted opening the menu enables the box",
      (await page.evaluate("document.getElementById('block-remote-images-input').disabled")) ===
        false,
    );
    await click("block-remote-images-input");
    await settle(`window.__beforeReload === undefined && (${settled})`);
    await page.evaluate("document.fonts.ready.then(() => true)");
    await page.evaluate(frames());
    const blocked = await page.evaluate(MEASURE);
    check(
      "blocked the box is ticked after the page loads again",
      (await page.evaluate("document.getElementById('block-remote-images-input')?.checked")) ===
        true,
    );
    check(
      "blocked no image is drawn: every badge is its chip, in its link",
      blocked.images === 0 &&
        blocked.badges.length === 5 &&
        blocked.badges.every((badge) => badge.kind === "chip"),
      blocked.badges,
    );
    check(
      "blocked each chip says its alt text and the address its image would have loaded",
      blocked.badges.every((badge, at) => badge.tip === IMAGES[at]) &&
        blocked.badges.map((badge) => badge.text).join("|") ===
          "Follow @ojoshe on X|CI|npm|Standalone|Insecure",
      blocked.badges,
    );
    check(
      "blocked the unlinked badges link to their images",
      blocked.badges[3].href === IMAGES[3] && blocked.badges[4].href === IMAGES[4],
      blocked.badges,
    );
    // The chip's tooltip is the app's own, inside a rendered document: hovering a chip shows
    // the address its image would have loaded.
    for (const at of [0, 3]) {
      const { box } = blocked.badges[at];
      await page.send("Input.dispatchMouseEvent", { type: "mouseMoved", x: 5, y: 5 });
      await page.send("Input.dispatchMouseEvent", {
        type: "mouseMoved",
        x: box.left + box.width / 2,
        y: box.top + box.height / 2,
      });
      await settle(
        `document.querySelector(".custom-tooltip")?.classList.contains("visible") && document.querySelector(".custom-tooltip").textContent.includes("Image from ${IMAGES[at]}")`,
      ).catch(() => {});
      // The chip is inside a link, whose card is the one tooltip and names the image's
      // address (docs/design-system.md, Tooltips on Links).
      check(
        `blocked hovering the chip of ${blocked.badges[at].text} shows its image's address`,
        (
          (await page.evaluate(`document.querySelector(".custom-tooltip")?.textContent ?? ""`)) ??
          ""
        ).includes(`Image from ${IMAGES[at]}`),
        await page.evaluate(`document.querySelector(".custom-tooltip")?.textContent ?? null`),
      );
    }
    checkOneLine("blocked", blocked.badges);
    checkLinks("blocked", blocked);
    check(
      "blocked no request left the page, the Mermaid diagram's image included",
      requests.length === 0,
      requests,
    );
    const narrow = await policy("metabrowser.blockRemoteImages=1");
    check(
      "blocked the policy admits only this origin, data, and the avatar host",
      narrow.includes("img-src 'self' data: https://avatars.githubusercontent.com;"),
      narrow,
    );
    // The browser itself refuses an image from the web under that policy.
    const probe = await page.evaluate(`new Promise((resolve) => {
      const image = new Image();
      image.onload = () => resolve("loaded");
      image.onerror = () => resolve("refused");
      image.src = "https://badges.test/probe.svg";
    })`);
    check("blocked the browser refuses an image from the web", probe === "refused", probe);
    check(
      "blocked the refused probe never left the page",
      !requests.some((request) => request.url.endsWith("/probe.svg")),
      requests,
    );
    await screenshot(page, "blocked");

    // And off again: the cookie is cleared, and the images are back.
    requests.length = 0;
    await openMenu();
    await click("block-remote-images-input");
    await settle(`window.__beforeReload === undefined && (${settled})`);
    const again = await page.evaluate(MEASURE);
    check(
      "blocked turned off again, the box is clear, the cookie says so, and the images load again",
      (await page.evaluate("document.getElementById('block-remote-images-input').checked")) ===
        false &&
        (await page.evaluate("document.cookie")).includes("metabrowser.blockRemoteImages=0") &&
        again.images === 4 &&
        again.badges.slice(0, 4).every((badge) => badge.kind === "image" && badge.loaded === 90) &&
        requests.some((request) => request.url === IMAGES[0]) &&
        requests.some((request) => request.url === DIAGRAM_IMAGE),
      { again, requests },
    );
  } finally {
    await stop();
  }
  phase("untrusted");
} finally {
  // Chrome with a request still paused for this session's answer, or a page still open on a
  // server that has stopped, was seen not to exit when asked to (it then held this process
  // open), so the session lets go of both first.
  await page.send("Fetch.disable").catch(() => {});
  await page.send("Page.navigate", { url: "about:blank" }).catch(() => {});
  await page.close();
}
phase("closed");

if (failures.length) {
  process.stdout.write(`${failures.length} of ${checks} checks failed:\n${failures.join("\n")}\n`);
  process.exit(1);
}
process.stdout.write(`markdown badges in Chrome: ${checks} checks passed\n`);
