const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { pathToFileURL } = require("node:url");
const root = path.resolve(__dirname, "../..");
const fixture = (name) =>
  JSON.parse(fs.readFileSync(path.join(root, "tests/fixtures", name), "utf8"));
const files = fixture("github-pull-files-responses.json");
const pages = fixture("github-pull-page-responses.json");
for (const answer of Object.values(pages)) {
  for (const envelope of [answer.body, answer.body?.pull]) {
    for (const field of ["record", "status", "readiness", "checks"]) {
      const holder = envelope?.[field]?.same_as;
      if (holder !== undefined) {
        // Anything kept beside the name, a status's own time, is this answer's.
        const { same_as: _held, ...own } = envelope[field];
        envelope[field] = { ...pages[holder].body[field], ...own };
      }
    }
  }
}
const routes = { atob, btoa, TextDecoder, TextEncoder, Uint8Array };
routes.window = routes;
for (const name of ["navigation.js", "git-path.js"]) {
  vm.runInNewContext(
    fs.readFileSync(path.join(root, "src/metabrowser/static", name), "utf8"),
    routes,
  );
}
globalThis.window = {
  MetabrowserGitPath: routes.MetabrowserGitPath,
  MetabrowserNavigationRoute: routes.MetabrowserNavigationRoute,
};
(async () => {
  const load = (name) =>
    import(pathToFileURL(path.join(root, "src/metabrowser/builtin_plugins/github", name)).href);
  const [catalog, page, tree] = await Promise.all(
    ["pulls-panel.js", "pull-page.js", "pull-files-tree.js"].map(load),
  );
  // One fixed sentence per outcome on all three surfaces, whatever the job's message said:
  // that stays in `last_refresh.message` for agents (docs/design-system-messages.md).
  for (const [state, help, said] of [
    ["gh_missing", "install", "GitHub CLI is not installed."],
    ["gh_too_old", "update", "GitHub CLI needs an update."],
    ["not_logged_in", undefined, "Run gh auth login --hostname github.com to sign in to GitHub."],
  ]) {
    const envelope = files[`failed ${state}`];
    assert.equal(envelope.last_refresh.outcome, state);
    for (const last of [envelope.last_refresh, { ...envelope.last_refresh, message: null }]) {
      const supplied = { ...envelope, last_refresh: last };
      const catalogFailure = catalog.refreshFailure(supplied, (at) => at);
      const fileFailure = tree.fileListFailure(supplied, (at) => at, String);
      const detail = page.describePull(
        { ...pages.current.body, last_refresh: last },
        {
          number: 7,
          tab: "",
          nowMs: Date.parse("2026-09-17T12:00:30Z"),
        },
      );
      assert.equal(catalogFailure.help, help);
      assert.equal(catalogFailure.text, said);
      assert.equal(fileFailure.retry, true);
      assert.equal(fileFailure.help, help);
      assert.equal(fileFailure.text, said);
      assert.equal(detail.failureHelp, help);
      assert.equal(detail.failure, said);
      if (last.message !== null) {
        for (const text of [catalogFailure.text, fileFailure.text, detail.failure]) {
          assert(!text.includes(last.message), "the job's message stays in the envelope");
        }
      }
      assert(detail.pull !== null, "setup failures must retain the cached PR");
      assert.equal(detail.canRefresh, true);
    }
  }
  const refused = "gh's github.com credentials were refused; run gh auth login";
  const rejected = catalog.refreshFailure(
    {
      ...files["failed not_logged_in"],
      last_refresh: { ...files["failed not_logged_in"].last_refresh, message: refused },
    },
    (at) => at,
  );
  assert.equal(rejected.text, "Run gh auth login --hostname github.com to sign in to GitHub.");
  for (const state of ["network_error", "not_found_or_private", "rate_limited"]) {
    const supplied = files[`failed ${state}`];
    const notice = catalog.refreshFailure(supplied, (at) => at);
    assert.equal(
      notice.help,
      undefined,
      "permission/network/rate failures must not become installation failures",
    );
    assert(!notice.text.includes("Install"));
  }
  console.log(
    JSON.stringify({
      setupStates: 3,
      views: 3,
      nullMessageFallbacks: true,
      backendTextWithheld: true,
      cachedRecordPreserved: true,
      authUsesNormalizedGuidance: true,
      otherFailureKindsPreserved: true,
    }),
  );
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
