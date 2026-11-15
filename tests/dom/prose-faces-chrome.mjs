// Which face rendered text is drawn in, in a real engine, under both reading fonts and both
// font sets: a document in the reading font, and chrome prose in sans under either
// (docs/design-system.md, "Serif Is for Documents").
//
//   CHROME_BIN=/path/to/chrome CHROME_PROFILES=/dir/the/caller/removes \
//     node tests/dom/prose-faces-chrome.mjs http://127.0.0.1:PORT COMMIT
//
// CHROME_PROFILES is where Chrome's profile goes (tests/dom/chrome-session.mjs);
// tests/test_prose_faces_chrome.py owns it and removes it, and serves a repository with a
// doc.md, a README.md the Overview shows, and a COMMIT with a body.
//
// A face is the cascade's answer: custom properties resolved where they are declared and
// inherited, KPress's prose token declared again on its own `.kpress` element, and the
// reading font and font set on <html>. A check of the stylesheets' text passed while a
// pull request's page set the Markdown files in its Changes in sans, because a rule on the
// whole page reached them. So this reads the computed family, and for the vendored faces
// the face Chrome drew the text with.
//
// The documents are the shell's own: a Markdown file's Document view and the Overview's
// README. The chrome prose is a commit's body. A pull request's texts are the same KPress
// article inside `.chrome-prose`, which the page puts on each text
// (tests/dom/github-pull-first-paint-behavior.js checks that on the production page); here
// the document's own article is placed in one. A Markdown file in a pull request's Changes
// is the diff plugin's rendered Markdown, built by its own exports, in the containers the
// pull request page and the diff view put it in, with their stylesheets. A plugin's
// Markdown view without KPress is the `md-body` convention: its text is a document, the
// host's message in such a view is chrome, and its text inside `.chrome-prose` is chrome.
//
// Each Markdown text also holds an h2. KPress sets its h2 italic, which a serif document
// keeps and a sans text does not: upright in chrome prose and under the sans reading font,
// with the size, weight, and margins it has under the serif one.
import { launchChrome } from "./chrome-session.mjs";

const [base, commit] = process.argv.slice(2);
// How long a page has to show what it is probed for. A page took 72 to 305 ms from its
// navigation to its last probe, in CI and on a Mac at a load average of 7, so this is
// generous; a probe that never shows fails by name well inside the test's 30 s run budget.
const PROBE_WAIT_MS = 4000;
const PROBE_POLL_MS = 25;
// How long Chrome is asked again for the faces of a text it reports none for, as it does
// for text not laid out yet.
const FACE_RETRY_MS = 2000;
const FACE_POLL_MS = 50;
const failures = [];
let checks = 0;
// A failure is written as it is found, so a run cut short still says what failed.
const check = (label, ok, detail = "") => {
  checks += 1;
  if (!ok) {
    const failure = `${label}${detail ? `: ${detail}` : ""}`;
    failures.push(failure);
    console.error(`FAILED ${failure}`);
  }
};

// In the page: wait for every probe's text, then mark the element that holds it directly
// and return its computed family, and the families the font set's tokens compute to.
const MARK = `async (probes, waitMs, pollMs) => {
  const holder = (probe) => {
    const scope = document.querySelector(probe.selector);
    if (!scope) return null;
    return [scope, ...scope.querySelectorAll("*")].find((node) =>
      [...node.childNodes].some(
        (child) => child.nodeType === 3 && child.textContent.includes(probe.text),
      ),
    ) ?? null;
  };
  // The probe's h2, by its text, when the probe names one.
  const heading = (probe) =>
    [...document.querySelectorAll(probe.selector + " h2")].find((node) =>
      node.textContent.includes(probe.heading),
    ) ?? null;
  const shown = (probe) =>
    holder(probe) !== null && (probe.heading === undefined || heading(probe) !== null);
  const deadline = performance.now() + waitMs;
  while (probes.some((probe) => !shown(probe)) && performance.now() < deadline) {
    await new Promise((resolve) => setTimeout(resolve, pollMs));
  }
  // A text just placed has a style but no layout yet, and Chrome reports the faces of laid
  // out text only: a commit's body read on the frame it was placed in reported none, in CI.
  // So lay it out, then let the faces it asks for load.
  for (const probe of probes) {
    holder(probe)?.getBoundingClientRect();
  }
  await new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  await document.fonts.ready;
  const reference = (token) => {
    const span = document.createElement("span");
    span.style.fontFamily = "var(" + token + ")";
    document.body.append(span);
    const family = getComputedStyle(span).fontFamily;
    span.remove();
    return family;
  };
  return {
    html: [document.documentElement.dataset.proseFont, document.documentElement.dataset.appFont],
    stacks: {
      "sans clean": reference("--app-sans-clean"),
      "sans system": reference("--app-sans-system"),
      "serif system": reference("--app-serif-system"),
      // What the rest of the chrome reads, whatever it resolves to.
      chrome: reference("--font-sans"),
    },
    probes: probes.map((probe) => {
      const node = holder(probe);
      if (node === null) return { name: probe.name, missing: true };
      node.setAttribute("data-face-probe", probe.name);
      const found = { name: probe.name, family: getComputedStyle(node).fontFamily };
      if (probe.heading !== undefined) {
        const h2 = heading(probe);
        if (h2 === null) return { ...found, h2: null };
        const style = getComputedStyle(h2);
        found.h2 = {
          style: style.fontStyle,
          // What the h2 keeps under either face: its size, weight and spacing.
          box: [style.fontSize, style.fontWeight, style.marginTop, style.marginBottom].join(" "),
        };
      }
      return found;
    }),
  };
}`;

// In the page: text placed where the app puts it, each under an element whose
// `data-face-place` the probes find it by; every other class is the production markup's.
const PLACE = `(async () => {
  const mb = window.metabrowser;
  await mb.ensureKindAssets("pull-request");
  await mb.ensureKindAssets("diff");
  await mb.ensureAsset("inert-html");
  const inert = window.MetabrowserInertHtml;
  const { appendBlocks, sanitizeBlock } = await import("/plugin-static/diff/diff-markdown.js");
  const place = (name, chain, content) => {
    const outer = document.createElement("div");
    outer.setAttribute("data-face-place", name);
    let inner = outer;
    for (const [tag, className] of chain) {
      const next = document.createElement(tag);
      next.className = className;
      inner.append(next);
      inner = next;
    }
    inner.append(content);
    document.body.append(outer);
  };
  // A pull request's text: kpressHost's host and article in textBlock's element.
  const article = document.querySelector(".metabrowser-markdown-document > article.kpress").cloneNode(true);
  for (const node of article.querySelectorAll("p")) {
    if (node.textContent.includes("A paragraph of document prose")) {
      node.textContent = "A message about the content.";
    }
  }
  for (const node of article.querySelectorAll("h2")) {
    if (node.textContent.includes("A document section")) {
      node.textContent = "A message section";
    }
  }
  place("chrome-prose", [["div", "github-pull-text chrome-prose"], ["div", "metabrowser-kpress-host"]], article);
  // A Markdown file in Changes: diff-markdown.js's article and block rows, in its section
  // of the diff view, in the pull request page.
  const rendered = document.createElement("article");
  rendered.className = "kpress kpress-inert diff-markdown";
  const blocks = document.createDocumentFragment();
  const template = document.createElement("template");
  appendBlocks(
    blocks,
    [
      { kind: "added", html: "<h2>A section among the changes</h2>" },
      { kind: "added", html: "<p>A Markdown file among a pull request's changes.</p>" },
    ],
    (html) => sanitizeBlock(html, inert, template, document, () => false),
  );
  rendered.append(blocks);
  place(
    "changes",
    [
      ["div", "content-body pull-request-host github-pull"],
      ["div", "github-pull-body"],
      ["div", "github-pull-diff metabrowser-diff-host"],
      ["div", "diff-root"],
      ["section", "diff-file"],
    ],
    rendered,
  );
  // A plugin's view with the manifest's md-body container.
  const view = (html) => {
    const node = document.createElement("div");
    node.className = "content-body md-body";
    node.innerHTML = html;
    return node;
  };
  place("md-body", [], view("<h2>A plugin's section</h2><p>A plugin's Markdown view.</p>"));
  // What view-composition.js writes into a view whose render threw.
  place(
    "md-body-message",
    [],
    view('<div class="preview-empty" role="alert">Could not display this view. Refresh the page to try again.</div>'),
  );
  place(
    "md-body-chrome-prose",
    [["div", "chrome-prose"]],
    view("<h2>A message's section</h2><p>A message in a plugin's Markdown.</p>"),
  );
})()`;

const DOCUMENT = "document";
const CHROME = "chrome";
const PAGES = [
  {
    path: "/view/doc.md",
    place: true,
    probes: [
      {
        name: "the Document view",
        kind: DOCUMENT,
        selector: ".metabrowser-markdown-document",
        text: "A paragraph of document prose",
        heading: "A document section",
      },
      {
        name: "chrome prose's KPress Markdown",
        kind: CHROME,
        selector: '[data-face-place="chrome-prose"]',
        text: "A message about the content.",
        heading: "A message section",
      },
      {
        name: "a Markdown file in a pull request's Changes",
        kind: DOCUMENT,
        selector: '[data-face-place="changes"]',
        text: "A Markdown file among",
        heading: "A section among the changes",
      },
      {
        name: "a plugin's md-body Markdown",
        kind: DOCUMENT,
        selector: '[data-face-place="md-body"]',
        text: "A plugin's Markdown view.",
        heading: "A plugin's section",
        // The md-body fallback's own h2, which no rule sets italic.
        fallback: true,
      },
      {
        name: "the host's message in a plugin's md-body view",
        kind: CHROME,
        selector: '[data-face-place="md-body-message"]',
        text: "Could not display this view.",
        // The host's own chrome, not chrome prose: it reads the chrome's face.
        face: "chrome",
      },
      {
        name: "md-body Markdown inside chrome prose",
        kind: CHROME,
        selector: '[data-face-place="md-body-chrome-prose"]',
        text: "A message in a plugin's Markdown.",
        heading: "A message's section",
        fallback: true,
      },
    ],
  },
  {
    path: "/view/",
    probes: [
      {
        name: "the Overview's README",
        kind: DOCUMENT,
        selector: ".folder-overview-panel .metabrowser-markdown-document",
        text: "A paragraph of README prose",
        heading: "A README section",
      },
    ],
  },
  {
    path: () => `/commit/${commit}`,
    probes: [
      {
        name: "a commit's body",
        kind: CHROME,
        selector: ".git-commit-body",
        text: "A commit body paragraph",
      },
    ],
  },
];

async function main() {
  const bin = process.env.CHROME_BIN;
  const profiles = process.env.CHROME_PROFILES;
  if (!bin || !profiles || !base || !commit) {
    throw new Error("CHROME_BIN, CHROME_PROFILES, a server address, and a commit are required");
  }
  const browser = await launchChrome(bin, { profiles });
  try {
    for (const domain of ["Page", "DOM", "CSS", "Network"]) {
      await browser.send(`${domain}.enable`);
    }
    // The faces Chrome drew the probe's text with: its own text nodes' platform fonts,
    // asked again while Chrome reports none.
    const drawn = async (name) => {
      const deadline = Date.now() + FACE_RETRY_MS;
      for (;;) {
        const { root } = await browser.send("DOM.getDocument", { depth: -1 });
        const { nodeId } = await browser.send("DOM.querySelector", {
          nodeId: root.nodeId,
          selector: `[data-face-probe="${name}"]`,
        });
        if (!nodeId) {
          return "(the text left the page)";
        }
        const { fonts } = await browser.send("CSS.getPlatformFontsForNode", { nodeId });
        if (fonts.length > 0 || Date.now() > deadline) {
          return fonts.map((font) => font.familyName).join(" + ") || "(no face reported)";
        }
        await new Promise((resolve) => setTimeout(resolve, FACE_POLL_MS));
      }
    };
    // Each h2's size, weight and margins under the serif reading font, by font set.
    const serifBoxes = new Map();
    for (const prose of ["serif", "sans"]) {
      for (const set of ["clean", "system"]) {
        await browser.send("Network.clearBrowserCookies");
        const host = new URL(base).hostname;
        for (const [name, value] of [
          ["metabrowser.proseFont", prose],
          ["metabrowser.interfaceFont", set],
        ]) {
          await browser.send("Network.setCookie", { name, value, domain: host, path: "/" });
        }
        for (const page of PAGES) {
          const path = typeof page.path === "function" ? page.path() : page.path;
          const started = Date.now();
          await browser.send("Page.navigate", { url: `${base}${path}` });
          await browser.waitFor("document.readyState === 'complete'", PROBE_WAIT_MS);
          if (page.place) {
            await browser.waitFor(
              "!!document.querySelector('.metabrowser-markdown-document > article.kpress .kpress-prose')",
              PROBE_WAIT_MS,
            );
            await browser.evaluate(PLACE);
          }
          const read = await browser.evaluate(
            `(${MARK})(${JSON.stringify(page.probes)}, ${PROBE_WAIT_MS}, ${PROBE_POLL_MS})`,
          );
          const where = `${prose} reading font, ${set} fonts`;
          console.error(`${where}, ${path}: ${Date.now() - started} ms`);
          check(`${where}: <html> says so`, read.html.join(" ") === `${prose} ${set}`, read.html);
          for (const [index, probe] of page.probes.entries()) {
            const found = read.probes[index];
            const label = `${where}: ${probe.name}`;
            if (found.missing) {
              check(`${label} is shown`, false);
              continue;
            }
            const serif = probe.kind === DOCUMENT && prose === "serif";
            if (probe.heading !== undefined) {
              // KPress's h2 italic stays in the serif and goes in the sans. The md-body
              // fallback sets none.
              const italic = serif && !probe.fallback;
              const h2 = found.h2;
              check(
                `${label}: its h2 is ${italic ? "italic" : "upright"}`,
                h2 !== null && h2.style === (italic ? "italic" : "normal"),
                h2 === null ? "no h2 shown" : h2.style,
              );
              // Measured in the serif pass, which runs first, and held in the sans one.
              const key = `${set} ${probe.name}`;
              if (prose === "serif") {
                serifBoxes.set(key, h2?.box);
              } else {
                check(
                  `${label}: its h2 keeps its size, weight and spacing`,
                  h2 !== null && h2.box === serifBoxes.get(key),
                  `${h2?.box}, not ${serifBoxes.get(key)}`,
                );
              }
            }
            const faces = set === "clean" ? await drawn(probe.name) : null;
            if (serif && set === "clean") {
              // KPress's vendored reading face, which it names itself.
              check(
                `${label} is drawn in the vendored serif`,
                /PT Serif/.test(faces) && !/Source Sans/.test(faces),
                `${faces} (${found.family})`,
              );
              continue;
            }
            const want = read.stacks[probe.face ?? (serif ? "serif system" : `sans ${set}`)];
            check(
              `${label} is set in the ${serif ? "serif" : "sans"} of the ${set} fonts`,
              found.family === want,
              `${found.family}, not ${want}`,
            );
            if (faces !== null) {
              check(
                `${label} is drawn in the vendored sans`,
                /Source Sans 3/.test(faces) && !/PT Serif/.test(faces),
                faces,
              );
            }
          }
        }
      }
    }
  } finally {
    await browser.close();
  }
}

main()
  .catch((error) => {
    failures.push(`prose faces session threw: ${error?.stack || error}`);
    console.error(`FAILED ${failures.at(-1)}`);
  })
  .then(() => {
    if (failures.length > 0) {
      console.error(`${failures.length} of ${checks} checks failed`);
      process.exitCode = 1;
    } else {
      console.log(`prose faces in Chrome: ${checks} checks passed`);
    }
  });
