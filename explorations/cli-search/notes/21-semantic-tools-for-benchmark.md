# Semantic and Hybrid Tools: Benchmark Recipes (pinned, CPU-only)

For the benchmark agent. Companion to `20-semantic-landscape.md`. All commands assume
`source bench/env.sh` (so `$SCRATCH`, `$BIN`, `$DL`, `$IDX`, `$C_MB`, `$C_MBDOCS`,
`$C_LINUX`, `XDG_*`, `NPM_CONFIG_PREFIX`, `TMPDIR` are set) and a 4-vCPU CPU-only Linux
x86_64 host. Versions and SHA-256 values were checked on 2026-11-26. Nothing here was
timed by me; I only smoke-tested `--help` and two-file schemas.

## Which tools, on which corpus

| Tool | Version | Embedder (download) | Run on `$C_MBDOCS` (608 md, 10.9 MiB) | `$C_MB` (2,881 files, 69.6 MiB) | `$C_LINUX` (86,618 files, 1.4 GiB) |
| --- | --- | --- | --- | --- | --- |
| qmd BM25 (`search`) | 2.9.0 | none | yes | yes (set glob) | optional |
| qmd hybrid (`query`) | 2.9.0 | ~2.25 GB GGUF | yes, if bandwidth/disk allow | no (CPU cost) | no |
| Vera | 2.5.0 | potion-code-16M-v2 (~32 MB) | yes | yes | yes (static model) |
| Semble | 0.7.3 | potion-code-16M-v2 (~33 MB) | yes (`--content docs`) | yes | optional (1 MB file cap) |
| ColGREP | 1.8.5 | LateOn-Code-edge INT8 (17.2 MB) | yes | yes | no (ColBERT CPU encode) |
| ck | 0.8.1 | bge-small-en-v1.5 ONNX (~67 MB) | yes | yes | no |
| zvec-grep (`zg`) | 0.3.1 | potion-code-16m-v2 | yes (text output only) | yes | optional |
| semtools search | 3.0.1 | potion-multilingual-128M | yes (explicit file list) | no | no |

Skip: grepai (needs a running Ollama), mgrep and claude-context (cloud), osgrep (stale),
jina-grep (Apple Silicon only), cocoindex-code `[full]` (~1 GB torch), qmd `query` on
Linux.

Record for each: first-run model download size and time (separately from indexing), cold
index wall/CPU time and max RSS (`/usr/bin/time -v`), index bytes on disk, incremental
re-index after touching 1 file, warm query latency (hyperfine `--warmup 3 --runs 10`),
cold query (first after index, page cache warm), result bytes per query, and top-10 recall
on known-answer queries. Run qmd sequentially (SQLite lock). Note the host is shared and
noisy.

## Isolation

```bash
source bench/env.sh
export HF_HOME="$SCRATCH/cache/hf"                 # Semble, colgrep, Vera, ck model caches
export SEMBLE_CACHE_LOCATION="$IDX/semble"
export CK_INDEX_DIR="$IDX/ck"                      # keep .ck/ out of the corpus
export VERA_NO_UPDATE_CHECK=1
export UV_TOOL_DIR="$SCRATCH/uvtools" UV_TOOL_BIN_DIR="$BIN" UV_CACHE_DIR="$SCRATCH/cache/uv"
mkdir -p "$HF_HOME" "$SEMBLE_CACHE_LOCATION" "$CK_INDEX_DIR"
```

Vera and zg write their index inside the corpus (`.vera/`, `.zvec-grep/`). Either copy the
corpus first (`cp -a "$C_MBDOCS" "$IDX/vera-mbdocs"`) or delete the directory after the
run so walk-based tools are not affected. ColGREP writes to `$XDG_DATA_HOME/colgrep`.
qmd writes `$XDG_CACHE_HOME/qmd/<index>.sqlite` and models under
`$XDG_CACHE_HOME/qmd/models/`.

## Install (pinned)

```bash
cd "$DL"
# Vera 2.5.0 (single binary, 134 MB unpacked)
curl -fsSLo vera-2.5.0.tgz https://github.com/VeraTools/vera/releases/download/v2.5.0/vera-x86_64-unknown-linux-gnu.tar.gz
echo "11e359acf7d453fad27e3879657be986a7a7bb7aa181296f36820c8b8539314c  vera-2.5.0.tgz" | sha256sum -c
tar xzf vera-2.5.0.tgz && install -m755 vera-x86_64-unknown-linux-gnu/vera "$BIN/vera"

# ColGREP 1.8.5 (single binary with ONNX Runtime, 168 MB unpacked)
curl -fsSLo colgrep-1.8.5.txz https://github.com/lightonai/next-plaid/releases/download/v1.8.5/colgrep-x86_64-unknown-linux-gnu.tar.xz
echo "532e1da739f6b5d489cdaefd20c5918fa1bb0ff9f456c89098eb49a6379ae205  colgrep-1.8.5.txz" | sha256sum -c
tar xJf colgrep-1.8.5.txz && install -m755 colgrep-x86_64-unknown-linux-gnu/colgrep "$BIN/colgrep"

# ck 0.8.1 is already in bench/install.sh (sha256 042db74e...ba1ac)
# qmd 2.9.0 is already in bench/install.sh (npm @tobilu/qmd@2.9.0)

# Semble 0.7.3 (Python via uv)
uv tool install semble==0.7.3

# zvec-grep 0.3.1 (Rust binary shipped through npm; 136 MB)
npm install -g --no-fund --no-audit @zvec/zvec-grep@0.3.1

# semtools 3.0.1 is already in bench/install.sh

# Optional: grepai 1.2.0 (needs Ollama + `ollama pull nomic-embed-text`)
# curl -fsSLo grepai-1.2.0.tgz https://github.com/yoanbernabeu/grepai/releases/download/v1.2.0/grepai_1.2.0_linux_amd64.tar.gz
# echo "ea21d0c9324ee41b087b80b5ef528a11996941c712efdeeb9a6dddc8a4691dc6  grepai-1.2.0.tgz" | sha256sum -c

vera --version; colgrep --version; ck --version; qmd --version; semble --version; zg --version
```

## Index and query commands

Use `Q` for a natural-language query and `C` for the corpus copy.

### qmd 2.9.0

```bash
IDXNAME=mbdocs-$(date -u +%Y%m%d)
qmd collection add "$C_MBDOCS" --name mbdocs --index "$IDXNAME"   # BM25 index (qmd update rescans)
qmd search "$Q" --index "$IDXNAME" --format json -n 10           # BM25, JSON array
qmd search "$Q" --index "$IDXNAME" --format files -n 10          # docid,score,uri
# Hybrid (downloads ~2.25 GB; time separately):
qmd pull --progress                                              # embeddinggemma Q8 334 MB, qwen3-reranker Q8 639 MB, expansion q4_k_m 1.28 GB
qmd embed --index "$IDXNAME"                                      # 900-token chunks, CPU
qmd vsearch "$Q" --index "$IDXNAME" --format json -n 10 --no-gpu
qmd query "$Q" --index "$IDXNAME" --format json -n 10 --no-gpu               # full pipeline
qmd query "$Q" --index "$IDXNAME" --format json -n 10 --no-gpu --no-rerank   # RRF only
# Warm daemon variant for latency: qmd mcp --http --daemon; POST /query ; qmd mcp stop
```

For `$C_MB` use `qmd collection add "$C_MB" --name mb --mask '**/*.{md,py,js,mjs,swift}'`
(`--mask` takes a glob; comma-separated or brace unions, per the README; default mask is
`**/*.md`). Index file: `$XDG_CACHE_HOME/qmd/$IDXNAME.sqlite`.

### Vera 2.5.0

```bash
C="$IDX/vera-mbdocs"; cp -a "$C_MBDOCS" "$C"; cd "$C"
vera setup --potion-code --yes                       # saves the CPU backend, no prompts (verified in --help)
vera index .                                         # hybrid index (.vera/)
vera search "$Q" --json --limit 10 --scope all --timing
vera search "$Q" --json --limit 10 --scope docs      # prose
vera search "$Q" --json --limit 10 --path "docs/**"  # subtree scope
touch some/file.md && vera update .                  # incremental
du -sh .vera
# Keyword-only baseline (no model): vera index . --full-text-only
```

`--scope all` matters on a Markdown corpus: Vera favours source files by default.

### Semble 0.7.3

```bash
semble search "$Q" "$C_MBDOCS" --content docs -k 10 --format json          # first call indexes + downloads model
semble search "$Q" "$C_MB" --content all -k 10 --format json
semble search "$Q" "$C_MBDOCS/docs/project/specs" --content docs -k 10      # subtree = separate root
du -sh "$SEMBLE_CACHE_LOCATION"
```

Per-call Python start-up is ~0.7 s even warm (smoke test); also time the in-process
latency with `python -I -c 'from semble import SembleIndex, ContentType; ...'` or the
`semble --http` server so index/query cost is separated from interpreter start.

### ColGREP 1.8.5

```bash
colgrep settings --int8                      # explicit INT8 on CPU (build default on non-CUDA)
colgrep init "$C_MBDOCS"                     # index in $XDG_DATA_HOME/colgrep/indices
colgrep --json -k 10 "$Q" "$C_MBDOCS"
colgrep --json -k 10 --semantic-only "$Q" "$C_MBDOCS"
colgrep --json -k 10 --include="docs/**" "$Q" "$C_MBDOCS"
colgrep status "$C_MBDOCS"; du -sh "$XDG_DATA_HOME/colgrep"
```

Do not run `colgrep --install-agent` (2.5 GB model).

### ck 0.8.1

```bash
ck --index "$C_MBDOCS"                                    # bge-small, index in $CK_INDEX_DIR
ck --jsonl --sem --topk 10 --threshold 0 "$Q" "$C_MBDOCS"
ck --jsonl --hybrid --topk 10 "$Q" "$C_MBDOCS"
ck --jsonl --lex --topk 10 "$Q" "$C_MBDOCS"               # BM25 (Tantivy)
ck --status-verbose "$C_MBDOCS"; du -sh "$CK_INDEX_DIR"
```

`--sem` defaults to threshold 0.6, which can hide results; pass `--threshold 0` for recall
measurement. JSONL rows carry byte and line spans.

### zvec-grep 0.3.1

```bash
C="$IDX/zg-mbdocs"; cp -a "$C_MBDOCS" "$C"; cd "$C"
zg --index . --embedding local/potion-code-16m-v2 --mode direct --device cpu   # flags verified in `zg --help index`
zg --status
zg --mode direct --limit 10 --preview none "$Q"                  # hybrid (text output only)
zg --mode direct --limit 10 --preview none --fts "$Q"
zg --mode direct --limit 10 --preview none --vector "$Q"
du -sh .zvec-grep
```

No JSON output in 0.3.1; parse `path:start-end` lines from `--preview none`. Semble's
benchmark ran zg in `direct` mode; a server-mode run (`zg --server on`) shows warm latency.

### semtools 3.0.1

```bash
find "$C_MBDOCS" -name '*.md' -print0 | xargs -0 semtools search "$Q" --top-k 10 --json
```

Embeds every passed file on every call unless `SEMTOOLS_WORKSPACE` is set; measure both.

## Suggested known-answer queries (metabrowser Markdown corpus)

Check each target exists at the pinned commit before use; drop any that do not.

| Query | Expected primary document |
| --- | --- |
| keyboard palette that fuzzy matches files and pull requests | `docs/project/specs/active/plan-2026-07-17-scalable-file-search.md` |
| how fuzzy file results are scored and ordered | `docs/project/research/research-2026-07-31-fuzzy-file-ranking.md` |
| rendering many small rectangles for disk usage view | `docs/project/research/research-2026-11-22-dense-treemap-rendering.md` |
| showing modified and untracked files from git | `docs/project/research/research-2026-08-26-git-status-and-dirty-working-trees.md` |
| following relative links between markdown documents | `docs/project/research/research-2026-08-13-markdown-link-navigation.md` |
| packaging the desktop app for mac | `docs/project/research/research-2026-11-08-macos-app-packaging.md` |

The queries deliberately avoid the target's filename words where possible, to separate
semantic recall from filename/keyword luck. Run the same queries through `rg -l -i` with
2 to 3 hand-picked terms for the keyword baseline, as in the 2026-05 brief.
