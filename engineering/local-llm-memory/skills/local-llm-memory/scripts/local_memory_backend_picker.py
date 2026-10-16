#!/usr/bin/env python3
"""Score local-only vector/memory backends for a self-hosted LLM agent (LM Studio/Ollama/llama.cpp),
and refuse to pick when the constraints are contradictory. Stdlib-only, CLI-first, JSON output.
"""

import argparse
import json
import sys

# Each backend: fixed facts about install weight, native-dependency risk, and whether
# it can run embeddings fully offline against a local GGUF/ONNX model (no network call).
BACKENDS = {
    "chromadb_onnx_minilm": {
        "label": "ChromaDB + local ONNX MiniLM embedder",
        "install_weight_mb": 180,
        "native_deps": True,
        "offline_capable": True,
        "max_comfortable_records": 200_000,
        "query_latency_class": "low",
        "notes": "DuckDB-backed persistent store; one-time ONNX model fetch (~90MB), then fully offline.",
    },
    "sqlite_vec": {
        "label": "SQLite + sqlite-vec extension",
        "install_weight_mb": 5,
        "native_deps": True,
        "offline_capable": True,
        "max_comfortable_records": 500_000,
        "query_latency_class": "low",
        "notes": "Single-file DB, no server process; embeddings must come from elsewhere (LM Studio /v1/embeddings).",
    },
    "faiss_flat": {
        "label": "FAISS flat index (in-process)",
        "install_weight_mb": 60,
        "native_deps": True,
        "offline_capable": True,
        "max_comfortable_records": 1_000_000,
        "query_latency_class": "very_low",
        "notes": "No persistence layer of its own — pair with a sidecar JSONL for metadata/rebuild.",
    },
    "jsonl_lexical": {
        "label": "Plain JSONL + lexical (substring/BM25-lite) search",
        "install_weight_mb": 0,
        "native_deps": False,
        "offline_capable": True,
        "max_comfortable_records": 20_000,
        "query_latency_class": "medium",
        "notes": "Zero dependencies, human-readable, but no semantic recall — exact/near-exact phrasing only.",
    },
    "managed_cloud_vector_db": {
        "label": "Managed cloud vector DB (Pinecone/Weaviate Cloud/etc.)",
        "install_weight_mb": 1,
        "native_deps": False,
        "offline_capable": False,
        "max_comfortable_records": 10_000_000,
        "query_latency_class": "network_bound",
        "notes": "Needs outbound network + an account/API key — defeats a fully local stack.",
    },
}


def score_backend(name, facts, expected_records, offline_required, ram_budget_mb, want_semantic_recall):
    score = 100
    reasons = []

    if offline_required and not facts["offline_capable"]:
        return 0, ["disqualified: not offline-capable, offline_required=true"]

    if want_semantic_recall and name == "jsonl_lexical":
        score -= 55
        reasons.append("-55 no semantic/vector recall, only lexical match")

    if facts["install_weight_mb"] > ram_budget_mb:
        score -= 30
        reasons.append(f"-30 install footprint {facts['install_weight_mb']}MB exceeds ram_budget_mb {ram_budget_mb}")

    if expected_records > facts["max_comfortable_records"]:
        over = expected_records / facts["max_comfortable_records"]
        penalty = min(40, int(10 * over))
        score -= penalty
        reasons.append(f"-{penalty} expected_records {expected_records} exceeds comfortable ceiling {facts['max_comfortable_records']}")

    if facts["native_deps"]:
        score -= 5
        reasons.append("-5 native/compiled dependency (platform wheel risk on an unusual arch)")

    score = max(0, min(100, score))
    if not reasons:
        reasons.append("no penalties")
    return score, reasons


def recommend(expected_records, offline_required, ram_budget_mb, want_semantic_recall):
    results = []
    for name, facts in BACKENDS.items():
        score, reasons = score_backend(
            name, facts, expected_records, offline_required, ram_budget_mb, want_semantic_recall
        )
        results.append(
            {
                "backend": name,
                "label": facts["label"],
                "score": score,
                "reasons": reasons,
                "notes": facts["notes"],
                "disqualified": score == 0,
            }
        )
    results.sort(key=lambda r: r["score"], reverse=True)

    survivors = [r for r in results if not r["disqualified"]]
    if not survivors:
        return {
            "verdict": "NO_VIABLE_BACKEND",
            "reason": "every backend disqualified under these constraints (check offline_required against managed_cloud_vector_db-only use cases)",
            "candidates": results,
        }

    top = survivors[0]
    runner_up = survivors[1] if len(survivors) > 1 else None
    tie = runner_up is not None and (top["score"] - runner_up["score"]) <= 5
    verdict = "TIE_PICK_EITHER" if tie else "RECOMMENDED"
    return {
        "verdict": verdict,
        "recommended": top["backend"] if not tie else None,
        "tied_candidates": [top["backend"], runner_up["backend"]] if tie else None,
        "candidates": results,
    }


def main():
    p = argparse.ArgumentParser(
        description="Pick a local-only memory/vector backend for a self-hosted (LM Studio/Ollama/llama.cpp) agent."
    )
    p.add_argument("--expected-records", type=int, default=5000, help="Rough count of memory entries expected at steady state.")
    p.add_argument("--offline-required", action="store_true", help="Set if the stack must never make an outbound network call.")
    p.add_argument("--ram-budget-mb", type=int, default=200, help="Install/runtime footprint budget in MB for the memory backend itself.")
    p.add_argument("--no-semantic-recall", dest="semantic_recall", action="store_false", help="Set if exact/lexical match is acceptable (skip embeddings).")
    p.add_argument("--sample", action="store_true", help="Run with embedded sample constraints and exit (demo/test, zero config).")
    p.add_argument("--output", choices=["json", "text"], default="text")
    p.set_defaults(semantic_recall=True)
    args = p.parse_args()

    if args.sample:
        result = recommend(expected_records=8000, offline_required=True, ram_budget_mb=250, want_semantic_recall=True)
    else:
        result = recommend(
            expected_records=args.expected_records,
            offline_required=args.offline_required,
            ram_budget_mb=args.ram_budget_mb,
            want_semantic_recall=args.semantic_recall,
        )

    if args.output == "json":
        print(json.dumps(result, indent=2))
        return

    print(f"Verdict: {result['verdict']}")
    if result.get("recommended"):
        print(f"Recommended: {result['recommended']}")
    if result.get("tied_candidates"):
        print(f"Tied: {result['tied_candidates']} — pick either, or break the tie with a non-technical factor.")
    print()
    for c in result["candidates"]:
        flag = "DISQUALIFIED" if c["disqualified"] else f"score={c['score']}"
        print(f"- {c['backend']} ({flag}): {c['label']}")
        for r in c["reasons"]:
            print(f"    {r}")
        print(f"    note: {c['notes']}")

    sys.exit(0 if result["verdict"] != "NO_VIABLE_BACKEND" else 4)


if __name__ == "__main__":
    main()
