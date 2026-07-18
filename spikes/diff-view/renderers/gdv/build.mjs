// Bundle @git-diff-view/core into one unminified ESM artifact and report size.
import { readFileSync } from "node:fs";
import { gzipSync } from "node:zlib";
import { build } from "esbuild";

await build({
  entryPoints: ["entry.js"],
  bundle: true,
  format: "esm",
  platform: "browser",
  minify: false,
  logLevel: "warning",
  outfile: "dist/bundle.js",
});

const raw = readFileSync("dist/bundle.js");
console.log(JSON.stringify({ bytes: raw.length, gzipBytes: gzipSync(raw).length }, null, 1));
