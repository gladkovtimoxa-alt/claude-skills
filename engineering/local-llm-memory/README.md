# local-llm-memory

Pick an embedding backend and vector/memory store for an agent running on a
self-hosted model (LM Studio, Ollama, or a bare `llama.cpp` server) instead of
a cloud API — fully offline, sized against the same machine's RAM/VRAM the
chat model already uses.

## Why this exists

Every existing memory-architecture skill in this repository (`memory-engineering`,
`agent-memory`) is written model-hosting-agnostic or cloud-first. Neither
answers "which local vector store and which local embedder, given that the
chat model is already sitting in the only GPU/CPU slot I have." This skill
answers that narrower, self-hosted-specific question.

## What's in this plugin

```
local-llm-memory/
├── .claude-plugin/
│   ├── plugin.json
│   └── authoring-notes.json
├── README.md
└── skills/local-llm-memory/
    ├── SKILL.md
    ├── scripts/
    │   └── local_memory_backend_picker.py   # stdlib-only, --help/--sample/--output json
    └── references/
        └── local-embedding-stacks.md        # cited backend comparison + failure modes
```

## Quick start

```bash
python3 skills/local-llm-memory/scripts/local_memory_backend_picker.py \
  --expected-records 8000 --ram-budget-mb 250 --offline-required
```

See `SKILL.md` for the full workflow (build-from-scratch / diagnose-a-stall /
re-evaluate-after-model-consolidation) and `references/local-embedding-stacks.md`
for the cited backend comparison.

## License

MIT.
