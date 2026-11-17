// Browserless session: a pull request text the server would not render stays plain, and says why.
//
// The Markdown route renders each text in the server's Markdown child under a deadline
// (src/metabrowser/builtin_plugins/github/pull_markdown.py) and refuses one past it. This
// session runs the production createPullController in builtin_plugins/github/pull-page.js
// on the pull route's answer the application gave for pull request 7
// (tests/fixtures/github-pull-page-responses.json, recorded by
// tests/test_github_pull_page_session.py) and on the route's refusal of a text
// (tests/fixtures/github-pull-text-refusal.json, pinned to the route by
// tests/test_github_pulls.py), and records what the page is told: a refused text is
// unavailable with the line refusedTextNote says for it, a rendered text renders, and a
// part the record lacks stays plain with nothing said. Where the page puts the line, under
// the text's plain text as a warning notice, is the glue's (`refusedText` in mountPullPage).

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { pathToFileURL } = require("node:url");

const repoRoot = path.resolve(__dirname, "../..");
const fixtures = path.join(repoRoot, "tests/fixtures");
const recorded = JSON.parse(
  fs.readFileSync(path.join(fixtures, "github-pull-page-responses.json"), "utf8"),
);
const refusal = JSON.parse(
  fs.readFileSync(path.join(fixtures, "github-pull-text-refusal.json"), "utf8"),
);
const pagePath = path.join(repoRoot, "src/metabrowser/builtin_plugins/github/pull-page.js");

// The page module reads the shell's route and Git path codecs at import, as in the shell.
const routeContext = { atob, btoa, TextDecoder, TextEncoder, Uint8Array };
routeContext.window = routeContext;
for (const name of ["navigation.js", "git-path.js"]) {
  const file = path.join(repoRoot, "src/metabrowser/static", name);
  vm.runInNewContext(fs.readFileSync(file, "utf8"), routeContext, { filename: file });
}
globalThis.window = {
  MetabrowserGitPath: routeContext.MetabrowserGitPath,
  MetabrowserNavigationRoute: routeContext.MetabrowserNavigationRoute,
};

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

async function settle() {
  for (let turn = 0; turn < 20; turn += 1) {
    await new Promise((resolve) => setImmediate(resolve));
  }
}

async function main() {
  const runtime = await import(pathToFileURL(pagePath).href);
  const record = recorded.current.body.record;
  const comment = record.issue_comments[0].id;
  const markdown = new Map([
    ["body", { status: refusal.status, etag: null, body: refusal.body }],
    [`issue_comment/${comment}`, recorded["markdown issue_comment"]],
  ]);
  const asked = [];
  const told = [];
  const deps = {
    async request(_method, route) {
      if (route.startsWith("/api/plugin/github/pull-markdown")) {
        const part = decodeURIComponent(route.split("&part=")[1]);
        asked.push(part);
        return markdown.get(part) ?? recorded["markdown missing"];
      }
      return recorded.current;
    },
    schedule: () => 0,
    cancel() {},
    now: () => Date.parse("2026-09-17T12:00:30Z"),
    isVisible: () => true,
    render() {},
    renderMarkdown(part) {
      told.push({ part, rendered: true });
    },
    textUnavailable(part, text, note) {
      told.push({ part, unavailable: true, text: text.slice(0, 32), note: note ?? null });
    },
    reload() {},
    navigate() {},
  };
  const controller = runtime.createPullController(deps, { number: 7, tab: "" });
  await controller.start();
  await settle();
  for (const part of ["body", `issue_comment/${comment}`, "issue_comment/1"]) {
    controller.requestMarkdown(part);
    await settle();
  }
  // A text asked for again on the same record is not asked of the server again.
  controller.requestMarkdown("body");
  await settle();
  controller.dispose();

  const notes = {};
  for (const code of [
    "render_deadline",
    "renderer_exited",
    "renderer_unavailable",
    "render_failed",
  ]) {
    notes[code] = runtime.refusedTextNote(422, { code, deadline_ms: 5000 });
  }
  notes.recorded = runtime.refusedTextNote(refusal.status, refusal.body);
  notes.unknown_part = runtime.refusedTextNote(404, recorded["markdown missing"].body);
  notes.ok = runtime.refusedTextNote(200, recorded["markdown issue_comment"].body);

  assert(asked.filter((part) => part === "body").length === 1, "a refused text is asked once");
  const body = told.find((entry) => entry.part === "body");
  assert(body?.unavailable && body.note === notes.recorded, "a refused text says why");
  console.log(JSON.stringify({ asked, told, notes }, null, 2));
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
