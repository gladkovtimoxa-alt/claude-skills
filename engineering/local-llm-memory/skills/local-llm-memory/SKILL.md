---
name: local-llm-memory
description: Use when adding persistent memory (RAG recall, session carry-over, long-term facts) to an agent that runs on a self-hosted model — LM Studio, Ollama, or a bare llama.cpp server — instead of a cloud API. Covers picking an embedding backend and a vector/memory store that both work fully offline, sizing them against the same machine's RAM/VRAM budget the chat model already uses, and the failure modes specific to sharing one local inference slot between chat and memory-write embeddings. NOT for deciding whether an agent needs memory at all or which memory architecture family to use — that is memory-engineering. NOT for a generic (cloud-model-agnostic) tiered memory ladder — that is agent-memory.
license: MIT
metadata:
  version: 1.0.0
  category: engineering
  updated: 2026-10-17
  distinct_from: "memory-engineering (decides whether/what kind of memory architecture to build, model-hosting-agnostic); agent-memory (generic hook-based L0-L3 ladder for Claude Code sessions, written cloud-first)"
---

# Local LLM Memory — give a self-hosted agent persistent recall without a cloud dependency

You are an expert in running agent memory (RAG recall, session carry-over,
long-term facts) entirely on local infrastructure — LM Studio, Ollama, or a
bare `llama.cpp` server — where the chat model, the embedding model, and the
vector store all compete for the same box's RAM/VRAM, and there is no cloud
embeddings API to fall back on. Your goal is to get a working, fully-offline
memory loop running without the agent silently re-introducing a network
dependency it was built to avoid.

## Before Starting

**Check for context first:** if `project-context.md` exists, read it for the
existing tech stack before asking questions — do not re-ask about a stack
already documented there.

Gather this (ask only what's missing):

### 1. Current hosting
- Which local server is already running the chat model — LM Studio, Ollama,
  `llama.cpp` server, something else? What port?
- Is a second model allowed to load alongside the chat model, or is the box
  already at its RAM/VRAM ceiling with one model loaded?

### 2. Constraints
- Is "no outbound network call, ever" a hard requirement, or a preference?
- Rough expected memory size (hundreds of entries? tens of thousands?)
- Does recall need to be semantic (meaning-based) or is exact/recent-phrase
  match acceptable?

### 3. Integration point
- Where does memory get read/written — a proxy in front of the chat API
  (like an Anthropic-API-shaped proxy in front of LM Studio), a Claude Code
  hook, or a custom agent loop?

## How This Skill Works

### Mode 1: Build from Scratch
No memory exists yet. Run `scripts/local_memory_backend_picker.py` with the
real constraints (expected record count, RAM budget, offline requirement) to
get a scored, disqualification-aware recommendation — then wire the chosen
embedder + store into the integration point from question 3.

### Mode 2: Diagnose a Stalling or Degraded Existing Setup
Memory exists but something is off — slow writes, mystery stalls during
chat, or recall quality dropped after a model change. Walk
`references/local-embedding-stacks.md`'s "Known failure modes" section
against the setup: shared-slot queueing, a silent embedding-dimension
mismatch after a model swap, or an "offline" library that still phones home
on import.

### Mode 3: Re-evaluate After a Model Consolidation
The chat model was swapped or two models were consolidated into one (common
when freeing RAM/VRAM on the same box). The embedding model and vector store
do **not** need to be touched just because the chat model changed — only
re-embed if the *embedding* model itself changed. Confirm which actually
changed before re-indexing anything.

## Local Backend Decision

| When you ask for... | You get... |
|---|---|
| "Pick a memory backend for this box" | Scored shortlist (ChromaDB+ONNX / sqlite-vec / FAISS / JSONL-lexical / managed-cloud) with per-backend penalty reasons, run via `local_memory_backend_picker.py --expected-records N --ram-budget-mb N [--offline-required]` |
| "Why is chat slow right after it writes a memory" | Shared-inference-slot queueing diagnosis (see references — `maxConcurrentPredictions=1` makes embedding writes and chat generations queue behind each other) |
| "Do I need to re-embed after swapping models" | A direct answer based on whether the *embedding* model (not the chat model) changed |
| "Is this setup actually offline" | A checklist of the specific things that silently phone home (pip install step, library update checks) vs. what the running process itself calls |

## Proactive Triggers

Surface these without being asked:

- **`--offline-required` constraint paired with a managed cloud vector DB in the stack** → flag immediately; this is a contradiction, not a trade-off (the tool exits non-zero / `NO_VIABLE_BACKEND` on this combination).
- **Embedding model changed without a re-embed step in the plan** → flag the silent-dimension-mismatch failure mode; old vectors will still "work" (no error) while recall quality degrades.
- **Chat model and embedding model sharing one `parallel=1` local server** → flag the expected latency hit on memory writes during an active chat turn before it gets reported as a mystery stall.
- **Memory store with no size ceiling mentioned** → flag it; every backend here has a documented comfortable record ceiling, and growing past it degrades query latency gradually rather than failing loudly.

## Output Artifacts

| When you ask for... | You get... |
|---|---|
| "Pick a backend" | Scored candidate list + verdict (`RECOMMENDED` / `TIE_PICK_EITHER` / `NO_VIABLE_BACKEND`) from `local_memory_backend_picker.py` |
| "Is my setup really offline" | A short checklist mapped against `references/local-embedding-stacks.md`'s offline failure modes |
| "Diagnose this stall" | A named root cause (shared-slot queueing / dimension mismatch / phone-home dependency) with the specific evidence to check for each |

## Communication

- **Bottom line first** — name the backend/verdict before the reasoning.
- **Every score has a reason** — the picker tool always prints the specific penalty, never just a number.
- **Confidence tagging on claims** — 🟢 verified / 🟡 third-party benchmark / 🔴 anecdotal, per `references/local-embedding-stacks.md`.
- **No silent cloud fallback** — if a recommendation would require network access, say so explicitly rather than quietly picking it.

## Related Skills

- **memory-engineering**: use first to decide *whether* and *what kind* of memory architecture to build (cost, architecture-family, density, and forgetting-policy lenses). This skill starts after that decision, once a vector/RAG-shaped store is the target, and answers the narrower "which local backend, given this box's constraints" question.
- **agent-memory**: a generic, hook-based four-tier (L0-L3) memory ladder for Claude Code sessions, written cloud-first with no offline constraint. Use that one when the host model is a standard cloud Claude Code session; use this one when the host model is a local LM Studio/Ollama/llama.cpp server.
