# Keyword and Structural Tools to Benchmark: Pinned Installs

Companion to [10-keyword-structural-landscape.md](10-keyword-structural-landscape.md).
Versions, URLs and asset names were checked on 2026-11-26 through the GitHub releases
API, crates.io, npm, PyPI and the Go module proxy. Each `curl` URL below returned HTTP
200 on that date unless noted.

Host notes for this VM (Linux x86_64, 4 vCPU, shared):

- Release downloads from `github.com/<owner>/<repo>/releases/download/...` work with
  `curl -L`. **Source archives from `codeload.github.com` return 403** for repositories
  not attached to the session. For source builds, use `git clone --depth 1 --branch <tag>`
  or `gh api repos/<owner>/<repo>/tarball/<tag> > x.tar.gz`, with `NO_PROXY` set as in the
  shared brief.
- The system ships `rg` 14.1.0 at `/usr/bin/rg` and `/usr/bin/sg` (shadow-utils, **not**
  ast-grep). Install pinned tools into a private bin directory and invoke them by
  absolute path so neither shadows the other.
- Go is 1.24.7 locally with `GOTOOLCHAIN=auto`; Zoekt requires Go 1.26 (go.mod
  `toolchain go1.27.3`), so `go install` will download a toolchain through the proxy.
- Available build dependencies: `build-essential`, `autoconf`, `libpcre2-dev`,
  `zlib1g-dev`.

Suggested layout (outside every checkout, per the shared brief):

```bash
export KW="${CLI_SEARCH_SCRATCH:?set to the shared scratch root}/keyword-bench"   # downloads and installs
mkdir -p "$KW/dl" "$KW/bin"
export NO_PROXY="api.github.com,github.com,codeload.github.com,objects.githubusercontent.com,release-assets.githubusercontent.com,raw.githubusercontent.com"
```

## Priority 1: Core Comparisons

### ripgrep 16.0.0 (and keep system rg 14.1.0 as a baseline)

```bash
cd "$KW/dl"
V=16.0.0; A=ripgrep-$V-x86_64-unknown-linux-musl.tar.gz
curl -fsSLO https://github.com/BurntSushi/ripgrep/releases/download/$V/$A
curl -fsSLO https://github.com/BurntSushi/ripgrep/releases/download/$V/$A.sha256
sha256sum -c $A.sha256 && tar xzf $A && cp ripgrep-$V-x86_64-unknown-linux-musl/rg "$KW/bin/rg16"
"$KW/bin/rg16" --version   # expect: ripgrep 16.0.0 (rev 669cb4c755), +pcre2
```

Static musl build, 2.2 MB tarball. A verified copy is already unpacked in the shared scratch root under
`keyword/bin/rg`.

Measure `--json` versus plain output, `--json -C2`, `-l`, `-c`, `--in0` with large path
lists, `-m`, `--max-bytes`, the `--sort=path` slowdown, and the time to the first JSON
line.

### ugrep 7.8.5 (source build; no Linux release binary)

```bash
cd "$KW/dl"
git clone --depth 1 --branch v7.8.5 https://github.com/Genivia/ugrep.git ugrep-7.8.5
cd ugrep-7.8.5 && ./build.sh --prefix="$KW/ugrep" && make install
"$KW/ugrep/bin/ugrep" --version
# optional indexer for --index runs:
cd "$KW/dl" && git clone --depth 1 --branch v1.0.0 https://github.com/Genivia/ugrep-indexer.git
cd ugrep-indexer && ./build.sh --prefix="$KW/ugrep" && make install   # repo has build.sh and configure; flags UNVERIFIED
```

`build.sh` options are in the ugrep README (`--disable-avx2` and others). The build uses
all cores for about one to two minutes; run it when the benchmark host is idle. Compare
`ug -r --ignore-files -I` with `rg`, `ug --json` sizes, `-Z` fuzzy, `-%` Boolean, and
`--index` on a cold cache, if a cache drop is possible.

### microsoft/tgrep 1.2.9 (indexed grep, rg-compatible JSON)

```bash
cd "$KW/dl"
V=v1.2.9; A=tgrep-$V-x86_64-unknown-linux-musl.tar.gz
curl -fsSLO https://github.com/microsoft/tgrep/releases/download/$V/$A
curl -fsSLO https://github.com/microsoft/tgrep/releases/download/$V/checksums.txt
grep " $A\$" checksums.txt | sha256sum -c - && tar xzf $A
find . -maxdepth 2 -name tgrep -type f -exec cp {} "$KW/bin/tgrep" \;
"$KW/bin/tgrep" --version
```

Measure `tgrep index .` build time, peak memory and `.tgrep/` size; query latency with
and without `tgrep serve`; `--max-results` against rg plus caller kill; and freshness lag
after edits (`tgrep status .`). Keep `.tgrep/` out of the corpus (add it to
`.gitignore` or use `--index-path` outside the tree).

### git grep and GNU grep (system)

Already installed: `git 2.43.0` and GNU `grep 3.11` (upstream current: git 2.56.1, grep
3.12). Record the system versions; do not upgrade.

### SQLite FTS5 (trigram and unicode61) via Python stdlib and the sqlite3 CLI

Python 3.13 under `uv` bundles SQLite 3.53.1 with FTS5 (confirmed). The CLI is optional:

```bash
cd "$KW/dl"
curl -fsSLO https://www.sqlite.org/2026/sqlite-tools-linux-x64-3540100.zip
python3 -m zipfile -e sqlite-tools-linux-x64-3540100.zip sqlite-tools && cp sqlite-tools/sqlite3 "$KW/bin/"
"$KW/bin/sqlite3" --version   # expect 3.54.1
```

Benchmark plan: one table `fts5(path UNINDEXED, body, tokenize='trigram')`, and another
with `tokenize='unicode61'`, at whole-file granularity. Measure build time, DB size versus
corpus bytes, `MATCH` latency for 3+ character literals, `snippet()` cost, prefix scoping
with `WHERE path >= ? AND path < ?`, and incremental update of N files.

### qmd 2.9.0 (`qmd search`, BM25 only)

```bash
npm install -g @tobilu/qmd@2.9.0    # requires Node >= 22; installs better-sqlite3, node-llama-cpp
qmd --version
```

Use only `qmd search` (BM25). Do not run `qmd query`, `qmd vsearch` or `qmd embed` in
the keyword benchmark: they download GGUF models of about 1.3 GB. Use a unique `--index`
name and run qmd sequentially (see the 2026-05 brief). Note that the npm package is
scoped: the unscoped `qmd` is an unrelated 2016 package.

### ast-grep 0.51.3 (structural)

```bash
cd "$KW/dl"
curl -fsSLO https://github.com/ast-grep/ast-grep/releases/download/0.51.3/app-x86_64-unknown-linux-musl.zip
python3 -m zipfile -e app-x86_64-unknown-linux-musl.zip ast-grep-0.51.3
cp ast-grep-0.51.3/ast-grep "$KW/bin/ast-grep" && chmod +x "$KW/bin/ast-grep"
"$KW/bin/ast-grep" --version   # expect: ast-grep 0.51.3
```

No `.sha256` is attached to ast-grep releases; record `sha256sum` of the zip. The gnu
build is already unpacked in the shared scratch root under `keyword/bin/ast-grep`. Measure `run -p ... --json=stream`
latency and output bytes, and `outline --json=stream` over a repo.

## Priority 2: Indexed and Ranked Alternatives

### Zoekt (pseudo-version pinned)

```bash
export GOBIN="$KW/bin" GOPATH="$KW/gopath" GOMODCACHE="$KW/gomodcache" GOTOOLCHAIN=auto
Z=github.com/sourcegraph/zoekt
P=v0.0.0-20261125095755-c639b2fafda5
go install $Z/cmd/zoekt-index@$P $Z/cmd/zoekt-git-index@$P $Z/cmd/zoekt@$P
"$KW/bin/zoekt" -h 2>&1 | head -3
```

Optional: universal-ctags for symbol ranking (`apt-get install universal-ctags`, if
permitted). Measure `zoekt-index -index $KW/zoekt-idx <corpus>` time and shard size (the
design doc says about 3.5x the corpus), then `zoekt -index_dir ... -jsonl 'needle
file:^src/'` latency.

### tantivy (Python binding, for a BM25 index baseline)

```bash
uv venv "$KW/venv-tantivy" && uv pip install --python "$KW/venv-tantivy" 'tantivy==0.27.0'
```

tantivy-cli 0.25.0 is behind the engine (0.27.0); prefer the Python binding. If the CLI
is wanted: `cargo install tantivy-cli --version 0.25.0 --locked --root "$KW"` (compiles
for several minutes).

### probe 0.6.0-rc347 (no-index BM25 over AST blocks)

```bash
cd "$KW/dl"
V=v0.6.0-rc347; A=probe-$V-x86_64-unknown-linux-musl.tar.gz
curl -fsSLO https://github.com/probelabs/probe/releases/download/$V/$A
curl -fsSLO https://github.com/probelabs/probe/releases/download/$V/$A.sha256
sha256sum -c $A.sha256 && tar xzf $A && find . -name probe -type f -perm -u+x -exec cp {} "$KW/bin/probe" \;
"$KW/bin/probe" --version
```

If the `.sha256` file format does not match `sha256sum -c`, compare the hash by hand.

### cs (boyter) 3.2.0 (no-index BM25)

```bash
GOBIN="$KW/bin" GOTOOLCHAIN=auto go install github.com/boyter/cs/v3@v3.2.0   # module path confirmed (go.mod: github.com/boyter/cs/v3, go 1.26.4)
```

### fff-search 0.11.0 (in-process Python library)

```bash
uv venv "$KW/venv-fff" && uv pip install --python "$KW/venv-fff" 'fff-search==0.11.0'
```

Measure scan time, RSS, and `FileFinder.grep(..., mode="plain")` latency after the
scan. Note that its background watcher holds resources; use `watch=False` for timing.

## Priority 3: Optional or Baseline-Only

| Tool | Pinned install | Why optional |
| --- | --- | --- |
| fd 10.5.2 | `curl -fsSLO https://github.com/sharkdp/fd/releases/download/v10.5.2/fd-v10.5.2-x86_64-unknown-linux-musl.tar.gz` | Filename search baseline for the existing Quick Search |
| fzf 0.75.0 | `curl -fsSLO https://github.com/junegunn/fzf/releases/download/v0.75.0/fzf-0.75.0-linux_amd64.tar.gz` | `--filter` filename ranking baseline |
| hyperfine 2.0.0 | `curl -fsSLO https://github.com/sharkdp/hyperfine/releases/download/v2.0.0/hyperfine-v2.0.0-x86_64-unknown-linux-musl.tar.gz` | Timing harness (2.0.0 released 2026-10-07; the 2026-05 brief used 1.20.0) |
| ripgrep-all 0.10.10 | `curl -fsSLO https://github.com/phiresky/ripgrep-all/releases/download/v0.10.10/ripgrep_all-v0.10.10-x86_64-unknown-linux-musl.tar.gz` | Only for PDF/Office corpora |
| Google codesearch | `GOBIN="$KW/bin" go install github.com/google/codesearch/cmd/...@master` | Archived; `@latest` resolves to v1.2.0 (2020) |
| comby 1.8.1 | `curl -fsSLO https://github.com/comby-tools/comby/releases/download/1.8.1/comby-1.8.1-x86_64-linux.tar.gz` | 2022 release; structural only |
| opengrep 2.1.0 | `curl -fsSLO https://github.com/opengrep/opengrep/releases/download/v2.1.0/opengrep_linux_x86` (162 MB; cosign `.sig`/`.cert` alongside) | Rules engine, not navigation |
| tree-sitter 0.27.2 | `curl -fsSLO https://github.com/tree-sitter/tree-sitter/releases/download/v0.27.2/tree-sitter-linux-x64.gz` | Needs locally built grammars; text output |

Release assets were confirmed by the GitHub API, but the `curl` lines in this table were
not individually executed (the ripgrep, ast-grep and tree-sitter downloads were).
Verify hashes where the release publishes them (fd, fzf, and hyperfine attach checksum
files under different names; check the release page).

## Suggested Measurement Matrix

| Axis | Values |
| --- | --- |
| Corpora | (1) this repository, about 10k files at most; (2) a large public tree, such as the Linux kernel or a 100k-file monorepo |
| Queries | rare literal; common literal; case-insensitive literal; regex with literal prefix; regex without literals (`\w+_SUSPEND`); 3-term OR; 2-character literal (trigram edge case) |
| Modes | plain, `--json`, `--json -C2`, `-l`, `-c`, scoped to a subtree, scoped to an `--in0` list of 1k paths |
| Metrics | cold and warm wall time, time to first result, peak RSS, output bytes and approximate tokens, index build time and size, incremental update time, cancel-to-exit latency |
| Host | record CPU, vCPU count, RAM, disk type, and that the host is shared and noisy |
