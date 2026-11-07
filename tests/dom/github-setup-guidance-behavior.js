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
    const holder = envelope?.record?.same_as;
    if (holder !== undefined) {
      envelope.record = pages[holder].body.record;
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
  for (const [state, help, command] of [
    ["gh_missing", "install", "gh auth login --hostname github.com"],
    ["gh_too_old", "update", "gh auth status --hostname github.com"],
    ["not_logged_in", undefined, "gh auth login --hostname github.com"],
  ]) {
    const envelope = files[`failed ${state}`];
    assert.equal(envelope.last_refresh.outcome, state);
    for (const last of [envelope.last_refresh, { ...envelope.last_refresh, message: null }]) {
      const supplied = { ...envelope, last_refresh: last };
      const catalogFailure = catalog.refreshFailure(supplied, (at) => at);
      const fileFailure = tree.fileListFailure(supplied, (at) => at);
      const detail = page.describePull(
        { ...pages.current.body, last_refresh: last },
        {
          number: 7,
          tab: "",
          nowMs: Date.parse("2026-09-17T12:00:30Z"),
        },
      );
      assert.equal(catalogFailure.help, help);
      assert(catalogFailure.text.includes(command));
      assert(
        !catalogFailure.text.includes("You can still browse local files"),
        "the connection row supplies its own cache context",
      );
      assert.equal(fileFailure.retry, true);
      assert.equal(fileFailure.help, help);
      assert(fileFailure.text.includes(command));
      assert(
        fileFailure.text.includes("You can still browse local files and any cached pull requests."),
      );
      if (help) {
        assert(fileFailure.text.includes("https://cli.github.com/"));
      }
      if (last.message !== null) {
        assert(fileFailure.text.startsWith(last.message), "file setup retains safe backend text");
        assert(detail.failure.includes(last.message), "PR setup retains safe backend text");
      }
      assert.equal(detail.failureHelp, help);
      assert(detail.failure.includes(command));
      assert(detail.failure.includes("You can still browse local files"));
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
  assert.equal(rejected.text, "Run gh auth login --hostname github.com to connect.");
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
      backendTextPreserved: true,
      cachedRecordPreserved: true,
      authUsesNormalizedGuidance: true,
      otherFailureKindsPreserved: true,
    }),
  );
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
