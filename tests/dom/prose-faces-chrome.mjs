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
// the document's own article is placed in one. The same article in the pull request page's
// containers, with its plugins' stylesheets, is a Markdown file in its Changes, which keeps
// the reading font. A plugin's Markdown view without KPress is the `md-body` convention.
import { launchChrome } from "./chrome-session.mjs";

const [base, commit] = process.argv.slice(2);
const failures = [];
let checks = 0;
const check = (label, ok, detail = "") => {
  checks += 1;
  if (!ok) {
    failures.push(`${label}${detail ? `: ${detail}` : ""}`);
  }
};

// In the page: wait for every probe's text, then mark the element that holds it directly
// and return its computed family, and the families the font set's tokens compute to.
const MARK = `async (probes) => {
  const holder = (probe) => {
    const scope = document.querySelector(probe.selector);
    if (!scope) return null;
    return [scope, ...scope.querySelectorAll("*")].find((node) =>
      [...node.childNodes].some(
        (child) => child.nodeType === 3 && child.textContent.includes(probe.text),
      ),
    ) ?? null;
  };
  const deadline = performance.now() + 20000;
  while (probes.some((probe) => holder(probe) === null) && performance.now() < deadline) {
    await new Promise((resolve) => setTimeout(resolve, 25));
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
    },
    probes: probes.map((probe) => {
      const node = holder(probe);
      if (node === null) return { name: probe.name, missing: true };
      node.setAttribute("data-face-probe", probe.name);
      return { name: probe.name, family: getComputedStyle(node).fontFamily };
    }),
  };
}`;

// In the page: a Markdown file's article placed where chrome prose and a pull request's
// Changes put KPress Markdown, with the stylesheets of the plugins that draw that page, and
// a plugin's Markdown view without KPress.
const PLACE = `(async () => {
  await window.metabrowser.ensureKindAssets("pull-request");
  await window.metabrowser.ensureKindAssets("diff");
  const article = document.querySelector(".metabrowser-markdown-document > article.kpress");
  const place = (classes, text) => {
    const outer = document.createElement("div");
    let inner = outer;
    for (const name of classes) {
      const next = document.createElement("div");
      next.className = name;
      inner.append(next);
      inner = next;
    }
    const copy = article.cloneNode(true);
    for (const node of copy.querySelectorAll("p")) {
      if (node.textContent.includes("A paragraph of document prose")) node.textContent = text;
    }
    inner.append(copy);
    document.body.append(outer);
  };
  place(["chrome-prose", "metabrowser-kpress-host"], "A message about the content.");
  place(
    ["content-body pull-request-host github-pull", "github-pull-body", "github-pull-diff metabrowser-diff-host"],
    "A Markdown file among a pull request's changes.",
  );
  const view = document.createElement("div");
  view.className = "content-body md-body";
  view.innerHTML = "<p>A plugin's Markdown view.</p>";
  document.body.append(view);
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
      },
      {
        name: "chrome prose's Markdown",
        kind: CHROME,
        selector: ".chrome-prose",
        text: "A message about the content.",
      },
      {
        name: "a Markdown file in a pull request's Changes",
        kind: DOCUMENT,
        selector: ".github-pull",
        text: "A Markdown file among",
      },
      {
        name: "a plugin's md-body view",
        kind: DOCUMENT,
        selector: ".md-body:not(.metabrowser-kpress-host)",
        text: "A plugin's Markdown view.",
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
    // The faces Chrome drew the probe's text with: its own text nodes' platform fonts. Asked
    // again for up to 2 s while Chrome reports none, as it does for text not laid out yet.
    const drawn = async (name) => {
      const deadline = Date.now() + 2000;
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
        await new Promise((resolve) => setTimeout(resolve, 50));
      }
    };
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
          await browser.waitFor("document.readyState === 'complete'");
          if (page.place) {
            await browser.waitFor(
              "!!document.querySelector('.metabrowser-markdown-document > article.kpress .kpress-prose')",
            );
            await browser.evaluate(PLACE);
          }
          const read = await browser.evaluate(`(${MARK})(${JSON.stringify(page.probes)})`);
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
            const want = read.stacks[serif ? "serif system" : `sans ${set}`];
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
  })
  .then(() => {
    if (failures.length > 0) {
      console.error(failures.join("\n"));
      process.exitCode = 1;
    } else {
      console.log(`prose faces in Chrome: ${checks} checks passed`);
    }
  });
