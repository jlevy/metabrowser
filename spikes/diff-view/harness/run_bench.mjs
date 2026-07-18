// Drives every renderer spike page in headless Chromium and collects results.
import { spawn } from "node:child_process";
import { createHash } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { gzipSync } from "node:zlib";
import { chromium } from "playwright";

const here = dirname(fileURLToPath(import.meta.url));
const spikeRoot = resolve(here, "..");
const PORT = 8177;
const RENDERERS = ["custom", "server_html", "pierre", "gdv"];

function serve() {
  const proc = spawn("python3", ["-m", "http.server", String(PORT), "--directory", spikeRoot], {
    stdio: "ignore",
  });
  return proc;
}

async function waitForServer() {
  for (let i = 0; i < 50; i += 1) {
    try {
      const res = await fetch(`http://127.0.0.1:${PORT}/fixtures/out/scenarios.json`);
      if (res.ok) return;
    } catch {
      // retry
    }
    await new Promise((r) => setTimeout(r, 100));
  }
  throw new Error("http.server did not become ready");
}

function bundleInfo(rel) {
  const path = join(spikeRoot, rel);
  if (!existsSync(path)) return null;
  const raw = readFileSync(path);
  return {
    file: rel,
    bytes: statSync(path).size,
    gzipBytes: gzipSync(raw).length,
    sha256: createHash("sha256").update(raw).digest("hex").slice(0, 16),
  };
}

const server = serve();
try {
  await waitForServer();
  const executablePath = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome";
  const browser = await chromium.launch({
    headless: true,
    executablePath: existsSync(executablePath) ? executablePath : undefined,
    args: ["--no-sandbox", "--disable-dev-shm-usage"],
  });
  const all = [];
  const consoleErrors = {};
  for (const renderer of RENDERERS) {
    const page = await browser.newPage({ viewport: { width: 1400, height: 1000 } });
    consoleErrors[renderer] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") consoleErrors[renderer].push(msg.text().slice(0, 300));
    });
    page.on("pageerror", (err) => consoleErrors[renderer].push(String(err).slice(0, 300)));
    try {
      await page.goto(`http://127.0.0.1:${PORT}/renderers/${renderer}/index.html`);
      await page.waitForFunction(() => window.__benchDone === true, undefined, {
        timeout: renderer === "pierre" ? 300000 : 120000,
      });
    } catch (err) {
      all.push({ name: `${renderer}:TIMEOUT`, error: String(err).slice(0, 200) });
    }
    const results = await page.evaluate(() => window.__RESULTS ?? []);
    all.push(...results);
    await page.close();
    console.error(`[bench] ${renderer}: ${results.length} results, ${consoleErrors[renderer].length} console errors`);
  }
  await browser.close();

  const bundles = {
    pierre: bundleInfo("renderers/pierre/dist/bundle.js"),
    gdv: bundleInfo("renderers/gdv/dist/bundle.js"),
    custom: bundleInfo("renderers/custom/diff_render.js"),
  };
  const out = { results: all, bundles, consoleErrors };
  mkdirSync(join(here, "results"), { recursive: true });
  writeFileSync(join(here, "results", "results.json"), JSON.stringify(out, null, 1));

  console.log("| scenario | renderMs | longTaskMs | tasks | domNodes |");
  console.log("| --- | --- | --- | --- | --- |");
  for (const r of all) {
    if (r.error) {
      console.log(`| ${r.name} | ERROR: ${r.error} | | | |`);
    } else {
      console.log(
        `| ${r.name} | ${r.renderMs} | ${r.longTaskMs ?? ""} | ${r.longTasks ?? ""} | ${r.domNodes} |`,
      );
    }
  }
  console.log("\nbundles:", JSON.stringify(bundles, null, 1));
  const errs = Object.entries(consoleErrors).filter(([, v]) => v.length);
  if (errs.length) console.log("\nconsole errors:", JSON.stringify(errs, null, 1));
} finally {
  server.kill();
}
