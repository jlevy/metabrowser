// Bundle @pierre/diffs (vanilla entry) into one unminified ESM artifact, the way a
// vendored build would, and verify byte determinism by building twice.
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { gzipSync } from "node:zlib";
import { build } from "esbuild";

const common = {
  entryPoints: ["entry.js"],
  bundle: true,
  format: "esm",
  platform: "browser",
  minify: false,
  logLevel: "warning",
};

await build({ ...common, outfile: "dist/bundle.js" });
await build({ ...common, outfile: "dist/bundle-repeat.js" });

const a = readFileSync("dist/bundle.js");
const b = readFileSync("dist/bundle-repeat.js");
const sha = (buf) => createHash("sha256").update(buf).digest("hex");
console.log(
  JSON.stringify(
    {
      bytes: a.length,
      gzipBytes: gzipSync(a).length,
      deterministic: sha(a) === sha(b),
      sha256: sha(a).slice(0, 16),
    },
    null,
    1,
  ),
);
