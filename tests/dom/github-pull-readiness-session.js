// The pull-request page's readiness, its header's badge and its Checks tab's Merge status
// section, in the browserless page session: github-pull-page-session.js, run whole, prints
// this part alone, for the recorded story's verdict and for the answers the server decides
// in tests/fixtures/github-pull-page-readiness.json (tests/test_github_pull_readiness_page.py).
// It is a transcript of its own because the session's first part is near the size
// tryscript's matcher compiles, as github-pull-page-second-session.js is.

process.argv.push("--part", "readiness");
require("./github-pull-page-session.js");
