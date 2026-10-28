"""Corpus publication/scope regressions; no hosted embedding or LLM."""
import json
from pathlib import Path
import shutil

import pytest

from src.commerce.corpus import CommerceCorpus

ROOT = Path(__file__).resolve().parents[2] / "fixtures/commerce"


def test_product_and_market_filters_apply_before_ranking():
    corpus=CommerceCorpus(ROOT, "demo-tenant", load_vectors=False)
    data=corpus.search("washing machine cleaning", "DE", "PRODUCT-CLOUDSTEP-RUNNER")
    assert data["sections"]
    assert any(s["document_id"] == "cloudstep-care" for s in data["sections"])
    assert all(s["canonical_product_id"] in {None,"PRODUCT-CLOUDSTEP-RUNNER"} and "DE" in s["markets"] for s in data["sections"])
    key=next(k for k,v in corpus.records.items() if v["canonical_product_id"] == "PRODUCT-CLOUDSTEP-RUNNER")
    with pytest.raises(ValueError): corpus.read(key, "DE", "PRODUCT-NIGHTPACE-RUNNER")
    with pytest.raises(ValueError): CommerceCorpus(ROOT,"other-tenant",load_vectors=False)


def test_manifest_hash_prevents_unpublished_source_changes(tmp_path):
    shutil.copytree(ROOT,tmp_path/'corpus',ignore=shutil.ignore_patterns('vectors.json'))
    target=tmp_path/'corpus'
    manifest=json.loads((target/'manifest.json').read_text())
    path=target/manifest['documents'][0]['file'];path.write_text(path.read_text()+'\nUnpublished change')
    with pytest.raises(ValueError, match='document_digest_mismatch'):
        CommerceCorpus(target,'demo-tenant',load_vectors=False)


def test_index_rebuild_can_replace_old_manifest_version(tmp_path):
    shutil.copytree(ROOT,tmp_path/'corpus',ignore=shutil.ignore_patterns('vectors.json'))
    target=tmp_path/'corpus'
    (target/'vectors.json').write_text(json.dumps({'corpus_version':'outdated'}))
    with pytest.raises(ValueError,match='dense_index_version_mismatch'): CommerceCorpus(target,'demo-tenant')
    assert CommerceCorpus(target,'demo-tenant',load_vectors=False).records
