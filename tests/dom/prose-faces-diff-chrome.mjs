// The face a pull request's rendered Markdown diff is drawn in, in a real engine, under
// both reading fonts and both font sets, when KPress's version has a local segment.
//
//   CHROME_BIN=/path/to/chrome CHROME_PROFILES=/dir/the/caller/removes \
//     node tests/dom/prose-faces-diff-chrome.mjs http://127.0.0.1:PORT
//
// tests/test_prose_faces_chrome.py serves pull request 8 of the GitHub stand-in
// (tests/github_pull_fixture.py), which changes docs/guide.md by adding the paragraph
// "More.", and owns the profile.
//
// A Markdown file in a pull request's Docs or Changes is a document, so it reads in the
// reading font (docs/design-system.md, "Serif Is for Documents"). Its face comes from
// KPress's document.css, which only the diff loads on these tabs: the pull request has no
// description, so no text of its own loads KPress's stylesheets. The diff loads those its
// projection names (`kpressStylesheets` in builtin_plugins/diff/diff-markdown.js), at
// addresses under KPress's version, and an editable or development KPress's version has a
// PEP 440 local segment, `0.3.10.dev10+5c60a81`. A filter that refused the `+` dropped
// every stylesheet of such a KPress, and the document read in sans under the serif reading
// font (mb-2r08). Where KPress is a release, each projection's answer is given the local
// segment on its way to the page (`Fetch.requestPaused` below), as an editable KPress names
// its addresses; the server answers any version segment with the installed files, as it
// does a page rendered before an upgrade.
import { launchChrome } from "./chrome-session.mjs";

const [base] = process.argv.slice(2);
// How long a page has to show the rendered paragraph. Each page's time from its navigation
// to the end of its read is on stderr as `<pass>, <path>: N ms`.
const PROBE_WAIT_MS = 15000;
const PROBE_POLL_MS = 25;
// How long Chrome is asked again for the faces of a text it reports none for.
const FACE_RETRY_MS = 2000;
const FACE_POLL_MS = 50;
// The local segment an editable KPress built from a commit past its release puts in its
// version (uv-dynamic-versioning), which the projections' addresses are given.
const LOCAL = ".dev10+5c60a81";
// A KPress address under a version with a local segment, given here or by KPress itself.
const LOCAL_ADDRESS = /^\/kpress-static\/(?:@[0-9a-f]+\/)?v[^/]*\+[^/]*\//;
const RENDERED_ROUTE = "/api/plugin/github/pull-rendered-diff";
const PAGES = ["/pull/8/docs", "/pull/8/files"];
const TEXT = "More.";
const failures = [];
let checks = 0;
const check = (label, ok, detail = "") => {
  checks += 1;
  if (!ok) {
    const failure = `${label}${detail ? `: ${detail}` : ""}`;
    failures.push(failure);
    console.error(`FAILED ${failure}`);
  }
};

// In the page: wait for the rendered paragraph outside any inert stage, mark it, and return
// its computed family, the font set's tokens, and the KPress stylesheets the page links.
const READ = `async (text, waitMs, pollMs) => {
  const holder = () =>
    [...document.querySelectorAll(".diff-markdown .kpress-prose p")].find(
      (node) =>
        node.closest("[inert]") === null &&
        node.textContent.trim() === text &&
        getComputedStyle(node).visibility === "visible",
    ) ?? null;
  const deadline = performance.now() + waitMs;
  while (holder() === null && performance.now() < deadline) {
    await new Promise((resolve) => setTimeout(resolve, pollMs));
  }
  const node = holder();
  node?.getBoundingClientRect();
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
  node?.setAttribute("data-face-probe", "diff");
  return {
    html: [document.documentElement.dataset.proseFont, document.documentElement.dataset.appFont],
    family: node === null ? null : getComputedStyle(node).fontFamily,
    stacks: {
      "sans clean": reference("--app-sans-clean"),
      "sans system": reference("--app-sans-system"),
      "serif system": reference("--app-serif-system"),
    },
    documentSheets: [...document.querySelectorAll('link[rel~="stylesheet"]')]
      .map((link) => new URL(link.href).pathname)
      .filter((path) => path.startsWith("/kpress-static/") && path.endsWith("/css/document.css")),
  };
}`;

async function main() {
  const bin = process.env.CHROME_BIN;
  const profiles = process.env.CHROME_PROFILES;
  if (!bin || !profiles || !base) {
    throw new Error("CHROME_BIN, CHROME_PROFILES, and a server address are required");
  }
  const browser = await launchChrome(bin, { profiles });
  try {
    for (const domain of ["Page", "DOM", "CSS", "Network", "Runtime"]) {
      await browser.send(`${domain}.enable`);
    }
    // What the diff says when it leaves a stylesheet out or one does not load.
    const warnings = [];
    browser.on("Runtime.consoleAPICalled", (event) => {
      const said = event.args.map((arg) => arg.value ?? arg.description ?? "").join(" ");
      if (said.startsWith("metabrowser diff:")) {
        warnings.push(said.slice(0, 400));
      }
    });
    // Each projection as an editable KPress's server names it: every KPress address under
    // a version with a local segment.
    let localized = 0;
    browser.on("Fetch.requestPaused", (event) => {
      void (async () => {
        const { body, base64Encoded } = await browser.send("Fetch.getResponseBody", {
          requestId: event.requestId,
        });
        const text = base64Encoded ? Buffer.from(body, "base64").toString("utf8") : body;
        let answer = text;
        try {
          const projection = JSON.parse(text);
          for (const asset of projection?.assets?.assets ?? []) {
            const url = String(asset.public_url ?? "");
            // A KPress built from a commit already names a local version: kept as it is.
            if (LOCAL_ADDRESS.test(url)) {
              localized += 1;
              continue;
            }
            const local = url.replace(
              /^(\/kpress-static\/(?:@[0-9a-f]+\/)?v[^/+]+)\//,
              `$1${LOCAL}/`,
            );
            if (local !== url) {
              asset.public_url = local;
              localized += 1;
            }
          }
          answer = JSON.stringify(projection);
        } catch {
          // Not a projection: passed on as it came.
        }
        await browser.send("Fetch.fulfillRequest", {
          requestId: event.requestId,
          responseCode: event.responseStatusCode ?? 200,
          responseHeaders: (event.responseHeaders ?? []).filter(
            ({ name }) => !/^(content-encoding|content-length)$/i.test(name),
          ),
          body: Buffer.from(answer, "utf8").toString("base64"),
        });
      })().catch((error) => {
        failures.push(`the projection's rewrite threw: ${error?.stack || error}`);
      });
    });
    await browser.send("Fetch.enable", {
      patterns: [{ urlPattern: `*${RENDERED_ROUTE}*`, requestStage: "Response" }],
    });
    const drawn = async () => {
      const deadline = Date.now() + FACE_RETRY_MS;
      for (;;) {
        const { root } = await browser.send("DOM.getDocument", { depth: -1 });
        const { nodeId } = await browser.send("DOM.querySelector", {
          nodeId: root.nodeId,
          selector: '[data-face-probe="diff"]',
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
        for (const path of PAGES) {
          const where = `${prose} reading font, ${set} fonts, ${path}`;
          warnings.length = 0;
          const before = localized;
          const started = Date.now();
          await browser.send("Page.navigate", { url: `${base}${path}` });
          await browser.waitFor("document.readyState === 'complete'", PROBE_WAIT_MS);
          const read = await browser.evaluate(
            `(${READ})(${JSON.stringify(TEXT)}, ${PROBE_WAIT_MS}, ${PROBE_POLL_MS})`,
          );
          console.error(`${where}: ${Date.now() - started} ms`);
          if (read.family === null) {
            check(`${where}: the rendered paragraph is shown`, false, read.html.join(" "));
            continue;
          }
          check(
            `${where}: KPress's document.css loads from a local version's address`,
            localized > before && read.documentSheets.some((sheet) => LOCAL_ADDRESS.test(sheet)),
            `${localized - before} addresses given the local segment; ${JSON.stringify(read.documentSheets)}`,
          );
          check(`${where}: the diff warns of nothing`, warnings.length === 0, warnings.join("; "));
          const serif = prose === "serif";
          const faces = set === "clean" ? await drawn() : null;
          if (serif && set === "clean") {
            check(
              `${where}: the document is drawn in the vendored serif`,
              /PT Serif/.test(faces) && !/Source Sans/.test(faces),
              `${faces} (${read.family})`,
            );
            continue;
          }
          const want = read.stacks[serif ? "serif system" : `sans ${set}`];
          check(
            `${where}: the document is set in the ${serif ? "serif" : "sans"} of the ${set} fonts`,
            read.family === want,
            `${read.family}, not ${want}`,
          );
          if (faces !== null) {
            check(
              `${where}: the document is drawn in the vendored sans`,
              /Source Sans 3/.test(faces) && !/PT Serif/.test(faces),
              faces,
            );
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
    failures.push(`rendered diff faces session threw: ${error?.stack || error}`);
    console.error(`FAILED ${failures.at(-1)}`);
  })
  .then(() => {
    if (failures.length > 0) {
      console.error(`${failures.length} of ${checks} checks failed`);
      process.exitCode = 1;
    } else {
      console.log(`rendered diff faces in Chrome: ${checks} checks passed`);
    }
  });
