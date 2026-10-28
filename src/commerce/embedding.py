"""Local embedding adapter; no hosted model credentials or generation calls."""
class LocalCommerceEmbedding:
    model_name = "local-all-MiniLM-L6-v2"

    def __init__(self):
        from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2
        self.model = ONNXMiniLM_L6_V2(preferred_providers=["CPUExecutionProvider"])

    def embed(self, texts):
        return [v.tolist() for v in self.model(texts)]
