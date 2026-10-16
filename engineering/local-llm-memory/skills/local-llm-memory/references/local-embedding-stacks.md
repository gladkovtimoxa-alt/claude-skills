# Local embedding & vector-store stacks for a self-hosted agent

Confidence tags: 🟢 verified against primary docs/source · 🟡 third-party benchmark · 🔴 anecdotal/folklore.

## Why this is a different problem than cloud agent memory

Every memory-architecture guide written for a cloud-first agent (long-context vs
RAG vs graph vs agentic memory — see `memory-engineering`) assumes an embeddings
API call is cheap, fast, and always reachable. A self-hosted stack running
against LM Studio, Ollama, or a bare `llama.cpp` server removes that assumption:
the embedding model, the vector store, and the chat model are all competing for
the same machine's RAM/VRAM, and "offline" is often a hard requirement, not a
cost optimization. 🟢

## Embedding backends

| Backend | Where it runs | Model size | Notes |
|---|---|---|---|
| ONNX Runtime + a MiniLM/BGE-small sentence-transformer | In-process, CPU | 80-130MB | One-time model fetch, then zero network. Used by ChromaDB's default local embedding function. 🟢 |
| LM Studio `/v1/embeddings` endpoint | The same local server already hosting the chat model | Whatever embedding-capable GGUF is loaded | Avoids a second runtime, but shares the one GPU/CPU slot with chat inference — queue contention under `parallel=1`. 🟢 |
| `llama.cpp --embedding` server | A second local server process | Any embedding GGUF | Same contention trade-off as LM Studio; useful when the chat server is a different binary (not LM Studio). 🟢 |
| Ollama `ollama pull nomic-embed-text` | Ollama's own runtime | ~270MB | Convenient if Ollama is already the chat backend; adds Ollama as a second dependency if LM Studio is primary. 🟢 |

Source: ONNX Runtime docs (onnxruntime.ai), Chroma's `DefaultEmbeddingFunction`
source (`chromadb/utils/embedding_functions`), LM Studio REST API docs
(lmstudio.ai/docs/developer/core), llama.cpp server README
(`examples/server/README.md`), Ollama embedding models docs
(ollama.com/blog/embedding-models). 🟢

## Vector/memory stores

| Store | Persistence | Semantic recall | Good fit |
|---|---|---|---|
| ChromaDB (local, DuckDB-backed) | Yes, on-disk | Yes (needs an embedder) | Project already has Python + wants a turnkey persistent store with metadata filtering. 🟢 |
| `sqlite-vec` extension | Yes, single file | Yes (bring your own embedder) | Already shipping SQLite elsewhere in the stack; wants zero extra server process. 🟢 |
| FAISS (flat/IVF index) | No built-in on-disk format — the app writes the index to disk itself | Yes | Pure speed/scale on one machine; willing to hand-roll the metadata sidecar and index save/load calls. 🟢 |
| Plain JSONL + substring/BM25-lite | Yes, human-readable | No (lexical only) | Small memory sets (<20k entries) where "search" really means "grep the last N turns." 🟢 |
| Managed cloud vector DB (Pinecone, Weaviate Cloud, Qdrant Cloud, ...) | Yes, remote | Yes | **Disqualified** the moment the stack's goal is "no network call" — it reintroduces the exact cloud dependency a local-LLM setup exists to avoid. 🟢 |

Source: Chroma docs (docs.trychroma.com — persistent client, embedding
functions), sqlite-vec README (github.com/asg017/sqlite-vec), FAISS wiki
(github.com/facebookresearch/faiss/wiki). 🟢

## Known failure modes specific to the local-LLM case

- **KV-cache thrash from a shared slot.** When the embedder and the chat model
  share one LM Studio instance at `maxConcurrentPredictions=1`, a memory-write
  embedding call during an active chat turn queues behind it — budget for that
  latency rather than discovering it as a mystery stall. 🟢 (direct consequence
  of LM Studio's single-slot behavior, documented in its REST API concurrency
  notes)
- **Model-swap cache loss.** Switching the loaded chat model (e.g. consolidating
  from two models to one, as in a model-swap event) does not invalidate a
  persistent vector store's embeddings — those stay valid as long as the
  *embedding* model didn't change, independent of which chat model is loaded.
  Conflating "we changed chat models" with "we must rebuild memory" wastes a
  full re-embed for no reason. 🟢
- **Silent embedding-dimension mismatch.** If the embedding model is swapped
  (e.g. MiniLM-384-dim → BGE-small-384-dim looks compatible but a different
  model family often is not numerically interchangeable), old vectors compare
  against new query vectors in the same space without erroring — just with
  degraded recall. Pin and record the embedding model name/version alongside
  the store, and re-embed on any change, not just on dimension mismatch. 🟡
  (widely reported community pattern, not covered by a single primary doc)
- **"Offline" claims that still phone home.** `pip install sentence-transformers`
  itself needs network once; several embedding libraries also silently check
  for model updates on import unless an offline/`HF_HUB_OFFLINE=1`-style flag is
  set. Verify the *running* process opens zero outbound connections, not just
  that the README says "local." 🟢 (Hugging Face Hub offline-mode docs)

## Related skills

- **memory-engineering**: use first — it decides *whether* and *what kind* of
  memory architecture to build (cost lens, architecture-family lens, density
  lens, forgetting-policy lens), independent of hosting. This skill assumes
  that decision already favors a vector/RAG-shaped store and answers the
  narrower "which local backend" question.
- **agent-memory**: a generic, hook-based four-tier (L0-L3) memory ladder for
  Claude Code sessions, written cloud-first (no offline constraint, no
  embedding-backend choice). Use this skill instead when the host model is a
  local LM Studio/Ollama/llama.cpp server and "never calls the network" is a
  hard requirement, not a preference.
