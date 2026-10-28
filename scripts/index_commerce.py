"""Validate a published Markdown corpus; optionally build real dense embeddings.

The default command makes no model calls. --dense defaults to a local embedding model; --embedding configured may incur cost. Source documents are never rewritten by an LLM.
"""
import argparse
import json
from pathlib import Path
from src.commerce.corpus import CommerceCorpus


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--tenant", default="demo-tenant")
    parser.add_argument("--dense", action="store_true")
    parser.add_argument("--embedding", choices=["local", "configured"], default="local")
    args = parser.parse_args()
    corpus = CommerceCorpus(args.root, args.tenant, load_vectors=False)
    if args.dense:
        if args.embedding == "local":
            from src.commerce.embedding import LocalCommerceEmbedding
            embedding = LocalCommerceEmbedding()
            model_name = embedding.model_name
        else:
            from src.core.settings import load_settings
            from src.libs.embedding.embedding_factory import EmbeddingFactory
            settings = load_settings()
            embedding = EmbeddingFactory.create(settings)
            model_name = settings.embedding.model
        ids = list(corpus.records)
        vectors = embedding.embed([f"{r['title']}\n{r['section']}\n{r['content']}" for r in corpus.records.values()])
        if len(vectors) != len(ids):
            raise ValueError("embedding_result_count_mismatch")
        data = {"corpus_version": corpus.corpus_version, "embedding_model": model_name,
            "vectors": dict(zip(ids, vectors))}
        temp = args.root / "vectors.json.tmp"
        temp.write_text(json.dumps(data))
        temp.replace(args.root / "vectors.json")
    print(json.dumps({"sections": len(corpus.records), "corpus_version": corpus.corpus_version, "dense_built": args.dense}))


if __name__ == "__main__":
    main()
