import json
from pathlib import Path

from embedding_search import Embedder


class FaissRuleIndex:

    def __init__(self, index_path, metadata_path):
        self.index_path = index_path
        self.metadata_path = metadata_path
        self.metadata = _load_metadata(metadata_path)
        self.index = _load_faiss_index(index_path)

    def search(self, query, scenes=None, branches=None, nodes=None, top_k=5):
        faiss = _import_faiss()
        embedder = Embedder(
            self.metadata.get("provider", "local-hash"),
            self.metadata.get("model", ""),
            self.metadata.get("dimensions", 384),
            self.metadata.get("profile", ""),
        )
        query_vector = embedder.embed(query)
        query_matrix = _to_float32_matrix([query_vector])
        faiss.normalize_L2(query_matrix)

        documents = self.metadata.get("documents", [])
        has_filters = bool(scenes or branches or nodes)
        fetch_k = len(documents) if has_filters else min(top_k, len(documents))
        if fetch_k == 0:
            return []

        scores, indices = self.index.search(query_matrix, fetch_k)
        scene_set = set(scenes or [])
        branch_set = set(branches or [])
        node_set = set(nodes or [])
        matches = []

        for score, index in zip(scores[0], indices[0]):
            if index < 0 or index >= len(documents):
                continue
            document = documents[index]
            meta = document.get("meta", {})
            if scene_set and meta.get("scene") not in scene_set:
                continue
            if branch_set and meta.get("branch") not in branch_set:
                continue
            if node_set and meta.get("node") not in node_set:
                continue
            matches.append({
                "score": round(float(score), 6),
                "record_index": document.get("record_index"),
                "meta": meta,
                "text": document.get("text", ""),
            })
            if len(matches) >= top_k:
                break

        return matches


def build_faiss_index(
    records,
    index_path,
    metadata_path,
    provider="local-hash",
    model="",
    dimensions=384,
    precomputed_documents=None,
    profile="",
):
    faiss = _import_faiss()
    documents = []
    vectors = []

    if precomputed_documents is not None:
        for document in precomputed_documents:
            record = document.get("record", {})
            vectors.append(document.get("vector", []))
            documents.append({
                "record_index": document.get("record_index"),
                "meta": record.get("meta", {}),
                "text": record.get("text", ""),
            })
    else:
        embedder = Embedder(provider, model, dimensions, profile)
        for record_index, record in enumerate(records):
            text = _document_text(record)
            vectors.append(embedder.embed(text))
            documents.append({
                "record_index": record_index,
                "meta": record.get("meta", {}),
                "text": record.get("text", ""),
            })

    if not vectors:
        raise ValueError("Cannot build FAISS index from empty records.")

    matrix = _to_float32_matrix(vectors)
    faiss.normalize_L2(matrix)
    index = faiss.IndexFlatIP(len(matrix[0]))
    index.add(matrix)
    faiss.write_index(index, str(index_path))

    metadata = {
        "version": 1,
        "provider": provider,
        "model": model,
        "dimensions": len(matrix[0]),
        "profile": profile,
        "metric": "cosine",
        "documents": documents,
    }
    with Path(metadata_path).open("w", encoding="utf-8") as file:
        json.dump(metadata, file, ensure_ascii=False, indent=2)
    return metadata


def _load_faiss_index(path):
    faiss = _import_faiss()
    return faiss.read_index(str(path))


def _load_metadata(path):
    with Path(path).open("r", encoding="utf-8-sig") as file:
        return json.load(file)


def _import_faiss():
    try:
        import faiss
    except ImportError as error:
        raise RuntimeError(
            "FAISS is not installed. Install faiss-cpu in the runtime before using FAISS indexing."
        ) from error
    return faiss


def _to_float32_matrix(vectors):
    try:
        import numpy as np
    except ImportError as error:
        raise RuntimeError(
            "NumPy is required for FAISS indexing. Install numpy with faiss-cpu."
        ) from error
    return np.array(vectors, dtype="float32")


def _document_text(record):
    meta = record.get("meta", {})
    parts = [
        meta.get("scene", ""),
        meta.get("branch", ""),
        meta.get("node", ""),
        meta.get("actor", ""),
        record.get("text", ""),
    ]
    return "\n".join(part for part in parts if part)
