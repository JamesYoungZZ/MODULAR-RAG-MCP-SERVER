"""Versioned, tenant-scoped corpus using the project's sparse and RRF components.

Whole authored sections are retrieval units: no LLM rewriting and no slicing
away qualifiers. The manifest is the publication boundary, not a user argument.
"""
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import tempfile

from src.core.types import Chunk, RetrievalResult
from src.core.query_engine.fusion import RRFFusion
from src.ingestion.embedding.sparse_encoder import SparseEncoder
from src.ingestion.storage.bm25_indexer import BM25Indexer


class CommerceCorpus:
    def __init__(self, root: Path, tenant_id: str, *, load_vectors: bool = True):
        self.root = root.resolve()
        self.tenant_id = tenant_id
        self.encoder = SparseEncoder()
        self.records = {}
        manifest = json.loads((self.root / "manifest.json").read_text())
        if manifest["tenant_id"] != tenant_id or manifest["schema_version"] != "commerce-documents-v1":
            raise ValueError("corpus_scope_or_version_mismatch")
        self.corpus_version = sha256((self.root / "manifest.json").read_bytes()).hexdigest()
        snapshot_name = manifest.get("catalog_snapshot")
        if snapshot_name:
            snapshot_path = (self.root / snapshot_name).resolve()
            if not snapshot_path.is_relative_to(self.root):
                raise ValueError("invalid_catalog_snapshot_path")
            snapshot_bytes = snapshot_path.read_bytes()
            if sha256(snapshot_bytes).hexdigest() != manifest.get("catalog_snapshot_sha256"):
                raise ValueError("catalog_snapshot_digest_mismatch")
            snapshot = json.loads(snapshot_bytes)
            expected = [p["canonical_product_id"] for p in snapshot["products"]]
            actual = [d["canonical_product_id"] for d in manifest["documents"] if d["canonical_product_id"] is not None]
            if len(actual) != len(set(actual)) or len(expected) != len(set(expected)) or set(actual) != set(expected):
                raise ValueError("product_document_coverage_mismatch")
        pdf_files = set()
        for doc in manifest["documents"]:
            if "pdf_file" in doc:
                if not re.fullmatch(r"(?:products|policies)/[a-z0-9-]+\.pdf", doc["pdf_file"]):
                    raise ValueError("invalid_published_pdf_path")
                if doc["pdf_file"] in pdf_files or doc.get("pdf_page") != 1:
                    raise ValueError("standalone_pdf_identity_or_page_mismatch")
                if not re.fullmatch(r"[0-9a-f]{64}", doc.get("pdf_sha256", "")):
                    raise ValueError("published_pdf_digest_missing")
                pdf_files.add(doc["pdf_file"])
            path = (self.root / doc["file"]).resolve()
            if not path.is_relative_to(self.root) or path.suffix != ".md":
                raise ValueError("invalid_document_path")
            raw = path.read_bytes()
            if sha256(raw).hexdigest() != doc["sha256"]:
                raise ValueError("document_digest_mismatch")
            for field in ("effective_from", "effective_until"):
                if doc.get(field) is not None:
                    date = datetime.fromisoformat(doc[field].replace("Z", "+00:00"))
                    if date.tzinfo is None:
                        raise ValueError("document_dates_require_timezone")
            text = raw.decode("utf-8")
            headings = list(re.finditer(r"^## (.+)$", text, re.MULTILINE))
            for i, heading in enumerate(headings):
                end = headings[i+1].start() if i+1 < len(headings) else len(text)
                body = text[heading.end():end].strip()
                if not body or len(body) > 6000:
                    raise ValueError("section_requires_editorial_split")
                section_id = f"{doc['document_id']}@{doc['version']}:{i+1}"
                if section_id in self.records:
                    raise ValueError("duplicate_section_identity")
                self.records[section_id] = {**doc, "section_id": section_id,
                    "section": heading.group(1), "content": body,
                    "source_uri": f"corpus://{manifest['corpus_id']}/{doc['document_id']}@{doc['version']}#{i+1}",
                    "tenant_id": tenant_id}
        self._tmp = tempfile.TemporaryDirectory(prefix="commerce-bm25-")
        chunks = [Chunk(id=k, text=f"{r['title']}\n{r['section']}\n{r['content']}", metadata={"source_path": r["file"]}) for k, r in self.records.items()]
        self.index = BM25Indexer(self._tmp.name)
        self.index.build(self.encoder.encode(chunks), collection="commerce")
        self.vectors = None
        vector_path = self.root / "vectors.json"
        if load_vectors and vector_path.exists():
            candidate = json.loads(vector_path.read_text())
            if candidate.get("corpus_version") != self.corpus_version:
                raise ValueError("dense_index_version_mismatch")
            self.vectors = candidate

    def allowed(self, record, *, market, product_id):
        now = datetime.now(timezone.utc)
        start = datetime.fromisoformat(record["effective_from"].replace("Z", "+00:00"))
        end = datetime.fromisoformat(record["effective_until"].replace("Z", "+00:00")) if record.get("effective_until") else None
        return (record["tenant_id"] == self.tenant_id and market in record["markets"]
            and record.get("canonical_product_id") in {None, product_id}
            and start <= now and (end is None or now < end) and record["status"] == "published")

    def search(self, query, market, product_id, top_k=5, *, embedding=None):
        if not 1 <= top_k <= 8 or not query.strip() or len(query) > 500 or market not in {"DE", "FR"}:
            raise ValueError("invalid_search_arguments")
        eligible = {k: r for k, r in self.records.items() if self.allowed(r, market=market, product_id=product_id)}
        # Rank all lexical matches before applying the requested top_k. This
        # avoids losing in-scope hits behind out-of-scope high scoring products.
        terms = self.encoder._tokenize(query)
        sparse_raw = self.index.query(terms, top_k=len(self.records)) if terms else []
        sparse = [RetrievalResult(chunk_id=r["chunk_id"], score=r["score"], text=eligible[r["chunk_id"]]["content"], metadata={})
            for r in sparse_raw if r["chunk_id"] in eligible]
        mode, degraded = "bm25", False
        ranked = sparse[:top_k]
        if self.vectors is not None and embedding is not None:
            try:
                import math
                vector = embedding.embed([query])[0]
                norm = math.sqrt(sum(x*x for x in vector))
                dense = []
                for key, value in self.vectors["vectors"].items():
                    if key not in eligible:
                        continue
                    if len(value) != len(vector):
                        raise ValueError("embedding_dimension_mismatch")
                    denominator = norm * math.sqrt(sum(x*x for x in value))
                    score = sum(a*b for a,b in zip(vector, value))/denominator if denominator else 0
                    dense.append(RetrievalResult(chunk_id=key, score=score, text=eligible[key]["content"], metadata={}))
                dense.sort(key=lambda r: r.score, reverse=True)
                ranked = RRFFusion().fuse([sparse[:20], dense[:20]], top_k=top_k)
                mode = "dense_bm25_rrf"
            except Exception:
                degraded = True
        return {"schema_version": "commerce-retrieval-v1", "tenant_id": self.tenant_id,
            "market": market, "requested_product_id": product_id, "corpus_version": self.corpus_version,
            "retrieval_mode": mode, "degraded": degraded, "coverage": "retrieved_sections_not_exhaustive",
            "sections": [{**eligible[r.chunk_id], "retrieval_score": r.score} for r in ranked]}

    def read(self, section_id, market, product_id):
        record = self.records.get(section_id)
        if record is None or not self.allowed(record, market=market, product_id=product_id):
            raise ValueError("section_not_available_in_scope")
        return {"schema_version": "commerce-retrieval-v1", "tenant_id": self.tenant_id, "market": market,
            "requested_product_id": product_id, "corpus_version": self.corpus_version,
            "retrieval_mode": "exact_section", "degraded": False, "coverage": "one_section", "sections": [record]}
