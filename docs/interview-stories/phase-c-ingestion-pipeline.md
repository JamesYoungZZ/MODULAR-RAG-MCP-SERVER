# Phase C Ingestion Pipeline

## Shorter 45-Second Version

In Phase C, I built the offline ingestion path for the RAG system: PDF loading, file integrity checks, document chunking, LLM-ready transforms, dense and sparse encoding, vector upsert, BM25 indexing, image storage, and a CLI entry point. The main design choice was to keep every stage dependency-injected and contract-driven, so each component can be tested with fakes while the production path still wires real storage and model providers through configuration. This turned ingestion from isolated utilities into a repeatable pipeline that can skip unchanged files and persist all retrieval artifacts.

## One Strong Interview Framing

The hardest tradeoff was balancing a real end-to-end pipeline with testability. I did not want unit tests to call external LLMs or vector databases, so the pipeline accepts injected loaders, transforms, encoders, and stores. At the same time, the default constructors wire the real implementations from settings. That gives two benefits: local tests stay fast and deterministic, while the production code path remains close to the real architecture. It also makes failure handling cleaner because each stage has a clear boundary and can report exactly where ingestion failed.